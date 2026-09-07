#!/usr/bin/env python3
"""Generate 1200x630 link-preview cards from tall full-page covers.

Why this exists
---------------
A project's `cover` doubles as its `og:image`. Most of these covers are
full-page screenshots -- 900x4009 in the worst case -- and every platform that
renders a link preview crops to roughly 1.91:1. A 900x4009 image therefore
arrives on LinkedIn as a ~900x471 band lifted out of the middle of a page:
unrecognisable, and often just white space.

That matters more here than it looks. Pasting a case-study link into LinkedIn
is the main way this site gets seen, so the preview is doing more work than
any other single image in the project.

What it does
------------
For each project whose cover is too tall for the slot, it takes the TOP of the
highest-resolution source available and renders a 1200x630 card. The top is
the right region for a page screenshot: it holds the wordmark, the headline
and the hero visual, which is exactly what should appear in a preview.

Sources are preferred in descending resolution -- `_src/<stem>.png`, then
`<stem>.full.jpg`, then the cover itself -- so every card is a downscale.
Nothing is ever upscaled.

Covers already close to the target ratio are left alone; they preview fine.

Why the crop is not done with sips
---------------------------------
`sips -c` crops from the CENTRE of the image, and `--cropOffset` is measured
from that centre rather than from the top edge. Asking sips for "the top
1008 rows of a 5778-row screenshot" therefore returns rows 2385-3393 -- the
middle of the page -- at exactly the dimensions requested. Checking the output
size does not catch it; the first version of this script did check, passed,
and produced six cards showing mid-page filler. A large negative offset
over-runs the top edge and pads with white instead of clamping.

So the crop is arithmetic, via png-cut-rows.crop_top: keep the first N
scanlines and rewrite the height. Exact, and it cannot silently land
somewhere else. sips is used only for the downscale and JPEG encode, which
are whole-image operations with no offset semantics to get wrong.

Sources must therefore be PNG. All current ones are (`_src/*.png`); the
script fails loudly rather than falling back to a centre crop.

Usage
-----
    python3 tools/make-share-cards.py [--dry-run] [--only SLUG ...]

Writes projects/<dir>/assets/share.jpg. build.py picks that up automatically
in preference to the cover.
"""

import importlib.util
import json
import pathlib
import struct
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

# png-cut-rows.py has a hyphen in its name, so it cannot be imported normally.
_spec = importlib.util.spec_from_file_location(
    "png_cut_rows", pathlib.Path(__file__).with_name("png-cut-rows.py"))
cutter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cutter)
OG_W, OG_H = 1200, 630
OG_RATIO = OG_W / OG_H                      # 1.905
# A cover only needs a card if cropping it to 1.91:1 would throw away most of
# the image. Anything at or above this ratio already previews acceptably.
MIN_SAFE_RATIO = 1.2
QUALITY = "82"


def img_size(path):
    """(width, height) for PNG or JPEG. Same approach as build.py's png_size."""
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg = struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + seg
    return None


def sips(*args):
    r = subprocess.run(["sips", *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("sips failed: %s\n%s" % (" ".join(args), r.stderr.strip()))


def best_source(assets, cover_name):
    """Highest-resolution PNG version of this cover, so the card is a downscale.

    PNG only -- the crop is done on raw scanlines, not by sips. See the module
    docstring for why that matters.
    """
    stem = pathlib.Path(cover_name).stem
    p = assets / "_src" / ("%s.png" % stem)
    if p.is_file() and img_size(p):
        return p
    p = assets / cover_name
    if p.is_file() and p.suffix.lower() == ".png" and img_size(p):
        return p
    return None


def make_card(src, dest, offset=0):
    """Crop a 1.91:1 band from `src`, then scale it to exactly 1200x630.

    `offset` is the first source row to keep, and defaults to the very top --
    right for a page screenshot, where the top holds the wordmark and the
    hero. It is wrong for a presentation board, where the top holds the
    board's own title: Fissa3's cover is one of those, and an offset of 0
    produced a card reading "High Fidelity screens", which tells a stranger
    nothing. Projects that need a lower band set `shareOffset` in their
    content.json.
    """
    w, h = img_size(src)
    band = min(round(w / OG_RATIO), h)
    if offset + band > h:
        offset = max(0, h - band)
    with tempfile.TemporaryDirectory() as tmp:
        cut = pathlib.Path(tmp) / "cut.png"
        cutter.crop_band(str(src), str(cut), offset, band)
        got = img_size(cut)
        if got != (w, band):
            sys.exit("crop did not apply: wanted %dx%d, got %s -- %s"
                     % (w, band, got, src))
        sips("-z", str(OG_H), str(OG_W),
             "-s", "format", "jpeg", "-s", "formatOptions", QUALITY,
             str(cut), "--out", str(dest))
    got = img_size(dest)
    if got != (OG_W, OG_H):
        sys.exit("resize did not apply: wanted %dx%d, got %s" % (OG_W, OG_H, got))
    return band


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    only = set()
    if "--only" in args:
        only = set(args[args.index("--only") + 1:])

    for folder in sorted((ROOT / "projects").iterdir()):
        cfg = folder / "content.json"
        if not cfg.is_file():
            continue
        project = json.loads(cfg.read_text(encoding="utf-8"))
        if only and project["slug"] not in only:
            continue
        assets = folder / "assets"
        cover = assets / project["cover"].split("/")[-1]
        if not cover.is_file():
            print("%-16s cover missing: %s" % (project["slug"], cover))
            continue

        cw, ch = img_size(cover)
        ratio = cw / ch
        if ratio >= MIN_SAFE_RATIO:
            print("%-16s %-12s ratio %.2f  ok, no card needed"
                  % (project["slug"], "%dx%d" % (cw, ch), ratio))
            continue

        src = best_source(assets, project["cover"].split("/")[-1])
        if src is None:
            print("%-16s no usable source" % project["slug"])
            continue
        sw, sh = img_size(src)
        dest = assets / "share.jpg"
        if dry:
            print("%-16s %-12s ratio %.2f  -> card from %s (%dx%d)"
                  % (project["slug"], "%dx%d" % (cw, ch), ratio,
                     src.relative_to(assets), sw, sh))
            continue

        offset = int(project.get("shareOffset", 0))
        band = make_card(src, dest, offset)
        print("%-16s card from %s (%dx%d), rows %d..%d -> %dx%d, %d KB"
              % (project["slug"], src.relative_to(assets), sw, sh,
                 offset, offset + band - 1, OG_W, OG_H,
                 dest.stat().st_size // 1024))


if __name__ == "__main__":
    main()
