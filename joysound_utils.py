import construct, io
from construct import *
from construct import singleton, stream_read, byte2int

# SJIS works like UTF-8 for CString purposes
construct.core.possiblestringencodings["sjis"] = 1

LZSSBlock = Struct(
    Const(b"SSZL"),
    "unk" / Int32ul,
    "csize" / Int32ul,
    "dsize" / Int32ul,
    "data" / Bytes(lambda ctx: ctx.csize)
)

class LZSSAdapter(Subconstruct):
    def _parse(self, stream, context, path):
        lz = LZSSBlock._parse(stream, context, path)
        dsize = lz.dsize
        data = lz.data
        p = 0
        dictb = [0] * 0x1000
        bp = 0xfee
        dout = []
        while len(dout) < dsize:
            flags = data[p]
            p += 1
            for i in range(8):
                if flags & 1:
                    dout.append(data[p])
                    dictb[bp] = data[p]
                    p += 1
                    bp = (bp + 1) & 0xfff
                else:
                    a, b = data[p:p + 2]
                    p += 2
                    offset = ((b << 4) & 0xf00) | a
                    length = (b & 0xf) + 3
                    for i in range(length):
                        dout.append(dictb[(offset + i) & 0xfff])
                        dictb[bp] = dictb[(offset + i) & 0xfff]
                        bp = (bp + 1) & 0xfff
                flags >>= 1
                if len(dout) >= dsize:
                    break
        return self.subcon._parse(io.BytesIO(bytes(dout[:dsize])), context, path)

    def _build(self, obj, stream, context, path):
        raise NotImplementedError()

    def _sizeof(self, context, path):
        raise SizeofError

def CJString(*args, **kwargs):
    return CString(*args, **kwargs, encoding="sjis")

class SJIS16StringAdapter(Adapter):
    def _encode(self, obj, context, path):
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
    def _decode(self, obj, context, path):
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

class RGB15Adapter(Adapter):
    def _encode(self, obj, context, path):
        return (obj[0] << 10 | obj[1] << 5 | obj[2])
    def _decode(self, obj, context, path):
        return obj >> 10, (obj >> 5) & 0x1f, obj & 0x1f

RGB15b = RGB15Adapter(Int16ub)
RGB15l = RGB15Adapter(Int16ul)

@singleton
class VarIntb(Construct):
    def _parse(self, stream, context, path):
        acc = []
        while True:
            b = byte2int(stream_read(stream, 1))
            acc.append(b & 0b01111111)
            if not b & 0b10000000:
                break
        num = 0
        for b in acc:
            num = (num << 7) | b
        return num
