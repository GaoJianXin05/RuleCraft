"""
lzx_xnb.py - Minimal LZX decompressor for XNB files (Terraria/XNA format)
Ported from MonoGame's LzxDecoder.cs (MIT license)
https://github.com/MonoGame/MonoGame/blob/develop/MonoGame.Framework/Utilities/LzxDecoder.cs
"""
import struct, io

PRETREE_MAXSYMBOLS = 20
PRETREE_TABLEBITS = 6
MAINTREE_MAXSYMBOLS = 720
MAINTREE_TABLEBITS = 11
LENGTH_MAXSYMBOLS = 249
LENGTH_TABLEBITS = 9
ALIGNED_MAXSYMBOLS = 8
ALIGNED_TABLEBITS = 7
LENTABLE_SAFETY = 64

_extra_bits = [0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,9,9,10,10,11,11,12,12,13,13,14,14,15,15,16,16,17,17,18,18,19,19,20,20,21,21,22,22,23,23,24]
_position_base = []
s = 0
for i in range(51):
    _position_base.append(s)
    s += 1 << _extra_bits[i]

class LzxDecoder:
    def __init__(self, window_bits=16):
        self.window_size = 1 << window_bits
        self.window = bytearray(self.window_size)
        self.window_posn = 0
        self.R0 = self.R1 = self.R2 = 1
        self.main_elements = 256
        self.header_read = False
        self.block_type = 0
        self.block_length = 0
        self.block_remaining = 0
        self.intel_filesize = 0
        self.intel_started = False
        self.maintree_len = [0] * (MAINTREE_MAXSYMBOLS + LENTABLE_SAFETY)
        self.length_len   = [0] * (LENGTH_MAXSYMBOLS   + LENTABLE_SAFETY)
        self.aligned_len  = [0] * (ALIGNED_MAXSYMBOLS  + LENTABLE_SAFETY)

    def decompress(self, in_data: bytes, out_size: int) -> bytes:
        output = bytearray(out_size)
        buf = _BitReader(in_data)
        togo = out_size
        out_pos = 0

        while togo > 0:
            if not self.header_read:
                intel = buf.read_bits(1)
                if intel:
                    hi = buf.read_bits(16)
                    lo = buf.read_bits(16)
                    self.intel_filesize = (hi << 16) | lo
                self.header_read = True

            if self.block_remaining == 0:
                self.block_type = buf.read_bits(3)
                bl = (buf.read_bits(16) << 8) | buf.read_bits(8)
                self.block_length = self.block_remaining = bl

                if self.block_type == 1:  # verbatim
                    self._read_lengths(buf, self.maintree_len, 0, 256)
                    self._read_lengths(buf, self.maintree_len, 256, self.main_elements)
                    self.maintree_table = self._make_table(MAINTREE_MAXSYMBOLS, self.maintree_len, MAINTREE_TABLEBITS)
                    if self.maintree_len[0xE8]: self.intel_started = True
                    self._read_lengths(buf, self.length_len, 0, LENGTH_MAXSYMBOLS - 1)
                    self.length_table = self._make_table(LENGTH_MAXSYMBOLS, self.length_len, LENGTH_TABLEBITS)
                elif self.block_type == 2:  # aligned
                    for i in range(8): self.aligned_len[i] = buf.read_bits(3)
                    self.aligned_table = self._make_table(ALIGNED_MAXSYMBOLS, self.aligned_len, ALIGNED_TABLEBITS)
                    self._read_lengths(buf, self.maintree_len, 0, 256)
                    self._read_lengths(buf, self.maintree_len, 256, self.main_elements)
                    self.maintree_table = self._make_table(MAINTREE_MAXSYMBOLS, self.maintree_len, MAINTREE_TABLEBITS)
                    if self.maintree_len[0xE8]: self.intel_started = True
                    self._read_lengths(buf, self.length_len, 0, LENGTH_MAXSYMBOLS - 1)
                    self.length_table = self._make_table(LENGTH_MAXSYMBOLS, self.length_len, LENGTH_TABLEBITS)
                elif self.block_type == 3:  # uncompressed
                    self.intel_started = True
                    buf.align()
                    self.R0 = buf.read_u32()
                    self.R1 = buf.read_u32()
                    self.R2 = buf.read_u32()
                else:
                    raise ValueError(f"Unknown block type {self.block_type}")

            this_run = min(self.block_remaining, togo)
            togo -= this_run
            self.block_remaining -= this_run

            if self.block_type == 3:  # uncompressed
                raw = buf.read_bytes(this_run)
                output[out_pos:out_pos+this_run] = raw
                # copy to window
                for b in raw:
                    self.window[self.window_posn % self.window_size] = b
                    self.window_posn += 1
                out_pos += this_run
            else:
                for _ in range(this_run):
                    main_element = self._read_huff(self.maintree_table, self.maintree_len, MAINTREE_MAXSYMBOLS, MAINTREE_TABLEBITS, buf)
                    if main_element < 256:
                        output[out_pos] = main_element
                        self.window[self.window_posn % self.window_size] = main_element
                        self.window_posn += 1
                        out_pos += 1
                    else:
                        main_element -= 256
                        match_length = main_element & 7
                        if match_length == 7:
                            match_length = self._read_huff(self.length_table, self.length_len, LENGTH_MAXSYMBOLS, LENGTH_TABLEBITS, buf) + 7
                        match_length += 2
                        offset_slot = main_element >> 3

                        if self.block_type == 2 and offset_slot > 2:
                            extra = _extra_bits[offset_slot]
                            match_offset = _position_base[offset_slot] - 2
                            if extra > 3:
                                match_offset += buf.read_bits(extra - 3) << 3
                                match_offset += self._read_huff(self.aligned_table, self.aligned_len, ALIGNED_MAXSYMBOLS, ALIGNED_TABLEBITS, buf)
                            elif extra == 3:
                                match_offset += self._read_huff(self.aligned_table, self.aligned_len, ALIGNED_MAXSYMBOLS, ALIGNED_TABLEBITS, buf)
                            elif extra > 0:
                                match_offset += buf.read_bits(extra)
                            else:
                                match_offset = 1
                            self.R2 = self.R1; self.R1 = self.R0; self.R0 = match_offset
                        elif offset_slot == 0:
                            match_offset = self.R0
                        elif offset_slot == 1:
                            match_offset = self.R1; self.R1 = self.R0; self.R0 = match_offset
                        elif offset_slot == 2:
                            match_offset = self.R2; self.R2 = self.R0; self.R0 = match_offset
                        else:
                            extra = _extra_bits[offset_slot]
                            match_offset = _position_base[offset_slot] - 2 + buf.read_bits(extra)
                            self.R2 = self.R1; self.R1 = self.R0; self.R0 = match_offset

                        rundest = self.window_posn % self.window_size
                        runsrc = (self.window_posn - match_offset) % self.window_size
                        for _ in range(match_length):
                            b = self.window[runsrc % self.window_size]
                            output[out_pos] = b
                            self.window[rundest % self.window_size] = b
                            runsrc += 1; rundest += 1; self.window_posn += 1; out_pos += 1

        return bytes(output)

    def _read_lengths(self, buf, lens, first, last):
        pre_len = [0] * (PRETREE_MAXSYMBOLS + LENTABLE_SAFETY)
        for i in range(PRETREE_MAXSYMBOLS): pre_len[i] = buf.read_bits(4)
        pre_table = self._make_table(PRETREE_MAXSYMBOLS, pre_len, PRETREE_TABLEBITS)
        x = first
        while x < last:
            z = self._read_huff(pre_table, pre_len, PRETREE_MAXSYMBOLS, PRETREE_TABLEBITS, buf)
            if z == 17:
                y = buf.read_bits(4) + 4
                while y > 0 and x < last: lens[x] = 0; x += 1; y -= 1
            elif z == 18:
                y = buf.read_bits(5) + 20
                while y > 0 and x < last: lens[x] = 0; x += 1; y -= 1
            elif z == 19:
                y = buf.read_bits(1) + 4
                z = self._read_huff(pre_table, pre_len, PRETREE_MAXSYMBOLS, PRETREE_TABLEBITS, buf)
                z = (lens[x] - z + 17) % 17
                while y > 0 and x < last: lens[x] = z; x += 1; y -= 1
            else:
                lens[x] = (lens[x] - z + 17) % 17; x += 1

    def _make_table(self, syms, lengths, bits):
        table_size = 1 << bits
        table = [0] * (table_size + syms * 2)
        bl_count = [0] * 17
        for i in range(syms):
            if lengths[i] <= 16: bl_count[lengths[i]] += 1
        next_code = [0] * 17
        code = 0
        bl_count[0] = 0
        for i in range(1, 17):
            code = (code + bl_count[i-1]) << 1
            next_code[i] = code
        for sym in range(syms):
            llen = lengths[sym]
            if llen == 0: continue
            fill = next_code[llen]
            next_code[llen] += 1
            if llen < bits:
                fill_count = 1 << (bits - llen)
                ofill = fill << (bits - llen)
                for i in range(fill_count): table[ofill + i] = sym
            elif llen == bits:
                if fill < table_size: table[fill] = sym
        return table

    def _read_huff(self, table, lengths, syms, bits, buf):
        buf.ensure_bits(16)
        i = table[buf.peek_bits(bits)]
        if i >= syms:
            j = 1 << (32 - bits)
            while i >= syms:
                j >>= 1
                bit = (buf.peek_bits(32) >> 31) & 1 if buf._count >= 1 else 0
                i = table[(i << 1) | bit]
                buf.remove_bits(1)
        else:
            buf.remove_bits(lengths[i])
        return i


class _BitReader:
    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0
        self._bits = 0
        self._count = 0

    def ensure_bits(self, n):
        while self._count < n:
            if self._pos < len(self._data):
                b = self._data[self._pos]; self._pos += 1
            else:
                b = 0
            self._bits = (self._bits << 8) | b
            self._count += 8

    def read_bits(self, n) -> int:
        self.ensure_bits(n)
        v = (self._bits >> (self._count - n)) & ((1 << n) - 1)
        self._count -= n
        self._bits &= (1 << self._count) - 1
        return v

    def peek_bits(self, n) -> int:
        self.ensure_bits(n)
        return (self._bits >> (self._count - n)) & ((1 << n) - 1)

    def remove_bits(self, n):
        self._count -= n
        if self._count < 0: self._count = 0

    def align(self):
        # discard bits to reach byte boundary (from stream position)
        self._bits = 0; self._count = 0

    def read_u32(self) -> int:
        b = [self._data[self._pos + i] if self._pos + i < len(self._data) else 0 for i in range(4)]
        self._pos += 4
        return b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)

    def read_bytes(self, n) -> bytes:
        self._bits = 0; self._count = 0  # flush bit buffer
        out = self._data[self._pos:self._pos+n]
        self._pos += n
        return out


def decompress_xnb(data: bytes) -> bytes:
    """Decompress an XNB file and return the raw content stream bytes."""
    if data[:3] != b'XNB':
        raise ValueError("Not an XNB file")
    compressed = bool(data[5] & 0x80)
    if not compressed:
        return data[10:]
    decomp_size = struct.unpack_from('<I', data, 10)[0]
    # Content is a series of LZX blocks: each block = uint16 comp, uint16 decomp, LZX data
    pos = 14
    all_compressed = bytearray()
    total_decomp = 0
    # Collect all LZX chunks
    chunks = []
    while pos < len(data) - 4:
        comp_sz = struct.unpack_from('<H', data, pos)[0]; pos += 2
        dcmp_sz = struct.unpack_from('<H', data, pos)[0]; pos += 2
        if comp_sz == 0: break
        chunks.append((data[pos:pos+comp_sz], dcmp_sz))
        pos += comp_sz

    # Decompress all chunks with one LzxDecoder instance (state carries over)
    dec = LzxDecoder(16)
    result = bytearray()
    for chunk_data, dcmp_sz in chunks:
        part = dec.decompress(chunk_data, dcmp_sz)
        result.extend(part)
    return bytes(result)


def parse_texture2d(content: bytes):
    """Parse XNB content stream and extract Texture2D as (width, height, pixels_rgba)."""
    pos = 0
    def read7():
        nonlocal pos
        val = shift = 0
        while True:
            b = content[pos]; pos += 1
            val |= (b & 0x7F) << shift
            if not (b & 0x80): return val
            shift += 7
    def readstr():
        n = read7()
        nonlocal pos
        s = content[pos:pos+n].decode('utf-8', errors='replace'); pos += n
        return s

    type_count = read7()
    for _ in range(type_count):
        readstr(); pos += 4  # skip version

    read7()  # shared resource count
    read7()  # primary asset type index (1-based)

    surface_format = struct.unpack_from('<i', content, pos)[0]; pos += 4
    width  = struct.unpack_from('<i', content, pos)[0]; pos += 4
    height = struct.unpack_from('<i', content, pos)[0]; pos += 4
    mip_count = struct.unpack_from('<i', content, pos)[0]; pos += 4
    data_size  = struct.unpack_from('<i', content, pos)[0]; pos += 4
    pixels = content[pos:pos+data_size]

    # XNA Color (format 0) is stored as BGRA on Windows → convert to RGBA
    if surface_format == 0:
        rgba = bytearray(len(pixels))
        for i in range(0, len(pixels), 4):
            rgba[i]   = pixels[i+2]  # R
            rgba[i+1] = pixels[i+1]  # G
            rgba[i+2] = pixels[i]    # B
            rgba[i+3] = pixels[i+3]  # A
    else:
        rgba = bytearray(pixels)

    return width, height, bytes(rgba)


def write_png(width: int, height: int, rgba: bytes) -> bytes:
    """Write a minimal PNG file from RGBA pixels."""
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', c)

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    scanlines = bytearray()
    for y in range(height):
        scanlines.append(0)  # filter = None
        scanlines.extend(rgba[y*width*4:(y+1)*width*4])
    idat = zlib.compress(bytes(scanlines), 9)

    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', idat)
            + chunk(b'IEND', b''))


def extract_tile_sprite(xnb_path: str, tile_x: int, tile_y: int,
                        tile_w: int = 18, tile_h: int = 18) -> bytes:
    """
    Extract a single tile from a Tiles_N.xnb sprite sheet.
    tile_x, tile_y: grid position (in tiles, 0-based)
    Returns PNG bytes of the extracted sprite.
    """
    with open(xnb_path, 'rb') as f:
        data = f.read()
    content = decompress_xnb(data)
    width, height, rgba = parse_texture2d(content)

    # crop
    px = tile_x * tile_w
    py = tile_y * tile_h
    crop = bytearray(tile_w * tile_h * 4)
    for row in range(tile_h):
        src_row = py + row
        src = ((src_row * width) + px) * 4
        dst = row * tile_w * 4
        crop[dst:dst + tile_w * 4] = rgba[src:src + tile_w * 4]

    return write_png(tile_w, tile_h, bytes(crop))


if __name__ == '__main__':
    import sys, os
    xnb_dir = "C:/Program Files (x86)/Steam/steamapps/common/Terraria/Content/Images"
    out_dir  = "sprites_real"
    os.makedirs(out_dir, exist_ok=True)

    # Test: extract full sprite sheet for tile 0 (Dirt)
    for tid in [0, 1, 53]:
        path = f"{xnb_dir}/Tiles_{tid}.xnb"
        print(f"Processing Tiles_{tid}.xnb ...", end=' ', flush=True)
        with open(path, 'rb') as f:
            raw = f.read()
        try:
            content = decompress_xnb(raw)
            w, h, rgba = parse_texture2d(content)
            png = write_png(w, h, rgba)
            out = f"{out_dir}/sheet_{tid}.png"
            with open(out, 'wb') as f: f.write(png)
            print(f"OK {w}x{h} -> {out}")
        except Exception as e:
            import traceback
            print(f"FAIL: {e}")
            traceback.print_exc()
