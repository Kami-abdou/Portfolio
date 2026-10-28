#!/usr/bin/env python3
"""Small cover derivatives for the Selected work index.

    python3 tools/make-index-thumbs.py [--apply]

WHY A THIRD SIZE EXISTS. optimize-images.py already makes two of every
shot: <name>.jpg at 900px for the grid and <name>.full.jpg at 1400 for
the lightbox. The index needs neither. It needs a thumbnail at roughly
280 CSS px, and the five covers at 900px weigh 1.4 MB between them --
Groupado alone is 622 KB. Putting those on the homepage would take it
from 423 KB to nearly two megabytes, on phones, which is the one place
that cost is unaffordable.

WHY THE INDEX NEEDS IMAGES AT ALL. The covers were reachable only
through the cursor preview, which is gated on `(hover: hover) and
(pointer: fine)`. That gate is correct -- a cursor preview with no
cursor is nothing -- but it meant the homepage rendered exactly ONE
image, the portrait, and a phone visitor to a product designer's
portfolio saw no work at all. Reported by an outside reviewer, and
true.

So: a 560px derivative (280 CSS px at 2x) at a lower quality than the
grid uses, because at this size the difference is invisible and the
bytes are not.

Only covers get one. Running this over every image would make 200
files nothing references.

Sources come from assets/_src/, like every other derivative, so this
is idempotent and never recompresses its own output. Requires sips.
"""

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARD_W = 480      # 240 CSS px at 2x
CARD_Q = 48       # the JPEG fallback only; AVIF is what almost everyone gets
CARD_AVIF_Q = 55  # 168 KB for all five covers, against 526 as JPEG
EXTS = (".jpg", ".jpeg", ".png", ".webp")


def dims(path):
    out = subprocess.run(["sips", "-g", "pixelWidth", str(path)],
                         capture_output=True, text=True).stdout.split()
    return int(out[-1]) if out and out[-1].isdigit() else 0


def source_for(assets, cover_name):
    """The _src original a cover was rendered from, by stem."""
    src_dir = assets / "_src"
    if not src_dir.is_dir():
        return None
    stem = pathlib.Path(cover_name).stem
    for p in sorted(src_dir.iterdir()):
        if p.is_file() and p.stem == stem and p.suffix.lower() in EXTS:
            return p
    return None


def main():
    apply_changes = "--apply" in sys.argv
    total_before = total_after = 0
    rows = []

    for content in sorted(ROOT.glob("projects/*/content.json")):
        data = json.loads(content.read_text(encoding="utf-8"))
        # indexImage first: a cover designed FOR the index, rather than a
        # page screenshot cropped to fit it. Four of them are purpose-made
        # banners -- number, name, claim, device shots -- which is a better
        # three-second impression than the top 16:10 of a 4000px-tall
        # homepage capture, which is all the crop could ever see.
        cover = data.get("indexImage") or data.get("cover")
        if not cover:
            continue
        assets = content.parent / "assets"
        live = content.parent / cover
        src = source_for(assets, pathlib.Path(cover).name)
        if src is None:
            rows.append((data.get("slug", "?"), "NO _src ORIGINAL", 0, 0))
            continue

        stem = live.with_suffix("")
        jpg = stem.with_name(stem.name + ".card.jpg")
        avif = stem.with_name(stem.name + ".card.avif")
        before = live.stat().st_size if live.exists() else src.stat().st_size
        total_before += before

        if apply_changes:
            wide = dims(src) > CARD_W
            for dest, fmt, q in ((jpg, "jpeg", CARD_Q), (avif, "avif", CARD_AVIF_Q)):
                cmd = ["sips", "-s", "format", fmt, "-s", "formatOptions", str(q)]
                if wide:
                    cmd += ["--resampleWidth", str(CARD_W)]
                cmd += [str(src), "--out", str(dest)]
                subprocess.run(cmd, capture_output=True)

        # AVIF is what ships; the JPEG exists so <picture> has somewhere to
        # fall back to. Both are committed -- a <source> that 404s renders
        # NOTHING, it does not fall back, which this repo learned once.
        after = avif.stat().st_size if avif.exists() else 0
        total_after += after
        rows.append((data.get("slug", "?"), avif.name, before, after))

    for slug, name, before, after in rows:
        if not after:
            print("  %-11s %s" % (slug, name))
            continue
        print("  %-11s %-34s %6.0f KB -> %5.0f KB" %
              (slug, name[:34], before / 1024, after / 1024))
    if total_after:
        print("\n  %d covers: %.0f KB -> %.0f KB (%.0f%% smaller)"
              % (len(rows), total_before / 1024, total_after / 1024,
                 100 * (1 - total_after / total_before)))
    if not apply_changes:
        print("\n  dry run. pass --apply to write.")


if __name__ == "__main__":
    main()
