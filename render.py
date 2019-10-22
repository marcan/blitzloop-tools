#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2012-2013 Hector Martin "marcan" <hector@marcansoft.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 or version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

import os
import time
import subprocess
import argparse

import ctypes

from blitzloop import graphics, layout, mpvplayer, song, util

parser = util.get_argparser()
parser.add_argument(
    'songpath', metavar='SONGPATH', help='path to the song file')
parser.add_argument(
    '--show-timings', dest='st', action='store_true',
    help='show mpv timings')
parser.add_argument(
    '--offset', type=float, default=0.0, help='song offset')
parser.add_argument(
    '--width', type=int, default=1280, help='render width')
parser.add_argument(
    '--height', type=int, default=720, help='render height')
parser.add_argument(
    '--fps', type=float, default=60, help='render FPS')
parser.add_argument(
    '--sync', type=float, default=0.3, help='lyrics scroll-ahead time')
parser.add_argument(
    '--variant', type=int, default=0, help='song variant')
parser.add_argument(
    'ffmpeg_opts', metavar='OPTS', nargs=argparse.REMAINDER, help='ffmpeg options')
opts = util.get_opts()

print(opts.ffmpeg_opts)

opts.display = "surfaceless"
opts.mpv_ao = "null"
opts.mpv_vo = "null"

s = song.Song(opts.songpath)

display = graphics.Display(opts.width, opts.height)

import OpenGL.GLES3 as gl

renderer = graphics.get_renderer().KaraokeRenderer(display)
layout = layout.SongLayout(s, list(s.variants.keys())[opts.variant], renderer)

# Use mpv to get duration only
mpv = mpvplayer.Player(display)
mpv.load_song(s)
duration = mpv.duration or mpv.file_duration
mpv.shutdown()
print("Song duration: %f" % duration)

song_time = 0
ffmpeg = subprocess.Popen([
    "ffmpeg",
    "-c:v", "rawvideo",
    "-f", "rawvideo",
    "-pix_fmt", "rgba",
    "-s", "%dx%d" % (opts.width, opts.height),
    "-r", "%f" % opts.fps,
    "-i", "pipe:",
    "-vf", "vflip,unpremultiply=inplace=1",
    ] + opts.ffmpeg_opts, stdin=subprocess.PIPE)

buf = ctypes.create_string_buffer(opts.width * opts.height * 4)

def render():
    global song_time
    try:
        while song_time < duration:
            renderer.draw(song_time + opts.sync, layout)
            gl.glFinish()
            gl.glReadBuffer(gl.GL_BACK)
            data = None
            gl.glReadPixels(0, 0, opts.width, opts.height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, buf)
            ffmpeg.stdin.write(buf)
            print("\r%.02f%%  " % (100 * song_time / duration), end=' ')
            song_time += 1.0 / opts.fps
            yield None
    except Exception as e:
        print(e)
    finally:
        ffmpeg.stdin.close()
        ffmpeg.wait()
        os._exit(0)

pause = False

display.set_render_gen(render)
display.main_loop()
