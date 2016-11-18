CFLAGS ?= -O2 -Wall

all: combine_karaoke

combine_karaoke: combine_karaoke.c
	$(CC) $(CFLAGS) -o $@ combine_karaoke.c -lm -lsndfile

clean:
	rm -f combine_karaoke
