from construct import *
from joysound_utils import *

JoyU2LyricsSection = Struct(
    "colors" / Array(15, RGB15b),
    "blocks" / GreedyRange(
        Struct(
            "size" / Int16ub,
            "flags" / Int16ub,
            "xpos" / Int16ub,
            "ypos" / Int16ub,
            "pre_fill" / Int8ub,
            "post_fill" / Int8ub,
            "pre_border" / Int8ub,
            "post_border" / Int8ub,
            "unkpos1" / Int16ub,
            "unkpos2" / Int16ub,
            "chars" / PrefixedArray(
                "count" / Int16ub,
                Struct(
                    "font" / Int8ub,
                    "char" / Int16ub,
                )
            ),
            "furi" / PrefixedArray(
                "furi_count" / Int16ub,
                Struct(
                    "length" / Int16ub,
                    "xpos" / Int16ub,
                    "char" / Array(lambda ctx: ctx.length, Int16ub),
                )
            ),
        )
    )
)

# 00 XX - start scrolling at speed XX * 10
# 01 XX - set speed to XX * 10
# 04 - fade out title card
# 05 XX - hide XX blocks
# 06 XX - show XX blocks
# 0c XX - start scrolling at speed XX
# 0d XX - set speed to XX

# 17 - hide lyrics?

# a0 - visualizer unknown?
# a1 - visualizer bg fade out
# a2 - visualizer bg fade out (?)
# a3 - visualizer bg on
# a7 - visualizer command upcoming (1 second before a[0123])

# c0 - lyrics start
# c1 - lyrics stop

JoyU2TimingSection = GreedyRange(
    Struct(
        "delta" / VarIntb,
        "payload" / Prefixed(Int8ub, GreedyBytes)
    )
)

JoyU2File = Struct(
    Const(b"JOY-U2"),
    "off_metadata" / Int32ub,
    "off_lyrics_1" / Int32ub,
    "off_timing_1" / Int32ub,
    "off_lyrics_2" / Int32ub,
    "off_timing_2" / Int32ub,
    "off_lyrics_3" / Int32ub,
    "off_timing_3" / Int32ub,
    "off_extra" / Int32ub,
    "metadata" / Pointer(lambda ctx: ctx.off_metadata,
        Struct(
            "type" / Int8ub,
            "subtype" / Int8ub,
            "off_title" / Int16ub,
            "off_artist" / Int16ub,
            "off_writer" / Int16ub,
            "off_composer" / Int16ub,
            "off_title_kana" / Int16ub,
            "off_artist_kana" / Int16ub,
            "off_jasrac_code" / Int16ub,
            "off_sample" / Int16ub,
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
    "sizes" / Sequence(
        Struct(
            "lyrics" / Pointer(this._._.off_lyrics_1,
                FixedSized(this._._.off_timing_1 - this._._.off_lyrics_1,
                    JoyU2LyricsSection)),
            "timing" / Pointer(this._._.off_timing_1,
                FixedSized(this._._.off_lyrics_2 - this._._.off_timing_1,
                    JoyU2TimingSection)),
        ),
        Struct(
            "lyrics" / Pointer(this._._.off_lyrics_2,
                FixedSized(this._._.off_timing_2 - this._._.off_lyrics_2,
                    JoyU2LyricsSection)),
            "timing" / Pointer(this._._.off_timing_2,
                FixedSized(this._._.off_lyrics_3 - this._._.off_timing_2,
                    JoyU2TimingSection)),
        ),
        Struct(
            "lyrics" / Pointer(this._._.off_lyrics_3,
                FixedSized(this._._.off_timing_3 - this._._.off_lyrics_3,
                    JoyU2LyricsSection)),
            "timing" / Pointer(this._._.off_timing_3,
                FixedSized(this._._.off_extra - this._._.off_timing_3,
                    JoyU2TimingSection)),
        ),
    ),
)

