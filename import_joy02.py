#!/usr/bin/env python3
# -!- coding: utf-8 -!-

import sys
from blitzloop.song import Song, Variant, Style, OrderedDict, JapaneseMolecule, MultiString, MixedFraction, Compound
from decimal import Decimal
from joy02_format import Joy02File

def is_furiganable(char):
    if char in " 　？！?!…。、.,-「」―-":
        return False
    code = ord(char)
    if 0x3040 <= code <= 0x30ff: # Kana
        return False
    return True

def escape(char):
    s = ""
    for c in char:
        if c in "()（）{}｛｝$^\\":
            s += "\\"
        s += c
    return s

class Joy02Importer(object):
    EV_SCROLL_START = 0
    EV_SCROLL_SETSPEED = 1
    EV_SCROLL_START2 = 0xc
    EV_SCROLL_SETSPEED2 = 0xd

    def __init__(self, song, lyrics=None, timing=None, metadata=None):
        self.song = song
        self.lyrics = lyrics
        self.timing = timing
        self.metadata = metadata

    def import_all(self):
        self.import_meta()
        self.import_lyrics()
        self.import_styles()
        self.import_timing()

    def import_meta(self):
        self.song.meta["title"] = MultiString([
            (None, self.metadata.title),
            ('k', self.metadata.title_kana)])
        self.song.meta["artist"] = MultiString([
            (None, self.metadata.artist),
            ('k', self.metadata.artist_kana)])
        self.song.meta["writer"] = MultiString([(None, self.metadata.writer)])
        self.song.meta["composer"] = MultiString([(None, self.metadata.composer)])

    def get_furi_width(self, furi):
        return 24 * len(furi.char)

    def get_char(self, c):
        return c

    def get_char_width(self, c):
        return c.width

    def import_lyrics(self):
        self.style_map = {}

        last_y = None
        last_block = None

        for block in self.lyrics.blocks:
            style = block.pre_fill, block.post_fill, block.pre_border, block.post_border
            if style not in self.style_map:
                st_code = chr(ord("A") + len(self.style_map))
                self.style_map[style] = st_code
                self.song.formats[st_code] = JapaneseMolecule
            else:
                st_code = self.style_map[style]

            block.st_code = st_code

            if last_block and (last_y != block.ypos or last_x >= block.xpos):
                last_block.source += "$"

            last_x = x = block.xpos
            last_y = block.ypos

            char_pos = {}
            new_chars = []

            # calculate char positions
            for i, char in enumerate(block.chars):
                char.uchar = self.get_char(char.char)
                char.left = x
                x += self.get_char_width(char)
                char.right = x
                char.furis = []
                char.furi = None
                if char.uchar != " ":
                    char_pos[(char.left + char.right) // 2] = char

            #print("%d,%d %d,%d" % (block.xpos, block.ypos, block.unkpos1,block.unkpos2))

            #for i, char in enumerate(block.chars):
                #print ("  %d..%d %s" % (char.left, char.right, char.uchar))

            # remove stupid leading spaces
            if block.chars[0].uchar == " ":
                block.chars = block.chars[1:]

            # assign furigana
            for furi in block.furi:
                furi.text = "".join(self.get_char(i) for i in furi.char)
                furi.assigned = False
                furi.left = furi.xpos + block.xpos
                # guess that furigana width per char is 24

                furi.right = furi.left + self.get_furi_width(furi)
                # get rid of spaces in furigana
                furi.text = furi.text.replace(" ", "")
                center = (furi.left + furi.right) // 2
                furi.count = 0
                # figure out how many beats for the furigana
                for i, c in enumerate(furi.text):
                    if i == 0 or c not in JapaneseMolecule.COMBINE_CHARS:
                        furi.count += 1
                # heuristically find matching base chars
                for dx in range(640):
                    for pos in (center - dx, center + dx):
                        if pos in char_pos:
                            if not is_furiganable(char_pos[pos].uchar):
                                break
                            char_pos[pos].furis.append((dx, furi))
                    else:
                        continue
                    break

            # figure out best fit furigana group for each char
            for i, char in enumerate(block.chars):
                if char.furis:
                    char.furis.sort(key=lambda x: x[0])
                    char.furi = char.furis[0][1]
                    char.furi.assigned = True

            for furi in block.furi:
                if not furi.assigned:
                    print("WARNING: furi block '%s' unassigned (in '%s')" %(furi.text, "".join(i.uchar for i in block.chars)))

            # merge characters together that are from the same furigana or beat
            # does not merge trailing combining chars after a furigana group
            new_chars = []
            beat_xpos = []
            for char in block.chars:
                if char.furi and new_chars and new_chars[-1].furi == char.furi:
                    new_chars[-1].uchar += char.uchar
                    new_chars[-1].right = char.right
                    new_chars[-1].needs_group = True
                elif (char.uchar in JapaneseMolecule.COMBINE_CHARS
                    and new_chars and not new_chars[-1].furi):
                    new_chars[-1].uchar += char.uchar
                    new_chars[-1].right = char.right
                else:
                    new_chars.append(char)
                    new_chars[-1].needs_group = False
            block.chars = new_chars

            # now build the molecule source text
            block.source = ""
            for char in block.chars:
                if char.needs_group:
                    block.source += "{%s}" % escape(char.uchar)
                else:
                    block.source += escape(char.uchar)
                if char.furi:
                    block.source += "(%s)" % escape(char.furi.text)

            # merge again, now ignoring furi, so that mergeable trailing characters
            # after a furi atom are joined for timing purposes
            new_chars = []
            for char in block.chars:
                if all(i in JapaneseMolecule.COMBINE_CHARS for i in char.uchar) and new_chars:
                    new_chars[-1].uchar += char.uchar
                    new_chars[-1].right = char.right
                else:
                    new_chars.append(char)
            block.chars = new_chars

            # build timing (beats) mapping to x coord:
            beat_xpos = []
            for char in block.chars:
                beat_xpos.append(char.left)
                if char.furi:
                    dx = float(char.right - char.left) / char.furi.count
                    for i in range(1, char.furi.count):
                        beat_xpos.append(int(char.left + dx * i))
            beat_xpos.append(char.right)

            block.beat_xpos = beat_xpos
            block.beat_time = []

            last_block = block

    def import_styles(self):
        def get_color(c):
            r,g,b = self.lyrics.colors[c]
            return "%02x%02x%02x" % (r*255//31, g*255//31, b*255//31)

        for style, st_code in sorted(list(self.style_map.items()), key=lambda x: x[1]):
            data = OrderedDict([
                ("colors", "%s,%s,000000" % (get_color(style[0]), get_color(style[2]))),
                ("colors_on", "%s,%s,000000" % (get_color(style[1]), get_color(style[3])))
            ])
            self.song.styles[st_code] = Style(data)

        self.song.variants["japanese"] = Variant(OrderedDict([
            ("name", "日本語"),
            ("tags", ",".join(sorted(self.style_map.values())))] +
            [("%s.style" % st_code, st_code)
            for st_code in sorted(self.style_map.values())]))

    def import_timing(self):

        block_idx = -1
        beats = []
        times = None
        for i, event in enumerate(self.timing):
            event_id = event.payload[0]
            #print("%.02f %x %r" % (event.time/1000 + 13.47 - 0.55, event_id, event.payload[1:]))
            if event_id in (self.EV_SCROLL_START,
                            self.EV_SCROLL_START2
                           ):
                for i in beats:
                    times.append(t1 + (i - x1) / speed)
                if times:
                    block.beat_time = times
                t1 = event.time / 1000.0
                block_idx += 1
                block = self.lyrics.blocks[block_idx]
                while block.flags == 0xff:
                    block.beat_time = [t1]
                    block_idx += 1
                    block = self.lyrics.blocks[block_idx]
                times = []
                beats = block.beat_xpos
                speed = event.payload[1]
                if event_id == self.EV_SCROLL_START:
                    speed *= 10
                x1 = block.xpos
            elif event_id in (self.EV_SCROLL_SETSPEED,
                              self.EV_SCROLL_SETSPEED2):
                t2 = event.time / 1000.0
                x2 = int(x1 + speed * (t2 - t1))
                while beats and beats[0] < x2:
                    times.append(t1 + (beats[0] - x1) / speed)
                    beats = beats[1:]
                t1 = t2
                x1 = x2
                speed = event.payload[1]
                if event_id == self.EV_SCROLL_SETSPEED:
                    speed *= 10

        for i in beats:
            times.append(t1 + (i - x1) / speed)
        if times:
            block.beat_time = times

        block_idx += 1
        while block_idx < len(self.lyrics.blocks):
            block = self.lyrics.blocks[block_idx]
            assert block.flags == 0xff
            block.beat_time = [t1]
            block_idx += 1

        for block in self.lyrics.blocks:
            timing = [Decimal("%.3f" % i) for i in block.beat_time]
            #print(hex(block.flags), block.source)
            compound = Compound(self.song.timing)
            compound.start = timing[0]
            compound.timing = [timing[i] - timing[i - 1] for i in range(1, len(timing))]
            compound[block.st_code] = JapaneseMolecule(block.source.strip())
            if block.flags != 0xff:
                assert compound[block.st_code].steps == len(compound.timing)
            else:
                assert 0 == len(compound.timing)
            self.song.compounds.append(compound)

if __name__ == "__main__":
    with open(sys.argv[1], "rb") as fd:
        js = Joy02File.parse(fd.read())

    song = Song()
    song.timing.add(0, 0)
    song.timing.add(1, 1)

    importer = Joy02Importer(song, js.lyrics, js.timing, js.metadata)
    importer.import_all()

    with open(sys.argv[2], "wb") as fd:
        fd.write(song.dump().encode("utf-8"))
