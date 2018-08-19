import binascii
from construct import *

from joysound_utils import *
from joyu2_format import *

XOR_PAD = binascii.unhexlify("""
b2393398 a6164f0e 9030fd17 0b4ee0f2 e381571d c17f4b2c a14f1dac 7f009ab6 \
d7dffe83 97ea45ba a54e8228 6b853fdb 95d8bb6e 4f4d4fe6 ae12e8ff 89079560 \
""".replace(" ", "").strip())

FontSection = Struct(
    "unk1" / Int16ub,
    "unk2" / Int16ub,
    "table_off" / Int32ub,
    "table_size" / Int32ub,
    "chars" / Pointer(this.table_off,
        Array(this.table_size // 4,
            Struct(
                "offset" / Int32ub,
                "char" / Pointer(this.offset,
                    Struct(
                        "unk" / Bytes(8),
                        "code" / Int16ub,
                        "advance" / Int8ub,
                        "size" / Int8ub,
                        "width" / Int8ub,
                        "height" / Int8ub,
                        "stride" / Int16ub,
                        "unk3" / Int8ub,
                        "unk4" / Int8ub,
                        "unk5" / Int8ub,
                        "unk6" / Int8ub,
                        "unk7" / Int8ub,
                        "unk8" / Int8ub,
                        "length" / Int16ul,
                        "data" / Bytes(this.length)
                    )
                )
            )
        )
    )
)

FontFile = Struct(
    "off_font1" / Int32ub,
    "off_font2" / Int32ub,
    "off_font3" / Int32ub,
    "len_font1" / Int32ub,
    "len_font2" / Int32ub,
    "len_font3" / Int32ub,
    "fonts" / Sequence(
        Pointer(this._.off_font1, FixedSized(this._.len_font1, FontSection)),
        Pointer(this._.off_font2, FixedSized(this._.len_font2, FontSection)),
        Pointer(this._.off_font3, FixedSized(this._.len_font3, FontSection)),
    ),
)

AudioFile = Struct(
    Const(b"TPSA"),
    "length" / Int32ub,
    "stream_count" / Int32ub,
    Int32ub,
    "headers" / Array(this.stream_count,
        Struct(
            "unk" / Int32ub,
            "data_size" / Int32ub,
            "stream_id" / Int32ub,
            "length" / Int32ub,
            "sampling_rate" / Int32ub,
            "channel_count" / Int32ub,
            "sampling_rate_2" / Int32ub,
            Int32ub
        )
    ),
    "blocks" / GreedyRange(
        Struct(
            "size" / Int32ul,
            "unk1" / Int32ul,
            "unk2" / Int32ul,
            "stream_id" / Int32ul,
            "data" / Bytes(this.size)
        )
    )
)

UJKFile = Struct(
    Const(b"UJK1"),
    "hdr_size" / Int32ub,
    "file_size" / Int32ub,
    "unk_checksum" / Int32ub,
    "offsets" / Pointer(lambda ctx: ctx.hdr_size,
        FixedSized(len(XOR_PAD), 
            ProcessXor(XOR_PAD,
                Struct(
                    "audio_off" / Int32ub,
                    "audio_size" / Int32ub,
                    "title_off" / Int32ub,
                    "title_size" / Int32ub,
                    "lyrics_off" / Int32ub,
                    "lyrics_size" / Int32ub,
                    "fonts_off" / Int32ub,
                    "fonts_size" / Int32ub
                )
            )
        )
    ),
    "title_card" / Pointer(this.offsets.title_off,
        Bytes(this.offsets.title_size)
    ),
    "lyrics" / Pointer(this.offsets.lyrics_off,
        LZSSAdapter(RawCopy(JoyU2File))
    ),
    "fonts" / Pointer(this.offsets.fonts_off,
        LZSSAdapter(RawCopy(FontFile))
    ),
    "audio" / Pointer(this.offsets.audio_off,
        FixedSized(this.offsets.audio_size, AudioFile)
    ),
)
