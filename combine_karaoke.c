#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <sndfile.h>

#define MAX_SHIFT (48000 * 5)

#define SINC_OVERSAMPLING 32
#define SINC_WIDTH 33
#define SINC_SIZE (((SINC_WIDTH - 1) * SINC_OVERSAMPLING) + 1)

#define COARSE_SIZE 15000
#define COARSE_MAX_SHIFT 200000

#define FINE_SIZE 256
#define FINE_MAX_SHIFT 128
#define FINE_SUBDIV 32
#define FINE_UNIT (1.0/FINE_SUBDIV)
#define FINE_INTERVAL 25000

#define Q_FACTOR 2.5
//#define Q_FACTOR 1

int channels = -1;
int search_channels = -1;
int samplerate = -1;

long len_a = 0;
float *buf_a;
float *buf_a2;
long len_b = 0;
float *buf_b;
float *buf_b2;
long len_o = 0;
float *buf_o;

float s_tab[SINC_SIZE];

#define MIXDOWN
#define HPF
#define HPF_A 0.8


#define FINE_DQ -50

static float interp(float *p, double pos, int ch)
{
    int i;

    int ipos = pos;
    float ioff = 1 - (pos - ipos);

    float spos = ioff * SINC_OVERSAMPLING;
    int sipos = spos;
    float f2 = spos - sipos;
    float f1 = 1 - f2;
    float *s_p = s_tab + sipos;

    p += (ipos - ((SINC_WIDTH / 2) - 1)) * ch;
    float sum = 0;
    for (i = 0; i < (SINC_WIDTH - 1); i++) {
        sum += (s_p[0] * f1 + s_p[1] * f2) * *p;
        s_p += SINC_OVERSAMPLING;
        p += ch;
    }
    return sum;
}

// The following two functions taken from SPUC, GPLv2+
// See http://spuc.sourceforge.net/

static double io(double x)
{
    const double t = 1.e-08;
    double y = 0.5*x;
    double e = 1.0;
    double de = 1.0;
    int i;
    double xi;
    double sde;
    for (i=1;i<26;i++) {
        xi = i;
        de *= y/xi;
        sde = de*de;
        e += sde;
        if ((e*t-sde) > 0) break;
    }
    return(e);
}

static void kaiser(double* w,long nf, double beta)
{
    // nf = filter length in samples
    // beta = parameter of kaiser window
    double bes = 1.0/io(beta);
    long i;
    long odd = nf%2;
    double xi;
    double xind = (nf-1)*(nf-1);
    for (i=0;i<(nf/2);i++) {
        if (odd) xi = i + 0.5;
        else xi = i;
        xi = 4*xi*xi;
        w[i]  = io(beta*sqrt(1.-xi/xind))*bes;
    }
    w[nf/2] = 0;
}

static void build_sinc_table(void)
{
    double k[(SINC_SIZE/2)+1];
    kaiser(k, SINC_SIZE, 7.68);
    int i;
    for (i = 0; i < SINC_SIZE; i++) {
        float x = ((float)(i - (SINC_SIZE / 2))) / SINC_OVERSAMPLING;
        float val = 1;
        if (x != 0)
            val = (sin(M_PI * x) / (M_PI * x)) * k[abs(i - (SINC_SIZE/2))];
        s_tab[i] = val;
    }
}

static void read_audio(const char *filename, float **buf, long *length)
{
    SF_INFO info;
    memset(&info, 0, sizeof(info));

    SNDFILE *fd = sf_open(filename, SFM_READ, &info);

    if (!fd) {
        printf("Failed to open %s: %s\n", filename, sf_strerror(NULL));
        exit(1);
    }

    printf("Reading %s...\n", filename);

    if (channels != -1 && info.channels != channels) {
        printf("Channel count mismatch (expected %d, got %d)\n", channels, info.channels);
        exit(1);
    }
    channels = info.channels;

    if (samplerate != -1 && info.samplerate != samplerate) {
        printf("Sample rate count mismatch (expected %d, got %d)\n", samplerate, info.samplerate);
        exit(1);
    }
    samplerate = info.samplerate;

    *buf = malloc((info.frames + COARSE_MAX_SHIFT) * sizeof(float) * channels);
    memset(*buf, 0, (info.frames + COARSE_MAX_SHIFT) * sizeof(float) * channels);
    info.frames = sf_readf_float(fd, *buf, info.frames);
    sf_close(fd);
    printf("Read %ld samples\n", info.frames);

    *length = info.frames;
}

static void write_audio(const char *filename, float *buf, long length, int channels)
{
    SF_INFO info;

    memset(&info, 0, sizeof(info));
    info.samplerate = samplerate;
    info.channels = channels;
    info.format = SF_FORMAT_WAV | SF_FORMAT_PCM_16;

    SNDFILE *fd = sf_open(filename, SFM_WRITE, &info);

    if (!fd) {
        printf("Failed to open %s: %s\n", filename, sf_strerror(NULL));
        exit(1);
    }

    printf("Writing %s...\n", filename);

    sf_writef_float(fd, buf, length);
    sf_close(fd);
    printf("Wrote %ld samples\n", length);
}

static int coarse_search(float *ref, float *p)
{
    int shift = -COARSE_MAX_SHIFT/2;
    int i;

    int best = -1;
    float bestv = 0;

    for (shift = -COARSE_MAX_SHIFT/2; shift < COARSE_MAX_SHIFT; shift++) {
        float *a, *b;
        a = ref;
        b = p + shift * search_channels;
        float acc = 0;
        for (i = 0; i < (COARSE_SIZE * search_channels); i++) {
            acc -= fabsf(*a++ - *b++);
        }
        if (best == -1 || acc > bestv) {
            best = shift;
            bestv = acc;
        }
    }
    return best;
}

static double fine_search(float *ref, float *p, float *quality)
{
    double shift = -FINE_MAX_SHIFT;
    int have_best = 0;
    double best;
    float bestv;
    int i;

    while (shift < FINE_MAX_SHIFT) {
        float acc = 0;
        float *q = p;
        float rms = 0;
        for (i = 0; i < (FINE_SIZE * search_channels); i++) {
            acc -= fabsf(ref[i] - interp(q++, shift, search_channels));
            rms += ref[i]*ref[i];
        }
        acc /= sqrtf(rms);
        if (!have_best || acc > bestv) {
            best = shift;
            bestv = acc;
            have_best = 1;
        }
        //printf("%f -> %f, %f, %f\n", shift, acc, best, bestv);
        shift += FINE_UNIT;
    }
    *quality = bestv;
    return best;
}

void mixdown(float **out, float *in, int len)
{
    float *p = malloc(sizeof(float) * len);
    *out = p;
    while (len--) {
        *p++ = in[0] - in[1];
        in+=2;
    }
}

void hpf(float **out, float *in, int len, int ch)
{
    float *p = malloc(sizeof(float) * len * ch);
    struct {
        float yx, ix;
    } state[ch];
    memset(state, 0, sizeof(state));
    *out = p;
    int i;
    float a = HPF_A;
    while (len--) {
        for (i=0; i<ch; i++) {
            p[i] = state[i].yx = a * state[i].yx + a * (in[i] - state[i].ix);
            state[i].ix = in[i];
        }
        in+=ch;
        p+=ch;
    }
}

int main(int argc, char **argv)
{
    if (argc != 4) {
        printf("Usage: %s <original audio> <instrumental audio> <output file.wav>\n", argv[0]);
        return 1;
    }

    build_sinc_table();

    read_audio(argv[1], &buf_a, &len_a);
    read_audio(argv[2], &buf_b, &len_b);

    buf_a2 = buf_a;
    buf_b2 = buf_b;
    search_channels = channels;
#ifdef MIXDOWN
    if (channels == 2) {
        mixdown(&buf_a2, buf_a, len_a);
        mixdown(&buf_b2, buf_b, len_b);
        search_channels = 1;
    }
#endif

#ifdef HPF
    printf("Highpassing...\n");
    hpf(&buf_a2, buf_a2, len_a, search_channels);
    hpf(&buf_b2, buf_b2, len_b, search_channels);
#endif

    int mid_pos = len_a / 3;
    if (mid_pos < COARSE_MAX_SHIFT)
        mid_pos = COARSE_MAX_SHIFT;
    float *mid_a = buf_a2 + search_channels * mid_pos;
    float *mid_b = buf_b2 + search_channels * mid_pos;

    printf("Performing coarse search...\n");
    int ioff = coarse_search(mid_a, mid_b);
    printf("Coarse offset: %d samples\n", ioff);

    int pos;

    struct control_point {
        int pos;
        float offset;
        float quality;
        int valid;
    };

    struct control_point *points;

    points = malloc(sizeof(*points) * (len_a / FINE_INTERVAL));

    printf("Fine tuning...");
    int npoints = 0;
    int ioff2 = ioff;
    float sum_q = 0;
    int nf = 1;
    for (pos = mid_pos; pos < (len_a - FINE_INTERVAL); pos += FINE_INTERVAL) {
        if ((pos + ioff) > (len_b - FINE_INTERVAL))
            break;
        float *p_a = buf_a2 + search_channels * pos;
        float *p_b = buf_b2 + search_channels * (pos + ioff);
        float q, q2;
        double doff = fine_search(p_a, p_b, &q);
        double dq = q * fabsf(doff) / nf;
        if (dq > FINE_DQ) {
            printf("Fine at %d: offset %f q %f delta %f dp %f\n", pos, ioff + doff, q, doff, dq);
            points[npoints].pos = pos;
            points[npoints].offset = ioff + doff;
            points[npoints].quality = q;
            npoints++;
            sum_q += q;
            ioff += (int)doff;
            nf = 1;
        } else {
            printf("Fail at %d: offset %f q %f delta %f dp %f\n", pos, ioff + doff, q, doff, dq);
            nf += 1;
        }
        if (doff > 0)
            printf(">");
        else
            printf("<");
        fflush(stdout);
    }
    printf("|");
    nf = 1;
    for (pos = mid_pos - FINE_INTERVAL; pos > FINE_INTERVAL; pos -= FINE_INTERVAL) {
        if ((pos + ioff2) < FINE_INTERVAL)
            break;
        float *p_a = buf_a2 + search_channels * pos;
        float *p_b = buf_b2 + search_channels * (pos + ioff2);
        float q;
        double doff = fine_search(p_a, p_b, &q);
        double dq = q * fabsf(doff) / nf;
        if (dq > FINE_DQ) {
            printf("Fine at %d: offset %f q %f delta %f dp %f\n", pos, ioff2 + doff, q, doff, dq);
            memmove(points + 1, points, sizeof(*points) * npoints);
            points[0].pos = pos;
            points[0].offset = ioff2 + doff;
            points[0].quality = q;
            npoints++;
            sum_q += q;
            ioff2 += (int)doff;
            nf = 1;
        } else {
            printf("Fail at %d: offset %f q %f delta %f dp %f\n", pos, ioff2 + doff, q, doff, dq);
            nf += 1;
        }
        if (doff > 0)
            printf(">");
        else
            printf("<");
        fflush(stdout);
    }
    printf(" done\n");

    int i,j;
    float avg_q = sum_q / npoints;
    double sum_off = 0;
    double sum2_off = 0;
    int valid_points = 0;
    for (i = 0; i < npoints; i++) {
        points[i].valid = 0;
        if (points[i].quality > Q_FACTOR*avg_q) {
            sum_off += points[i].offset;
            sum2_off += points[i].offset * points[i].offset;
            points[i].valid = 1;
            valid_points++;
        }
    }
    printf("%d %f %f\n", valid_points, sum_off, sum2_off);
    double avg_off = sum_off / valid_points;
    double stdev_off = sqrtf((sum2_off / valid_points) - avg_off * avg_off);

    printf("Average offset: %f, stdev %f, avg q %f\n", avg_off, stdev_off, avg_q);

    struct control_point *points2;
    points2 = malloc(sizeof(*points2) * valid_points);

    valid_points = 0;
    for (i = 0; i < npoints; i++) {
        if (points[i].valid && fabsf(points[i].offset - avg_off) < 2 * stdev_off) {
            points2[valid_points++] = points[i];
        }
    }

    for (i = 0; i < valid_points; i++) {
        points[i] = points2[i];
        printf("%d: %d %f %f\n", i, points[i].pos, points[i].offset, points[i].quality);
    }

    len_o = 0;
    buf_o = malloc(sizeof(float) * channels * 2 * len_a * 2);

    int point_idx = 2;
    struct control_point *pp = points;

    printf("Rendering...\n");
    int ch;

    for (i = 0; i < len_a; i++) {
        float *p_a = &buf_a[i * channels];
        float *p_o = &buf_o[len_o * channels * 2];

        if (i >= pp[1].pos && point_idx < valid_points) {
            pp++;
            point_idx++;
            //p_o[-channels] = 1.0;
        }

        float pos_p = (i - pp[0].pos) / (float)(pp[1].pos - pp[0].pos);
        pos_p = fminf(fmaxf(pos_p, 0), 1);
        float off = pp[1].offset * pos_p + pp[0].offset * (1 - pos_p);
        if ((i + off) < (SINC_WIDTH / 2) || (i + off) > (len_b - SINC_WIDTH / 2)) {
            for (ch = 0; ch < channels; ch++) {
                p_o[ch] = 0;
                p_o[ch+channels] = p_a[ch] * 0.8;
            }
        } else {
            for (ch = 0; ch < channels; ch++) {
                float v = interp(buf_b + ch, (double)i + off, channels);
                p_o[ch] = v * 0.8;
                p_o[ch+channels] = p_a[ch] * 0.8;
            }
        }
        len_o++;
    }

    write_audio(argv[3], buf_o, len_o, channels*2);

    return 0;
}

// kate: space-indent on; indent-width 4; mixedindent off; indent-mode cstyle;
