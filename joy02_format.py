#!/usr/bin/python3

import json, base64, sys

from construct import *
from joysound_utils import *

Joy02File = Struct(
    Const(b"JOY-02"),
    "off_metadata" / Int32ul,
    "off_lyrics" / Int32ul,
    "off_timing" / Int32ul,
    "vol_up_time" / Int32ul,
    "metadata" / Pointer(this.off_metadata,
        Struct(
            "type" / Int8ul,
            "subtype" / Int8ul,
            "off_title" / Int16ul,
            "off_artist" / Int16ul,
            "off_writer" / Int16ul,
            "off_composer" / Int16ul,
            "off_title_kana" / Int16ul,
            "off_artist_kana" / Int16ul,
            "off_jasrac_code" / Int16ul,
            "off_sample" / Int16ul,
            "duration" / Int16ul,
            "vocal_tracks" / Int32ul,
            "rhythm_tracks" / Int32ul,
            "title" / Pointer(this._.off_metadata + this.off_title, CJString()),
            "artist" / Pointer(this._.off_metadata + this.off_artist, CJString()),
            "writer" / Pointer(this._.off_metadata + this.off_writer, CJString()),
            "composer" / Pointer(this._.off_metadata + this.off_composer, CJString()),
            "title_kana" / Pointer(this._.off_metadata + this.off_title_kana, CJString()),
            "artist_kana" / Pointer(this._.off_metadata + this.off_artist_kana, CJString()),
            "jasrac_code" / Pointer(this._.off_metadata + this.off_jasrac_code, CJString()),
            "sample" / Pointer(this._.off_metadata + this.off_sample, CJString()),
        )
    ),
    "lyrics" / Pointer(this.off_lyrics,
        FixedSized(this.off_timing - this.off_lyrics,
            Struct(
                "colors" / Array(15, RGB15l),
                "blocks" / GreedyRange(
                    Struct(
                        "size" / Int16ul,
                        "flags" / Int16ul,
                        "xpos" / Int16ul,
                        "ypos" / Int16ul,
                        "pre_fill" / Int8ul,
                        "post_fill" / Int8ul,
                        "pre_border" / Int8ul,
                        "post_border" / Int8ul,
                        "chars" / PrefixedArray(
                            "count" / Int16ul,
                            Struct(
                                "font" / Int8ul,
                                "char" / SJISString(1),
                                "width" / Int16ul
                            )
                        ),
                        "furi" / PrefixedArray(
                            "furi_count" / Int16ul,
                            Struct(
                                "length" / Int16ul,
                                "xpos" / Int16ul,
                                "char" / SJISString(this.length),
                            )
                        ),
                    )
                )
            )
        )
    ),
    "timing" / Pointer(this.off_timing,
        GreedyRange(
            Struct(
                "time" / Int32ul,
                "payload" / PrefixedArray(
                    "size" / Int8ul,
                    "payload" / Int8ul
                )
            )
        )
    )
)
