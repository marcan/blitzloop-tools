#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2012-2020 Hector Martin "marcan" <marcan@marcan.st>
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
    '--variant', type=int, default=0, help='song variant')
opts = util.get_opts()

s = song.Song(opts.songpath)

variant = s.variants[list(s.variants.keys())[opts.variant]]
tags = set(i for i in variant.tag_list)

print("""
[Script Info]
Title: Default Aegisub file
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: 1920
PlayResY: 1080

[Aegisub Project Garbage]
Last Style Storage: Default
Audio File: dummy.flac
Video File: dummy.flac
Video AR Mode: 4
Video AR Value: 1.777778
Video Zoom Percent: 1.000000
Active Line: 29
Video Position: 11024

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Rounded Mplus 1c,90,&H00FFFFFF,&H00ffc080,&H00FF9664,&H6A000000,0,0,0,0,100,100,0,0,1,2.5,3,8,20,20,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""")

def ft(t):
    sec = int(t)
    cs = int((t - sec) * 100)
    m = sec // 60
    sec = sec % 60

    return "0:%02d:%02d.%02d" % (m, sec, cs)

for compound in s.compounds:

    count = compound.steps

    for tag in compound:
        if tag not in tags:
            continue
        v = compound[tag]

        offset = -0.22
        headstart = 60/180 * 1/2

        msec = headstart * 100

        line = "{\k%d}" % int(round(msec))
        #line = ""

        step = 0
        for atom in v.atoms:
            lm = int(round(msec))
            xs, xe = compound.get_atom_time(step, atom.steps)
            xe += offset
            xs += offset
            msec += (xe - xs) * 100
            line += "{\k%d}" % (int(round(msec)) - lm)
            step += atom.steps
            line += atom.text
        
        st, et = compound.get_atom_time(0, step)
        st += offset
        et += offset
        print("Dialogue: 0,%s,%s,Default,,0,0,0,,%s" %
            (ft(st - headstart), ft(et), line)) 
