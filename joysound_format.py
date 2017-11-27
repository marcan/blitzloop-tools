#!/usr/bin/python2

import json, base64, sys

from construct import Struct, Int8ul, Int16ul, Int32ul, Pointer, CString, Adapter, Array, Range, GreedyRange, PrefixedArray, Const, RepeatUntil, ListContainer, Tell

def CJString(*args, **kwargs):
    return CString(*args, **kwargs, encoding="sjis")

class SJIS16StringAdapter(Adapter):
    def _encode(self, obj, context):
        sj = obj.encode("sjis")
        i, l = 0, len(sj)
        v = []
        while i < l:
            c = ord(sj[i])
            if 0x80 <= c < 0xa0 or 0xe0 <= c:
                c2 = ord(sj[i+1])
                v.append(c2 | (c<<8))
                i += 2
            else:
                v.append(c)
        return v
    def _decode(self, obj, context):
        sj = bytearray()
        for c in obj:
            if c < 0xff:
                sj.append(c)
            else:
                sj.append(c >> 8)
                sj.append(c & 0xff)
        return sj.decode("sjis")

def SJISString(count):
    return SJIS16StringAdapter(Array(count, Int16ul))

class PrettyListAdapter(Adapter):
    def _encode(self, obj, context):
        return obj
    def _decode(self, obj, context):
        return ListContainer(obj)

class ShortListAdapter(Adapter):
    def _encode(self, obj, context):
        return obj
    def _decode(self, obj, context):
        return list(obj)

class RGB15Adapter(Adapter):
    def _encode(self, obj, context):
        return (obj[0] << 10 | obj[1] << 5 | obj[2])
    def _decode(self, obj, context):
        return obj >> 10, (obj >> 5) & 0x1f, obj & 0x1f

RGB15 = RGB15Adapter(Int16ul)

def ShortByteArray(size, name):
    return ShortListAdapter(Array(size, Int8ul(name)))

JoysoundFile = Struct(
    Const(b"JOY-02"),
    "off_metadata" / Int32ul,
    "off_lyrics" / Int32ul,
    "off_timing" / Int32ul,
    "vol_up_time" / Int32ul,
    Pointer(lambda ctx: ctx.off_metadata,
        "metadata" / Struct(
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
            Pointer(lambda ctx: ctx._.off_metadata + ctx.off_title, "title" / CJString()),
            Pointer(lambda ctx: ctx._.off_metadata + ctx.off_artist, "artist" / CJString()),
            Pointer(lambda ctx: ctx._.off_metadata + ctx.off_writer, "writer" / CJString()),
            Pointer(lambda ctx: ctx._.off_metadata + ctx.off_composer, "composer" / CJString()),
            Pointer(lambda ctx: ctx._.off_metadata + ctx.off_title_kana, "title_kana" / CJString()),
            Pointer(lambda ctx: ctx._.off_metadata + ctx.off_artist_kana, "artist_kana" / CJString()),
            Pointer(lambda ctx: ctx._.off_metadata + ctx.off_jasrac_code, "jasrac_code" / CJString()),
            Pointer(lambda ctx: ctx._.off_metadata + ctx.off_sample, "sample" / CJString()),
        )
    ),
    Pointer(lambda ctx: ctx.off_lyrics,
        "lyrics" / Struct(
            "colors" / Array(15, RGB15),
            PrettyListAdapter(RepeatUntil(lambda obj, list, ctx: obj.end_off >= ctx._.off_timing,
                "blocks" / Struct(
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
                            "char" / SJISString(lambda ctx: ctx.length),
                        )
                    ),
                    "end_off" / Tell
                )
            ))
        )
    ),
    Pointer(lambda ctx: ctx.off_timing,
        PrettyListAdapter(GreedyRange(
            "timing"/ Struct(
                "time" / Int32ul,
                "payload" / ShortListAdapter(PrefixedArray(
                    "size" / Int8ul,
                    "payload" / Int8ul
                ))
            )
        ))
    )
)
