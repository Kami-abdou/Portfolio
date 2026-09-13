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
The ordering is what buys that, not a check: every project resolves to a
source at least 1200px wide today, and only one with nothing but its own
900px cover could fall far enough through the list to be upscaled.

Covers already close to the target ratio are left alone; they preview fine.
A project can override that with `"shareCard": true` in its content.json, for
the case where the ratio looks safe but the image still is not a preview.
InstaDeep is the one: 900x540 passes the ratio test comfortably, but the
cover is a branded board whose bottom strip carries an internal "contact me
on Slack" line, so the top band has to be lifted out deliberately.

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

The cutter must therefore be handed a PNG. Most sources already are
(`_src/*.png`), but some projects only ever had JPEG exports, so a JPEG
source is transcoded to PNG in a temporary directory first -- see as_png().
The invariant is unchanged and now has exactly one enforcement point: nothing
reaches crop_band that is not a PNG. What is emphatically NOT done is
softening the crop to suit JPEG, because that would mean sips and a centre
crop again.

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
    """Highest-resolution version of this cover, so the card is a downscale.

    Strict priority, first match wins. The PNG rules come first because
    `_src/<stem>.png` is the untouched original and nothing beats it. The JPEG
    rules exist for projects that never had a PNG original -- InstaDeep is the
    only one today -- and `<stem>.full.jpg` outranks the cover itself so the
    result stays a downscale rather than an upscale of the small cover.

    Returns the path in whatever format it found it. Callers put it through
    as_png() before the cutter sees it; this function stays free of side
    effects so --dry-run can report the real source without doing any work.
    """
    stem = pathlib.Path(cover_name).stem
    for p in (assets / "_src" / ("%s.png" % stem),
              assets / ("%s.png" % stem),
              assets / ("%s.full.jpg" % stem),
              assets / ("%s.jpg" % stem)):
        if p.is_file() and img_size(p):
            return p
    return None


def as_png(src, tmpdir):
    """`src` as a PNG, transcoding into `tmpdir` first if it is a JPEG.

    crop_band reads raw PNG scanlines, so the source has to be PNG by the time
    it reaches make_card. Converting here rather than in the cutter keeps that
    invariant at a single point and keeps png-cut-rows free of format
    handling.

    The output always lands in a caller-owned temporary directory, never
    beside the source: `_src/` is the only copy of the originals and is never
    written to.
    """
    if src.suffix.lower() == ".png":
        return src
    out = tmpdir / ("%s.png" % src.stem)
    sips("-s", "format", "png", str(src), "--out", str(out))
    if not img_size(out):
        sys.exit("could not transcode to PNG: %s" % src)
    return out


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
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)

        # A source WIDER than 1.91:1 cannot be fixed by cutting rows -- taking
        # rows off a too-wide image only makes it wider. The old code clamped
        # `band` to h and let the final `sips -z` force the size anyway, which
        # does not preserve aspect ratio: it squeezes. That was unreachable
        # while every card came from a tall screenshot, and it stopped being
        # unreachable when InstaDeep's cover became a 1300x650 brand plate
        # (ratio 2.000). Forcing that to 1200x630 compressed it horizontally
        # by 4.75% -- on a centred logo with a registered trademark, which is
        # exactly the kind of thing a designer's portfolio must not ship.
        #
        # So trim the WIDTH first, centred, and only then run the row logic.
        # Centred rather than from the left because an over-wide source is a
        # deliberately composed plate, not a screenshot -- its subject is in
        # the middle, and both edges are margin. sips is safe for this one:
        # a centred crop to an exact size has no offset to get wrong, which
        # is the failure mode that motivated the hand-written row cutter.
        if w / h > OG_RATIO:
            trimmed = round(h * OG_RATIO)
            narrowed = tmp / "narrowed.png"
            sips("-c", str(h), str(trimmed), str(src), "--out", str(narrowed))
            got = img_size(narrowed)
            if got != (trimmed, h):
                sys.exit("width trim did not apply: wanted %dx%d, got %s -- %s"
                         % (trimmed, h, got, src))
            src, w = narrowed, trimmed

        band = min(round(w / OG_RATIO), h)
        if offset + band > h:
            offset = max(0, h - band)
        cut = tmp / "cut.png"
        cutter.crop_band(str(src), str(cut), offset, band)
        got = img_size(cut)
        if got != (w, band):
            sys.exit("crop did not apply: wanted %dx%d, got %s -- %s"
                     % (w, band, got, src))

        # Guard the property the whole function exists to produce. Anything
        # further than a rounding step from 1.91:1 here would be silently
        # stretched by the resize below.
        if abs((w / band) - OG_RATIO) > 0.01:
            sys.exit("band is %.3f:1, not %.3f:1 -- resizing would distort %s"
                     % (w / band, OG_RATIO, src))

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
        # An opt-in, not a switch: `shareCard: true` forces a card for a cover
        # the ratio test would wave through. Lowering MIN_SAFE_RATIO instead
        # would drag in konnect (1.41), pharmadrive (1.78) and fixerloop
        # (2.21), which genuinely preview fine and would just churn binaries.
        opted_in = bool(project.get("shareCard"))
        if ratio >= MIN_SAFE_RATIO and not opted_in:
            print("%-16s %-12s ratio %.2f  ok, no card needed"
                  % (project["slug"], "%dx%d" % (cw, ch), ratio))
            continue

        src = best_source(assets, project["cover"].split("/")[-1])
        if src is None:
            print("%-16s no usable source" % project["slug"])
            continue
        sw, sh = img_size(src)
        dest = assets / "share.jpg"
        why = " (opt-in)" if opted_in else ""
        if dry:
            print("%-16s %-12s ratio %.2f  -> card from %s (%dx%d)%s"
                  % (project["slug"], "%dx%d" % (cw, ch), ratio,
                     src.relative_to(assets), sw, sh, why))
            continue

        offset = int(project.get("shareOffset", 0))
        with tempfile.TemporaryDirectory() as tmp:
            band = make_card(as_png(src, pathlib.Path(tmp)), dest, offset)
        print("%-16s card from %s (%dx%d), rows %d..%d -> %dx%d, %d KB"
              % (project["slug"], src.relative_to(assets), sw, sh,
                 offset, offset + band - 1, OG_W, OG_H,
                 dest.stat().st_size // 1024))


if __name__ == "__main__":
    main()
