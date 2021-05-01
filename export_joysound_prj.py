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
import unicodedata

from io import BytesIO
import xml.etree.ElementTree as ET
from xml.dom import minidom

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
WIDTH = 720
HEIGHT = 480

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
        """.replace("\n", "").replace(" ", ""))
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
            telop.append(self._tag("artist_name", "♪ " + song.meta["artist"][None]))
            if "k" in song.meta["artist"]:
                info.append(self._tag("artist_name_yomi", song.meta["artist"]["k"]))
        info.append(self._tag("original_artist_name", " "))
        if "writer" in song.meta:
            info.append(self._tag("lyricist_name", song.meta["writer"][None]))
            telop.append(self._tag("lyricist_name", "作詞 " + song.meta["writer"][None]))
        if "composer" in song.meta:
            info.append(self._tag("composer_name", song.meta["composer"][None]))
            telop.append(self._tag("composer_name", "作曲 " + song.meta["composer"][None]))
        info.append(self._tag("cover_code", " "))

    def _load_audio(self, song, tag, path, **extra):
        el = ET.XML("""
            <music>
                <file_path/>
                <md5_sum/>
                <type>1</type>
                <format>1</format>
                <play_time/>
                <adjust_time>0</adjust_time>
                <vol>50</vol>
                <balance>0</balance>
                <reverb>0</reverb>
            </music>
        """.replace("\n", "").replace(" ", ""))
        el.tag = tag
        el.find("file_path").text = opts.pathbase + path
        h = hashlib.md5(open(os.path.join(song.pathbase, path), "rb").read()).hexdigest()
        el.find("md5_sum").text = h
        el.find("play_time").text = "%d" % (int(self.duration))
        for k,v in extra.items():
            el.append(self._tag(k, v))
        return el

    def _load_video(self, song, path, **extra):
        el = ET.XML("""
            <movie>
                <file_path/>
                <md5_sum/>
                <type>1</type>
                <format>4</format>
                <play_time/>
                <begin_time>0</begin_time>
                <end_time/>
                <enable>1</enable>
            </movie>
        """.replace("\n", "").replace(" ", ""))
        el.find("file_path").text = opts.pathbase + path
        h = hashlib.md5(open(os.path.join(song.pathbase, path), "rb").read()).hexdigest()
        el.find("md5_sum").text = h
        el.find("play_time").text = "%d" % (int(self.duration))
        el.find("end_time").text = "%d" % (int(self.duration))
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
            music = self._load_audio(song, "music", song.song["audio_instrumental"], enable="1")
            music.insert(0, self._tag("set", "1"))
            self.root.append(music)
        if "audio_vocal" in song.song:
            vocal = ET.Element("vocal")
            vocal.append(self._tag("set", "1"))
            vocal.append(self._load_audio(song, "song", song.song["audio_vocal"],
                                          song_type="0", song_number="0", enable="1",  marker_count="0"))
            self.root.append(vocal)
        if "audio" in song.song:
            mix = self._load_audio(song, "mix", song.song["audio"], enable="1")
            mix.insert(0, self._tag("set", "1"))
            self.root.append(mix)
        if "video" in song.song:
            back = ET.Element("back")
            back.append(self._tag("set", "1"))
            back.append(self._load_video(song, song.song["video"]))
            self.root.append(back)

    def _load_lyrics(self, s):
        telop = self.root.find("telop")

        renderer = graphics.get_renderer().KaraokeRenderer(self.display)
        lyt = layout.SongLayout(s, list(s.variants.keys())[opts.variant], renderer)

        lines = lyt.lines[song.TagInfo.BOTTOM]

        class Page(object):
            pass

        def ms(i):
            return str(int(round(i * 1000)))

        def color(rgb):
            r, g, b = rgb
            return "%d" % (r | (g << 8) | (b << 16))

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
                        li = " ".join(repr(v.molecules[0][0].text) for k,v in sorted(lines.items(), reverse=True))
                        raise Exception("overlapping lines! %r" % (li))
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
            styles = None
            for i in range(max(page.lines.keys()), -1, -1):
                le = ET.Element("line")
                text = ""
                if i not in page.lines:
                    if styles:
                        styles = [[styles[-1][0], 0, 0]]
                    else:
                        styles = [[page.lines.values()[0].molecules[0].style, 0, 0]]
                    # dummy line
                    w = ET.Element("word")
                    w.append(self._tag("text", " "))
                    w.append(self._tag("start_time", ms(t)))
                    w.append(self._tag("end_time", ms(t)))
                    le.append(w)
                    text = " "
                    width = cwidth = 0
                    align = 0
                else:
                    line = page.lines[i]
                    align = line.align
                    ruby = []
                    styles = []

                    for idx, instance in enumerate(line.molecules):
                        mol = instance.molecule
                        step = 0
                        start_pos = len(text)
                        for atom in mol.atoms:
                            start, end = instance.get_atom_time(step, atom.steps)
                            t = max(t, end)
                            step += atom.steps

                            w = ET.Element("word")
                            w.append(self._tag("text", atom.text))
                            w.append(self._tag("start_time", ms(start)))
                            w.append(self._tag("end_time", ms(end)))
                            le.append(w)

                            if atom.particles is not None:
                                edge = len(atom.text)
                                edge_l = 0
                                if atom.particle_edge:
                                    edge = atom.particle_edge
                                if atom.particle_edge_l:
                                    edge_l = atom.particle_edge_l
                                rt = ""
                                for i in atom.particles:
                                    rt += i.text
                                r = ET.Element("ruby")
                                r.append(self._tag("text", rt))
                                r.append(self._tag("start_pos", "%d" % (len(text) + edge_l)))
                                r.append(self._tag("end_pos", "%d" % (len(text) + edge - 1)))
                                ruby.append(r)

                            text += atom.text
                        if idx != (len(line.molecules) - 1):
                            text += "　"
                            w[0].text += "　"
                        if styles and instance.style == styles[-1]:
                            styles[-1][2] = len(text) - 1
                        else:
                            styles.append([instance.style, start_pos, len(text) - 1])

                    for r in ruby:
                        le.append(r)

                    print(text)
                    width = line.max_px - line.min_px
                    cwidth = len(text)
                    for i in text:
                        ew = unicodedata.east_asian_width(i)
                        if ew in ("F", "W", "A"):
                            cwidth += 1

                    if cwidth > 26:
                        print("  ^-- WARNING: Line likely too long")

                for style, start, end in styles:
                    e = ET.Element("color")
                    e.append(self._tag("before_text_color", color(style.colors[0])))
                    e.append(self._tag("after_text_color", color(style.colors_on[0])))
                    e.append(self._tag("before_shadow_color", color(style.colors[1])))
                    e.append(self._tag("after_shadow_color", color(style.colors_on[1])))
                    e.append(self._tag("before_text_no_fill_color", color(style.colors[0])))
                    e.append(self._tag("after_text_no_fill_color", color(style.colors_on[0])))
                    e.append(self._tag("before_shadow_no_fill_color", color(style.colors[1])))
                    e.append(self._tag("after_shadow_no_fill_color", color(style.colors_on[1])))
                    e.append(self._tag("start_pos", "%d" % start))
                    e.append(self._tag("end_pos", "%d" % end))
                    e.append(self._tag("no_fill", "1" if style.colors == style.colors_on else "0"))
                    le.append(e)

                e = ET.Element("duet")
                e.append(self._tag("mark", "0"))
                e.append(self._tag("start_pos", "0"))
                e.append(self._tag("end_pos", "%d" % (len(text) - 1)))
                le.append(e)

                e = ET.Element("offset")
                w = 720
                margin = 54
                offset = margin + (w * (1 - width) - 2 * margin) * align
                if offset < 0 or offset + w * width > w - margin:
                    print("  ^-- WARNING: Line too wide")
                # 0 = default
                # 1 = offset from default
                # 2 = abs left side
                e.append(self._tag("type", "2"))
                e.append(self._tag("auto_pos", "0"))
                e.append(self._tag("offset", "%d" % round(offset)))
                le.append(e)

                pe.append(le)

            telop.append(pe)

        self.root.remove(telop)
        self.root.append(telop)

        telop_edit_setting = ET.XML("""
            <telop_edit_setting>
                <music_volume>50</music_volume>
                <vocal_volume>50</vocal_volume>
            </telop_edit_setting>
        """.replace("\n", "").replace(" ", ""))
        self.root.append(telop_edit_setting)

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
bio = BytesIO()
pro.et.write(bio, encoding="UTF-8", xml_declaration=True)
xmlstr = bio.getvalue().replace(b"\n", b" ").replace(b"\r", b"")
xmlstr = minidom.parseString(xmlstr).toprettyxml(indent="  ", encoding="UTF-8").replace(b"\n", b"\r\n")
with open(opts.output, "wb") as fd:
    fd.write(xmlstr)

os._exit(0)
