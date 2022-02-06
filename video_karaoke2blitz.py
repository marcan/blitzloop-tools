#!/usr/bin/env python
'''
video_karaoke2blitz.py

create a dummy .blitz file for each video karaoke file (i. e. video with hardcoded lyrics). resulting
.blitz file contains no lyrics, it's only a placeholder so that blitzloop can read necessary
metadata and make the song visible in the list. audio/video must be in sync (but this is somewhat
expected for a karaoke video).

script takes a single argument - directory (`startdir') containing video files

 - scans `startdir' looking for directories named 'artist - song' (see `dirname_template' if this
   needs adjustment)
 - video/audio/cover file is a first match for corresponding filename glob (e. g. *.avi/*.mpg)
 - if no cover is found an attempt is made to download it via deezer API (www.deezer.com). image is
   saved as `deezer_cover.jpg'
 - album name is retrieved via deezer too

Limitations:
 - directories need to be properly named (according to a hard-coded template)
 - many values are either fixed or missing (latin format, style, lang..)
 - no checks are made on files found inside directories
 - .blitz generation is skipped if:
   - ultrastar's TXT file exists in the same folder (assuming this is not a karaoke video)
   - .blitz file is already present
   - video file is missing
 - dependency on a 3rd party service (deezer) and internet connection

Dependencies:
 - audioread module (to determine number of channels)
    - available in pip

'''
import requests
import json
import sys
import os
import re
import logging
import argparse
from time import sleep
from pprint import pprint
from glob import glob, escape
from os.path import basename
from audioread import audio_open
from logging import debug, info
from blitzloop.song import Song, LatinMolecule, Variant, Style, OrderedDict, MultiString

dirname_template = r'(?P<artist>.*?) - (?P<song>.*)'
lyrics_stub = '''L: {{{song}}}
@: 0 10
'''

def parse_args():
    parser = argparse.ArgumentParser(usage='Generate dummy .blitz files for video karaoke files found in START_DIR')
    parser.add_argument('start_dir', nargs=1, help='Directory containing video karaoke files', metavar='START_DIR')
    parser.add_argument('-d', help='Debug output', action='store_true', default=False, dest='debug_mode')
    args = parser.parse_args()
    return args.debug_mode, args.start_dir[0]
    

def get_song_info(artist, song):
    ret = None
    for artist, song in [(artist, song),
                         (artist, re.sub(r'\([^)]+\)', '', song))]:
        q = 'artist:"{}"&title:"{}"'.format(artist, song)
        r = requests.get('https://api.deezer.com/search',
                         params={'limit': 1, 'q': q})
        data = r.json()
        if data.get('total', 0) != 0:
            return data.get('data')[0]
    return {}


def get_album_genre(album_id):
    # first genre reported is returned
    r = requests.get('https://api.deezer.com/album/{}'.format(album_id))
    data = r.json()
    genres = data.get('genres', {}).get('data', {})
    if genres:
        genre_id = genres[0].get('id')
    else:
        return 'Unknown'

    r = requests.get('https://api.deezer.com/genre/{}'.format(genre_id))
    return r.json().get('name')


def get_cover(url, outfile):
    r = requests.get(url)
    with open(outfile, 'wb') as f:
        f.write(r.content)
    debug('Resting 15 seconds to now stress the API')
    sleep(15)


def get_dirs(start_path):
    ret = []
    for root, dirs, files in os.walk(start_path):
        for dir_name in dirs:
            ret.append(os.path.join(root, dir_name))
    return ret


def parse_songname(dir_name):
    match = re.match(dirname_template, os.path.basename(dir_name))
    if not match:
        return None
    return match.groups()


def get_videofile(dir_name):
    matches = glob(os.path.join(escape(dir_name), '*.[Aa][Vv][Ii]')) + \
              glob(os.path.join(escape(dir_name), '*.[Mm][Pp][gG4]'))
    if not matches:
        return None
    return matches[0]


def get_audiofile(dir_name):
    matches = glob(os.path.join(escape(dir_name), '*.[Mm][Pp]3')) + \
              glob(os.path.join(escape(dir_name), '*.[Mm]4[Aa]')) + \
              glob(os.path.join(escape(dir_name), '*.[Aa][Aa][Cc]'))
    if not matches:
        return None
    return matches[0]


def get_coverfile(dir_name):
    matches = glob(os.path.join(escape(dir_name), '*.[Jj][Pp][Gg]')) + \
              glob(os.path.join(escape(dir_name), '*.[Pp][Nn][Gg]'))
    if not matches:
        return None
    return matches[0]


def get_blitzfile(dir_name):
    matches = glob(os.path.join(escape(dir_name), '*.[Bb][Ll][Ii][Tt][Zz]'))
    if not matches:
        return None
    return matches[0]


def get_lyricsfile(dir_name):
    matches = glob(os.path.join(escape(dir_name), '*.[Tt][Xx][Tt]'))
    if not matches:
        return None
    return matches[0]


def get_blitzsong(title, artist, audiofile, videofile, coverfile, album, genre, channels):
    blitz_song = Song()
    blitz_song.meta['title'] = MultiString([(None, song)])
    blitz_song.meta['artist'] = MultiString([(None, artist)])
    blitz_song.song['audio'] = basename(audio_file)
    blitz_song.song['video'] = basename(video_file)
    blitz_song.song['cover'] = basename(cover_file)
    blitz_song.song['album'] = album_title
    blitz_song.song['genre'] = genre
    blitz_song.song['channels'] = 0 if channels <=2 else 1
    blitz_song.timing.add(0, 0)
    blitz_song.timing.add(1, 1)
    blitz_song.formats['L'] = LatinMolecule
    blitz_song.variants['latin'] = Variant(OrderedDict([
                                           ('name', 'latin'),
                                           ('tags', 'L'),
                                           ('style', 'latin')]))
    style_data = OrderedDict([('font', 'TakaoPGothic.ttf'),
                              ('size', 11),
                              ('outline_width', 0.3),
                              ('border_width', 0.8),
                              ('colors', 'ffffff,12309A,000000'),
                              ('colors_on', '12309A,ffffff,000000')])
    blitz_song.styles['latin'] = Style(style_data)
    return blitz_song


def make_blitzfile(dir_name, artist, song):
    return os.path.join(escape(dir_name), '{} - {}.blitz'.format(artist, song))


if __name__ == "__main__":
    debug_mode, start_dir = parse_args()
    if debug_mode:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    info('Processing files and dirs inside {}'.format(start_dir))
    dirs = get_dirs(start_dir)
    for dir_name in dirs:
        print('-' * 30)

        artist_song = parse_songname(dir_name)
        if not artist_song:
            print('Unable to parse artist+song from {}, skipping..'.format(dir_name))
            continue
        info(artist_song)
        audio_file = get_audiofile(dir_name) 
        video_file = get_videofile(dir_name) 
        lyrics_file = get_lyricsfile(dir_name)
        cover_file = get_coverfile(dir_name)
        blitz_file = get_blitzfile(dir_name)
        artist, song = artist_song

        if not video_file:
            # no reason to continue if there's no video file
            info('Cannot locate video file, skipping')
            continue

        if lyrics_file:
            # skip if we have lyrics in a separate file
            info('Lyrics found, no dummy blitz file will be created')
            continue

        if blitz_file:
            # don't overwrite existing stuff
            info('Blitz file already exists, ignoring')
            continue

        song_info = get_song_info(artist, song)
        debug('Song_info: {}'.format(song_info))
        album_title = song_info.get('album', {}).get('title')
        album_id = song_info.get('album', {}).get('id')
        if album_id:
            genre = get_album_genre(album_id)

        if not cover_file and album_title:
            if not song_info:
                debug('No cover image found')
            else:
                debug('Getting cover..')
                outfile = os.path.join(dir_name, 'deezer_cover.jpg')
                get_cover(song_info['album']['cover_big'], outfile)
                debug('Cover for {} saved into {}'.format(artist_song, outfile))

        # we set this even if the cover download was not successful
        cover_file = 'deezer_cover.jpg'

        # use video as audio if separate audio is unavailable
        if not audio_file:
            audio_file = video_file

        # let's check if we can determine number of channels
        # (fallback to stereo otherwise)
        try:
            channels = audio_open(audio_file).channels
        except:
            channels = 2

        if not album_title:
            album_title = 'Unknown'

        print('''Audio file: {audio_file} (album: {album_title})
Video file: {video_file}
Genre: {genre}
Lyrics file: {lyrics_file}
Cover file: {cover_file}
Blitz file: {blitz_file}
'''.format(**locals()))

        blitz_file = make_blitzfile(dir_name, artist, song)

        with open(blitz_file, 'w') as f:
            blitz_song = get_blitzsong(song, artist, audio_file, video_file, cover_file, album_title, genre, channels)
            f.write(blitz_song.dump() + lyrics_stub.format(song=song))
            info('new file ({}) written'.format(blitz_file))
