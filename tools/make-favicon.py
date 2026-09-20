#!/usr/bin/env python3
"""Regenerate the AY favicon set from the site's own Anton webfont.

    python3 tools/make-favicon.py

Why generated rather than dropped in
------------------------------------
The owner supplied the mark as a single 32x32 PNG: a white disc with a
black AY. That is a perfectly good tab icon and a hopeless source for
anything larger -- upscaled to 180 for the iOS home screen it is visibly
mush, because there are only 32 pixels of information in it.

The mark is "AY" set in Anton, which is already in this repo as
assets/fonts/anton-400.woff2 and is the same face the wordmark uses. So
instead of enlarging the raster, this re-sets the letterforms at 512 and
scales DOWN to every size that is needed, which is the direction that
keeps edges clean.

The size was not guessed. Rendering at a candidate size, downscaling to 32
and comparing ink pixels against the supplied file gave a clear minimum at
344px: 21 differing pixels out of 1024, against 43-53 for the neighbouring
candidates. The remainder is antialiasing landing either side of the
threshold, not a difference in shape.

Two shapes, on purpose
----------------------
The browser icons keep the supplied disc, transparent outside it.

apple-touch-icon does not: iOS composites a touch icon onto BLACK before
applying its own rounded-square mask, so a transparent corner arrives as a
black corner and the disc would sit in a dark box. It is a full-bleed white
square, and iOS rounds it.

Requires headless Chrome, which is already how the project screenshots
pages. Nothing here runs at build time -- the outputs are committed.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FONT = ROOT / "assets" / "fonts" / "anton-400.woff2"

#: Chosen by measuring against the supplied 32x32, not by eye. See above.
FONT_SIZE = 344
CANVAS = 512

PAGE = """<!doctype html><meta charset="utf-8">
<style>
  @font-face {{ font-family:'Anton'; src:url('anton.woff2') format('woff2');
                font-weight:400; font-display:block; }}
  html,body {{ margin:0; background:transparent; }}
  .mark {{ width:{c}px; height:{c}px; {shape} background:#fff;
           display:flex; align-items:center; justify-content:center; }}
  .mark span {{ font-family:'Anton'; font-size:{fs}px; line-height:1;
                color:#000; letter-spacing:-0.01em; }}
</style>
<div class="mark"><span>AY</span></div>
"""


def render(work, shape, out):
    (work / "mark.html").write_text(
        PAGE.format(c=CANVAS, fs=FONT_SIZE, shape=shape), encoding="utf-8")
    subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
         "--default-background-color=00000000",
         "--allow-file-access-from-files",
         "--virtual-time-budget=3000",
         "--window-size=%d,%d" % (CANVAS, CANVAS),
         "--screenshot=%s" % out, str(work / "mark.html")],
        check=True, capture_output=True)


def resize(src, dst, size):
    subprocess.run(["sips", "-Z", str(size), str(src), "--out", str(dst)],
                   check=True, capture_output=True)


def main():
    if not pathlib.Path(CHROME).exists():
        sys.exit("headless Chrome not found at %s" % CHROME)
    if not FONT.is_file():
        sys.exit("missing %s" % FONT)

    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp)
        shutil.copy(FONT, work / "anton.woff2")

        disc = work / "disc-512.png"
        render(work, "border-radius:50%;", disc)
        for size in (32, 192):
            resize(disc, ROOT / "assets" / ("favicon-%d.png" % size), size)

        # Square, opaque: iOS turns a transparent corner black.
        square = work / "square-512.png"
        render(work, "", square)
        resize(square, ROOT / "assets" / "apple-touch-icon.png", 180)

    for name in ("favicon-32.png", "favicon-192.png", "apple-touch-icon.png"):
        p = ROOT / "assets" / name
        print("%-22s %6d bytes" % (name, p.stat().st_size))


if __name__ == "__main__":
    main()
