#!/usr/bin/env python3
"""Static site generator for Abdou Yaackoubi's portfolio.

Reads site.json, tokens.json and projects/*/content.json, then writes plain
HTML to disk. There is no runtime data fetching: fetch() is blocked on
file:// in Chrome, so everything is baked in at build time.

Internal links are extensionless -- /work, /about, /contact -- which a host
resolves and a filesystem does not. So each page still RENDERS completely
from file://, but navigating between them now needs a server. That is the
price of the clean URLs and it was paid deliberately.

    python3 build.py

Outputs index.html and work.html (identical; /work is the canonical of the
pair), about.html, contact.html, projects/<slug>.html and assets/tokens.css.

The FILES keep their .html suffix -- that is what GitHub Pages needs on disk
in order to serve /work, /about, /contact and /projects/<slug>. No internal
link, canonical or sitemap entry carries the suffix.
"""

import datetime
import html
import json
import os
import re
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
SITE = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
TOKENS = json.loads((ROOT / "tokens.json").read_text(encoding="utf-8"))

# Fields rendered in the facts table, in order.
FACTS = ["role", "client", "year", "duration", "team", "status"]


# ─────────────────────────────────────────── helpers

def e(text):
    """Escape for HTML text/attribute context."""
    return html.escape(str(text if text is not None else ""), quote=True)


def is_todo(value):
    """BUILD.md: skip any field whose value starts with TODO."""
    return isinstance(value, str) and value.strip().startswith("TODO")


def usable(value):
    return bool(value) and not is_todo(value)


def page_format(project):
    """Which template tier a project page renders at.

    "highlights" pages show cover, summary, images, metrics and links and
    skip the process narrative. The prose stays in content.json -- it is not
    rendered, so promoting a project back to a full case study is a matter of
    deleting one field.

    This replaces `category` as the tier signal. `category` claimed to drive
    homepage grouping, but site.json's slug arrays have always been the real
    source of that, and the two drifted: Fissa3 and Groupado are
    "case-study" yet belong in the Tier-2 band, and Fixerloop was mislabelled
    "project" while carrying the fullest write-up in the set.
    """
    return project.get("format") or "case-study"


def content_updated():
    """When the content last changed, as (iso_date, "Month YYYY").

    Stamped from the newest mtime across the JSON sources rather than from
    the clock, so rebuilding without editing anything does not bump the date
    and produce a diff that claims a change nobody made.

    Caveat: a fresh `git clone` sets every mtime to checkout time, so a build
    run straight after cloning would read "today". The generated HTML is
    committed, so the date visitors see is the one stamped on the machine
    where the edit actually happened.
    """
    sources = [ROOT / "site.json", ROOT / "tokens.json"]
    sources += sorted((ROOT / "projects").glob("*/content.json"))
    newest = max(p.stat().st_mtime for p in sources if p.is_file())
    stamp = datetime.date.fromtimestamp(newest)
    return stamp.isoformat(), stamp.strftime("%B %Y")


def png_size(path):
    """Intrinsic size of a PNG or JPEG, so <img> can reserve space.

    Named for PNG because that was all the export produced, but the
    portrait is a JPEG and every <img> must carry width/height or the
    page reflows as images load.
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(24)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack(">II", head[16:24])
            if head[:2] == b"\xff\xd8":                 # JPEG: walk to a SOF marker
                fh.seek(2)
                while True:
                    byte = fh.read(1)
                    while byte and byte != b"\xff":
                        byte = fh.read(1)
                    if not byte:
                        return None
                    marker = fh.read(1)
                    while marker == b"\xff":
                        marker = fh.read(1)
                    if not marker:
                        return None
                    if marker[0] in (0xC0, 0xC1, 0xC2, 0xC3):
                        fh.read(3)
                        height, width = struct.unpack(">HH", fh.read(4))
                        return width, height
                    length = struct.unpack(">H", fh.read(2))[0]
                    fh.seek(length - 2, 1)
    except (OSError, struct.error):
        pass
    return None


def _png_pixels(path, step=4):
    """Sparse RGBA sample of a PNG. Yields (r, g, b, a) every `step` pixels.

    Only used by icon_needs_plate(). Interlaced PNGs are not handled; the
    icon pipeline writes progressive files via sips, and an unreadable file
    simply yields nothing, which reads as "no plate".
    """
    try:
        b = path.read_bytes()
        if b[:8] != b"\x89PNG\r\n\x1a\n":
            return
        w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", b[16:29])
        if depth != 8 or interlace or ctype not in (0, 2, 4, 6):
            return
        idat = b""
        i = 8
        while i < len(b) - 8:
            ln = struct.unpack(">I", b[i:i + 4])[0]
            if b[i + 4:i + 8] == b"IDAT":
                idat += b[i + 8:i + 8 + ln]
            i += 12 + ln
        raw = zlib.decompress(idat)
        bpp = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
        stride = w * bpp
        prev = bytearray(stride)
        pos = 0
        for y in range(h):
            f = raw[pos]; pos += 1
            line = bytearray(raw[pos:pos + stride]); pos += stride
            for x in range(stride):          # unfilter: every byte, unavoidably
                a = line[x - bpp] if x >= bpp else 0
                bb = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                if f == 1:   line[x] = (line[x] + a) & 255
                elif f == 2: line[x] = (line[x] + bb) & 255
                elif f == 3: line[x] = (line[x] + ((a + bb) >> 1)) & 255
                elif f == 4:
                    pa, pb, pc = abs(bb - c), abs(a - c), abs(a + bb - 2 * c)
                    pr = a if (pa <= pb and pa <= pc) else (bb if pb <= pc else c)
                    line[x] = (line[x] + pr) & 255
            if y % step == 0:
                for x in range(0, w, step):
                    o = x * bpp
                    if ctype in (2, 6):
                        yield line[o], line[o + 1], line[o + 2], (line[o + 3] if ctype == 6 else 255)
                    else:
                        g = line[o]
                        yield g, g, g, (line[o + 1] if ctype == 4 else 255)
            prev = line
    except (OSError, struct.error, zlib.error, KeyError):
        return


def _relative_luminance(r, g, b):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def _hex_luminance(value):
    """Relative luminance of a #rrggbb token."""
    h = value.lstrip("#")
    return _relative_luminance(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


#: Read from the token, not restated here. This was once written out as
#: literal bytes, which meant the page background and the value the plate
#: heuristic measures against could drift apart in silence -- and catching a
#: contrast failure nobody can see is the heuristic's entire purpose. The
#: background has since changed from #0A0A0B to #02050C, which is exactly
#: the edit that would have desynchronised them.
PAGE_LUMINANCE = _hex_luminance(TOKENS["color"]["bg"])


def icon_needs_plate(path, threshold=3.0):
    """True when a mark would disappear against this page's background.

    Decided by measurement, not by hand, because the failure is silent. The
    Framer mark sat on the site at 1.03:1 -- pure black on #02050C, an empty
    chip -- and nobody spotted it until the contrast was actually computed.
    A person swapping an icon will not re-measure; the build will.

    The plate is a light tile behind the mark. It exists because recolouring
    is not available to us: vendor brand terms generally forbid altering the
    mark, so the only thing we may change is what sits behind it.

    Applying it unconditionally is just as wrong in the other direction.
    Measured over the current set against #02050C, four marks need it --
    MCP 1.00:1, Framer 1.03:1, Figma 2.10:1, VWO 2.48:1 -- while Creative
    Cloud (10.33:1), Notion (10.02:1), Miro (9.36:1) and Claude Code
    (6.60:1) are light marks that LOSE most of their contrast ON a white
    plate: Creative Cloud drops to 1.79:1.

    Those figures were re-measured rather than carried across. The previous
    version of this paragraph named MCP as the star example of a light mark,
    at 14.91:1 on the page and 1.20:1 on a plate. mcp.png on disk is now
    100% near-black over all 87 of its opaque pixels and takes a plate, and
    Git was quoted at 12.35:1 where it measures 5.11:1 -- both files were
    swapped at some point and the prose was not. The heuristic had been
    right the whole time; only the commentary rotted, which is the case for
    measuring at build time instead of writing numbers down.

    Averaging luminance over the opaque pixels is deliberately crude. It
    answers "is this mark broadly dark or broadly light", which is the only
    question the plate turns on.
    """
    total = 0.0
    count = 0
    for r, g, b, a in _png_pixels(path):
        if a > 128:
            total += _relative_luminance(r, g, b)
            count += 1
    if not count:
        return False
    ink = total / count
    contrast = (max(ink, PAGE_LUMINANCE) + 0.05) / (min(ink, PAGE_LUMINANCE) + 0.05)
    return contrast < threshold


def tool_chips(tools, depth=0):
    """Render tools as chips, using a real icon when one has been supplied.

    Brand marks are trademarked and are not bundled by default, so an icon
    appears only if assets/tools/<slug>.<ext> exists. Otherwise the chip
    falls back to a monogram set in the site's own type — a hand-redrawn
    logo looks worse than no logo.

    SVG is preferred and tried first, but raster is accepted: vendors ship
    press kits as PNG at least as often, and refusing them meant every
    supplied mark silently fell back to a monogram with no explanation.

    A note on why .tool__icon has a light plate in the CSS. Measured against
    this page's #02050C background, the marks as vendors ship them are:
    MCP 1.00:1, Framer 1.03:1, Figma's app tile 2.10:1, VWO 2.48:1 — the
    first two are literally invisible. The fix is NOT to recolour them; most
    brand terms forbid altering the mark. The plate leaves each mark
    untouched and changes what sits behind it.
    """
    up = "../" * depth
    out = []
    for name in tools:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        icon_rel = None
        for ext in ("svg", "png", "webp"):
            if (ROOT / "assets" / "tools" / ("%s.%s" % (slug, ext))).is_file():
                icon_rel = "assets/tools/%s.%s" % (slug, ext)
                break
        if icon_rel:
            cls = "tool__icon"
            if icon_needs_plate(ROOT / icon_rel):
                cls += " tool__icon--plate"
            mark = ('<img class="%s" src="%s%s%s" alt="" '
                    'width="18" height="18" loading="lazy" decoding="async">'
                    % (cls, up, icon_rel, asset_v(icon_rel)))
        else:
            mark = '<span class="tool__mono" aria-hidden="true">%s</span>' % e(name[0])
        out.append('<li class="tool">%s<span class="tool__name">%s</span></li>'
                   % (mark, e(name)))
    return '<ul class="tools">%s</ul>' % "".join(out)


#: Link labels are owner-authored, so match on a keyword inside the label
#: rather than on the whole string. "GitHub" and "Source on GitHub" are both
#: GitHub; "Live site" is deliberately nothing.
LINK_ICONS = ("linkedin", "github", "email", "cv")


def link_icon(label, depth=0, *, slug=None):
    """An <img> for a known link, or "" for anything else.

    Same contract as the tool chips: the icon appears only if the file has
    been supplied, and the plate is decided by measuring the mark rather
    than by hand. Measured against this page at #02050C, all four read as
    shipped -- cv 13.70:1, email 12.79:1, github 9.05:1, linkedin 8.61:1 --
    so none currently takes a plate. GitHub is the interesting one: its
    black disc does vanish into the page and the white Octocat is what
    survives, which is still the mark, so averaging over opaque pixels gives
    the right answer for the wrong-looking reason. Verified on screen.

    Intrinsic dimensions are read from the file, not assumed square: the CV
    mark is a portrait sheet at 29x36 and hardcoding 36x36 would squash it
    or reserve the wrong box and shift the row as it loads.
    """
    if slug is None:
        low = label.lower()
        slug = next((k for k in LINK_ICONS if k in low), None)
        # "CV" is two letters and would match inside ordinary words, so it
        # only counts as its own token.
        if slug is None and "cv" in low.split():
            slug = "cv"
    if not slug:
        return ""
    rel = None
    for ext in ("svg", "png", "webp"):
        if (ROOT / "assets" / "links" / ("%s.%s" % (slug, ext))).is_file():
            rel = "assets/links/%s.%s" % (slug, ext)
            break
    if not rel:
        return ""
    cls = "btn__icon"
    if icon_needs_plate(ROOT / rel):
        cls += " btn__icon--plate"
    size = png_size(ROOT / rel)
    dims = ' width="%d" height="%d"' % size if size else ""
    return ('<img class="%s" src="%s%s%s" alt=""%s loading="lazy" '
            'decoding="async">'
            % (cls, "../" * depth, rel, asset_v(rel), dims))


def link_btn(label, href, depth=0, *, slug=None, rel_attr=""):
    """A .btn carrying its mark, so the four sites cannot drift apart."""
    return ('<a class="btn" href="%s"%s>%s<span>%s</span></a>'
            % (e(href), rel_attr, link_icon(label, depth, slug=slug), e(label)))


def is_phone(size):
    """True for a narrow portrait screenshot, i.e. a phone screen.

    These must not be cropped: cover-fitting a 375x812 screen into a wide
    short tile shows only its top third. They get a denser grid and are
    contained rather than cropped.
    """
    if not size:
        return False
    w, h = size
    return w <= 520 and (w / h) < 0.7


def masked(text):
    """Wrap text so it can slide up from behind a mask.

    The outer span clips; the inner one is what moves. Used on the oversized
    headings only — at that scale a whole-line reveal reads far better than
    a per-character stagger.
    """
    return '<span class="mask"><span class="mask__in">%s</span></span>' % e(text)


def paragraphs(body):
    """Split a body string into <p> blocks on blank lines."""
    out = []
    for chunk in re.split(r"\n\s*\n", (body or "").strip()):
        chunk = chunk.strip()
        if chunk:
            out.append("<p>%s</p>" % e(chunk).replace("\n", "<br>"))
    return "\n        ".join(out)


def load_projects():
    """Every project that is still published, in display order.

    `"published": false` retires one without deleting anything. The folder,
    the content.json, the assets and the _src originals all stay exactly
    where they are; the project simply stops being built, stops appearing
    in either band, stops being linked by the pager and leaves the sitemap.
    Putting it back is one line.

    That matters because retiring is a judgement call that gets revisited.
    The alternative -- deleting the folder -- makes the decision permanent
    and takes the only copy of the originals with it.
    """
    projects = []
    for folder in sorted((ROOT / "projects").iterdir()):
        cfg = folder / "content.json"
        if cfg.is_file():
            data = json.loads(cfg.read_text(encoding="utf-8"))
            if data.get("published") is False:
                continue
            data["_dir"] = folder.name          # e.g. "01-steer"
            projects.append(data)
    projects.sort(key=lambda p: p.get("order", 999))
    return projects


def by_slug(projects):
    return {p["slug"]: p for p in projects}


# ─────────────────────────────────────────── tokens → css

def flatten_tokens(tokens):
    """tokens.json → CSS custom properties.

    color.bgAlt      -> --color-bg-alt
    fontSize.2xl     -> --font-size-2xl
    layout.proseWidth-> --prose-width      (layout keys are un-prefixed)
    """
    alias = {"layout": ""}
    lines = []
    for group, values in tokens.items():
        if group.startswith("_") or not isinstance(values, dict):
            continue
        prefix = alias.get(group, group)
        prefix = re.sub(r"(?<!^)(?=[A-Z])", "-", prefix).lower()
        for key, value in values.items():
            name = re.sub(r"(?<!^)(?=[A-Z])", "-", str(key)).lower()
            var = "--%s-%s" % (prefix, name) if prefix else "--%s" % name
            lines.append("  %s: %s;" % (var, value))
    return lines


def write_tokens_css():
    """tokens.json is the single source of truth; this file is derived.

    The palette is a single warm-paper set rather than a prefers-color-scheme
    pair, so there is no second colour set to keep in sync. It was near-black
    until this redesign; the flip was a tokens.json edit and nothing else,
    because styles.css holds 180 var(--color-*) references and zero colour
    literals outside comments.
    """
    body = "\n".join(flatten_tokens(TOKENS))
    css = (
        "/* GENERATED by build.py from tokens.json — do not edit by hand. */\n"
        ":root {\n%s\n  color-scheme: light;\n}\n" % body
    )
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "tokens.css").write_text(css, encoding="utf-8")
    return css.count("--")


# ─────────────────────────────────────────── page chrome

def wordmark():
    """The logo as two stacked lines, the second indented.

    Splits on the first space so a middle name would ride with the surname
    rather than creating a third line the layout does not allow for.
    """
    parts = SITE["name"].split(" ", 1)
    first = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    lines = '<span class="wordmark__line">%s</span>' % e(first)
    if rest:
        lines += '<span class="wordmark__line wordmark__line--in">%s</span>' % e(rest)
    return lines


def asset_v(rel):
    """Short content hash for cache-busting.

    Without this a browser keeps serving a stale styles.css or enhance.js
    after a deploy — which cost real debugging time here, since a cached
    script silently ran an older version of the file with no error.

    It was applied to CSS and JS only, and that omission cost the same
    debugging time again — four separate times — on IMAGES. The portraits
    and covers keep a stable filename while their contents change, which is
    the exact shape of the problem: the Fixerloop cover was replaced and the
    old banner kept appearing, the hero portrait was swapped and the old
    photograph kept appearing, and in between a deleted AVIF left a cached
    page requesting a file that now 404s. `<picture>` does not fall back
    when its chosen <source> fails, so that last one rendered nothing at all.

    Now applied to the two site-level portraits as well. Project images are
    not versioned because their filenames change with their content; these
    two do not.
    """
    f = ROOT / rel
    if not f.is_file():
        return ""
    import hashlib
    return "?v=" + hashlib.sha1(f.read_bytes()).hexdigest()[:8]


def abs_url(path, depth=0):
    """Absolute URL for a site-root-relative path, when site.url is set.

    Social scrapers and search engines need absolute URLs; a relative
    og:image silently yields no preview card. Falls back to the relative
    path so the site still works unpublished or opened from file://.
    """
    base = (SITE.get("url") or "").rstrip("/")
    path = path.lstrip("/")
    if not base:
        return ("../" * depth) + path
    return "%s/%s" % (base, path)


def json_ld():
    """Person schema, so search results can show a name and job title."""
    data = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": SITE["name"],
        "jobTitle": SITE["title"],
        "email": "mailto:%s" % SITE["email"],
        # metaDescription, not tagline. tagline is a visible display line on
        # the homepage and is written to be read; this field is written to be
        # indexed. Pointing both at one string meant every rewrite of the
        # visible copy silently rewrote the structured data, and the version
        # search engines were being handed had drifted a full positioning
        # behind the page it described.
        "description": SITE.get("metaDescription") or SITE["tagline"],
        "image": abs_url(SITE.get("profileImage", "")),
    }
    if SITE.get("url"):
        data["url"] = SITE["url"]
    if SITE.get("location"):
        data["address"] = {"@type": "PostalAddress", "addressLocality": SITE["location"]}
    if SITE.get("links"):
        data["sameAs"] = [l["url"] for l in SITE["links"] if l.get("url", "").startswith("http")]
    return ('  <script type="application/ld+json">%s</script>\n'
            % json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def primary_nav(up, current=None):
    """The header nav, with the visitor's location marked.

    Three things were wrong with the previous version, and none of them was
    contrast -- measured at 6.47:1 against the page, comfortably past AA:

    1. Nothing marked the current page. `aria-current` appeared nowhere on
       the site, and on about.html the About link was styled exactly like the
       other two, so a visitor had no way to tell where they were. The only
       is-current rule in the stylesheet was for the project-page TOC.
    2. "Contact" was a `mailto:` sitting between two page links. In a nav
       that is a surprise: it fires a mail client, or on a machine with none
       configured it appears to do nothing. It now goes to the homepage
       contact band, which holds the address as selectable text, the CV and
       every link -- real navigation, with the mailto inside it where a
       visitor expects to find one.
    3. The links had zero padding, so the hit area was the text box: 24px
       tall, the bare WCAG 2.5.8 minimum and well under the 44px platform
       norm for touch. Padding is applied in CSS.

    `current` is "work" on the homepage and "about" on the about page. Project
    pages pass nothing: they sit under Work but they are not it, and marking
    Work as the current page there would be a lie a screen reader announces.

    Work points at the homepage itself, not at #work. It used to jump
    straight to the case-study band, which skipped the hero -- the one
    screen that says who this is -- and meant the nav's first item dropped
    you into the middle of a page you had never seen the top of. The
    wordmark already did the sensible thing, so Work now shares its href
    exactly. Measured: clicked from 3000px down the homepage, that href
    lands at scrollY 0.

    The #work id stays on the band. Nothing in the nav uses it now, but it
    is still a valid thing to link to from outside the site.
    """
    # Work and About sit inside a floating pill; Contact is pulled out of
    # it as a solid button. The reference this layout was briefed against
    # does the same thing, and the reason is that a contact link inside a
    # row of page links reads as another page rather than as the ask. It
    # is still the same href, still real navigation to the contact page,
    # and still marked aria-current when you are on it.
    items = [("work", "%swork" % up, "Work"),
             ("about", "%sabout" % up, "About")]
    out = []
    for key, href, label in items:
        mark = ' aria-current="page"' if key == current else ""
        out.append('<a href="%s"%s>%s</a>' % (e(href), mark, e(label)))
    contact_mark = ' aria-current="page"' if current == "contact" else ""
    return (
        '<nav class="site-nav" aria-label="Primary">\n'
        '        <span class="site-nav__pill">\n'
        '          <span class="site-nav__marker" aria-hidden="true"></span>\n'
        '          %s\n        </span>\n'
        '        <a class="site-nav__cta" href="%scontact"%s>Say hello</a>\n'
        '      </nav>' % ("\n          ".join(out), e(up), contact_mark))


def head(title, description, *, depth=0, image=None, page_url="",
         og_type="website", image_alt=None, nav_current=None):
    up = "../" * depth
    img = image or SITE.get("shareImage") or SITE.get("profileImage")
    og_image = ""
    if img:
        # Declaring the intrinsic size lets a scraper lay out the card before
        # it has finished fetching the image, which is the difference between
        # a preview that appears immediately and one that pops in late.
        size = png_size(ROOT / img)
        dims = ('\n  <meta property="og:image:width" content="%d">'
                '\n  <meta property="og:image:height" content="%d">' % size
                if size else "")
        og_image = (
            '\n  <meta property="og:image" content="%s">'
            '\n  <meta property="og:image:alt" content="%s">%s'
            % (e(abs_url(img, depth)),
               e(image_alt or "%s — %s" % (SITE["name"], SITE["title"])),
               dims)
        )
    canonical = ""
    if SITE.get("url") and page_url:
        canonical = '\n  <link rel="canonical" href="%s">' % e(abs_url(page_url, depth))
    og_url = ('\n  <meta property="og:url" content="%s">' % e(abs_url(page_url, depth))
              if SITE.get("url") and page_url else "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{e(title)}</title>
  <meta name="description" content="{e(description)}">
  <meta name="author" content="{e(SITE['name'])}">{canonical}
  <meta property="og:type" content="{e(og_type)}">
  <meta property="og:site_name" content="{e(SITE['name'])}">
  <meta property="og:title" content="{e(title)}">
  <meta property="og:description" content="{e(description)}">{og_url}{og_image}
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{e(title)}">
  <meta name="twitter:description" content="{e(description)}">
  <meta name="theme-color" content="{e(TOKENS['color']['bg'])}">
  <meta name="color-scheme" content="light">
  <link rel="icon" type="image/png" sizes="32x32" href="{up}assets/favicon-32.png{asset_v('assets/favicon-32.png')}">
  <link rel="icon" type="image/png" sizes="192x192" href="{up}assets/favicon-192.png{asset_v('assets/favicon-192.png')}">
  <link rel="apple-touch-icon" href="{up}assets/apple-touch-icon.png{asset_v('assets/apple-touch-icon.png')}">
  <!-- The two faces, preloaded. `font-display: swap` without this pair is a
       layout shift by construction: first paint uses a fallback whose metrics
       differ from Geist's, then the page reflows when the real face arrives.
       Measured on this site before the preload existed, that cost 0.389 CLS.

       `crossorigin` is required even though these are same-origin. Fonts are
       always fetched in CORS mode, so a preload without it is a SEPARATE
       cache entry from the one @font-face goes on to request -- the file gets
       downloaded twice and the preload buys nothing. -->
  <link rel="preload" href="{up}assets/fonts/geist-variable.woff2{asset_v('assets/fonts/geist-variable.woff2')}" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="{up}assets/fonts/gabarito-variable.woff2{asset_v('assets/fonts/gabarito-variable.woff2')}" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="{up}assets/fonts/anton-400.woff2{asset_v('assets/fonts/anton-400.woff2')}" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="{up}assets/fonts.css{asset_v("assets/fonts.css")}">
  <link rel="stylesheet" href="{up}assets/tokens.css{asset_v("assets/tokens.css")}">
  <link rel="stylesheet" href="{up}assets/styles.css{asset_v("assets/styles.css")}">
{json_ld()}</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="site-head">
    <div class="shell site-head__inner">
      <a class="site-head__name" href="{up}work" aria-label="{e(SITE['name'])} — home">{wordmark()}</a>
      {primary_nav(up, nav_current)}
    </div>
  </header>
  <main id="main" tabindex="-1">"""


def foot(depth=0):
    up = "../" * depth
    links = "\n        ".join(
        '<a href="%s">%s</a>' % (e(l["url"]), e(l["label"])) for l in SITE.get("links", [])
    )
    # The year was hardcoded and would have started lying on 1 January.
    # Both values are derived: the notice from the stamp's year, the stamp
    # from when the JSON last changed. Saying when the site was last touched
    # is the cheapest possible signal that it is still maintained.
    iso, pretty = content_updated()
    return f"""  </main>
  <footer class="site-foot">
    <div class="shell site-foot__inner">
      <p class="site-foot__note">© {iso[:4]} {e(SITE['name'])} · Last updated <time datetime="{iso}">{e(pretty)}</time></p>
      <nav class="site-foot__links" aria-label="Elsewhere">
        {links}
        <a href="{up}{e(SITE['cv'])}{asset_v(SITE['cv'])}">CV</a>
      </nav>
    </div>
  </footer>
  <script src="{up}assets/lightbox.js{asset_v("assets/lightbox.js")}" defer></script>
  <script src="{up}assets/enhance.js{asset_v("assets/enhance.js")}" defer></script>
</body>
</html>
"""


# ─────────────────────────────────────────── fragments

def video_figure(img, project_dir, depth):
    """One <figure> holding a motion clip rather than a still.

    The site had no motion on it anywhere -- no mp4, webm or gif, and no
    <video> in the template -- while the hero claims the thing that holds
    Abdou's attention is "how a thing responds, what it does while it waits,
    and how it recovers". That was the largest gap between what the site
    claimed and what it showed.

    Deliberately NOT autoplaying in the markup:

      - `controls` + no `autoplay` is the honest base state. It works with
        JavaScript off, it works from file://, and it respects a visitor who
        has asked for reduced motion WITHOUT needing a media query, because
        nothing moves until they ask.
      - autoplay is added by enhance.js only when `html.anim` is set, i.e.
        only when the visitor has not asked for calm. That is the same gate
        the scroll reveals use.
      - `muted` regardless. avconvert has no video-only preset, so the
        re-encode still carries its AAC track; a clip that could make noise
        on a portfolio is worse than a slightly larger file, and browsers
        block unmuted autoplay anyway.

    `poster` is mandatory in practice: without it the element is a black box
    until the first frame decodes, and on a near-black page that is
    indistinguishable from a broken embed -- which is exactly how the hero
    portrait went missing for a day.
    """
    base = "%s/%s" % (project_dir, img["video"]) if depth else "projects/%s/%s" % (project_dir, img["video"])
    poster_rel = img.get("poster")
    poster = ""
    if poster_rel:
        p = "%s/%s" % (project_dir, poster_rel) if depth else "projects/%s/%s" % (project_dir, poster_rel)
        poster = ' poster="%s"' % e(p)
        size = png_size(ROOT / "projects" / project_dir / poster_rel)
    else:
        size = None
    dims = ' width="%d" height="%d"' % size if size else ""
    caption = img.get("caption")
    cap_html = "\n          <figcaption>%s</figcaption>" % e(caption) if caption else ""
    # The <a> is the no-video fallback: a browser that cannot play it still
    # gets a route to the file rather than an empty frame.
    return f"""        <figure class="shot shot--video">
          <video class="shot__video" controls muted loop playsinline preload="metadata"{poster}{dims}>
            <source src="{e(base)}" type="video/mp4">
            <a href="{e(base)}">Download the animation (MP4)</a>
          </video>{cap_html}
        </figure>"""


def figure(img, project_dir, depth):
    """One <figure>. depth is how many folders deep the page sits."""
    if img.get("video"):
        return video_figure(img, project_dir, depth)
    src = "%s/%s" % (project_dir, img["src"]) if depth else "projects/%s/%s" % (project_dir, img["src"])
    disk = ROOT / "projects" / project_dir / img["src"]
    size = png_size(disk)
    # The grid shows a ~400px thumbnail; the lightbox opens up to 1200px. Point
    # the lightbox at the .full derivative when optimize-images.py made one, so
    # the page downloads thumbnails and fetches full pixels only on click.
    full_disk = disk.with_name(disk.stem + ".full" + disk.suffix)
    full = src.rsplit("/", 1)[0] + "/" + full_disk.name if full_disk.is_file() else src
    dims = ' width="%d" height="%d"' % size if size else ""
    # Very tall exports (4000px+) get capped in CSS and opened via the lightbox.
    tall = ' data-tall="true"' if size and size[1] > 2200 else ""
    if is_phone(size):
        tall += ' data-phone="true"'
        tall = tall.replace(' data-tall="true"', "")   # phones are capped differently
    caption = img.get("caption")
    cap_html = "\n          <figcaption>%s</figcaption>" % e(caption) if caption else ""
    return f"""        <figure class="shot"{tall}>
          <button class="shot__btn" type="button" data-full="{e(full)}" aria-label="Open full image: {e(img.get('alt',''))}">
            <img src="{e(src)}" alt="{e(img.get('alt',''))}"{dims} loading="lazy" decoding="async">
          </button>{cap_html}
        </figure>"""


def auto_images(project_dir, folder):
    """Build an image list from whatever is sitting in a folder.

    Lets new exports appear by dropping files in and re-running the build,
    with no JSON editing. Filenames drive order and labels:

        01-button.png            -> "Button"
        02-input-field.png       -> "Input field"
        03-toast--how-it-enters.png -> "Toast — how it enters"

    A leading "NN-" orders the list and is stripped from the label; "--"
    becomes an em dash; hyphens become spaces.
    """
    base = ROOT / "projects" / project_dir / "assets" / folder
    if not base.is_dir():
        return []
    out = []
    for f in sorted(base.iterdir()):
        if f.name.startswith(".") or f.suffix.lower() not in (".png", ".jpg", ".jpeg", ".gif"):
            continue
        if ".full." in f.name:
            continue                       # lightbox variant, not a separate view
        stem = re.sub(r"^\d+[-_]", "", f.stem)
        label = stem.replace("--", "\u0000").replace("-", " ").replace("_", " ")
        label = label.replace("\u0000", " \u2014 ").strip()
        label = label[:1].upper() + label[1:]
        out.append({"src": "assets/%s/%s" % (folder, f.name),
                    "alt": "%s — InstaDeep design system" % label,
                    "label": label})
    return out


def viewer(images, project_dir, depth, label="Component browser"):
    """A screen-in-screen browser: one frame, tabs to move between views.

    Progressive enhancement. Without JS every panel renders in sequence, so
    the content is always reachable; enhance.js hides all but one and turns
    the tabs live. Nothing here is hidden by CSS alone.
    """
    if not images:
        return ""
    up = "%s/" % project_dir if depth else "projects/%s/" % project_dir
    panels, tabs = [], []
    for i, img in enumerate(images):
        src = up + img["src"]
        disk = ROOT / "projects" / project_dir / img["src"]
        size = png_size(disk)
        dims = ' width="%d" height="%d"' % size if size else ""
        on = " is-on" if i == 0 else ""
        # detailed boards need zoom, so each panel opens in the lightbox; the
        # .full derivative is used when optimize-images.py has made one
        full_disk = disk.with_name(disk.stem + ".full" + disk.suffix)
        full = src.rsplit("/", 1)[0] + "/" + full_disk.name if full_disk.is_file() else src
        # Never stretch a view past the pixels it actually has. The frame is
        # ~830 CSS px on a laptop, which is 1660 device pixels at 2x — enough
        # to make a 580px crop look like a blurry upscale, because it is one.
        # Capping at natural width keeps every view sharp; narrow ones simply
        # centre instead of filling.
        cap = ' style="max-width:%dpx"' % size[0] if size else ""
        panels.append(
            '<div class="viewer__panel%s" id="vp-%d" role="tabpanel" aria-labelledby="vt-%d">'
            '<button class="shot__btn viewer__zoom" type="button" data-full="%s" '
            'aria-label="Open full size: %s"%s>'
            '<img src="%s" alt="%s"%s loading="lazy" decoding="async"></button>'
            '%s</div>'
            % (on, i, i, e(full), e(img.get("alt", "")), cap, e(src), e(img.get("alt", "")), dims,
               ('<p class="viewer__cap">%s</p>' % e(img["caption"])) if img.get("caption") else ""))
        tabs.append(
            '<button class="viewer__tab%s" id="vt-%d" role="tab" type="button" '
            'aria-controls="vp-%d" aria-selected="%s" data-i="%d">%s</button>'
            % (on, i, i, "true" if i == 0 else "false", i,
               e(img.get("label") or img.get("caption") or "View %d" % (i + 1))))
    return (
        '<div class="viewer" data-viewer>'
        '<div class="viewer__frame"><div class="viewer__bar" aria-hidden="true">'
        '<span></span><span></span><span></span></div>'
        '<div class="viewer__stage">%s</div></div>'
        '<div class="viewer__tabs" role="tablist" aria-label="%s">%s</div>'
        '</div>' % ("".join(panels), e(label), "".join(tabs)))


def section_opens(idx, section, live_sections):
    """Which case-study sections start expanded.

    Everything is collapsible; these are the ones a visitor should not
    have to click for. The first, because a page whose every section is
    shut reads as empty rather than as tidy and gives nothing to begin
    reading. And the outcome, because it is the payoff -- a case study
    that hides what came of the work behind a disclosure control has
    buried the one part a recruiter came for.

    A page with a single live section is always open: there is no length
    problem to solve and a lone collapsed heading is just an obstacle.
    """
    if len(live_sections) <= 1:
        return True
    if idx == 1:
        return True
    return section.get("id") == "outcome"


def screen_count(images):
    """"6 screens" on a collapsed section's summary.

    A closed section is a promise about its own contents, and a heading
    alone does not say whether there is a paragraph or twenty-one
    screenshots behind it. This is the smallest honest hint.
    """
    n = len(images or [])
    if not n:
        return ""
    return ('<span class="section__count">%d screen%s</span>'
            % (n, "" if n == 1 else "s"))


TINTS = ("sand", "teal", "sky")


def project_tint(project):
    """The project's container tint, as a `data-tint` value.

    Every screenshot in this portfolio is cooler than the paper the site is
    printed on -- measured at the image borders, the warmest cover is pure
    white (R-B 0) and the coolest is Fixerloop's blue at -143, against
    paper's +12. Not one is warm. So an image dropped straight onto the
    page always announces itself as a foreign rectangle.

    The fix is a tinted field behind the image, close enough to paper to
    merge with it and close enough to the image to meet it halfway: the eye
    reads paper -> tint -> image instead of paper -> image. The tint is
    chosen per project from the SAME three tokens the hero cards already
    use, so this is one colour system rather than two.

    Unknown or missing tints fall back to the neutral warm paper-alt rather
    than raising, because a wrong tint is a cosmetic bug and a broken build
    is not.
    """
    tint = project.get("tint")
    return tint if tint in TINTS else ""


def project_year(project):
    """The year segment of `meta`, or "" when there is none.

    Taken from `meta` rather than `year` because `year` is prose -- "January
    2024 — present", "February 2021 — September 2021" -- and one of the eight
    is still TODO. `meta` carries a short form already written for display.

    Deliberately the segment CONTAINING a year rather than the first one.
    "First segment" looked right on seven projects and quietly printed
    "Design and brand studio" on the eighth, because Smarthub's meta is
    "Design and brand studio · Founder" and has no date in it at all. A
    project with no year renders no year, which is the rule the rest of the
    build follows for a fact that does not exist yet.
    """
    meta = project.get("meta")
    if not usable(meta):
        return ""
    for segment in (s.strip() for s in meta.split("\u00b7")):
        if re.search(r"\b(19|20)\d{2}", segment):
            return segment
    return ""


def work_entry(project, *, large):
    """One row of the year rail.

    The rail is a dated spine: a dot and a year on the left, the project on
    the right, oldest at the bottom. It replaced a horizontal scroller for
    the case studies and a stack of covers for the gallery, so both bands
    now read as one system and the tiers differ by how much each row says
    rather than by being different components.

    Tier 1 carries category chips, a summary and a full-width cover.
    Tier 2 carries a line and a thumbnail. That difference is asserted.

    The link wraps the TITLE and an ::after covers the row, which is the
    block-link pattern this site has used since the cards: one control per
    row, named by the project, with the prose read as its siblings rather
    than crammed into its accessible name.
    """
    d = project["_dir"]
    cover = "projects/%s/%s" % (d, project["cover"])
    size = png_size(ROOT / "projects" / d / project["cover"])
    dims = ' width="%d" height="%d"' % size if size else ""

    year = project_year(project)
    year_html = ('<span class="entry__year">%s</span>' % e(year)) if year else ""

    tagline = project["tagline"] if usable(project.get("tagline")) else ""
    lede = ('<p class="entry__lede">%s</p>' % e(tagline)) if tagline else ""

    tags_html = note_html = ""
    if large:
        tags = [x for x in (project.get("tags") or []) if usable(x)][:3]
        if tags:
            tags_html = ('<ul class="entry__tags">%s</ul>'
                         % "".join("<li>%s</li>" % e(x) for x in tags))
        if usable(project.get("summary")):
            note_html = '<p class="entry__note">%s</p>' % e(project["summary"])

    cta = "Read the case study" if large else "See the screens"

    return """        <li class="entry entry--{tier}">
          <p class="entry__when">
            <span class="entry__dot" aria-hidden="true"></span>{year}
          </p>
          <div class="entry__body">
            <div class="entry__text">
              {tags}
              <h3 class="entry__title"><a href="projects/{slug}">{title}</a></h3>
              {lede}
              {note}
              <span class="entry__cta" aria-hidden="true">{cta} &rarr;</span>
            </div>
            <figure class="entry__media"{tint}>
              <img src="{cover}" alt="" {dims} loading="lazy" decoding="async">
            </figure>
          </div>
        </li>""".format(
        tier="lg" if large else "sm",
        year=year_html, tags=tags_html, lede=lede, note=note_html, cta=e(cta),
        slug=e(project["slug"]), title=e(project["title"]),
        tint=(' data-tint="%s"' % project_tint(project)) if project_tint(project) else "",
        cover=e(cover), dims=dims)


# ─────────────────────────────────────────── pages

def build_index(projects):
    slugs = by_slug(projects)
    out = [head(
        "%s — %s" % (SITE["name"], SITE["title"]),
        # heroStatement is the visible claim on the page and is written to be
        # short. metaDescription is the search snippet. One string cannot be
        # both: 150 keyword-bearing chars reads as a resume line on screen.
        SITE.get("metaDescription") or SITE.get("heroStatement")
            or (SITE["tagline"] + " " + SITE["intro"]),
        page_url="work",
        nav_current="work",
    )]

    # Cycling role line. Every role is in the DOM so it survives with JS off
    # and is indexable; JS reveals one at a time. The live list is aria-hidden
    # and a static label carries the accessible name, so assistive tech reads
    # the role once instead of announcing every swap.
    roles = [r for r in SITE.get("roles", []) if r] or [SITE["title"]]
    hero_img = SITE.get("heroImage") or SITE["profileImage"]
    psize = png_size(ROOT / hero_img)
    pdims = ' width="%d" height="%d"' % psize if psize else ""
    # No AVIF source here, deliberately. DO NOT ADD ONE WITH sips.
    #
    # The portrait is the homepage's LCP element, so an AVIF alternative is
    # the obvious win and it was tried. `sips -s format avif` produces a file
    # that passes every cheap check -- correct `ftyp avif` magic, correct
    # dimensions reported back by sips, `file` calls it "ISO Media, AVIF
    # Image", 60% smaller than the JPEG -- and which Chrome decodes to PURE
    # BLACK. Measured by drawing it to a canvas: max luminance 0 across the
    # frame, against 238 for the JPEG. The hero portrait silently vanished
    # and the only symptom was a dark rectangle behind dark type.
    #
    # site/profile.avif on the about page is fine, which is what made this
    # confusing: it was encoded by something else, not by sips.
    #
    # There is no avifenc, ImageMagick, cavif or vips on this machine and the
    # project takes no new dependencies, so there is no way to produce a
    # trustworthy AVIF here. The JPEG is instead sized to what the frame
    # actually needs -- clamp(190px, 26vw, 340px), so 700px covers 2x -- which
    # took it from 419 KB to 265 KB with no format risk.
    #
    # If you do add an AVIF later: verify the PIXELS, not the bytes. Load it
    # in a browser and sample it. Every metadata check passed on the broken one.
    hero_avif = ""
    # The marquee is gone. It was three rows of ultra-condensed poster type
    # scrolling behind the portrait, and it was the site's signature for two
    # years -- but it belonged to a near-black page, and this one is warm
    # paper built out of soft cards. Anton went with it; see assets/fonts.css.
    #
    # What replaces it is the fanned card stack below: three cards at slight
    # opposing rotations, which is a friendlier way to say "here are the
    # three kinds of thing I do" than a wall of moving type.

    # ── The opening ───────────────────────────────────────────────────
    # The clarity block, and the page's h1.
    #
    # This section is why the redesign exists. The marquee below it used to
    # BE the hero: the only h1 was `visually-hidden`, the rows are
    # aria-hidden by construction, and the first readable sentence on the
    # site sat 760px down the page. A visitor's first screen was a condensed
    # poster face clipped mid-word and a photograph -- striking, and silent
    # about what the man does.
    #
    # Measured against the four sites this redesign was briefed on: all four
    # put a specific, readable claim in the first screen, and the two
    # homepages (petradesigns.io, sandeep.design) both spend their h1 on the
    # value proposition rather than on a name. The wordmark in the header
    # already carries the name, and so do <title> and the JSON-LD.
    #
    # The marquee is NOT deleted -- it is the site's signature and the one
    # thing its owner said still felt like his. It moves one section down,
    # where being arresting costs nothing.
    facts = [f for f in SITE.get("heroFacts", [])
             if usable(f.get("label")) and usable(f.get("value"))]
    facts_html = "\n        ".join(
        '<div class="opening__fact"><dt>%s</dt><dd>%s</dd></div>'
        % (e(f["label"]), e(f["value"])) for f in facts)
    avail = SITE.get("availability", "")
    avail_note = SITE.get("availabilityNote", "")
    portfolio_label = SITE.get("portfolioLabel", "")
    email = SITE.get("email", "")

    # Every one of these is gated, same as the rest of the build: a field
    # that is missing or still TODO renders nothing rather than an empty
    # chip, a dangling separator or a mailto: with no address.
    status_bits = []
    if usable(avail):
        status_bits.append(
            '<span class="opening__avail">'
            '<span class="opening__dot" aria-hidden="true"></span>%s</span>' % e(avail))
    if usable(portfolio_label):
        status_bits.append('<span class="opening__portfolio">%s</span>' % e(portfolio_label))
    status_html = ('<p class="opening__status">%s</p>'
                   % '<span class="opening__sep" aria-hidden="true"></span>'.join(status_bits)
                   ) if status_bits else ""

    actions = ['<a class="btn btn--solid" href="#work">See the work</a>']
    if usable(email):
        actions.append('<a class="btn" href="mailto:%s">Email me</a>' % e(email))
    if usable(avail_note):
        actions.append('<span class="opening__note">%s</span>' % e(avail_note))

    cards = [c for c in SITE.get("heroCards", [])
             if usable(c.get("label")) and usable(c.get("body"))]
    fan_cards = "\n".join(
        '''        <li class="fan__card fan__card--%s">
          <h2 class="fan__label">%s</h2>
          <p class="fan__body">%s</p>
          <a class="fan__cta" href="%s">%s<span aria-hidden="true"> &rarr;</span></a>
        </li>''' % (e(c.get("tone", "sand")), e(c["label"]), e(c["body"]),
                     e(c.get("href", "#work")), e(c.get("cta", "Have a look")))
        for c in cards)

    # A newline in heroClaim is an author's line break, rendered as <br>.
    # The alternative is letting the measure wrap it, which moves the break
    # every time the viewport changes -- and the break is the joke here:
    # the greeting on one line, the job on the next.
    claim = SITE.get("heroClaim") or SITE["title"]
    claim_html = "<br>".join(e(line) for line in claim.split("\n"))

    out.append(f"""
    <section class="opening shell">
      {status_html}

      <h1 class="opening__claim">{claim_html}</h1>

      <p class="opening__support">{e(SITE.get('heroSupport') or SITE.get('heroStatement', ''))}</p>

      <div class="opening__actions">
        {"".join(actions)}
      </div>

      <dl class="opening__facts">
        {facts_html}
      </dl>
    </section>

    <!-- The fanned stack. Three cards at opposing rotations, which is the
         whole device: a hand of cards rather than a row of tiles. Each one
         is a real link to a section further down, so the stack is also the
         page's own table of contents.

         No pause control here and none needed: nothing moves on its own.
         The rotation is static and the only motion is on hover, which is
         WCAG 2.2.2 not applying rather than being satisfied. -->
    <section class="fan shell" aria-label="What's here">
      <ul class="fan__stack">
{fan_cards}
      </ul>
    </section>
""")

    # Two tiers: 3 across for the headline band, 4 for the rest.
    #
    # The column counts MUST differ, because they are what makes the headline
    # cards bigger. Both bands ran at 3 briefly, to avoid the orphan that 6
    # cards at 4-up leaves on the second row -- and that inverted the whole
    # hierarchy. grid--lg carries a 48px gap against grid--sm's 32px, so at
    # equal column counts the "large" cards came out NARROWER (352px vs 363px)
    # and shorter (a 3/2 media against 4/3 is 235px tall against 272px). Only
    # the title was bigger. Tier 2 visually outweighed Tier 1, which is the
    # exact opposite of the point.
    #
    # A short last row is a much smaller cost than an inverted hierarchy.
    # ── A bit about me ─────────────────────────────────────────────
    # Statement, portrait, a paragraph and a door to the about page. It
    # replaced a "How I work" band of three craft principles, whose
    # content moved to the about page where it sits next to the journey
    # and the values instead of competing with the work for the
    # homepage's attention.
    #
    # The statement is the sentence that used to be the h1. It was always
    # the best line on the site, and the hero opens with a greeting now,
    # so it was free.
    ab = SITE.get("aboutBlock") or {}
    if usable(ab.get("statement")):
        cta = ab.get("cta")
        cta_html = ('<a class="aboutblock__cta" href="about">%s'
                    '<span aria-hidden="true"> &rarr;</span></a>'
                    % e(cta)) if usable(cta) else ""
        body_html = ('<p class="aboutblock__body">%s</p>' % e(ab["body"])
                     if usable(ab.get("body")) else "")
        out.append(f"""
    <section class="band shell band--aboutblock" id="about-me">
      <div class="aboutblock__card">
      <p class="aboutblock__label">{e(ab.get("label", "A bit about me"))}</p>
      <div class="aboutblock__grid">
        <figure class="aboutblock__portrait">
          <img src="{e(hero_img)}{asset_v(hero_img)}" alt="Portrait of {e(SITE['name'])}"{pdims} loading="lazy" decoding="async">
        </figure>
        <div class="aboutblock__text">
          <h2 class="aboutblock__statement">{masked(ab["statement"])}</h2>
          {body_html}
          {cta_html}
        </div>
      </div>
      </div><!-- /.aboutblock__card -->
    </section>
""")

    # ── The work, as one dated rail ────────────────────────────────
    # Both bands render the same component now. They used to be two
    # different ones -- a horizontal scroller for the case studies and a
    # stack of covers for the gallery -- which meant the page had two
    # unrelated ways of showing a project and the only thing connecting
    # them was that they sat under similar headings.
    #
    # The tiers still differ, and by more than size: a case study row
    # carries category chips, a summary paragraph and a full-width cover;
    # a gallery row carries one line and a thumbnail. That difference is
    # the hierarchy, and it is asserted.
    for key, large in (("highlights", True), ("selectedWork", False)):
        meta = SITE["sections"][key]
        anchor = "work" if key == "highlights" else "gallery"
        live = [s for s in meta["slugs"] if s in slugs]
        rows = "\n".join(work_entry(slugs[s], large=large) for s in live)
        out.append(f"""
    <section class="band shell band--work" id="{anchor}">
      <div class="band__head">
        <h2>{masked(meta['heading'])}</h2>
        <p>{e(meta['description'])}</p>
      </div>
      <ol class="rail-years rail-years--{'lg' if large else 'sm'}">
{rows}
      </ol>
    </section>
""")

    out.append(contact_band())
    out.append(foot())

    # The homepage is served at two URLs on purpose. /work is what the nav
    # points at and what the canonical names, because "work" says what the
    # page is; / has to keep working because it is what people type and what
    # gets shared. Writing the same bytes to both avoids a redirect hop on
    # the most-shared URL in the site, and the shared canonical tells a
    # crawler which of the two is the real one, so there is no split.
    page = "\n".join(out)
    (ROOT / "index.html").write_text(page, encoding="utf-8")
    (ROOT / "work.html").write_text(page, encoding="utf-8")


def contact_band(*, depth=0, level="h2"):
    """The "Let's talk" block, shared by the homepage and /contact.

    It was inline in build_index until /contact became a real page. Copying
    it would have meant the email, the CV link and the link list each had two
    places to fall out of date, on the one block where being wrong costs an
    actual opportunity.

    `level` exists because one block cannot be the same rank in both places.
    On the homepage it is a section under the page's h1, so it is an h2. On
    /contact it is the only heading on the page, and hardcoding h2 left that
    page with NO h1 and a hierarchy that started at level two -- measured on
    the built file, which had exactly one heading element on it.
    """
    up = "../" * depth
    links = "\n        ".join(
        link_btn(l["label"], l["url"], depth) for l in SITE["links"]
    )
    # The CV was footer-only on the homepage, so the highest-intent element on
    # the site -- "Let's talk" -- offered no way to get the document a
    # recruiter actually needs. It is the last thing they look for and it was
    # the one thing not here.
    # Versioned like every other asset. The CV is the one file on the site
    # that gets REPLACED under the same name rather than added, so without a
    # content hash a returning visitor -- or a recruiter who opened the page
    # last week -- keeps downloading the previous document. This project has
    # lost time to exactly that failure four times on other assets.
    cv_btn = ('\n        ' + link_btn("CV (PDF)", up + SITE["cv"] + asset_v(SITE["cv"]),
                                      depth, slug="cv")
              if SITE.get("cv") else "")
    # And the address itself never appeared as selectable text anywhere on the
    # site -- only ever inside href="mailto:". A recruiter who wants to paste
    # it into their own system had to open a mail client to read it.
    addr = SITE.get("email")
    addr_line = ('\n      <p class="contact__addr"><a href="mailto:%s">%s</a></p>'
                 % (e(addr), e(addr))) if addr else ""
    return f"""
    <section class="band band--contact shell" id="contact">
      <{level}>{masked("Let's talk")}</{level}>
      <p class="lede">{e(SITE.get("contactLede", ""))}</p>{addr_line}
      <div class="btn-row">
        {links}{cv_btn}
      </div>
    </section>
"""


def build_contact():
    """/contact, carrying the same band the homepage ends on.

    Contact used to be index.html#contact in the nav -- a fragment jump that
    dropped a visitor at the foot of a long page. It is now a page, which is
    what the other two nav items are, and the homepage keeps its band so
    anyone who scrolls to the end still finds a way to get in touch.
    """
    out = [head(
        "Contact — %s" % SITE["name"],
        SITE.get("contactLede") or SITE.get("metaDescription", ""),
        page_url="contact",
        nav_current="contact",
    )]
    out.append(contact_band(level="h1"))
    out.append(foot())
    (ROOT / "contact.html").write_text("\n".join(out), encoding="utf-8")


def cv_block(index):
    """Reverse-chronological employment history, linked into the case studies.

    Why this exists: every fact in it was already in the JSON — `client`,
    `year` and `role` on each project — but no page assembled it, so a
    visitor could not see eight companies in six years without opening nine
    case studies. A recruiter skims for thirty seconds and leaves; this is
    the thirty-second version.

    `experience` is authored as its own list rather than derived from the
    projects, because employment and projects are not the same shape: two
    projects can sit inside one role (InstaDeep, T-ledger), and freelance
    work overlaps full-time work rather than following it. Array order is
    display order — no date parsing, so "October 2021 — November 2023" can
    stay human-readable.

    The `projects` slugs are the join back to the depth, which is the part a
    plain CV page cannot do: each row is a door into the reasoning.
    """
    roles = SITE.get("experience") or []
    if not roles:
        return ""

    rows = []
    for job in roles:
        # Company, then role, then place. Place used to sit between the first
        # two, which put "France" in the gap between "T+ informatique" and
        # "UI Designer" and broke the one pairing every reader is scanning for.
        place = ('<p class="cv__place">%s</p>' % e(job["place"])
                 if usable(job.get("place")) else "")

        # A TODO year renders as no year at all, matching how the facts tables
        # treat unfilled fields — an absent cell rather than the word TODO.
        years = ('<p class="cv__years"><time>%s</time></p>' % e(job["years"])
                 if usable(job.get("years")) else '<p class="cv__years"></p>')

        note = ('<p class="cv__note">%s</p>' % e(job["note"])
                if usable(job.get("note")) else "")

        links = []
        for slug in job.get("projects", []):
            p = index.get(slug)
            if p is None:
                raise SystemExit(
                    'site.json experience: "%s" lists unknown project "%s"'
                    % (job["company"], slug))
            links.append('<a href="projects/%s">%s</a>'
                         % (e(p["slug"]), e(p["title"])))
        work = ('<p class="cv__work">%s</p>' % "\n            ".join(links)
                if links else "")

        # Compact line always; place, note and project links in a panel
        # that opens on hover. The detail is NOT hidden from assistive tech
        # -- it collapses with max-height and opacity rather than display
        # or visibility, so it stays in the accessibility tree and is read
        # in order whether or not anyone can hover.
        head = ['<h3 class="cv__company">%s</h3>' % e(job["company"]),
                '<p class="cv__role">%s</p>' % e(job["role"])]
        detail = [b for b in (place, note, work) if b]
        detail_html = ('\n            <div class="cv__detail">\n              %s\n'
                       '            </div>' % "\n              ".join(detail)
                       ) if detail else ""
        rows.append('        <li class="cv__row">\n          %s\n'
                    '          <div class="cv__body">\n            %s%s\n'
                    '          </div>\n        </li>'
                    % (years, "\n            ".join(head), detail_html))

    kit = ""
    if SITE.get("toolkit"):
        # Chips, not a "A · B · C" string. The project pages have rendered
        # tool_chips() all along, so the about page was the one place the
        # toolkit appeared as plain text -- and it is the page where someone
        # actually goes looking for the stack. depth=0: about.html sits at
        # the root, so the icon paths need no ../ prefix.
        groups = "\n          ".join(
            "<dt>%s</dt>\n          <dd>%s</dd>"
            % (e(g["label"]), tool_chips(g["items"]))
            for g in SITE["toolkit"])
        kit = f"""
      <h2 class="cv__head" id="toolkit">Toolkit</h2>
      <dl class="cv__kit">
          {groups}
      </dl>"""

    return f"""
    <section class="shell cv" aria-labelledby="experience">
      <h2 class="cv__head" id="experience">Experience</h2>
      <ol class="cv__list">
{chr(10).join(rows)}
      </ol>{kit}
    </section>
"""


def values_block():
    """The values section: how he works, as against what he designs.

    Separate from the homepage's `principles`, which are about craft. This
    is the part a hiring manager is actually trying to find out, and every
    item is drawn from a sentence already in a case study -- a value with
    nothing behind it is decoration.
    """
    block = SITE.get("values") or {}
    items = [i for i in block.get("items", [])
             if usable(i.get("label")) and usable(i.get("body"))]
    if not items:
        return ""
    rows = "\n".join(
        '''        <li class="value">
          <span class="value__num" aria-hidden="true">%02d</span>
          <h3 class="value__label">%s</h3>
          <p class="value__body">%s</p>
        </li>''' % (n, e(i["label"]), e(i["body"]))
        for n, i in enumerate(items, 1))
    desc = block.get("description", "")
    desc_html = ("\n        <p>%s</p>" % e(desc)) if usable(desc) else ""
    return f"""
    <section class="shell band band--values" aria-labelledby="values">
      <div class="band__head">
        <h2 id="values">{masked(block.get("heading", "Values I believe in"))}</h2>{desc_html}
      </div>
      <ol class="values">
{rows}
      </ol>
    </section>
"""


def build_about(index):
    body = "\n      ".join("<p>%s</p>" % e(p) for p in SITE["about"])
    links = "\n        ".join(
        link_btn(l["label"], l["url"]) for l in SITE["links"]
    )
    size = png_size(ROOT / SITE["profileImage"])
    dims = ' width="%d" height="%d"' % size if size else ""

    # The portrait PNG is 741 KB — on its own more than the rest of this page
    # put together. An AVIF at 640px (twice the 320px column, so it still
    # holds up on a 2x screen) is 34 KB for the same picture, alpha included.
    # The PNG stays as the fallback source; a browser that understands AVIF
    # never downloads it, and one that doesn't is unchanged.
    avif = ROOT / "site" / "profile.avif"
    avif_src = ('<source srcset="site/profile.avif%s" type="image/avif">\n          '
                % asset_v("site/profile.avif")) if avif.is_file() else ""
    # intro is a voice line, not a search snippet — it ran 223 chars and Google
    # cuts at ~155. aboutDescription is written for the slot.
    out = [head("About — %s" % SITE["name"],
                SITE.get("aboutDescription") or SITE["intro"],
                # The designed 1200x630 card, not the portrait. profileImage is
                # square, and a scraper crops a preview to about 1.91:1 — from
                # an 800x800 portrait that is a horizontal band across the
                # face, which can arrive cropped at the eyes.
                image=SITE.get("shareImage") or SITE["profileImage"],
                page_url="about",
                nav_current="about",
                og_type="profile",
                image_alt="%s — %s, %s" % (SITE["name"], SITE["title"],
                                           SITE.get("location", "")))]
    # The page opens on the statement rather than on the word "About",
    # which is a label for a nav item and not a thing to say to someone
    # who has just arrived. Two authored lines, same break mechanism as
    # the homepage h1.
    intro = SITE.get("aboutIntro") or {}
    heading = intro.get("heading") or "About"
    intro_heading = masked(heading.split("\n")[0])
    for line in heading.split("\n")[1:]:
        intro_heading += "<br>" + masked(line)
    intro_body = "\n          ".join(
        "<p>%s</p>" % e(x) for x in intro.get("paragraphs", []) if usable(x))

    out.append(f"""
    <article class="shell about">
      <h1 class="about__statement">{intro_heading}</h1>
      <div class="about__grid">
        <figure class="about__portrait">
          <picture>
          {avif_src}<img src="{e(SITE['profileImage'])}{asset_v(SITE['profileImage'])}" alt="Portrait of {e(SITE['name'])}"{dims} decoding="async">
          </picture>
        </figure>
        <div class="prose">
          {intro_body}
          {body}
          <p class="about__cta">
            <a class="btn btn--solid" href="{e(SITE['cv'])}{asset_v(SITE['cv'])}">Download CV (PDF)</a>
          </p>
          <div class="btn-row">
        {links}
          </div>
        </div>
      </div>
    </article>
{cv_block(index)}
{values_block()}""")
    out.append(foot())
    (ROOT / "about.html").write_text("\n".join(out), encoding="utf-8")


def build_project(project, prev_p, next_p):
    d = project["_dir"]
    # A cover doubles as the link preview, and most covers here are full-page
    # screenshots — 900x4009 in the worst case. Every platform crops a preview
    # to about 1.91:1, so those arrived as an unrecognisable band lifted out of
    # the middle of a page. tools/make-share-cards.py renders a proper
    # 1200x630 card where one is needed; use it when it exists.
    share = ROOT / "projects" / d / "assets" / "share.jpg"
    og_img = ("projects/%s/assets/share.jpg" % d if share.is_file()
              else "projects/%s/%s" % (d, project["cover"]))
    out = [head(
        "%s — %s" % (project["title"], SITE["name"]),
        # summary is body copy — 3-4 sentences, up to 346 chars. Google cuts at
        # ~155, so a dedicated description is written for the slot.
        project.get("description") or project["summary"],
        depth=1,
        image=og_img,
        page_url="projects/%s" % project["slug"],
        # A case study is a written piece, not a site. og:type was hardcoded
        # "website" on all twelve pages.
        og_type="article",
        image_alt="%s — %s" % (project["title"], project["tagline"])
            if usable(project.get("tagline")) else project["title"],
    )]

    def facts_block(label, rows):
        if not rows:
            return ""
        body = "".join(
            '<div class="facts__row"><dt>%s</dt><dd>%s</dd></div>' % (e(k), e(v))
            for k, v in rows)
        return ('<div class="facts-group"><p class="facts-group__label">%s</p>'
                '<dl class="facts">%s</dl></div>' % (e(label), body))

    # engagement facts and craft facts answer different questions, so they are
    # two labelled blocks rather than one undifferentiated table
    engagement = [(f.capitalize(), project[f]) for f in FACTS if usable(project.get(f))]
    facts_html = facts_block("The engagement", engagement)
    # Platforms and Toolkit are groups whose label already names the field, so
    # they render as bare values — a "Platforms" row under a "Platforms" heading
    # says the same word twice.
    if project.get("platforms"):
        facts_html += ('<div class="facts-group"><p class="facts-group__label">Platforms</p>'
                       '<p class="facts-group__value">%s</p></div>'
                       % e(", ".join(project["platforms"])))
    if project.get("tools"):
        facts_html += ('<div class="facts-group"><p class="facts-group__label">Toolkit</p>'
                       '%s</div>' % tool_chips(project["tools"], depth=1))

    # Research numbers read as findings when they are set large with a short
    # caption underneath, rather than as a row of small stats in the header.
    metrics_html = ""
    if project.get("metrics"):
        cells = "".join(
            '<div class="insight"><span class="insight__value">%s</span>'
            '<span class="insight__label">%s</span></div>' % (e(m["value"]), e(m["label"]))
            for m in project["metrics"]
        )
        metrics_html = ('<section class="insights shell" aria-label="Research at a glance">'
                        '<div class="insights__grid">%s</div></section>' % cells)

    links_html = ""
    if project.get("links"):
        items = "".join(
            link_btn(l["label"], l["url"], 1, rel_attr=' rel="noopener"')
            for l in project["links"]
        )
        links_html = '<div class="btn-row">%s</div>' % items

    tags_html = ""
    if project.get("tags"):
        tags_html = '<ul class="tags">%s</ul>' % "".join(
            "<li>%s</li>" % e(t) for t in project["tags"])

    # BUILD.md: skip any field whose value starts with TODO. That has to hold
    # for prose too, not just the facts table — a placeholder tagline or an
    # unwritten section body would otherwise ship straight to the page.
    tagline_html = ('<p class="project__tagline">%s</p>' % e(project["tagline"])
                    if usable(project.get("tagline")) else "")

    csize = png_size(ROOT / "projects" / d / project["cover"])
    cover_dims = ' width="%d" height="%d"' % csize if csize else ""

    # A section whose body is still a placeholder and which has no images has
    # nothing to render, so it is dropped rather than left as a bare heading.
    live_sections = [
        sec for sec in project.get("sections", [])
        if usable(sec.get("body")) or sec.get("images")
    ]

    # A highlights page keeps the headings and the screens and drops the
    # prose. Sections with nothing to show once the prose goes are dropped
    # whole: a heading over an empty div is worse than no section. The source
    # dicts are copied rather than mutated -- load_projects() hands out the
    # parsed JSON itself, and blanking a body in place would also blank it for
    # write_sitemap and the figure count.
    if page_format(project) == "highlights":
        # `viewer` is dropped alongside the prose. The component browser is a
        # case-study device -- it shows one board at a time behind a tablist,
        # which is the right call when surrounding prose is walking the reader
        # through them one by one. On a gallery page there is no prose to do
        # that walking, so a tabbed frame just hides six of seven boards
        # behind controls nobody has been given a reason to click. Same
        # images, laid out flat.
        live_sections = [dict(sec, body="", viewer=False) for sec in live_sections
                         if sec.get("images") or sec.get("autoImages")]

    # Asymmetric header: narrative on the left, facts pinned on the right.
    toc_html = ""
    toc_items = [sec for sec in live_sections if sec.get("id")]
    # A highlights page has no prose to navigate, so its TOC would be a list
    # of links to image blocks.
    if len(toc_items) > 2 and page_format(project) != "highlights":
        rows = "".join(
            '<li><a href="#%s">%s</a></li>' % (e(sec["id"]), e(sec["heading"]))
            for sec in toc_items)
        toc_html = ('<nav class="toc" aria-label="On this page">'
                    '<p class="toc__label">On this page</p>'
                    '<ol class="toc__list">%s</ol></nav>' % rows)

    # One tint for the whole article: every shot inside inherits it through a
    # custom property, so a case study reads as a single colour world rather
    # than a column of unrelated white boxes.
    _tint = project_tint(project)
    tint_attr = ' data-tint="%s"' % _tint if _tint else ""

    # The sidebar has to stick for the length of the article, so it sits in a
    # grid whose height is the whole reading section — not inside the header,
    # where its containing block ended after a couple of hundred pixels.
    # Title, cover and insights stay full width above that grid.
    out.append(f"""
    <article class="project"{tint_attr}>
      <div class="progress" aria-hidden="true"><span class="progress__bar"></span></div>

      <header class="shell project__head">
        <p class="eyebrow">{e('Project' if page_format(project) == 'highlights' else 'Case study')}</p>
        <h1>{masked(project['title'])}</h1>
        {tagline_html}
        <p class="prose project__summary">{e(project['summary'])}</p>
        {tags_html}
        {links_html}
      </header>

      <figure class="cover-band">
        <!-- decorative: the <h1> immediately above names the project, so an
             alt of "<title> cover" only repeats it. -->
        <img src="{e(d)}/{e(project['cover'])}" alt=""{cover_dims} loading="eager" decoding="async">
      </figure>

      {metrics_html}

      <div class="project__layout shell">
        <aside class="project__meta">
          {toc_html}
          {facts_html}
        </aside>
        <div class="project__main">
""")

    # The expand-all control. Hidden until JS wires it, the same contract
    # as every other enhancement here: with script off each <summary>
    # still opens on its own, so nothing on screen offers a control that
    # cannot work. Only rendered when there is more than one section --
    # "expand all" over a single section is noise.
    if len(live_sections) > 1:
        out.append(
            '<div class="sections__control" hidden>'
            '<button type="button" class="sections__toggle" aria-expanded="false">'
            'Expand all</button></div>')

    # A leading "01" claims a position in a sequence. On a page with exactly
    # one live section there is no sequence, and the number reads as a
    # numbering bug rather than as structure -- most visibly on the highlights
    # pages whose single survivor is titled "The outcome", where "01 The
    # outcome" invites the question "the outcome of what?".
    numbered = len(live_sections) > 1

    def eyebrow(idx, section):
        """The `NN · PHASE` line above a section heading.

        pleurat.com runs this on every case study and it is the device that
        makes one "easy to explore": the eyebrow carries the generic stage
        name, which frees the heading itself to be a sentence rather than a
        label. Scannable and in a voice, instead of one or the other.

        The number used to live INSIDE the h2, which also meant its text
        content was the string "01DeepPCB" -- no separator, so that is what
        a screen reader announced and what the table of contents inherited.
        Out here it is a sibling, and the heading is just the heading.

        `phase` is optional. Where a section has none the eyebrow is the
        number alone, which is exactly what shipped before, so no project
        has to be rewritten for this to be safe.
        """
        phase = section.get("phase")
        bits = []
        if numbered:
            bits.append('<span class="project__num">%02d</span>' % idx)
        if usable(phase):
            bits.append('<span class="project__phase">%s</span>' % e(phase))
        if not bits:
            return ""
        # aria-hidden on the whole line: the number is decorative and the
        # phase repeats what the heading under it already says. Announcing
        # "zero one overview, overview" helps nobody.
        # A span, not a p. <summary>'s content model is phrasing content
        # optionally intermixed with heading content, and a <p> is flow
        # content -- it renders fine and is invalid to the parser.
        return ('<span class="project__eyebrow" aria-hidden="true">%s</span>'
                % '<span class="project__eyebrow-sep"></span>'.join(bits))

    for idx, section in enumerate(live_sections, start=1):
        num_html = eyebrow(idx, section)
        section_imgs = section.get("images", [])
        if section.get("autoImages"):
            section_imgs = section_imgs + auto_images(d, section["autoImages"])
        # a section marked "viewer" renders as a browsable frame instead of a grid
        # ── collapsible section ────────────────────────────────────
        # Fixerloop measured 26,747px, about 35 screens for one case
        # study, and the owner's read was that there is too much in it.
        # There is. The answer is not to delete the work; it is to stop
        # requiring that all of it be scrolled past to reach the end.
        #
        # <details> rather than a scripted accordion, because it is the
        # one disclosure widget that needs no script: <summary> is already
        # a button to the keyboard and to assistive tech, it already
        # carries its own expanded state, and it still opens with
        # JavaScript off. The JS added for this does only the TOC wiring
        # and the expand-all control -- never the opening itself.
        #
        # The FIGURES go inside. They were siblings following each
        # section, so collapsing a section alone would have hidden 500
        # words and left 21 screenshots exactly where they were.
        open_attr = " open" if section_opens(idx, section, live_sections) else ""
        count_html = screen_count(section_imgs)
        if section.get("viewer") and section_imgs:
            out.append(f"""
      <details class="project__section" id="{e(section.get('id',''))}"{open_attr}>
        <summary class="section__summary">
{num_html}
          <h2>{e(section['heading'])}</h2>
          {count_html}
        </summary>
        <div class="section__body">
        {('<div class="prose">%s</div>' % paragraphs(section.get("body"))) if usable(section.get("body")) else ""}
        {viewer(section_imgs, d, depth=1, label=section['heading'])}
        </div>
      </details>
""")
            continue
        figs = "\n".join(figure(img, d, depth=1) for img in section_imgs)
        # A grid of phone screens wants more, narrower columns. `.get("src")`
        # rather than `["src"]`: a motion entry carries `video`/`poster` and no
        # `src` at all, and indexing it here is what broke the build the first
        # time a clip was added. A clip is never a phone screen, so it counts
        # as not-a-phone and a section containing one keeps the normal grid.
        phones = sum(1 for img in section_imgs
                     if img.get("src")
                     and is_phone(png_size(ROOT / "projects" / d / img["src"])))
        variant = " shots--phone" if section_imgs and phones == len(section_imgs) else ""
        body_html = ('<div class="prose">%s</div>' % paragraphs(section.get("body"))
                     if usable(section.get("body")) else "")
        figs_html = ('\n      <div class="shots%s">\n%s\n      </div>' % (variant, figs)) if figs else ""
        out.append(f"""
      <details class="project__section" id="{e(section.get('id',''))}"{open_attr}>
        <summary class="section__summary">
{num_html}
          <h2>{e(section['heading'])}</h2>
          {count_html}
        </summary>
        <div class="section__body">
        {body_html}{figs_html}
        </div>
      </details>
""")

    nav = []
    if prev_p:
        nav.append('<a class="pager__link pager__link--prev" href="%s">'
                   '<span>Previous</span><strong>%s</strong></a>'
                   % (e(prev_p["slug"]), e(prev_p["title"])))
    if next_p:
        nav.append('<a class="pager__link pager__link--next" href="%s">'
                   '<span>Next project</span><strong>%s</strong></a>'
                   % (e(next_p["slug"]), e(next_p["title"])))
    out.append("""
        </div><!-- /.project__main -->
      </div><!-- /.project__layout -->

      <nav class="shell pager" aria-label="More projects">
        %s
      </nav>
    </article>
""" % "\n        ".join(nav))

    out.append(foot(depth=1))
    (ROOT / "projects" / ("%s.html" % project["slug"])).write_text(
        "\n".join(out), encoding="utf-8")


# ─────────────────────────────────────────── main

def write_sitemap(projects):
    """sitemap.xml + robots.txt, but only once site.url is set.

    A sitemap of relative paths is worse than none — it tells a crawler
    nothing it could not already reach, and an absolute one built on the
    wrong host would point every URL somewhere that does not exist.
    """
    base = (SITE.get("url") or "").rstrip("/")
    if not base:
        return 0
    # <lastmod> per page, from the JSON that page is generated out of, so a
    # crawler can tell which single case study changed instead of re-fetching
    # twelve pages. Project pages get their own content.json date; the home
    # and about pages are driven by site.json, which is also the floor for
    # everything else, so they use the site-wide stamp.
    site_iso = content_updated()[0]

    by_page = {}
    for p in projects:
        src = ROOT / "projects" / p["_dir"] / "content.json"
        if src.is_file():
            own = datetime.date.fromtimestamp(src.stat().st_mtime).isoformat()
            # max, not the project's own date: site.json drives the shared
            # head, nav and footer, so editing it really does change every
            # page. Claiming otherwise would be a lie a crawler acts on.
            by_page["projects/%s" % p["slug"]] = max(own, site_iso)

    def stamp(page):
        return by_page.get(page, site_iso)

    # The clean URLs, matching each page's own canonical. index.html is
    # deliberately absent: it is the same bytes as /work, which is the
    # canonical of the pair, and listing both would ask a crawler to decide
    # something the canonical already decided.
    pages = ["work", "about", "contact"] + [
        "projects/%s" % p["slug"] for p in projects]
    urls = "\n".join(
        "  <url><loc>%s/%s</loc><lastmod>%s</lastmod></url>"
        % (base, e(page), stamp(page)) for page in pages)
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n' % urls,
        encoding="utf-8")
    (ROOT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % base, encoding="utf-8")
    return len(pages)


def main():
    projects = load_projects()
    n_vars = write_tokens_css()
    build_index(projects)
    build_about(by_slug(projects))
    build_contact()
    for i, p in enumerate(projects):
        build_project(p, projects[i - 1] if i else None,
                      projects[i + 1] if i + 1 < len(projects) else None)
    n_urls = write_sitemap(projects)

    # autoImages boards are figures on the page like any other, so they
    # belong in this count. Leaving them out made the line under-report by
    # however many exports were sitting in a components/ folder -- quietly,
    # and by more the more the feature got used.
    imgs = 0
    for p in projects:
        for s in p.get("sections", []):
            imgs += len(s.get("images", []))
            if s.get("autoImages"):
                imgs += len(auto_images(p["_dir"], s["autoImages"]))
    print("tokens.css   %d custom properties" % n_vars)
    print("index.html   %d highlights, %d other projects"
          % (len(SITE["sections"]["highlights"]["slugs"]),
             len(SITE["sections"]["selectedWork"]["slugs"])))
    print("about.html   %d paragraphs, %d roles, %d toolkit groups"
          % (len(SITE["about"]), len(SITE.get("experience", [])),
             len(SITE.get("toolkit", []))))
    print("contact.html %d links, CV %s"
          % (len(SITE.get("links", [])), "yes" if SITE.get("cv") else "no"))
    print("projects/    %d pages, %d figures" % (len(projects), imgs))
    if n_urls:
        print("sitemap.xml  %d URLs, robots.txt written" % n_urls)
    else:
        print('sitemap.xml  skipped — set "url" in site.json to enable')


if __name__ == "__main__":
    main()
