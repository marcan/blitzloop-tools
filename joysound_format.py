#!/usr/bin/python2

import json, base64, sys

from construct import Struct, ULInt8, ULInt16, ULInt32, Const, Field, Pointer, CString, Adapter, Array, Range, GreedyRange, PrefixedArray, Magic, RepeatUntil, Anchor, ListContainer

def CJString(name):
    return CString(name, encoding="sjis")

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

def SJISString(name, count):
    return SJIS16StringAdapter(Array(count, ULInt16(name)))

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

def RGB15(name):
    return RGB15Adapter(ULInt16(name))

def ShortByteArray(size, name):
    return ShortListAdapter(Array(size, ULInt8(name)))

JoysoundFile = Struct("Joysound File",
    Magic(b"JOY-02"),
    ULInt32("off_metadata"),
    ULInt32("off_lyrics"),
    ULInt32("off_timing"),
    ULInt32("vol_up_time"),
    Pointer(lambda ctx: ctx.off_metadata,
        Struct("metadata",
            ULInt8("type"),
            ULInt8("subtype"),
            ULInt16("off_title"),
            ULInt16("off_artist"),
            ULInt16("off_writer"),
            ULInt16("off_composer"),
            ULInt16("off_title_kana"),
            ULInt16("off_artist_kana"),
            ULInt16("off_jasrac_code"),
            ULInt16("off_sample"),
            ULInt16("duration"),
            ULInt32("vocal_tracks"),
            ULInt32("rhythm_tracks"),
            Pointer(lambda ctx: ctx._.off_metadata + ctx.off_title, CJString("title")),
            Pointer(lambda ctx: ctx._.off_metadata + ctx.off_artist, CJString("artist")),
            Pointer(lambda ctx: ctx._.off_metadata + ctx.off_writer, CJString("writer")),
            Pointer(lambda ctx: ctx._.off_metadata + ctx.off_composer, CJString("composer")),
            Pointer(lambda ctx: ctx._.off_metadata + ctx.off_title_kana, CJString("title_kana")),
            Pointer(lambda ctx: ctx._.off_metadata + ctx.off_artist_kana, CJString("artist_kana")),
            Pointer(lambda ctx: ctx._.off_metadata + ctx.off_jasrac_code, CJString("jasrac_code")),
            Pointer(lambda ctx: ctx._.off_metadata + ctx.off_sample, CJString("sample")),
        )
    ),
    Pointer(lambda ctx: ctx.off_lyrics,
        Struct("lyrics",
            Array(15, RGB15("colors")),
            PrettyListAdapter(RepeatUntil(lambda obj, ctx: obj.end_off >= ctx._.off_timing,
                Struct("blocks",
                    ULInt16("size"),
                    ULInt16("flags"),
                    ULInt16("xpos"),
                    ULInt16("ypos"),
                    ULInt8("pre_fill"),
                    ULInt8("post_fill"),
                    ULInt8("pre_border"),
                    ULInt8("post_border"),
                    PrefixedArray(
                        Struct("chars",
                            ULInt8("font"),
                            SJISString("char", 1),
                            ULInt16("width")
                        ), length_field=ULInt16("count")
                    ),
                    PrefixedArray(
                        Struct("furi",
                            ULInt16("length"),
                            ULInt16("xpos"),
                            SJISString("char", lambda ctx: ctx.length),
                        ), length_field=ULInt16("furi_count")
                    ),
                    Anchor("end_off")
                )
            ))
        )
    ),
    Pointer(lambda ctx: ctx.off_timing,
        PrettyListAdapter(GreedyRange(
            Struct("timing",
                ULInt32("time"),
                ShortListAdapter(PrefixedArray(
                    ULInt8("payload"), length_field=ULInt8("size")
                ))
            )
        ))
    )
)
