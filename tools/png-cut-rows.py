#!/usr/bin/env python3
"""Delete a horizontal band of rows from a PNG and rejoin the halves.

Why this exists
---------------
Full-page screenshots sometimes carry a section that must not be published:
placeholder copy that was never filled in, a colleague's name on an annotation
card, an internal URL. Cropping can only take from the top or the bottom. This
takes a band out of the middle.

No image library is installed on this machine -- no PIL, no ImageMagick, no
Quartz bindings -- and `sips` can crop but cannot composite two pieces back
together. A PNG, though, is just zlib-deflated scanlines, so the operation is
possible with nothing but the standard library.

How it stays lossless and fast
------------------------------
A PNG row filter references at most the row immediately above it. So:

  * every scanline before the cut is copied byte for byte
  * every scanline after the cut is also copied byte for byte
  * only the FIRST row after the cut needs rewriting, because its filter used
    to reference a row that no longer exists

That single row is re-emitted with filter 0 (absolute values), after which
every downstream row's reference is valid again. No pixel is resampled, no
colour is re-quantised, and the two surviving halves are bit-identical to the
original.

Usage
-----
    python3 tools/png-cut-rows.py IN.png OUT.png FIRST LAST
    python3 tools/png-cut-rows.py --top N IN.png OUT.png
    python3 tools/png-cut-rows.py --band START COUNT IN.png OUT.png
    python3 tools/png-cut-rows.py --report IN.png

FIRST and LAST are inclusive, zero-based row numbers to remove. Use
--report to print section boundaries (rows where the left-edge pixel
changes colour) instead of cutting, which is how you find FIRST and LAST.

--top keeps the first N rows and discards the rest. It needs no filter
rewrite at all: row 0 references nothing and every retained row references
only the row above it, which is also retained. It exists because `sips -c`
crops from the CENTRE of an image, and `--cropOffset` is measured from that
centre rather than from the top edge -- so asking sips for "the top band of
a full-page screenshot" quietly returns a band from the middle of the page,
at exactly the dimensions you asked for. Verifying the output size does not
catch it. This does the crop arithmetically instead.
"""

import struct
import sys
import zlib

BYTES_PER_PIXEL = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def read_png(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        sys.exit("%s is not a PNG" % path)
    w, h, depth, ctype, comp, filt, interlace = struct.unpack(">IIBBBBB", raw[16:29])
    if depth != 8:
        sys.exit("only 8-bit channels supported, got %d" % depth)
    if interlace:
        sys.exit("interlaced PNGs not supported")
    if ctype not in BYTES_PER_PIXEL:
        sys.exit("unsupported colour type %d" % ctype)

    head, tail, idat = [], [], []
    i = 8
    while i < len(raw):
        n = struct.unpack(">I", raw[i : i + 4])[0]
        kind = raw[i + 4 : i + 8]
        chunk = raw[i : i + 12 + n]
        if kind == b"IDAT":
            idat.append(raw[i + 8 : i + 8 + n])
        elif kind == b"IEND":
            pass
        elif idat:
            tail.append(chunk)
        else:
            head.append(chunk)
        i += 12 + n
        if kind == b"IEND":
            break
    return w, h, ctype, head, tail, zlib.decompress(b"".join(idat))


def rows_of(data, h, stride):
    """Split the raw stream into (filter_byte, payload) per scanline."""
    return [(data[r * (stride + 1)], data[r * (stride + 1) + 1 : (r + 1) * (stride + 1)])
            for r in range(h)]


def unfilter(rows, upto, stride, bpp):
    """Reconstruct true pixel values for row `upto`, walking from row 0."""
    prev = bytearray(stride)
    for r in range(upto + 1):
        f, payload = rows[r]
        cur = bytearray(payload)
        if f == 1:
            for x in range(bpp, stride):
                cur[x] = (cur[x] + cur[x - bpp]) & 255
        elif f == 2:
            for x in range(stride):
                cur[x] = (cur[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride):
                a = cur[x - bpp] if x >= bpp else 0
                cur[x] = (cur[x] + ((a + prev[x]) >> 1)) & 255
        elif f == 4:
            for x in range(stride):
                a = cur[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                cur[x] = (cur[x] + (a if (pa <= pb and pa <= pc) else (b if pb <= pc else c))) & 255
        elif f != 0:
            sys.exit("unknown filter %d on row %d" % (f, r))
        prev = cur
    return bytes(prev)


def write_png(path, w, h, ctype, head, tail, stream):
    def chunk(kind, payload):
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))

    out = [b"\x89PNG\r\n\x1a\n"]
    # rebuild IHDR with the new height; keep every other header chunk as-is
    ihdr = struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0)
    out.append(chunk(b"IHDR", ihdr))
    for c in head:
        if c[4:8] != b"IHDR":
            out.append(c)
    out.append(chunk(b"IDAT", zlib.compress(stream, 9)))
    out.extend(tail)
    out.append(chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(b"".join(out))


def report(path):
    w, h, ctype, head, tail, data = read_png(path)
    bpp = BYTES_PER_PIXEL[ctype]
    stride = w * bpp
    rows = rows_of(data, h, stride)
    prev = bytearray(stride)
    last = None
    print("row      left-edge colour     (section boundaries)")
    for r in range(h):
        cur = bytearray(unfilter(rows, r, stride, bpp)) if False else None
        # incremental unfilter, one row at a time
        f, payload = rows[r]
        cur = bytearray(payload)
        if f == 1:
            for x in range(bpp, stride):
                cur[x] = (cur[x] + cur[x - bpp]) & 255
        elif f == 2:
            for x in range(stride):
                cur[x] = (cur[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride):
                a = cur[x - bpp] if x >= bpp else 0
                cur[x] = (cur[x] + ((a + prev[x]) >> 1)) & 255
        elif f == 4:
            for x in range(stride):
                a = cur[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                cur[x] = (cur[x] + (a if (pa <= pb and pa <= pc) else (b if pb <= pc else c))) & 255
        px = tuple(cur[0:3])
        if px != last:
            print("%6d   rgb%s" % (r, px))
            last = px
        prev = cur


def crop_band(src, dst, start, count):
    """Keep `count` rows beginning at `start`.

    start == 0 needs no filter fixup at all: row 0 references nothing, and
    every retained row references only the row above it, which is retained.

    start > 0 needs exactly one row rewritten -- the new first row, whose
    filter referenced a row that is now gone. It is re-emitted with filter 0
    (absolute values), after which every downstream reference is valid again.
    Same trick as the band removal above, and the reason both are cheap.
    """
    w, h, ctype, head, tail, data = read_png(src)
    if start < 0 or count < 1 or start + count > h:
        sys.exit("band %d..%d out of range for a %d-row image"
                 % (start, start + count - 1, h))
    bpp = BYTES_PER_PIXEL[ctype]
    stride = w * bpp
    rows = rows_of(data, h, stride)

    stream = bytearray()
    if start == 0:
        f, payload = rows[0]
        stream.append(f)
        stream += payload
    else:
        stream.append(0)
        stream += unfilter(rows, start, stride, bpp)
    for r in range(start + 1, start + count):
        f, payload = rows[r]
        stream.append(f)
        stream += payload

    write_png(dst, w, count, ctype, head, tail, bytes(stream))
    print("%s: %dx%d -> %dx%d (kept rows %d..%d)"
          % (dst, w, h, w, count, start, start + count - 1))


def crop_top(src, dst, keep):
    """Keep the first `keep` rows."""
    crop_band(src, dst, 0, keep)


def main():
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "--report":
        report(args[1])
        return
    if len(args) == 4 and args[0] == "--top":
        crop_top(args[2], args[3], int(args[1]))
        return
    if len(args) == 5 and args[0] == "--band":
        crop_band(args[3], args[4], int(args[1]), int(args[2]))
        return
    if len(args) != 4:
        sys.exit(__doc__)
    src, dst, first, last = args[0], args[1], int(args[2]), int(args[3])

    w, h, ctype, head, tail, data = read_png(src)
    bpp = BYTES_PER_PIXEL[ctype]
    stride = w * bpp
    if not (0 < first <= last < h - 1):
        sys.exit("rows %d..%d out of range for a %d-row image" % (first, last, h))

    rows = rows_of(data, h, stride)
    # the row that lands directly after the cut must become self-contained
    pixels = unfilter(rows, last + 1, stride, bpp)

    stream = bytearray()
    for r in range(first):
        f, payload = rows[r]
        stream.append(f)
        stream += payload
    stream.append(0)              # filter 0: absolute, references nothing
    stream += pixels
    for r in range(last + 2, h):
        f, payload = rows[r]
        stream.append(f)
        stream += payload

    new_h = h - (last - first + 1)
    write_png(dst, w, new_h, ctype, head, tail, bytes(stream))
    print("%s: %dx%d -> %dx%d (removed rows %d..%d, %d rows)"
          % (dst, w, h, w, new_h, first, last, last - first + 1))


if __name__ == "__main__":
    main()
