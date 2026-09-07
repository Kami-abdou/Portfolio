#!/usr/bin/env python3
"""Static site generator for Abdou Yaackoubi's portfolio.

Reads site.json, tokens.json and projects/*/content.json, then writes plain
HTML to disk. There is no runtime data fetching: fetch() is blocked on
file:// in Chrome, so everything is baked in at build time.

    python3 build.py

Outputs index.html, about.html, projects/<slug>.html and assets/tokens.css.
"""

import datetime
import html
import json
import os
import re
import struct
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


def tool_chips(tools, depth=0):
    """Render tools as chips, using a real icon when one has been supplied.

    Brand marks are trademarked and are not bundled with the site, so an
    icon appears only if assets/tools/<slug>.svg exists. Otherwise the chip
    falls back to a monogram set in the site's own type — a hand-redrawn
    logo looks worse than no logo.
    """
    up = "../" * depth
    out = []
    for name in tools:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        icon_file = ROOT / "assets" / "tools" / ("%s.svg" % slug)
        if icon_file.is_file():
            mark = ('<img class="tool__icon" src="%sassets/tools/%s.svg" alt="" '
                    'width="18" height="18" loading="lazy">' % (up, slug))
        else:
            mark = '<span class="tool__mono" aria-hidden="true">%s</span>' % e(name[0])
        out.append('<li class="tool">%s<span class="tool__name">%s</span></li>'
                   % (mark, e(name)))
    return '<ul class="tools">%s</ul>' % "".join(out)


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
    projects = []
    for folder in sorted((ROOT / "projects").iterdir()):
        cfg = folder / "content.json"
        if cfg.is_file():
            data = json.loads(cfg.read_text(encoding="utf-8"))
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

    The palette is dark by design rather than via prefers-color-scheme, so
    there is no second colour set to keep in sync. A light override could be
    added here later without touching styles.css.
    """
    body = "\n".join(flatten_tokens(TOKENS))
    css = (
        "/* GENERATED by build.py from tokens.json — do not edit by hand. */\n"
        ":root {\n%s\n  color-scheme: dark;\n}\n" % body
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


def head(title, description, *, depth=0, image=None, page_url="",
         og_type="website", image_alt=None):
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
  <meta name="viewport" content="width=device-width, initial-scale=1">
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
  <meta name="color-scheme" content="dark">
  <link rel="icon" href="{up}assets/favicon.svg" type="image/svg+xml">
  <link rel="apple-touch-icon" href="{up}assets/apple-touch-icon.png">
  <link rel="stylesheet" href="{up}assets/fonts.css{asset_v("assets/fonts.css")}">
  <link rel="stylesheet" href="{up}assets/tokens.css{asset_v("assets/tokens.css")}">
  <link rel="stylesheet" href="{up}assets/styles.css{asset_v("assets/styles.css")}">
{json_ld()}</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="site-head">
    <div class="shell site-head__inner">
      <a class="site-head__name" href="{up}index.html" aria-label="{e(SITE['name'])} — home">{wordmark()}</a>
      <nav aria-label="Primary">
        <a href="{up}index.html#work">Work</a>
        <a href="{up}about.html">About</a>
        <a href="mailto:{e(SITE['email'])}">Contact</a>
      </nav>
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
        <a href="{up}{e(SITE['cv'])}">CV</a>
      </nav>
    </div>
  </footer>
  <script src="{up}assets/lightbox.js{asset_v("assets/lightbox.js")}" defer></script>
  <script src="{up}assets/enhance.js{asset_v("assets/enhance.js")}" defer></script>
</body>
</html>
"""


# ─────────────────────────────────────────── fragments

def figure(img, project_dir, depth):
    """One <figure>. depth is how many folders deep the page sits."""
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


def project_card(project, *, large):
    cover = "projects/%s/%s" % (project["_dir"], project["cover"])
    size = png_size(ROOT / "projects" / project["_dir"] / project["cover"])
    dims = ' width="%d" height="%d"' % size if size else ""
    cls = "card card--lg" if large else "card"
    num = "%02d" % project.get("order", 0)
    # cards show the tagline, so the TODO rule has to hold here as well
    tagline = project["tagline"] if usable(project.get("tagline")) else ""
    return f"""        <li>
          <a class="{cls}" href="projects/{e(project['slug'])}.html">
            <span class="card__media">
              <span class="card__num" aria-hidden="true">{num}</span>
              <!-- alt="" on purpose: this img is inside the card's <a>, whose text
                   already carries the title and tagline. Describing it here made
                   every card announce its title twice. -->
              <img src="{e(cover)}" alt="" {dims} loading="lazy" decoding="async">
            </span>
            <span class="card__body">
              <span class="card__title">{e(project['title'])}</span>
              <span class="card__tagline">{e(tagline)}</span>
            </span>
          </a>
        </li>"""


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
        page_url="index.html",
    )]

    # Cycling role line. Every role is in the DOM so it survives with JS off
    # and is indexable; JS reveals one at a time. The live list is aria-hidden
    # and a static label carries the accessible name, so assistive tech reads
    # the role once instead of announcing every swap.
    roles = [r for r in SITE.get("roles", []) if r] or [SITE["title"]]
    hero_img = SITE.get("heroImage") or SITE["profileImage"]
    psize = png_size(ROOT / hero_img)
    pdims = ' width="%d" height="%d"' % psize if psize else ""
    # ── Marquee wall hero ──────────────────────────────────────────
    # One row per role, each scrolling horizontally, portrait sitting over
    # them. The row text is repeated so the strip can loop seamlessly: the
    # track holds two identical halves and slides exactly -50%.
    #
    # Durations are staggered per row (58/68/78s) so the rows never drift into
    # sync and read as one moving block.
    #
    # The wall is rendered twice — once behind the portrait at full strength,
    # once in front at low opacity. That is what makes the type appear to
    # pass across the photograph. Both copies share one animation definition,
    # so they stay in step without any JS.
    since = SITE.get("since", "")
    span = ("%s — 2026" % since) if since else ""

    def wall(rows, *, ghost):
        out = []
        for idx, role in enumerate(rows):
            reps = "".join(
                '<span class="wall__word">%s</span>' % e(role) for _ in range(8))
            out.append(
                '<div class="wall__row wall__row--%s" style="--dur: %ds">'
                '<div class="wall__track">%s%s</div></div>'
                % ("rev" if idx % 2 else "fwd", 58 + idx * 10, reps, reps))
        cls = "wall wall--ghost" if ghost else "wall"
        return '<div class="%s" aria-hidden="true">%s</div>' % (cls, "".join(out))

    wall_rows = roles[:3] if len(roles) >= 3 else roles

    out.append(f"""
    <section class="hero">
      <h1 class="visually-hidden">{e(SITE['name'])} — {e(", ".join(roles))}</h1>

      {wall(wall_rows, ghost=False)}

      <figure class="hero__portrait">
        <img src="{e(hero_img)}" alt="Portrait of {e(SITE['name'])}"{pdims} decoding="async">
      </figure>

      {wall(wall_rows, ghost=True)}

      <p class="hero__statement shell">{e(SITE.get('heroStatement', ''))}</p>

      <div class="hero__meta shell">
        <span>{e(SITE.get('location', ''))}</span>
        <span>{e(span)}</span>
      </div>
    </section>

    <section class="hero-copy shell">
      <p class="hero__tagline">{e(SITE['tagline'])}</p>
      <p class="hero__intro">{e(SITE['intro'])}</p>
    </section>
""")

    for key, large in (("caseStudies", True), ("otherProjects", False)):
        meta = SITE["sections"][key]
        anchor = ' id="work"' if key == "caseStudies" else ""
        cards = "\n".join(
            project_card(slugs[s], large=large) for s in meta["slugs"] if s in slugs
        )
        out.append(f"""
    <section class="band shell"{anchor}>
      <div class="band__head">
        <h2>{masked(meta['heading'])}</h2>
        <p>{e(meta['description'])}</p>
      </div>
      <ul class="grid {'grid--lg' if large else 'grid--sm'}" style="--cols: {2 if large else 4}">
{cards}
      </ul>
    </section>
""")

    contact_links = "\n        ".join(
        '<a class="btn" href="%s">%s</a>' % (e(l["url"]), e(l["label"])) for l in SITE["links"]
    )
    out.append(f"""
    <section class="band band--contact shell" id="contact">
      <h2>{masked("Let's talk")}</h2>
      <p class="lede">{e(SITE.get("contactLede", ""))}</p>
      <div class="btn-row">
        {contact_links}
      </div>
    </section>
""")
    out.append(foot())
    (ROOT / "index.html").write_text("\n".join(out), encoding="utf-8")


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
            links.append('<a href="projects/%s.html">%s</a>'
                         % (e(p["slug"]), e(p["title"])))
        work = ('<p class="cv__work">%s</p>' % "\n            ".join(links)
                if links else "")

        body = ['<h3 class="cv__company">%s</h3>' % e(job["company"]),
                '<p class="cv__role">%s</p>' % e(job["role"])]
        body += [b for b in (place, note, work) if b]
        rows.append('        <li class="cv__row">\n          %s\n'
                    '          <div class="cv__body">\n            %s\n'
                    '          </div>\n        </li>'
                    % (years, "\n            ".join(body)))

    kit = ""
    if SITE.get("toolkit"):
        groups = "\n          ".join(
            "<dt>%s</dt>\n          <dd>%s</dd>"
            % (e(g["label"]), e(" · ".join(g["items"])))
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


def build_about(index):
    body = "\n      ".join("<p>%s</p>" % e(p) for p in SITE["about"])
    links = "\n        ".join(
        '<a class="btn" href="%s">%s</a>' % (e(l["url"]), e(l["label"])) for l in SITE["links"]
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
                page_url="about.html",
                og_type="profile",
                image_alt="%s — %s, %s" % (SITE["name"], SITE["title"],
                                           SITE.get("location", "")))]
    out.append(f"""
    <article class="shell about">
      <h1>{masked("About")}</h1>
      <div class="about__grid">
        <figure class="about__portrait">
          <picture>
          {avif_src}<img src="{e(SITE['profileImage'])}" alt="Portrait of {e(SITE['name'])}"{dims} decoding="async">
          </picture>
        </figure>
        <div class="prose">
          {body}
          <p class="about__cta">
            <a class="btn btn--solid" href="{e(SITE['cv'])}">Download CV (PDF)</a>
          </p>
          <div class="btn-row">
        {links}
          </div>
        </div>
      </div>
    </article>
{cv_block(index)}""")
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
        page_url="projects/%s.html" % project["slug"],
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
            '<a class="btn" href="%s" rel="noopener">%s</a>' % (e(l["url"]), e(l["label"]))
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

    # Asymmetric header: narrative on the left, facts pinned on the right.
    toc_html = ""
    toc_items = [sec for sec in live_sections if sec.get("id")]
    if len(toc_items) > 2:
        rows = "".join(
            '<li><a href="#%s">%s</a></li>' % (e(sec["id"]), e(sec["heading"]))
            for sec in toc_items)
        toc_html = ('<nav class="toc" aria-label="On this page">'
                    '<p class="toc__label">On this page</p>'
                    '<ol class="toc__list">%s</ol></nav>' % rows)

    # The sidebar has to stick for the length of the article, so it sits in a
    # grid whose height is the whole reading section — not inside the header,
    # where its containing block ended after a couple of hundred pixels.
    # Title, cover and insights stay full width above that grid.
    out.append(f"""
    <article class="project">
      <div class="progress" aria-hidden="true"><span class="progress__bar"></span></div>

      <header class="shell project__head">
        <p class="eyebrow">{e('Case study' if project['category'] == 'case-study' else 'Project')}</p>
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

    for idx, section in enumerate(live_sections, start=1):
        section_imgs = section.get("images", [])
        if section.get("autoImages"):
            section_imgs = section_imgs + auto_images(d, section["autoImages"])
        # a section marked "viewer" renders as a browsable frame instead of a grid
        if section.get("viewer") and section_imgs:
            out.append(f"""
      <section class="project__section" id="{e(section.get('id',''))}">
        <h2><span class="project__num" aria-hidden="true">{'%02d' % idx}</span>{e(section['heading'])}</h2>
        {('<div class="prose">%s</div>' % paragraphs(section.get("body"))) if usable(section.get("body")) else ""}
        {viewer(section_imgs, d, depth=1, label=section['heading'])}
      </section>
""")
            continue
        figs = "\n".join(figure(img, d, depth=1) for img in section_imgs)
        # a grid of phone screens wants more, narrower columns
        phones = sum(1 for img in section_imgs
                     if is_phone(png_size(ROOT / "projects" / d / img["src"])))
        variant = " shots--phone" if section_imgs and phones == len(section_imgs) else ""
        body_html = ('<div class="prose">%s</div>' % paragraphs(section.get("body"))
                     if usable(section.get("body")) else "")
        figs_html = ('\n      <div class="shots%s">\n%s\n      </div>' % (variant, figs)) if figs else ""
        out.append(f"""
      <section class="project__section" id="{e(section.get('id',''))}">
        <h2><span class="project__num" aria-hidden="true">{'%02d' % idx}</span>{e(section['heading'])}</h2>
        {body_html}
      </section>{figs_html}
""")

    nav = []
    if prev_p:
        nav.append('<a class="pager__link pager__link--prev" href="%s.html">'
                   '<span>Previous</span><strong>%s</strong></a>'
                   % (e(prev_p["slug"]), e(prev_p["title"])))
    if next_p:
        nav.append('<a class="pager__link pager__link--next" href="%s.html">'
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
            by_page["projects/%s.html" % p["slug"]] = max(own, site_iso)

    def stamp(page):
        return by_page.get(page, site_iso)

    pages = ["index.html", "about.html"] + ["projects/%s.html" % p["slug"] for p in projects]
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
    for i, p in enumerate(projects):
        build_project(p, projects[i - 1] if i else None,
                      projects[i + 1] if i + 1 < len(projects) else None)
    n_urls = write_sitemap(projects)

    imgs = sum(len(s.get("images", [])) for p in projects for s in p.get("sections", []))
    print("tokens.css   %d custom properties" % n_vars)
    print("index.html   %d case studies, %d other projects"
          % (len(SITE["sections"]["caseStudies"]["slugs"]),
             len(SITE["sections"]["otherProjects"]["slugs"])))
    print("about.html   %d paragraphs, %d roles, %d toolkit groups"
          % (len(SITE["about"]), len(SITE.get("experience", [])),
             len(SITE.get("toolkit", []))))
    print("projects/    %d pages, %d figures" % (len(projects), imgs))
    if n_urls:
        print("sitemap.xml  %d URLs, robots.txt written" % n_urls)
    else:
        print('sitemap.xml  skipped — set "url" in site.json to enable')


if __name__ == "__main__":
    main()
