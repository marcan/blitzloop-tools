#!/usr/bin/python3

import subprocess
from blitzloop import song, util

parser = util.get_argparser()
parser.add_argument(
    'songpath', metavar='SONGPATH', help='path to the song file')
opts = util.get_opts()

s = song.Song(opts.songpath)

if s.channels == 0:
    af = ''
elif s.channels == 1:
    # Take the second track (with vocals)
    af = 'pan=stereo|c0=c2|c1=c3,'
else:
    # Mix all tracks together
    c0 = '+'.join("c%d" % (i*2) for i in range(s.channels + 1))
    c1 = '+'.join("c%d" % (i*2+1) for i in range(s.channels + 1))
    af = 'pan=stereo|c0=%s|c1=%s,' % (c0, c1)

cmd = [
    "ffmpeg", "-hide_banner", "-nostats",
    "-i", s.audiofile,
    "-af", "%sreplaygain" % af,
    "-f", "null", "-"
]

p = subprocess.run(cmd, stderr=subprocess.PIPE, check=True)

track_gain = None
track_peak = None

for line in p.stderr.split(b"\n"):
    line = line.split()
    if b"track_gain" in line:
        assert line[-1] == b"dB"
        track_gain = float(line[-2])
    if b"track_peak" in line:
        track_peak = float(line[-1])

if track_gain is None or track_peak is None:
    print("Failed to parse ffmpeg output! Output follows:")
    print(p.stderr.decode("utf-8"))
    sys.exit(1)

print("track_gain = %.04f" % track_gain)
print("track_peak = %.04f" % track_peak)

s.song["track_gain"] = "%.06f" % track_gain
s.song["track_peak"] = "%.06f" % track_peak

with open(opts.songpath, "wb") as fd:
    fd.write(s.dump().encode("utf-8"))

