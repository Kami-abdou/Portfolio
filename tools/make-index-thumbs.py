#!/usr/bin/env python3
"""Cover derivatives for the Selected work index.

    python3 tools/make-index-thumbs.py [--apply]

WHY A THIRD SIZE EXISTS. optimize-images.py already makes two of every
shot: <name>.jpg at 900px for the grid and <name>.full.jpg at 1400 for
the lightbox. The index needs neither. It needs a cover at roughly 330
CSS px on a phone and 700 on a tablet, and the 900px grid files weigh
1.4 MB between them -- Groupado alone is 622 KB. Putting those on the
homepage would take it from 423 KB to nearly two megabytes, on phones,
which is the one place that cost is unaffordable.

WHY THE INDEX NEEDS IMAGES AT ALL. The covers were reachable only
through the cursor preview, which is gated on `(hover: hover) and
(pointer: fine)`. That gate is correct -- a cursor preview with no
cursor is nothing -- but it meant the homepage rendered exactly ONE
image, the portrait, and a phone visitor to a product designer's
portfolio saw no work at all. Reported by an outside reviewer, and
true.

WHY A LADDER AND NOT ONE FILE. One 480px file was shipped first, and
measured on a phone it is soft: the cover renders in a 327 CSS px box,
so a DPR-3 screen wants 981 real pixels and was being handed 480. The
three widths below are 1x, 2x and 3x of the sizes the cover is actually
displayed at, which is a different ladder from the usual 800/1200/2400
because this image is never shown wider than a tablet -- on a device
with a cursor it is display:none and the peek takes over.

    480   phone at DPR 1.5, and the cursor peek's 300px box
    960   phone at DPR 3 (327 x 3 = 981), tablet at DPR 1.4
    1440  tablet at DPR 2 (704 x 2 = 1408)

AVIF rather than the WebP a brief might name: it is already this repo's
format for these files, and on flat colour and type it beats WebP by
enough to matter at these sizes. The JPEG beside each one is what
<picture> falls back to, and both are committed -- a <source> that 404s
renders NOTHING rather than falling back, which this repo learned once.

Only covers get these. Running this over every image would make 200
files nothing references.

Sources come from assets/_src/, like every other derivative, so this is
idempotent and never recompresses its own output. Requires sips.
"""

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: width -> (jpeg quality, avif quality). Bigger files can afford to be
#: compressed harder: the pixels are smaller on screen at every width
#: above the first, so artefacts shrink with them.
WIDTHS = {480: (48, 55), 960: (42, 48), 1440: (38, 44)}
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
    rows = []
    total = 0

    for content in sorted(ROOT.glob("projects/*/content.json")):
        data = json.loads(content.read_text(encoding="utf-8"))
        # indexImage first: a cover designed FOR the index, rather than a
        # page screenshot cropped to fit it. The four published ones are
        # purpose-made banners -- number, name, claim, device shots --
        # which is a better three-second impression than the top 16:10 of
        # a 4000px-tall homepage capture, which is all the crop could see.
        cover = data.get("indexImage") or data.get("cover")
        if not cover:
            continue
        slug = data.get("slug", "?")
        assets = content.parent / "assets"
        src = source_for(assets, pathlib.Path(cover).name)
        if src is None:
            rows.append((slug, "NO _src ORIGINAL", 0))
            continue

        src_w = dims(src)
        stem = (content.parent / cover).with_suffix("")
        made = 0
        for w, (jq, aq) in sorted(WIDTHS.items()):
            # Never upscale. A 1440 rendering of a 900px original is a
            # bigger file carrying no more detail, and the srcset would
            # pick it on a retina phone and pay for nothing.
            if src_w and w > src_w:
                continue
            for ext, fmt, q in (("jpg", "jpeg", jq), ("avif", "avif", aq)):
                dest = stem.with_name("%s.card-%d.%s" % (stem.name, w, ext))
                if apply_changes:
                    subprocess.run(
                        ["sips", "-s", "format", fmt, "-s", "formatOptions",
                         str(q), "--resampleWidth", str(w),
                         str(src), "--out", str(dest)],
                        capture_output=True)
                if dest.exists():
                    made += dest.stat().st_size if ext == "avif" else 0
        total += made
        rows.append((slug, "%s.card-{%s}" % (stem.name,
                     ",".join(str(w) for w in sorted(WIDTHS))), made))

    for slug, name, size in rows:
        if not size:
            print("  %-11s %s" % (slug, name))
            continue
        print("  %-11s %-34s %6.0f KB of AVIF" % (slug, name[:34], size / 1024))
    if total:
        print("\n  %d covers, %d widths each: %.0f KB of AVIF in total"
              % (len(rows), len(WIDTHS), total / 1024))
    if not apply_changes:
        print("\n  dry run. pass --apply to write.")


if __name__ == "__main__":
    main()
