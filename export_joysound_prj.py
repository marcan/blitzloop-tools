#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2012-2019 Hector Martin "marcan" <hector@marcansoft.com>
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
import hashlib

import xml.etree.ElementTree as ET

from blitzloop import graphics, layout, mpvplayer, song, util

parser = util.get_argparser()
parser.add_argument(
    'songpath', metavar='SONGPATH', help='path to the song file')
parser.add_argument(
    'output', metavar='OUTPUT', help='path to the output file')
parser.add_argument(
    '--variant', type=int, default=0, help='song variant')
parser.add_argument(
    '--pathbase', default="", help='file path base')
opts = util.get_opts()

opts.display = "surfaceless"
opts.mpv_ao = "null"
opts.mpv_vo = "null"

s = song.Song(opts.songpath)

# We need a virtual screen for line layout, just use something
WIDTH = 1280
HEIGHT = 720

class JoysoundProject(object):
    def __init__(self, song):
        self.root = ET.XML("""
            <kyokupro>
                <version>3</version>
                <app_version>0.2.4.1</app_version>
                <music_info>
                    <set>1</set>
                </music_info>
                <telop/>
            </kyokupro>
        """)
        self.et = ET.ElementTree(self.root)
        
        if song:
            self.load(song)
    
    def _tag(self, name, val):
        e = ET.Element(name)
        e.text = val
        return e
    
    def _load_music_info(self, song):
        info = self.root.find("music_info")
        telop = self.root.find("telop")
        
        if "title" in song.meta:
            info.append(self._tag("song_name", song.meta["title"][None]))
            telop.append(self._tag("song_name", song.meta["title"][None]))
            if "k" in song.meta["title"]:
                info.append(self._tag("song_name_yomi", song.meta["title"]["k"]))
        if "artist" in song.meta:
            info.append(self._tag("artist_name", song.meta["artist"][None]))
            telop.append(self._tag("artist_name", song.meta["artist"][None]))
            if "k" in song.meta["artist"]:
                info.append(self._tag("artist_name_yomi", song.meta["artist"]["k"]))
        if "composer" in song.meta:
            info.append(self._tag("composer_name", song.meta["composer"][None]))
            telop.append(self._tag("composer_name", song.meta["composer"][None]))
        if "writer" in song.meta:
            info.append(self._tag("lyricist_name", song.meta["writer"][None]))
            telop.append(self._tag("lyricist_name", song.meta["writer"][None]))

    def _load_audio(self, song, tag, path, **extra):
        el = ET.XML("""
            <music>
                <set>1</set>
                <file_path/>
                <md5_sum/>
                <type>1</type>
                <format>1</format>
                <play_time/>
                <adjust_time>0</adjust_time>
                <vol>50</vol>
                <balance>0</balance>
                <reverb>0</reverb>
                <enable>1</enable>
            </music>
        """)
        el.tag = tag
        el.find("file_path").text = opts.pathbase + path
        h = hashlib.md5(open(os.path.join(song.pathbase, path), "rb").read()).hexdigest()
        el.find("md5_sum").text = h
        el.find("play_time").text = "%d" % (int(self.duration * 1000))
        for k,v in extra.items():
            el.append(self._tag(k, v))
        return el

    def _load_resources(self, song):
        if "cover" in song.song:
            picture = ET.Element("picture")
            picture.append(self._tag("artist_file_path", opts.pathbase + song.song["cover"]))
            h = hashlib.md5(open(os.path.join(song.pathbase, song.song["cover"]), "rb").read()).hexdigest()
            picture.append(self._tag("artist_md5_sum", h))
            self.root.append(picture)
        if "audio_instrumental" in song.song:
            self.root.append(self._load_audio(song, "music", song.song["audio_instrumental"], set="1"))
        if "audio_vocal" in song.song:
            vocal = ET.Element("vocal")
            vocal.append(self._tag("set", "1"))
            vocal.append(self._load_audio(song, "song", song.song["audio_vocal"], song_type="0", song_number="0", marker_count="0"))
            self.root.append(vocal)
        if "audio" in song.song:
            self.root.append(self._load_audio(song, "mix", song.song["audio"], set="1"))

    def _load_lyrics(self, s):
        telop = self.root.find("telop")

        renderer = graphics.get_renderer().KaraokeRenderer(self.display)
        lyt = layout.SongLayout(s, list(s.variants.keys())[opts.variant], renderer)

        lines = lyt.lines[song.TagInfo.BOTTOM]

        class Page(object):
            pass

        def ms(i):
            return str(int(round(i * 1000)))

        # Group lines into pages
        pages = []
        page = Page()
        page.lines = {}
        last = None
        for l in lines:
            if l.row in page.lines or (last and (l.row > last.row or l.start > last.end)):
                pages.append(page)
                page = Page()
                page.lines = {}
            page.lines[l.row] = l
            last = l
        pages.append(page)
        
        # Compute page show/hide times
        prev = None
        pages2 = []
        for page in pages:
            lines = page.lines
            page.start = min(l.start for l in lines.values())
            page.min_start = min(l._start_t for l in lines.values())
            page.end = max(l.end for l in lines.values())
            page.min_end = max(l._end_t for l in lines.values())

            if prev and page.start < prev.end:
                page.start = min(page.min_start, prev.end)
                if prev and page.start < prev.end:
                    prev.end = max(prev.min_end, page.start)
                    if prev and page.start < prev.end:
                        raise Exception("overlapping lines!")
            prev = page
            pages2.append(page)
        
        # Generate XML
        for page in pages:
            pe = ET.Element("page")
            pe.append(self._tag("show_time", ms(page.start)))
            pe.append(self._tag("hide_time", ms(page.end)))
            pe.append(self._tag("paint_timing", "0"))
            pe.append(self._tag("layout", "xing_0"))

            t = page.min_start
            for i in range(max(page.lines.keys()), -1, -1):
                
                le = ET.Element("line")
                text = ""
                if i not in page.lines:
                    # dummy line
                    w = ET.Element("word")
                    w.append(self._tag("text", ""))
                    w.append(self._tag("start_time", ms(t)))
                    w.append(self._tag("end_time", ms(t)))
                    le.append(w)
                else:
                    line = page.lines[i]
                    assert len(line.molecules) == 1
                    mol, get_atom_time = line.molecules[0]
                    ruby = []
                    step = 0
                    for atom in mol.atoms:
                        start, end = get_atom_time(step, atom.steps)
                        step += atom.steps

                        w = ET.Element("word")
                        w.append(self._tag("text", atom.text))
                        w.append(self._tag("start_time", ms(start)))
                        w.append(self._tag("end_time", ms(end)))
                        le.append(w)
                        
                        if atom.particles is not None:
                            edge = len(atom.text)
                            if atom.particle_edge:
                                edge = atom.particle_edge 
                            rt = ""
                            for i in atom.particles:
                                rt += i.text
                            r = ET.Element("ruby")
                            r.append(self._tag("text", rt))
                            r.append(self._tag("start_pos", "%d" % len(text)))
                            r.append(self._tag("end_pos", "%d" % (len(text) + edge - 1)))
                            ruby.append(r)
                        
                        text += atom.text

                    for r in ruby:
                        le.append(r)

                    print(text)
                
                e = ET.Element("duet")
                e.append(self._tag("mark", "0"))
                e.append(self._tag("start_pos", "0"))
                e.append(self._tag("end_pos", "%d" % (len(text) - 1)))
                le.append(e)

                e = ET.Element("offset")
                e.append(self._tag("type", "0"))
                e.append(self._tag("offset", "0"))
                le.append(e)

                pe.append(le)
            
            telop.append(pe)
            

    def load(self, song):
        self.display = graphics.Display(WIDTH, HEIGHT)

        mpv = mpvplayer.Player(self.display, rendering=True)
        mpv.load_song(song)
        self.duration = int(round((mpv.duration or mpv.file_duration) * 1000))
        mpv.shutdown()

        #Use mpv to get duration only

        self._load_music_info(song)
        self._load_resources(song)
        self._load_lyrics(song)

pro = JoysoundProject(s)
pro.et.write(opts.output, encoding="UTF-8", xml_declaration=True)

os._exit(0)
