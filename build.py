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


def page_description(key):
    """The <meta name="description"> for one page.

    This is not decoration. Google prints it under the link, and
    LinkedIn, Slack and WhatsApp print it on the card when somebody
    pastes the URL into a hiring thread -- which is how most of the
    traffic that matters actually arrives.

    All three pages shared one forty-character string, "Product
    designer. I build what I design.", which is the h1 again and carries
    none of the words anyone searches for. One per page now, keyed in
    site.json.

    The old single string stays as the fallback so a page added without
    an entry still gets something. Project pages never used it: a case
    study writes its own from the study.
    """
    per_page = SITE.get("metaDescriptions") or {}
    return per_page.get(key) or SITE.get("metaDescription") or SITE["title"]


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


#: Attributes for a link that leaves the page for a new tab.
#:
#: `noopener` is belt and braces on a same-origin PDF -- every current
#: browser implies it for target="_blank" -- but it is one attribute and it
#: is what the rest of the file already does for outbound links.
#: The one place the booking URL lives, and now the only thing the site
#: knows about Cal: three "Book a call" links point straight at it.
#:
#: It used to be an inline embed at /contact. Cal's free plan renders an
#: attribution bar under the booker that no plan-less setting removes --
#: it is cross-origin, so nothing here can reach it, and hiding it would
#: be dodging the attribution the free tier is paid for with. Worse, the
#: bar renders WHITE in both themes (proven: cssVarsPerTheme reaches the
#: iframe and recolours the slots, and the bar ignores it), so on this
#: page it was a bright slab across a near-black page.
#:
#: Linking out puts the logo on Cal's own page, where it belongs, and
#: takes this site to ZERO third-party requests and zero third-party
#: script -- which is a claim the portfolio case study makes about
#: itself. The cost is one context switch before booking.
CAL_LINK = "https://cal.com/abdou-yaackoubi-lpkcep/30min"

NEW_TAB = ' target="_blank" rel="noopener"'

#: ...and the part a sighted visitor gets for free.
#:
#: A new tab is a change of context, and a link that changes context without
#: saying so is the surprise WCAG 3.2.5 is about: the back button no longer
#: goes back, which is disorienting if you cannot see that a tab appeared.
#: The note is in the accessible name and nowhere on screen, because the
#: visual cue is the tab itself.
NEW_TAB_NOTE = '<span class="visually-hidden"> (opens in a new tab)</span>'


def link_btn(label, href, depth=0, *, slug=None, rel_attr="", new_tab=False):
    """A .btn carrying its mark, so the four sites cannot drift apart."""
    attrs = rel_attr + (NEW_TAB if new_tab else "")
    note = NEW_TAB_NOTE if new_tab else ""
    return ('<a class="btn" href="%s"%s>%s<span>%s</span>%s</a>'
            % (e(href), attrs, link_icon(label, depth, slug=slug), e(label), note))


def ask_row(depth=0):
    """The hero's ask, set as a sentence instead of two buttons.

        Book a call  or  Copy email   (Open to new projects)

    The same two controls as actions_row, and the same three elements
    underneath them -- the button, the mailto fallback, the live region
    -- so enhance.js and the <noscript> rule reach this one without
    knowing it exists. Only the dress is different.

    WHY THE HERO DIFFERS from the closing band, which keeps the solid
    buttons: a filled pill above the fold asks for the meeting before
    the visitor has seen one thing you made. The quiet version offers it
    without insisting; the loud one waits at the bottom, where the work
    has already made the argument. Quiet at the top, loud once it is
    earned. That is the rule, written down so it stays a rule and does
    not read later as two components that drifted.

    The badge is what replaced the "OPEN TO WORK" eyebrow above the h1.
    Same fact, but attached to the action it qualifies instead of
    floating over the headline, where it reads as a state rather than a
    plea.
    """
    addr = SITE.get("email", "")
    label = SITE.get("availability", "")
    # The dot is decoration -- "Open to new projects" already says it --
    # so it is aria-hidden and the badge is not given a role. A status
    # role here would make a screen reader announce availability every
    # time focus passed through the hero.
    badge = ('<span class="ask__badge">'
             '<span class="ask__dot" aria-hidden="true"></span>%s</span>'
             % e(label)) if usable(label) else ""
    book = ('<a class="ask__act" href="%s"%s>Book a call%s</a>'
            % (e(CAL_LINK), NEW_TAB, NEW_TAB_NOTE))
    if not usable(addr):
        return '<p class="ask">%s%s</p>' % (book, badge)
    # With JavaScript off the button hides and the mailto shows, and
    # because the fallback follows the "or" in source order the sentence
    # still reads straight through: "Book a call or Email me".
    return (
        '<p class="ask">'
        '%s'
        '<span class="ask__or">or</span>'
        '<button class="ask__act js-copy" type="button" data-copy="%s">'
        'Copy email</button>'
        '<a class="ask__act js-copy-fallback" href="mailto:%s">Email me</a>'
        '%s'
        '<span class="visually-hidden" role="status" aria-live="polite"'
        ' data-copy-status></span>'
        '</p>' % (book, e(addr), e(addr), badge))


def reach_line():
    """The address in plain sight, and what happens after you use it.

    "Copy email" serves the person reading the page. It does nothing for
    the person RELAYING it: the recruiter pasting an address into an
    applicant tracker, or forwarding it to the hiring manager who makes
    the actual call. That person needs the string itself, selectable, on
    the page. The button stays; this is the address it copies, said out
    loud next to it.

    The reply time sits beside it because that is the question being
    asked at this point in the page. Not "can I reach him" -- the three
    controls above answer that -- but "will he answer".
    """
    addr = SITE.get("email", "")
    reply = SITE.get("replyTime", "")
    bits = []
    if usable(addr):
        bits.append('<a class="reach__addr" href="mailto:%s">%s</a>'
                    % (e(addr), e(addr)))
    if usable(reply):
        bits.append('<span class="reach__reply">%s</span>' % e(reply))
    if not bits:
        return ""
    sep = '<span class="reach__sep" aria-hidden="true"> · </span>'
    return '<p class="reach">%s</p>' % sep.join(bits)


def actions_row(depth=0, *, cls="actions"):
    """"Book a call" and "Copy email", the site's only two asks.

    Two places use this -- the homepage's closing line and /about -- and
    the brief for both is "the same component", so it is a function
    rather than two copies of the same markup. The hero is the third ask
    and the one exception; see ask_row for why.

    Book a call is an <a>, not a <button>. It navigates, and a button that
    navigates loses the middle-click, the context menu and the status bar
    for no gain. Copy email is a real <button>, because it acts on the page
    instead of going anywhere.

    It opens a new tab, and says so in its accessible name. Booking is a
    detour, not a destination: sending someone off-site in the tab they
    were reading in means the way back to the work is the back button.

    THREE controls are emitted, not two. The button is the enhanced path;
    the mailto next to it is the fallback, hidden by default and revealed
    in exactly two situations:

      * JavaScript is off      -- the <noscript> rule in head() shows it
      * the Clipboard API is missing -- enhance.js shows it

    Without that, a visitor with no clipboard gets a button that silently
    does nothing, which is worse than the mailto this site shipped before.

    The status span is the aria-live region. It is a sibling rather than
    the button's own text so that the label change ("Copy email" ->
    "Copied") and the announcement are separate: changing a button's label
    while it is focused is not reliably announced on its own.
    """
    addr = SITE.get("email", "")
    book = ('<a class="btn btn--solid" href="%s"%s>Book a call%s</a>'
            % (e(CAL_LINK), NEW_TAB, NEW_TAB_NOTE))
    if not usable(addr):
        return '<div class="%s">%s</div>' % (cls, book)
    return (
        '<div class="%s">'
        '%s'
        '<button class="btn js-copy" type="button" data-copy="%s">'
        'Copy email</button>'
        '<a class="btn js-copy-fallback" href="mailto:%s">Email me</a>'
        '<span class="visually-hidden" role="status" aria-live="polite" data-copy-status></span>'
        '</div>' % (cls, book, e(addr), e(addr)))


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

    DARK IS THE DEFAULT. The overhaul moved the site to a near-black
    software-craft language, so `color` is that set and `colorLight` is the
    alternate. The direction of the override matters: a dark-default site
    that emits light in :root flashes white on every load for the majority
    of visitors, which is the one thing a dark site must not do.

    The canvas is a warm-cast black rather than a neutral one, so the page
    carries the brand hue instead of borrowing a reference's. The structure
    is borrowed; the colour is not.

    Emitted three ways:

      :root
          the dark default, so a cold load paints dark with no script.
      @media (prefers-color-scheme: light) + :root:not([data-theme="dark"])
          follows a visitor whose system asks for light.
      :root[data-theme="light"]
          an explicit choice, which has to beat the system.

    styles.css holds ~180 var(--color-*) references and zero colour
    literals, so the whole of both themes is these declarations.
    """
    body = "\n".join(flatten_tokens(TOKENS))
    alt = TOKENS.get("colorLight") or {}
    def decls(indent):
        return "\n".join(
            "%s--color-%s: %s;" % (indent, re.sub(r"(?<!^)(?=[A-Z])", "-", k).lower(), v)
            for k, v in alt.items())

    out = ["/* GENERATED by build.py from tokens.json - do not edit by hand. */",
           ":root {", body, "  color-scheme: dark light;", "}"]
    if alt:
        out += ["",
                "@media (prefers-color-scheme: light) {",
                '  :root:not([data-theme="dark"]) {',
                decls("    "),
                "  }",
                "}",
                "",
                ':root[data-theme="light"] {',
                decls("  "),
                "}"]
    css = "\n".join(out) + "\n"
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
    # The theme control. The page follows the system by default; this is for
    # the visitor whose machine says dark but who wants to see the paper,
    # which is most of what this site's identity IS. aria-pressed rather than
    # a label that has to be kept in sync with what it would switch TO.
    #
    # No icon library ships here and hand-drawn SVG paths are not worth it
    # for one control, so the mark is a circle whose right half fills: two
    # divs and a border-radius, which is the shape every OS uses for this.
    toggle = ('<button class="theme-toggle" type="button" '
              'aria-label="Switch between light and dark" aria-pressed="false">'
              '<span class="theme-toggle__dial" aria-hidden="true"></span>'
              '</button>')
    return (
        '<nav class="site-nav" aria-label="Primary">\n'
        '        <span class="site-nav__pill">\n'
        '          <span class="site-nav__marker" aria-hidden="true"></span>\n'
        '          %s\n        </span>\n'
        '        %s\n'
        '        <a class="site-nav__cta" href="%s"%s>Book a call%s</a>\n'
        '      </nav>' % ("\n          ".join(out), toggle,
                          e(CAL_LINK), NEW_TAB, NEW_TAB_NOTE))


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
               e(image_alt or "%s - %s" % (SITE["name"], SITE["title"])),
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
  <!-- With JavaScript off the copy button cannot copy anything, so it is
       swapped for the mailto beside it. That is why actions_row emits
       both: a control that silently does nothing is worse than a link. -->
  <noscript><style>.js-copy{{display:none}}.js-copy-fallback{{display:inline-flex}}</style></noscript>
  <!-- One theme-color per scheme. A single value painted the browser
       chrome, the iOS status bar and the Android task-switcher card in
       the dark canvas even when the page was showing light, which is a
       seam exactly where the OS meets the page. enhance.js overwrites
       BOTH when the toggle is used, so an explicit choice beats the
       system preference there too. -->
  <meta name="theme-color" media="(prefers-color-scheme: dark)" content="{e(TOKENS['color']['bg'])}">
  <meta name="theme-color" media="(prefers-color-scheme: light)" content="{e(TOKENS['colorLight']['bg'])}">
  <!-- `light` was left here when the site flipped to dark-first. It
       tells the browser to paint form controls, scrollbars and the
       default canvas light while the stylesheet says `dark light`, and
       the browser believes the meta until the CSS lands. -->
  <meta name="color-scheme" content="dark light">
  <link rel="icon" type="image/png" sizes="32x32" href="{up}assets/favicon-32.png{asset_v('assets/favicon-32.png')}">
  <link rel="icon" type="image/png" sizes="192x192" href="{up}assets/favicon-192.png{asset_v('assets/favicon-192.png')}">
  <link rel="apple-touch-icon" href="{up}assets/apple-touch-icon.png{asset_v('assets/apple-touch-icon.png')}">
  <!-- The two faces, preloaded. `font-display: swap` without this pair is a
       layout shift by construction: first paint uses a fallback whose metrics
       differ from the body face's, then the page reflows when it arrives.
       Measured on this site before the preload existed, that cost 0.389 CLS.

       `crossorigin` is required even though these are same-origin. Fonts are
       always fetched in CORS mode, so a preload without it is a SEPARATE
       cache entry from the one @font-face goes on to request -- the file gets
       downloaded twice and the preload buys nothing. -->
  <link rel="preload" href="{up}assets/fonts/instrument-variable.woff2{asset_v('assets/fonts/instrument-variable.woff2')}" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="{up}assets/fonts/bricolage-variable.woff2{asset_v('assets/fonts/bricolage-variable.woff2')}" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="{up}assets/fonts.css{asset_v("assets/fonts.css")}">
  <link rel="stylesheet" href="{up}assets/tokens.css{asset_v("assets/tokens.css")}">
  <link rel="stylesheet" href="{up}assets/styles.css{asset_v("assets/styles.css")}">
{json_ld()}  <script>
    /* Before first paint, or the page renders in the system theme and then
       snaps to the stored one. Inline and synchronous on purpose: a deferred
       script runs after the first frame, which IS the flash.
       Wrapped because Safari throws on localStorage in private browsing, and
       an exception here would take the rest of the head with it. */
    try {{
      var t = localStorage.getItem("theme");
      if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
    }} catch (e) {{}}
  </script>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="site-head">
    <div class="shell site-head__inner">
      <a class="site-head__name" href="{up}work" aria-label="{e(SITE['name'])}, home">{wordmark()}</a>
      {primary_nav(up, nav_current)}
    </div>
  </header>
  <main id="main" tabindex="-1">"""


def foot(depth=0):
    """One line, which is all a footer on this site has to be now.

    It carried the copyright, a "Last updated" stamp and a row of link
    buttons repeating the email, LinkedIn and CV that were already in the
    contact band directly above it. The band is gone and the repetition
    went with it: LinkedIn and the CV live here, once.

    The year is still derived rather than typed, because a hardcoded one
    starts lying on 1 January.

    The "Last updated" stamp came back. A portfolio with no date on it
    is read as abandoned, and "is he still looking" is the first thing
    a recruiter wants settled. It is stamped from the newest mtime
    across the JSON sources, so it cannot claim a change nobody made.
    """
    up = "../" * depth
    iso, stamp = content_updated()
    linkedin = next((l for l in SITE.get("links", [])
                     if "linkedin" in l.get("label", "").lower()), None)
    bits = ["Last updated %s" % e(stamp)]
    if linkedin:
        bits.append('<a href="%s"%s>%s%s</a>'
                    % (e(linkedin["url"]), NEW_TAB, e(linkedin["label"]), NEW_TAB_NOTE))
    if SITE.get("cv"):
        bits.append('<a href="%s%s%s"%s>CV (PDF)%s</a>'
                    % (up, e(SITE["cv"]), asset_v(SITE["cv"]), NEW_TAB, NEW_TAB_NOTE))
    sep = '<span class="site-foot__sep" aria-hidden="true"> · </span>'
    tail = "".join(sep + b for b in bits)
    return f"""  </main>
  <footer class="site-foot">
    <div class="shell site-foot__inner">
      <p class="site-foot__note">© {iso[:4]} {e(SITE['name'])}{tail}</p>
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
                    "alt": "%s, InstaDeep design system" % label,
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


TINTS = ("sand", "clay", "ash")


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


# ─────────────────────────────────────────── pages

def project_domain(project):
    """The middle segment of `meta`: "2024-now \u00b7 AI \u00b7 Senior product
    designer" -> "AI".

    Returns "" when meta has no middle, which is the same rule the rest of
    this build follows: a fact that does not exist renders nothing rather
    than an empty cell.
    """
    meta = project.get("meta")
    if not usable(meta):
        return ""
    parts = [x.strip() for x in meta.split("\u00b7") if x.strip()]
    return parts[1] if len(parts) > 2 else ""


def index_row(project, n, depth=0):
    """One line of the work index.

    This replaces a 1152x720 cover card. Three of those filled two and a
    half screens and said four words each; five of these fit in one
    screen and each says what the project WAS.

    Nothing here is authored twice. The line is the project's own
    tagline, the domain and the year are segments of its meta, and the
    cover is the one the case study already uses -- the homepage had
    been carrying its own copy of all of it.

    The cover has not gone away, it moved: it is on `data-peek`, and
    enhance.js shows it following the cursor. A row that cannot show an
    image on hover still reads perfectly, which is why the image is an
    attribute rather than markup.
    """
    up = "../" * depth
    d = project["_dir"]
    cover = "projects/%s/%s" % (d, project["cover"])
    line = project.get("tagline") if usable(project.get("tagline")) else ""
    return """        <li class="index__row">
          <a class="index__link" href="{up}projects/{slug}" data-peek="{up}{cover}{v}">
            <span class="index__num" aria-hidden="true">{n:02d}</span>
            <span class="index__name">{title}</span>
            <span class="index__line">{line}</span>
            <span class="index__domain">{domain}</span>
            <span class="index__year">{year}</span>
            <span class="index__arrow" aria-hidden="true">&#8599;</span>
          </a>
        </li>""".format(
        up=up, slug=e(project["slug"]), cover=e(cover), v=asset_v(cover), n=n,
        title=e(project["title"]), line=e(line),
        domain=e(project_domain(project)), year=e(project_year(project)))


def build_index(projects):
    """The homepage: a hero, the work, and one way to get in touch.

    It used to say 557 words before the footer. It carried an availability
    badge, a portfolio-year label, a supporting paragraph, four stat
    blocks, a fanned stack of three cards, an "A bit about me" section
    duplicating /about, two bands of projects each with chips and a
    summary, and a "Let's talk" band repeating the email, LinkedIn and CV
    that the footer repeated again.

    Every one of those was defensible on its own and the sum was noise: a
    visitor arriving to see the work had to scroll past four asks and two
    biographies to reach it. What is left is a greeting, the work, and the
    same two buttons twice.
    """
    slugs = by_slug(projects)
    out = [head(
        "%s - %s" % (SITE["name"], SITE["title"]),
        page_description("home"),
        page_url="work",
        nav_current="work",
    )]

    hero_img = SITE.get("heroImage") or SITE["profileImage"]
    psize = png_size(ROOT / hero_img)
    pdims = ' width="%d" height="%d"' % psize if psize else ""

    # Authored line breaks, same mechanism as before: the break is the
    # joke, and letting the measure decide it moves the break on every
    # viewport. Each line is its own block, so there is no <br> between
    # them -- a <br> between two blocks renders a phantom empty line.
    claim = SITE.get("heroClaim") or SITE["title"]
    claim_lines = claim.split("\n")
    claim_html = "".join(
        '<span class="claim__line%s">%s</span>'
        % (" claim__line--built" if i == len(claim_lines) - 1 else "", e(line))
        for i, line in enumerate(claim_lines))

    meta_line = SITE.get("heroMeta", "")
    meta_html = ('\n      <p class="opening__meta">%s</p>' % e(meta_line)
                 ) if usable(meta_line) else ""

    out.append(f"""
    <div class="shell hero-band">
    <section class="opening">
      <figure class="opening__portrait">
        <img src="{e(hero_img)}{asset_v(hero_img)}" alt="Portrait of {e(SITE['name'])}"{pdims} decoding="async">
      </figure>

      <h1 class="opening__claim">{claim_html}</h1>{meta_html}

      {ask_row()}
    </section>
    </div>
""")

    # ── Selected work ────────────────────────────────────────────────
    # Every live project, in one index. The split into "three cards and a
    # More work line" existed because a cover card is expensive: three was
    # all that fit. A row costs a line, so the two tiers collapse into one
    # list and nothing is relegated to a footnote.
    sel = SITE.get("sections", {}).get("selected") or {}
    items = [i["slug"] for i in sel.get("items", []) if i.get("slug") in slugs]
    if items:
        rows = "\n".join(index_row(slugs[sl], n)
                         for n, sl in enumerate(items, 1))
        out.append(f"""
    <section class="band shell band--work" id="work">
      <h2 class="band__title">{e(sel.get("heading", "Selected work"))}</h2>
      <ol class="index">
{rows}
      </ol>
    </section>
""")

    # ── The closing ask ──────────────────────────────────────────────
    # The hero's ask again, in its loud form, plus the two things the
    # quiet version at the top deliberately leaves out.
    #
    # The proof line is here and not in the hero because it answers the
    # h1 rather than introducing it. "I build what I design" is the
    # claim the whole site rests on and until now the homepage asserted
    # it and changed the subject; this is the sentence that cashes it,
    # placed where a visitor who has just read five projects can check
    # it against what they saw.
    proof = SITE.get("buildProof", "")
    proof_html = ('\n      <p class="close__proof">%s</p>'
                  % e(proof)) if usable(proof) else ""
    out.append(f"""
    <section class="band shell band--close" id="contact">
      <h2 class="band__close">{e(SITE.get("closingLine", "Have something in mind?"))}</h2>{proof_html}
      {actions_row()}
      {reach_line()}
    </section>
""")

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


def experience_list(index):
    """Company, role, years. Nothing else.

    This was a reverse-chronological history with a note under every job,
    a place, and a row of linked case studies -- the longest block on the
    page. The notes said in prose what the case studies say properly one
    click away, so they went and the link stayed.

    A company whose name IS a case study links straight to it. A company
    that ran more than one, and whose own name has no page, carries them
    in parentheses instead: "T-ledger (Konnect, Fissa3)". That rule is
    what produces the four rows without a special case for any of them.

    Years are hyphenated, not en-dashed. The brief wrote "2024-now" with
    an en dash; every year on the site is a hyphen, and TestNoEmDashes
    bans en dashes in anything a visitor can see.
    """
    roles = SITE.get("experience") or []
    if not roles:
        return ""
    rows = []
    for job in roles:
        company = job.get("company", "")
        linked = [index[s] for s in job.get("projects", []) if s in index]
        own = next((x for x in linked if x["title"] == company), None)
        if own:
            name = '<a href="projects/%s">%s</a>' % (e(own["slug"]), e(company))
        elif linked:
            inner = ", ".join('<a href="projects/%s">%s</a>'
                              % (e(x["slug"]), e(x["title"])) for x in linked)
            name = "%s (%s)" % (e(company), inner)
        else:
            name = e(company)
        rows.append(
            '        <li class="job">'
            '<span class="job__company">%s</span>'
            '<span class="job__role">%s</span>'
            '<span class="job__years">%s</span>'
            '</li>' % (name, e(job.get("role", "")), e(job.get("years", ""))))
    return """
    <section class="band shell band--jobs" aria-labelledby="experience">
      <h2 id="experience">%s</h2>
      <ul class="jobs">
%s
      </ul>
    </section>
""" % (e(SITE.get("experienceHeading", "Experience")), "\n".join(rows))


def values_block():
    """How I work: three lines, each a claim and its consequence.

    It was "Values I believe in": an intro paragraph, numbered counters
    and a longer body under each. The numbers implied a ranking that was
    never meant, and the intro explained what the three items already
    say.
    """
    block = SITE.get("values") or {}
    items = [i for i in block.get("items", [])
             if usable(i.get("label")) and usable(i.get("body"))]
    if not items:
        return ""
    rows = "\n".join(
        '        <li class="value">'
        '<strong class="value__label">%s</strong> '
        '<span class="value__body">%s</span></li>'
        % (e(i["label"]), e(i["body"])) for i in items)
    return """
    <section class="band shell band--values" aria-labelledby="values">
      <h2 id="values">%s</h2>
      <ul class="values">
%s
      </ul>
    </section>
""" % (e(block.get("heading", "How I work")), rows)


def build_about(index):
    """About: the headline, one paragraph, the jobs, the tools, how I work.

    478 words before this. Four paragraphs of intro, a "Six years and four
    companies" line, a note under every job, three grouped tool lists and
    a numbered values section with its own introduction.

    The portrait went with them. It is the same photograph the homepage
    hero now opens with, one click away, and this page is a page of words.
    """
    out = [head("About - %s" % SITE["name"],
                page_description("about"),
                image=SITE.get("shareImage") or SITE["profileImage"],
                page_url="about",
                nav_current="about",
                og_type="profile",
                image_alt="%s - %s, %s" % (SITE["name"], SITE["title"],
                                           SITE.get("location", "")))]
    intro = SITE.get("aboutIntro") or {}
    heading = intro.get("heading") or "About"
    # No <br> between the lines: .mask and .mask__in are both display:block,
    # so a <br> between two of them renders a phantom empty line box.
    intro_heading = "".join(masked(line) for line in heading.split("\n"))
    intro_body = "\n        ".join(
        "<p>%s</p>" % e(x) for x in intro.get("paragraphs", []) if usable(x))

    # Chips with the real marks, not a line of names.
    #
    # The About rewrite flattened this to "Figma \u00b7 Framer \u00b7 ..." because
    # the brief capped the page at 160 words and the toolkit was three
    # labelled groups costing about sixteen. The flattening threw out the
    # logos with the labels, which was the wrong half to lose: a mark is
    # an image, so it costs the budget NOTHING, and a row of marks is
    # read in one glance where a list of names has to be read.
    #
    # Same seven tools, same seven words. tool_chips supplies the mark
    # when assets/tools/<slug> exists and a monogram when it does not,
    # and it is the same function the case studies use, so the two
    # cannot drift.
    tools = SITE.get("tools") or []
    tools_html = ""
    if tools:
        tools_html = """
    <section class="band shell band--tools" aria-labelledby="tools">
      <h2 id="tools">%s</h2>
      %s
    </section>
""" % (e(SITE.get("toolsHeading", "Tools")), tool_chips(tools))

    # The same two actions as everywhere else, with the two documents a
    # reader of this page actually goes looking for underneath them.
    cv_link = ('<a href="%s%s"%s>CV (PDF)%s</a>'
               % (e(SITE["cv"]), asset_v(SITE["cv"]), NEW_TAB, NEW_TAB_NOTE)
               ) if SITE.get("cv") else ""
    linkedin = next((l for l in SITE.get("links", [])
                     if "linkedin" in l.get("label", "").lower()), None)
    li_link = ('<a href="%s"%s>%s%s</a>'
               % (e(linkedin["url"]), NEW_TAB, e(linkedin["label"]), NEW_TAB_NOTE)
               ) if linkedin else ""
    small = " ".join(x for x in (cv_link, li_link) if x)
    small_html = ('\n      <p class="about__small">%s</p>' % small) if small else ""

    out.append(f"""
    <article class="shell about">
      <h1 class="about__statement">{intro_heading}</h1>
      <div class="about__intro prose">
        {intro_body}
      </div>
    </article>
{experience_list(index)}{tools_html}{values_block()}
    <section class="band shell band--close">
      <h2 class="band__close">{e(SITE.get("closingLine", "Have something in mind?"))}</h2>
      {actions_row()}{small_html}
    </section>
""")
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
        "%s - %s" % (project["title"], SITE["name"]),
        # summary is body copy — 3-4 sentences, up to 346 chars. Google cuts at
        # ~155, so a dedicated description is written for the slot.
        project.get("description") or project["summary"],
        depth=1,
        image=og_img,
        page_url="projects/%s" % project["slug"],
        # A case study is a written piece, not a site. og:type was hardcoded
        # "website" on all twelve pages.
        og_type="article",
        image_alt="%s - %s" % (project["title"], project["tagline"])
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
    # §9.F of the taste skill bans section-number eyebrows outright: "if the
    # user can count, they don't need the label". The headers read
    # "01 · Product · DeepPCB" and the number carried nothing the ordered
    # table of contents beside them does not already carry. The phase stays,
    # because the same rule asks eyebrows to NAME the topic in plain
    # language, which "Product" / "System" / "States" does.
    #
    # The flag is kept rather than deleted: a section with no phase then
    # renders no eyebrow at all, which is the behaviour this guards.
    numbered = False

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
    pages = ["work", "about"] + [
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


#: What the homepage word budget does NOT count, beyond the nav and footer.
#:
#: The brief excludes project names. It does not excuse tags or years, so
#: those are counted. js-copy-fallback is the mailto twin of the copy
#: button: it is in the DOM for a visitor with no Clipboard API and is
#: display:none for everyone else, so counting it would charge the page
#: for words almost nobody sees.
HOME_NOT_COPY = frozenset({"card__name", "more-work__name", "js-copy-fallback"})


def body_words(path, drop=frozenset()):
    """Visible words on a built page, excluding the chrome.

    The brief caps the homepage at 60 words of body copy and the about
    page at 160, so the build counts them and the test asserts them --
    a budget nobody measures is a budget nobody keeps.

    Dropped: the nav, the footer, anything hidden from sight, and any
    class named by the caller. The homepage passes its project names,
    which the brief excludes from the count.
    """
    from html.parser import HTMLParser

    class Counter(HTMLParser):
        SKIP = {"script", "style", "nav", "footer", "header", "head"}

        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack, self.depth, self.words = [], 0, []

        def handle_starttag(self, tag, attrs):
            if tag in ("br", "img", "input", "meta", "link", "hr", "source"):
                return
            cls = (dict(attrs).get("class") or "").split()
            hide = tag in self.SKIP or "visually-hidden" in cls or any(c in drop for c in cls)
            self.stack.append((tag, hide))
            if hide:
                self.depth += 1

        def handle_endtag(self, tag):
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    self.depth -= sum(1 for _, h in self.stack[i:] if h)
                    del self.stack[i:]
                    return

        def handle_data(self, data):
            if self.depth == 0:
                self.words += re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019@./+-]*", data)

    c = Counter()
    c.feed(Path(path).read_text(encoding="utf-8"))
    return len(c.words)


def main():
    projects = load_projects()
    n_vars = write_tokens_css()
    build_index(projects)
    build_about(by_slug(projects))
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
    sel = SITE.get("sections", {}).get("selected", {})
    print("index.html   %d rows, %d words of body copy"
          % (len(sel.get("items", [])),
             body_words(ROOT / "index.html", drop=HOME_NOT_COPY)))
    print("about.html   %d jobs, %d values, %d words"
          % (len(SITE.get("experience", [])),
             len((SITE.get("values") or {}).get("items", [])),
             body_words(ROOT / "about.html", drop={"js-copy-fallback"})))
    print("projects/    %d pages, %d figures" % (len(projects), imgs))
    if n_urls:
        print("sitemap.xml  %d URLs, robots.txt written" % n_urls)
    else:
        print('sitemap.xml  skipped — set "url" in site.json to enable')


if __name__ == "__main__":
    main()
