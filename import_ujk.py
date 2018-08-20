#!/usr/bin/env python3
# -!- coding: utf-8 -!-

import sys, os, subprocess
from blitzloop.song import Song, Variant, Style, OrderedDict, JapaneseMolecule, MultiString, MixedFraction, Compound
from decimal import Decimal
from ujk_format import UJKFile
from import_joy02 import Joy02Importer

def get_bitmap(char):
    PAL = " .,-+*iotwITW&#@"[::-1]
    bitmap = "+" +  "--" * char.width + "+\n"
    for j in range(char.height):
        row = ""
        for i in range(char.width):
            byte = j * char.stride + i // 2
            shift = 0 if i & 1 else 4
            row += PAL[(char.data[byte] >> shift) & 0xf] * 2
        bitmap += "|" + row + "|\n"
    bitmap += "+" +  "--" * char.width + "+\n"
    return bitmap

CHARMAP = {
    0xa177: "ー",
    0xa220: " ",
    0xa477: "ー", # furigana
    0xa521: "♠", # smaller?
    0xa522: "♥", # smaller?
    0xa66a: "♡",
    0xa66b: "♥",
    0xa66c: "♢",
    0xa66d: "♦",
    0xa66e: "♧",
    0xa66f: "♣",
    0xa924: "ä",
    0xa926: "ü",
    0xa931: "è",
    0xa932: "é",
    0xa933: "à",
    0xa935: "í",
    0xa936: "ò",
    0xa938: "ù",
    0xad21: "・",
    0xad28: "溢", # JIS2004 form
    0xad2c: "錆", # JIS2004 form
    0xad35: "㊙",
    0xae65: "･", # maybe?
    0xae66: "・", # maybe?
}

class JoyU2Importer(Joy02Importer):
    def __init__(self, ujk, song):
        self.js = ujk.lyrics.value
        self.font = ujk.fonts.value.fonts[0]
        super().__init__(song,
                         lyrics=self.js.sizes[0].lyrics,
                         timing=self.js.sizes[0].timing,
                         metadata=self.js.metadata)

    def get_furi_width(self, furi):
        return sum(self.font.chars[i].char.width for i in furi.char)

    def get_char(self, c):
        char = self.font.chars[c].char
        code = char.code
        if code in CHARMAP:
            return CHARMAP[code]
        elif 0x20 <= code <= 0x7f:  # the real ASCII
            return chr(code)
        elif 0x121 <= code <= 0x15f:  # varying width spaces
            return " "
        elif 0xa021 <= code <= 0xa073:  # hiragana
            return chr(code - 0xa020 + 0x3040)
        elif 0xa121 <= code <= 0xa176:  # katagana
            return chr(code - 0xa120 + 0x30a0)
        elif 0xa321 <= code <= 0xa373:  # hiragana (furigana)
            return chr(code - 0xa320 + 0x3040)
        elif 0xa421 <= code <= 0xa476:  # katagana (furigana)
            return chr(code - 0xa420 + 0x30a0)
        elif 0xa820 <= code <= 0xa87f:  # some other ASCII
            return chr(code - 0xa800)
        elif 0xab20 <= code <= 0xab7f:  # ASCII again?
            return chr(code - 0xab00)
        elif 0x8000 <= code <= 0x9fff or 0xe000 <= code <= 0xffff:
            sj = bytes([code >> 8, code & 0xff])
            return sj.decode("sjis")
        else:
            raise Exception("Unmapped character code 0x%04x.\nDimensions: %dx%d (adv:%d).\nBitmap:\n%s\n" % (
                code, char.width, char.height, char.advance, get_bitmap(char)))

    def get_char_width(self, c):
        return self.font.chars[c.char].char.advance

    def import_timing(self):
        t = 0
        for ev in self.timing:
            t += ev.delta
            ev.time = t

        super().import_timing()

NAMES = ["Percussion", "Melody", "Vocal", "Ch4", "Ch5"]

if __name__ == "__main__":
    with open(sys.argv[1], "rb") as fd:
        ujk = UJKFile.parse(fd.read())

    destdir = sys.argv[2]

    if not os.path.exists(destdir):
        os.mkdir(destdir)

    song = Song()
    # Lol timing is off in the source files
    song.timing.add(0.2, 0)
    song.timing.add(1.2, 1)

    importer = JoyU2Importer(ujk, song)
    importer.import_all()

    with open(os.path.join(destdir, "title_card.png"), "wb") as fd:
        fd.write(ujk.title_card)

    streams = []

    for i, hdr in enumerate(ujk.audio.headers):
        assert hdr.stream_id == i
        streams.append([])

    for block in ujk.audio.blocks:
        streams[block.stream_id].append(block.data)

    streams = [b"".join(l) for l in streams]

    print("Merging audio...")

    cmd = [
        "ffmpeg", "-loglevel", "error", "-y"
    ]

    for i, data in enumerate(streams):
        path = os.path.join(destdir, "stream%d.aac" % i)
        with open(path, "wb") as fd:
            fd.write(data)
        cmd += ["-i", path]

    filters = ["[%d]apad[p%d]" % (i, i) for i in range(1, len(streams))]
    filters.append("[0]" +
                   "".join("[p%d]" % i for i in range(1, len(streams))) +
                   ("amerge=inputs=%d[aout]" % len(streams)))

    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[aout]", os.path.join(destdir, "audio.opus")
    ]

    subprocess.run(cmd, check=True, stdin=subprocess.PIPE)

    song.song["audio"] = "audio.opus"
    song.song["fade_in"] = "0"
    song.song["fade_out"] = "0"
    song.song["volume"] = 1.0
    song.song["channels"] = len(streams) - 1
    song.song["channel_names"] = ",".join(NAMES[:len(streams) - 1])
    song.song["channel_defaults"] = ",".join((["10"] + ["5"] + ["10"] * len(streams))[:len(streams) - 1])

    with open(os.path.join(destdir, "song.blitz"), "wb") as fd:
        fd.write(song.dump().encode("utf-8"))

    print("Done.")
