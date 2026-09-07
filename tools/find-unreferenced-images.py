#!/usr/bin/env python3
"""Report image files under the built site that nothing references.

Read-only. Prints the referenced set, the unreferenced set grouped by folder,
and exact duplicates by content hash. Deleting is a separate, manual step --
see --print-list to feed a deletion.

The referenced set is built the same way a browser and the two image tools
would resolve things:

  * every src / srcset / href in index.html, about.html, projects/*.html,
    resolved relative to the HTML file that holds it
  * per project content.json: "cover", every section images[].src, and the
    contents of any section's autoImages folder (which build.py globs at
    build time instead of listing in JSON)
  * site.json: profileImage, heroImage, shareImage, cv
  * make-share-cards.py's best_source() for each cover: _src/<stem>.png

Some files are load-bearing without any HTML pointing at them, so they are
held by pattern rather than by reference:

  * projects/*/assets/_src/**  and site/_src/**  -- the ONLY copies of the
    originals optimize-images.py regenerates every derivative from
  * projects/*/assets/*.full.jpg  -- lightbox targets, opened by lightbox.js
  * projects/*/assets/share.jpg   -- link-preview cards from make-share-cards.py
  * site/profile.avif             -- <source srcset> emitted by build.py

notes/ is out of scope: working files and preserved originals, not shipped.
"""

import hashlib
import html
import json
import pathlib
import re
import sys
from collections import defaultdict
from urllib.parse import unquote, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".avif", ".webp", ".gif", ".svg"}
ASSET_EXT = IMAGE_EXT | {".pdf"}

# Where we are willing to consider a file for deletion at all.
CANDIDATE_ROOTS = ("projects", "site", "assets")

# Held by pattern, not by reference. Each entry is a rel-path predicate.
PROTECTED = (
    ("_src originals (image pipeline sources)",
     lambda p: "_src" in p.parts),
    ("*.full.jpg lightbox targets",
     lambda p: p.name.endswith(".full.jpg")),
    ("share.jpg link-preview cards",
     lambda p: p.name == "share.jpg" and p.parts[:1] == ("projects",)),
    ("site/profile.avif <source srcset>",
     lambda p: p.as_posix() == "site/profile.avif"),
)


def rel(path):
    return path.resolve().relative_to(ROOT)


def is_local(url):
    """Skip absolute URLs, protocol-relative, data:, mailto:, bare anchors."""
    if not url or url.startswith(("#", "data:", "mailto:", "tel:", "//")):
        return False
    return not urlparse(url).scheme


def resolve(base_dir, url):
    """Resolve one href/src against the directory of the file holding it."""
    url = html.unescape(url.strip())
    if not is_local(url):
        return None
    path = unquote(urlparse(url).path)
    if not path:
        return None
    if path.startswith("/"):
        target = ROOT / path.lstrip("/")
    else:
        target = base_dir / path
    try:
        target = target.resolve()
        target.relative_to(ROOT)          # refuse to escape the site tree
    except ValueError:
        return None
    return target


ATTR_RE = re.compile(
    r"""\b(src|srcset|href|content|data-full)\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE)


def urls_in_html(text):
    """Every URL in a src / srcset / href / content / data-full attribute.

    srcset is comma-separated with trailing size descriptors; content and
    data-full are here as a safety net -- og:image lives in a meta content
    attribute and lightbox.js reads data-full.
    """
    for attr, value in ATTR_RE.findall(text):
        if attr.lower() == "srcset":
            for part in value.split(","):
                candidate = part.strip().split()
                if candidate:
                    yield candidate[0]
        else:
            yield value


def strings_in(obj):
    """Every string in a nested JSON structure, with its key path."""
    stack = [("", obj)]
    while stack:
        path, node = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                stack.append(("%s.%s" % (path, key), value))
        elif isinstance(node, list):
            for i, value in enumerate(node):
                stack.append(("%s[%d]" % (path, i), value))
        elif isinstance(node, str):
            yield path, node


def looks_like_asset(text):
    return pathlib.PurePosixPath(text.split("?")[0]).suffix.lower() in ASSET_EXT


def auto_image_files(project_dir, folder):
    """Mirror build.py's auto_images(): the folder contents ARE the list."""
    base = ROOT / "projects" / project_dir / "assets" / folder
    if not base.is_dir():
        return []
    return [f for f in sorted(base.iterdir())
            if not f.name.startswith(".")
            and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif")]


def collect_referenced():
    """(referenced set, {origin -> [rel paths]}, [unresolved complaints])"""
    referenced = set()
    origins = defaultdict(list)
    problems = []

    def add(target, origin):
        if target is None:
            return
        referenced.add(target)
        origins[origin].append(rel(target).as_posix())

    # --- HTML -------------------------------------------------------------
    html_files = [ROOT / "index.html", ROOT / "about.html"]
    html_files += sorted((ROOT / "projects").glob("*.html"))
    for page in html_files:
        if not page.is_file():
            problems.append("missing page: %s" % rel(page))
            continue
        text = page.read_text(encoding="utf-8", errors="replace")
        for url in urls_in_html(text):
            if not is_local(url) or not looks_like_asset(url):
                continue
            target = resolve(page.parent, url)
            if target is None:
                continue
            if not target.is_file():
                problems.append("BROKEN REF %s -> %s" % (rel(page), url))
                continue
            add(target, "html:%s" % rel(page).as_posix())

    # --- per-project content.json ----------------------------------------
    for content in sorted((ROOT / "projects").glob("*/content.json")):
        project_dir = content.parent.name
        base = content.parent
        data = json.loads(content.read_text(encoding="utf-8"))
        origin = "content.json:%s" % project_dir

        cover = data.get("cover")
        if cover:
            target = resolve(base, cover)
            if target and target.is_file():
                add(target, origin + " cover")
            else:
                problems.append("BROKEN cover %s -> %s" % (project_dir, cover))
            # make-share-cards.py best_source(): _src/<stem>.png, else the cover
            stem = pathlib.PurePosixPath(cover).stem
            src_png = base / "assets" / "_src" / ("%s.png" % stem)
            if src_png.is_file():
                add(src_png.resolve(), origin + " share-card source")

        for si, section in enumerate(data.get("sections", []) or []):
            for image in section.get("images", []) or []:
                src = image.get("src") if isinstance(image, dict) else image
                if not src:
                    continue
                target = resolve(base, src)
                if target and target.is_file():
                    add(target, origin + " images[]")
                else:
                    problems.append("BROKEN images[].src %s sec%d -> %s"
                                    % (project_dir, si, src))
            folder = section.get("autoImages")
            if folder:
                found = auto_image_files(project_dir, folder)
                if not found:
                    problems.append("autoImages folder empty/missing: %s/%s"
                                    % (project_dir, folder))
                for f in found:
                    add(f.resolve(), origin + " autoImages:%s" % folder)

        # Safety net: any asset-looking string anywhere else in the JSON
        # (a body paragraph with an inline image, a link to a PDF, ...).
        for keypath, value in strings_in(data):
            if not looks_like_asset(value) or not is_local(value):
                continue
            target = resolve(base, value)
            if target and target.is_file() and target not in referenced:
                add(target, origin + " other-key%s" % keypath)

    # --- site.json --------------------------------------------------------
    site = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
    for key in ("profileImage", "heroImage", "shareImage", "cv"):
        value = site.get(key)
        if not value:
            continue
        target = resolve(ROOT, value)
        if target and target.is_file():
            add(target, "site.json:%s" % key)
        else:
            problems.append("BROKEN site.json %s -> %s" % (key, value))
    for keypath, value in strings_in(site):
        if not looks_like_asset(value) or not is_local(value):
            continue
        target = resolve(ROOT, value)
        if target and target.is_file() and target not in referenced:
            add(target, "site.json:other-key%s" % keypath)

    return referenced, origins, problems


def candidates():
    """Every image file we would even consider deleting."""
    out = []
    for top in CANDIDATE_ROOTS:
        base = ROOT / top
        if not base.is_dir():
            continue
        for f in base.rglob("*"):
            if not f.is_file() or f.name.startswith("."):
                continue
            if f.suffix.lower() in IMAGE_EXT:
                out.append(f.resolve())
    return sorted(set(out))


def protected_reason(relpath):
    for label, test in PROTECTED:
        if test(relpath):
            return label
    return None


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.0f %s" % (n, unit) if unit == "B" else "%.1f %s" % (n, unit)
        n /= 1024.0


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    print_list = "--print-list" in sys.argv

    referenced, origins, problems = collect_referenced()
    all_files = candidates()

    unreferenced, held = [], defaultdict(list)
    for f in all_files:
        if f in referenced:
            continue
        reason = protected_reason(rel(f))
        if reason:
            held[reason].append(f)
        else:
            unreferenced.append(f)

    if print_list:
        for f in unreferenced:
            print(rel(f).as_posix())
        return 0

    print("=" * 72)
    print("REFERENCE SCAN")
    print("=" * 72)
    print("image files scanned under %s/ : %d"
          % ("/, ".join(CANDIDATE_ROOTS), len(all_files)))
    print("referenced (incl. non-image assets like the CV): %d" % len(referenced))
    print()
    print("reference origins:")
    for origin in sorted(origins):
        print("  %-52s %3d" % (origin, len(origins[origin])))

    print()
    print("held by pattern (NOT referenced by HTML, NOT deletable):")
    for label, _ in PROTECTED:
        files = held.get(label, [])
        size = sum(f.stat().st_size for f in files)
        print("  %-44s %3d files  %9s" % (label, len(files), human(size)))

    if problems:
        print()
        print("!! %d problem(s) found while scanning:" % len(problems))
        for p in problems:
            print("   " + p)

    print()
    print("=" * 72)
    print("UNREFERENCED  --  %d files, %s"
          % (len(unreferenced), human(sum(f.stat().st_size for f in unreferenced))))
    print("=" * 72)
    by_folder = defaultdict(list)
    for f in unreferenced:
        by_folder[rel(f).parent.as_posix()].append(f)
    for folder in sorted(by_folder):
        files = by_folder[folder]
        total = sum(f.stat().st_size for f in files)
        print()
        print("%s/  (%d files, %s)" % (folder, len(files), human(total)))
        for f in sorted(files, key=lambda p: p.name):
            print("    %-46s %9s" % (f.name, human(f.stat().st_size)))

    # --- duplicates -------------------------------------------------------
    print()
    print("=" * 72)
    print("EXACT DUPLICATES (byte-identical, sha256) across ALL image files")
    print("=" * 72)
    by_size = defaultdict(list)
    for f in all_files:
        by_size[f.stat().st_size].append(f)
    groups = defaultdict(list)
    for size, files in by_size.items():
        if len(files) < 2:
            continue                      # unique size => unique content
        for f in files:
            groups[(size, sha256(f))].append(f)

    dup_groups = {k: v for k, v in groups.items() if len(v) > 1}

    def describe(f):
        r = rel(f)
        tags = []
        if f in referenced:
            tags.append("REFERENCED")
        pr = protected_reason(r)
        if pr:
            tags.append("HELD: %s" % pr)
        if not tags:
            tags.append("unreferenced")
        return "    %-58s [%s]" % (r.as_posix(), ", ".join(tags))

    # An original and its derivative being identical is the expected outcome
    # whenever re-encoding wouldn't have saved anything -- optimize-images.py
    # just copies. Those pairs are not duplication to clean up: the _src copy
    # is the only original. So judge a group by its NON-_src members only --
    # drop the originals, and if two shipped files remain identical, that is
    # real duplication. Testing "does any member live in _src" instead would
    # hide a genuine pair inside a three-member group.
    shipped, pipeline_pairs = {}, {}
    for key, files in dup_groups.items():
        live = [f for f in files if "_src" not in rel(f).parts]
        if len(live) > 1:
            shipped[key] = live
        else:
            pipeline_pairs[key] = files

    print()
    print("-- duplicates within the shipped tree (actionable) --")
    if not shipped:
        print("none")
    reclaimable = 0
    for (size, digest), files in sorted(shipped.items(),
                                        key=lambda kv: -kv[0][0] * (len(kv[1]) - 1)):
        reclaimable += size * (len(files) - 1)
        print()
        print("%s x%d  (%s redundant)  %s"
              % (human(size), len(files), human(size * (len(files) - 1)), digest[:12]))
        for f in sorted(files):
            print(describe(f))
    print()
    print("shipped-tree duplicate groups: %d, redundant bytes: %s"
          % (len(shipped), human(reclaimable)))

    print()
    print("-- _src original == its derivative (expected, informational) --")
    print("optimize-images.py copies when re-encoding saves nothing.")
    pipe_bytes = sum(size * (len(files) - 1)
                     for (size, _), files in pipeline_pairs.items())
    print("%d group(s), %s notionally redundant -- NOT deletable, the _src side"
          % (len(pipeline_pairs), human(pipe_bytes)))
    print("is the only original and the derivative is what the pages load.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
