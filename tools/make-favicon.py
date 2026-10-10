#!/usr/bin/env python3
"""Regenerate the favicon set from the owner's portrait.

    python3 tools/make-favicon.py

What changed and why
--------------------
This used to re-set an "AY" monogram in Anton and scale it down. The owner
asked for their face instead, so the source is now a photograph:
site/_src/favicon-portrait.webp, kept with the other site-level originals
so the derivatives stay regenerable.

A photograph is a worse favicon than a monogram and the reason is just
arithmetic: a 16x16 tab icon has 256 pixels to say something with, and two
black letterforms survive that where a face mostly does not. The crop below
is as far as the geometry can be pushed in the right direction -- head
filling the frame, no shoulders, no background worth looking at -- and at
32px it still reads as a person in a cap with glasses. It will read as a
warm smudge at 16. That is the trade, made knowingly.

Two shapes, on purpose
----------------------
The browser icons (32, 192) are a DISC, transparent outside it. That was
true of the monogram and is kept: the disc is the mark's silhouette in a
tab strip, and a circular crop is the natural way to show a face anyway.

apple-touch-icon does NOT get the disc. iOS composites a touch icon onto
BLACK before applying its own rounded-square mask, so a transparent corner
arrives as a black corner and the disc would sit in a dark box. It is a
full-bleed opaque square, and iOS rounds it itself.

No Chrome
---------
The old version rendered through headless Chrome because it was setting
type. Cropping and scaling a photograph needs neither a browser nor a
font: sips does the resampling and the rest is here. Nothing runs at build
time -- the outputs are committed.
"""
import pathlib
import struct
import subprocess
import sys
import tempfile
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "site" / "_src" / "favicon-portrait.webp"

#: Square crop box on the 1376x1505 original, as (left, top, side).
#: Chosen against the picture, not by centring: the face sits above the
#: middle of the frame and the subject's hand enters from the right, so a
#: centred crop clips the chin and gives away a third of the width to a
#: wall. This box puts the cap at the top edge and the chin near the
#: bottom one.
CROP = (250, 300, 860)

#: (filename, pixels, disc?) -- see "Two shapes, on purpose" above.
OUTPUTS = [
    ("favicon-32.png", 32, True),
    ("favicon-192.png", 192, True),
    ("apple-touch-icon.png", 180, False),
]

#: Samples per axis when deciding how much of an edge pixel the circle
#: covers. 4 means 16 samples a pixel, which is enough that the rim reads
#: as smooth at 32px and costs nothing at these sizes.
SUPERSAMPLE = 4


# ── minimal PNG i/o ───────────────────────────────────────────────────────
# Enough to read what sips writes and write what browsers read. No support
# for interlacing or bit depths other than 8, because sips produces
# neither; both are asserted rather than silently mishandled.

def png_read(path):
    """-> (width, height, channels, colour_type, [row bytes])."""
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        sys.exit("%s is not a PNG" % path)
    pos, idat, ihdr = 8, b"", None
    while pos < len(raw):
        ln = struct.unpack(">I", raw[pos:pos + 4])[0]
        typ = raw[pos + 4:pos + 8]
        if typ == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", raw[pos + 8:pos + 8 + ln])
        elif typ == b"IDAT":
            idat += raw[pos + 8:pos + 8 + ln]
        pos += 12 + ln
    w, h, depth, ctype, _, _, interlace = ihdr
    if depth != 8 or interlace:
        sys.exit("%s: depth=%d interlace=%d, expected 8 and 0"
                 % (path, depth, interlace))
    nch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    data = zlib.decompress(idat)
    stride = w * nch
    rows, prev, i = [], bytearray(stride), 0
    for _ in range(h):
        f = data[i]; i += 1
        line = bytearray(data[i:i + stride]); i += stride
        for x in range(stride):
            a = line[x - nch] if x >= nch else 0
            b = prev[x]
            c = prev[x - nch] if x >= nch else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        rows.append(bytes(line))
        prev = line
    return w, h, nch, ctype, rows


def _filter_row(line, prev, nch):
    """Pick the PNG row filter that compresses best, by the standard heuristic.

    Filter 0 everywhere costs real bytes on a photograph: the 192px icon
    came out at 113KB unfiltered against 14KB for the whole monogram set it
    replaced, and a favicon is on every page. Trying all five and keeping
    the one with the smallest sum of absolute signed deviations is what
    every PNG encoder does, and it is the difference between shipping a
    photograph and shipping a problem.
    """
    cands = []
    for f in range(5):
        out = bytearray(len(line))
        for x in range(len(line)):
            a = line[x - nch] if x >= nch else 0
            b = prev[x]
            c = prev[x - nch] if x >= nch else 0
            v = line[x]
            if f == 1:   v -= a
            elif f == 2: v -= b
            elif f == 3: v -= (a + b) >> 1
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                v -= a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
            out[x] = v & 255
        cost = sum(v if v < 128 else 256 - v for v in out)
        cands.append((cost, f, out))
    cost, f, out = min(cands, key=lambda t: t[0])
    return f, out


def png_write(path, w, h, ctype, rows):
    nch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    body = bytearray()
    prev = bytearray(w * nch)
    for r in rows:
        f, filtered = _filter_row(r, prev, nch)
        body.append(f)
        body += filtered
        prev = bytearray(r)
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(body), 9))
        + chunk(b"IEND", b""))


# ── steps ─────────────────────────────────────────────────────────────────

def to_png(src, dst):
    subprocess.run(["sips", "-s", "format", "png", str(src), "--out", str(dst)],
                   check=True, capture_output=True)


def resize(src, dst, size):
    subprocess.run(["sips", "-Z", str(size), str(src), "--out", str(dst)],
                   check=True, capture_output=True)


def crop(src, dst, box):
    x0, y0, side = box
    w, h, nch, ctype, rows = png_read(src)
    if not (0 <= x0 and x0 + side <= w and 0 <= y0 and y0 + side <= h):
        sys.exit("crop %r falls outside the %dx%d source" % (box, w, h))
    png_write(dst, side, side, ctype,
              [rows[y][x0 * nch:(x0 + side) * nch]
               for y in range(y0, y0 + side)])


def circle_coverage(px, py, size):
    """How much of pixel (px, py) lies inside the inscribed circle: 0..1."""
    r = size / 2
    inside = 0
    for sy in range(SUPERSAMPLE):
        for sx in range(SUPERSAMPLE):
            dx = px + (sx + 0.5) / SUPERSAMPLE - r
            dy = py + (sy + 0.5) / SUPERSAMPLE - r
            if dx * dx + dy * dy <= r * r:
                inside += 1
    return inside / (SUPERSAMPLE * SUPERSAMPLE)


def write_disc(src, dst, size):
    """RGBA, with an antialiased circular cut-out."""
    w, h, nch, _, rows = png_read(src)
    out = []
    for y in range(h):
        row = bytearray()
        for x in range(w):
            o = x * nch
            r, g, b = rows[y][o], rows[y][o + 1], rows[y][o + 2]
            row += bytes((r, g, b, round(255 * circle_coverage(x, y, size))))
        out.append(bytes(row))
    png_write(dst, w, h, 6, out)


def write_square(src, dst):
    """RGB, no alpha: iOS turns a transparent corner black."""
    w, h, nch, _, rows = png_read(src)
    if nch == 3:
        png_write(dst, w, h, 2, rows)
        return
    flat = []
    for y in range(h):
        row = bytearray()
        for x in range(w):
            o = x * nch
            row += bytes(rows[y][o:o + 3])
        flat.append(bytes(row))
    png_write(dst, w, h, 2, flat)


def main():
    if not SOURCE.is_file():
        sys.exit("missing %s" % SOURCE)

    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp)
        full = work / "full.png"
        square = work / "square.png"
        to_png(SOURCE, full)
        crop(full, square, CROP)

        for name, size, disc in OUTPUTS:
            scaled = work / ("scaled-%d.png" % size)
            resize(square, scaled, size)
            dst = ROOT / "assets" / name
            if disc:
                write_disc(scaled, dst, size)
            else:
                write_square(scaled, dst)

    for name, size, disc in OUTPUTS:
        p = ROOT / "assets" / name
        print("%-22s %3dpx  %-6s %6d bytes"
              % (name, size, "disc" if disc else "square", p.stat().st_size))


if __name__ == "__main__":
    main()
