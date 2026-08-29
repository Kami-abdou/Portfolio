#!/usr/bin/env python3
"""Generate web-sized derivatives of the project imagery.

Every shot on a project page does two jobs: it sits in the grid at roughly
400 CSS px, and it opens in the lightbox at up to 1200 px. Shipping one
file for both means the page downloads lightbox-grade pixels for thumbnails
nobody has clicked yet — that is how the DeepPCB page reached 19 MB.

So each source becomes two files:

    <name>.jpg        THUMB_W wide — referenced by content.json, loads with the page
    <name>.full.jpg   FULL_W  wide — referenced by data-full, loads only on click

Transparency is preserved: a PNG whose alpha is actually used stays a PNG,
because flattening it to JPEG would composite it onto black. The alpha flag
in the file header is not trusted — screenshots routinely carry a fully
opaque alpha channel — so the pixels are inspected instead.

Idempotent: sources live in <project>/assets/_src/, so re-running rebuilds
derivatives from the originals rather than recompressing already-compressed
output. Requires only sips (macOS built-in).
"""

import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent

THUMB_W = 900     # ~404 CSS px in the grid, 2x for retina, plus headroom
FULL_W = 1400     # lightbox caps at 1200 px; a little over for sharpness
QUALITY = 80
MIN_BYTES = 120 * 1024   # leave small files alone; recompressing them can grow them

IMG_RE = re.compile(r"\.(png|jpe?g)$", re.I)


# ── image inspection ────────────────────────────────────────────────

def dims(path):
    """(width, height) via sips, or (0, 0)."""
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
                         capture_output=True, text=True).stdout
    w = h = 0
    for line in out.splitlines():
        if "pixelWidth" in line:
            w = int(line.split(":")[1])
        elif "pixelHeight" in line:
            h = int(line.split(":")[1])
    return w, h


def _decode_png_min_alpha(path):
    """Smallest alpha value in a PNG, or None when it has no alpha channel."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\x0a":
        return None
    pos, idat, ihdr = 8, b"", None
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        if typ == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", data[pos + 8:pos + 8 + ln])
        elif typ == b"IDAT":
            idat += data[pos + 8:pos + 8 + ln]
        elif typ == b"IEND":
            break
        pos += 12 + ln
    if not ihdr:
        return None
    w, h, depth, ctype = ihdr[0], ihdr[1], ihdr[2], ihdr[3]
    if ctype not in (4, 6):          # 4 = gray+alpha, 6 = RGBA
        return None
    channels = 4 if ctype == 6 else 2
    bpp = channels * (depth // 8)
    raw = zlib.decompress(idat)
    stride = w * bpp
    prev = bytearray(stride)
    p = 0
    lo = 255
    a_off = (3 if ctype == 6 else 1) * (depth // 8)
    for _ in range(h):
        f = raw[p]; p += 1
        line = bytearray(raw[p:p + stride]); p += stride
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                c = prev[i - bpp] if i >= bpp else 0
                b = prev[i]
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        for x in range(w):
            v = line[x * bpp + a_off]
            if v < lo:
                lo = v
        prev = line
    return lo


# Below this, alpha is a real cut-out and the file must stay a PNG. Above it,
# the image is a solid rectangle with at most faint translucency (a soft shadow
# or an antialiased corner), which composites to within ~8% on any background —
# every such file here measured 234-252, i.e. no cut-outs at all.
CUTOUT_ALPHA = 200


def uses_transparency(path):
    """True when alpha is load-bearing, not merely present.

    The image is downsampled first: decoding a 1920x6645 RGBA PNG in pure
    Python is far too slow, and averaging preserves the signal — a fully
    opaque image stays at 255, any real transparency drops below it.
    """
    if path.suffix.lower() in (".jpg", ".jpeg"):
        return False
    tmp = path.parent / (path.stem + ".__alpha.png")
    try:
        subprocess.run(["sips", "-s", "format", "png", "--resampleWidth", "48",
                        str(path), "--out", str(tmp)], capture_output=True)
        if not tmp.exists():
            return True                     # unreadable: assume the risky case
        lo = _decode_png_min_alpha(tmp)
        return lo is not None and lo < CUTOUT_ALPHA
    except Exception:
        return True
    finally:
        tmp.unlink(missing_ok=True)


# ── derivative generation ───────────────────────────────────────────

def render(src, dest, width, transparent):
    fmt = "png" if transparent else "jpeg"
    cmd = ["sips", "-s", "format", fmt]
    if not transparent:
        cmd += ["-s", "formatOptions", str(QUALITY)]
    w, _ = dims(src)
    if w > width:
        cmd += ["--resampleWidth", str(width)]
    cmd += [str(src), "--out", str(dest)]
    subprocess.run(cmd, capture_output=True)
    return dest.exists() and dest.stat().st_size > 0


def main():
    apply_changes = "--apply" in sys.argv
    renames = {}
    before = after = 0
    made = kept = 0

    for assets in sorted(ROOT.glob("projects/*/assets")):
        src_dir = assets / "_src"
        src_dir.mkdir(exist_ok=True)

        # originals already stashed on a previous run, plus anything new
        sources = sorted(p for p in src_dir.iterdir() if p.is_file() and IMG_RE.search(p.name))
        fresh = [p for p in assets.iterdir()
                 if p.is_file() and IMG_RE.search(p.name) and not p.name.endswith(".full.jpg")]
        for p in fresh:
            target = src_dir / p.name
            if not target.exists():
                shutil.copy2(p, target)
                sources.append(target)
        sources = sorted(set(sources))

        for src in sources:
            size = src.stat().st_size
            before += size
            stem = src.stem
            transparent = uses_transparency(src)

            if size < MIN_BYTES:
                dest = assets / src.name
                if not dest.exists():
                    shutil.copy2(src, dest)
                after += dest.stat().st_size
                kept += 1
                continue

            ext = ".png" if transparent else ".jpg"
            thumb = assets / (stem + ext)
            full = assets / (stem + ".full" + ext)

            if not render(src, thumb, THUMB_W, transparent):
                print("  FAILED thumb:", src)
                after += size
                continue
            render(src, full, FULL_W, transparent)

            # drop the superseded original if the extension changed
            old = assets / src.name
            if old.exists() and old.resolve() != thumb.resolve():
                old.unlink()
                renames[str(old.relative_to(ROOT))] = str(thumb.relative_to(ROOT))

            after += thumb.stat().st_size + (full.stat().st_size if full.exists() else 0)
            made += 1

    (ROOT / ".image-renames.json").write_text(json.dumps(renames, indent=2))
    print(f"  processed  : {made} resized, {kept} left as-is")
    print(f"  before     : {before / 1024 / 1024:.1f} MB")
    print(f"  after      : {after / 1024 / 1024:.1f} MB  "
          f"({100 * (1 - after / before):.0f}% smaller)" if before else "")
    print(f"  renamed    : {len(renames)} (written to .image-renames.json)")


if __name__ == "__main__":
    main()
