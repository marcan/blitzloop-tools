#!/usr/bin/env python3
# -!- coding: utf-8 -!-

import sys
from blitzloop.song import Song, Variant, Style, OrderedDict, JapaneseMolecule, MultiString, MixedFraction, Compound
from decimal import Decimal
from joysound_format import JoysoundFile

with open(sys.argv[1], "rb") as fd:
    js = JoysoundFile.parse(fd.read())

song = Song()
song.meta["title"] = MultiString([
    (None, js.metadata.title),
    ('k', js.metadata.title_kana)])
song.meta["artist"] = MultiString([
    (None, js.metadata.artist),
    ('k', js.metadata.artist_kana)])
song.meta["writer"] = MultiString([(None, js.metadata.writer)])
song.meta["composer"] = MultiString([(None, js.metadata.composer)])
song.timing.add(0, 0)
song.timing.add(1, 1)
style_map = {}

last_y = None
last_block = None

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

for block in js.lyrics.blocks:
    style = block.pre_fill, block.post_fill, block.pre_border, block.post_border
    if style not in style_map:
        st_code = chr(ord("A") + len(style_map))
        style_map[style] = st_code
        song.formats[st_code] = JapaneseMolecule
    else:
        st_code = style_map[style]

    block.st_code = st_code

    if last_block and (last_y != block.ypos or last_x >= block.xpos):
        last_block.source += "$"

    last_x = x = block.xpos
    last_y = block.ypos
    

    char_pos = {}
    new_chars = []

    # calculate char positions
    for i, char in enumerate(block.chars):
        char.left = x
        x += char.width
        char.right = x
        char.furi = None
        if char.char != " ":
            char_pos[(char.left + char.right) // 2] = char

    # remove stupid leading spaces
    if block.chars[0].char == " ":
        block.chars = block.chars[1:]

    # assign furigana
    for furi in block.furi:
        furi.left = furi.xpos + block.xpos
        # guess that furigana width per char is 24
        furi.right = furi.left + 24 * len(furi.char)
        center = (furi.left + furi.right) // 2
        furi.count = 0
        # figure out how many beats for the furigana
        for i, c in enumerate(furi.char):
            if i == 0 or c not in JapaneseMolecule.COMBINE_CHARS:
                furi.count += 1
        # heuristically find matching base chars
        for dx in range(640):
            for pos in (center - dx, center + dx):
                if pos in char_pos:
                    if not is_furiganable(char_pos[pos].char):
                        break
                    char_pos[pos].furi = furi
            else:
                continue
            break

    # merge characters together that are from the same furigana or beat
    # does not merge trailing combining chars after a furigana group
    new_chars = []
    beat_xpos = []
    for char in block.chars:
        if char.furi and new_chars and new_chars[-1].furi == char.furi:
            new_chars[-1].char += char.char
            new_chars[-1].right = char.right
            new_chars[-1].needs_group = True
        elif (char.char in JapaneseMolecule.COMBINE_CHARS
              and new_chars and not new_chars[-1].furi):
            new_chars[-1].char += char.char
            new_chars[-1].right = char.right
        else:
            new_chars.append(char)
            new_chars[-1].needs_group = False
    block.chars = new_chars

    # now build the molecule source text
    block.source = ""
    for char in block.chars:
        if char.needs_group:
            block.source += "{%s}" % escape(char.char)
        else:
            block.source += escape(char.char)
        if char.furi:
            block.source += "(%s)" % escape(char.furi.char)

    # merge again, now ignoring furi, so that mergeable trailing characters
    # after a furi atom are joined for timing purposes
    new_chars = []
    for char in block.chars:
        if all(i in JapaneseMolecule.COMBINE_CHARS for i in char.char) and new_chars:
            new_chars[-1].char += char.char
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

block_idx = -1
beats = []
times = None
for i, event in enumerate(js.timing):
    event_id = event.payload[0]
    if event_id == 0:
        for i in beats:
            times.append(t1 + (i - x1) / speed)
        if times:
            block.beat_time = times
        block_idx += 1
        block = js.lyrics.blocks[block_idx]
        times = []
        beats = block.beat_xpos
        t1 = event.time / 1000.0
        speed = event.payload[1] * 10.0
        x1 = block.xpos
    elif event_id == 1:
        t2 = event.time / 1000.0
        x2 = int(x1 + speed * (t2 - t1))
        while beats and beats[0] < x2:
            times.append(t1 + (beats[0] - x1) / speed)
            beats = beats[1:]
        t1 = t2
        x1 = x2
        speed = event.payload[1] * 10.0

for i in beats:
    times.append(t1 + (i - x1) / speed)
if times:
    block.beat_time = times

for block in js.lyrics.blocks:
    timing = [Decimal("%.3f" % i) for i in block.beat_time]
    compound = Compound(song.timing)
    compound.start = timing[0]
    compound.timing = [timing[i] - timing[i - 1] for i in range(1, len(timing))]
    compound[block.st_code] = JapaneseMolecule(block.source)
    assert compound[block.st_code].steps == len(compound.timing)
    song.compounds.append(compound)

def get_color(c):
    r,g,b = js.lyrics.colors[c]
    return "%02x%02x%02x" % (r*255/31, g*255/31, b*255/31)

for style, st_code in sorted(list(style_map.items()), key=lambda x: x[1]):
    data = OrderedDict([
        ("colors", "%s,%s,000000" % (get_color(style[0]), get_color(style[2]))),
        ("colors_on", "%s,%s,000000" % (get_color(style[1]), get_color(style[3])))
    ])
    song.styles[st_code] = Style(data)

song.variants["japanese"] = Variant(OrderedDict([
    ("name", "日本語"),
    ("tags", ",".join(sorted(style_map.values())))] +
    [("%s.style" % st_code, st_code)
     for st_code in sorted(style_map.values())]))

with open(sys.argv[2], "wb") as fd:
    fd.write(song.dump().encode("utf-8"))
