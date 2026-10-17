#!/usr/bin/env python3
"""Build-output tests. Run: python3 tools/test_build.py

The site ships with no dependencies and no test framework, so these use
stdlib unittest and assert against the real generated HTML.

build.py is run as a SUBPROCESS rather than imported: it reads site.json
into a module global at import time (build.py:22), so an in-process import
would test a stale copy of the very file most of these tests change.
"""
import html
import json
import pathlib
import re
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).parent.parent.resolve()


def run_build():
    """Run build.py, returning stdout. Raises with both streams on failure."""
    proc = subprocess.run(
        [sys.executable, "build.py"], cwd=str(ROOT),
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(
            "build.py exited %d\n--- stdout ---\n%s\n--- stderr ---\n%s"
            % (proc.returncode, proc.stdout, proc.stderr))
    return proc.stdout


class BuildCase(unittest.TestCase):
    """Base: build once for the whole class, expose the artefacts."""

    @classmethod
    def setUpClass(cls):
        cls.stdout = run_build()
        cls.site = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))

    def html(self, name):
        return (ROOT / name).read_text(encoding="utf-8")

    def content(self, folder):
        path = ROOT / "projects" / folder / "content.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def live_projects(self):
        """Every project that still ships, as (folder, parsed content).

        `"published": false` retires one without deleting it, so the
        folder and its content.json stay on disk and a plain glob still
        finds them. Several tests used that glob to decide which pages to
        open, and started erroring on files the build no longer writes the
        moment a project was retired. This is the single answer to "which
        projects ship".
        """
        out = []
        for path in sorted((ROOT / "projects").glob("*/content.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("published") is False:
                continue
            out.append((path.parent.name, data))
        return out


class TestSelectedWork(BuildCase):
    """Three cards, in a stated order, and nothing retired among them.

    This replaces TestHomepageTiers, which asserted a two-band system --
    "full-time jobs" above "everything else", each band a different tier
    of the same component. The homepage shows three cards and a line of
    two more now, so the tiers, the bands and the interleaving rules they
    protected have no subject left.

    What survives is the part that was never about tiers: the order is
    deliberate, a project appears once, and a retired project appears
    nowhere.
    """

    def selected(self):
        sel = self.site.get("sections", {}).get("selected") or {}
        self.assertTrue(sel.get("items"), "site.json lists no selected work")
        return sel

    def test_instadeep_is_the_first_card(self):
        """The current job leads. A visitor reads the first one."""
        slugs = [i["slug"] for i in self.selected()["items"]]
        self.assertEqual(slugs[0], "instadeep",
                         "the first card is %s, not InstaDeep" % slugs[0])

    def test_the_index_lists_every_live_project(self):
        """Three cards and a "More work" footnote became one list.

        The split existed because a 1152x720 cover card is expensive and
        three was all that fit. A row costs a line, so nothing has to be
        relegated any more -- and a project that is good enough to have a
        case study is good enough to appear in the index.
        """
        listed = [i["slug"] for i in self.selected()["items"]]
        live = sorted(d["slug"] for _, d in self.live_projects())
        self.assertEqual(sorted(listed), live,
                         "the index and the published projects disagree")


    def test_a_row_says_what_the_project_was(self):
        """Each row carries a line, a domain and a year -- and takes all
        three from the project itself.

        The homepage used to author its own tag and years per project,
        which is the same fact written in two files. The row reads the
        tagline and the meta the case study already has, so the two
        cannot drift.
        """
        page = self.html("index.html")
        for _, data in self.live_projects():
            with self.subTest(slug=data["slug"]):
                row = re.search(
                    r'<li class="index__row">.*?projects/%s".*?</li>'
                    % re.escape(data["slug"]), page, re.S)
                self.assertIsNotNone(row, "%s has no row" % data["slug"])
                body = row.group(0)
                self.assertIn(html.escape(data["tagline"], quote=True), body,
                              "%s's row does not carry its tagline" % data["slug"])
                for cls in ("index__domain", "index__year", "index__num"):
                    self.assertIn(cls, body)


    def test_no_project_is_both_a_card_and_a_footnote(self):
        sel = self.selected()
        cards = {i["slug"] for i in sel["items"]}
        more = set(sel.get("more", []))
        self.assertFalse(cards & more,
                         "%s is both a card and in the More work line"
                         % ", ".join(sorted(cards & more)))

    def test_every_linked_project_is_live(self):
        """A card pointing at a retired project is a 404 on the homepage."""
        live = {d["slug"] for _, d in self.live_projects()}
        sel = self.selected()
        for slug in [i["slug"] for i in sel["items"]] + list(sel.get("more", [])):
            with self.subTest(slug=slug):
                self.assertIn(slug, live, "%s is linked but not published" % slug)

    def test_retired_work_is_gone_from_every_page(self):
        """Kept from the class this replaces, and widened.

        It used to check two names against the band lists in site.json.
        It now checks them against the rendered HTML of every page, which
        is where a stale link would actually hurt.
        """
        names = ["pharmadrive", "undrive"]
        pages = ["index.html", "work.html", "about.html"]
        pages += ["projects/%s.html" % d["slug"] for _, d in self.live_projects()]
        for name in names:
            for page in pages:
                with self.subTest(name=name, page=page):
                    self.assertNotIn(name, self.html(page).lower(),
                                     "%s still mentions %s" % (page, name))

    def test_the_work_anchor_survives(self):
        """#work is linked from outside the site and from old posts."""
        self.assertIn('id="work"', self.html("index.html"))

class TestHeroPositioning(BuildCase):
    """The hero must not claim AI is the whole practice.

    Asserted as a rendered-output property, not a string match on site.json:
    what matters is what the visitor reads. heroStatement is checked for the
    breadth signal rather than exact wording, so the owner can rewrite the
    copy without breaking the test.
    """



    def test_the_visible_claim_is_a_real_h1(self):
        """The regression this redesign exists to prevent coming back.

        The marquee hero's only h1 was `visually-hidden` and its three rows
        were aria-hidden by construction, so the first readable sentence on
        the site sat 760px down the page -- a first screen that was striking
        and silent about what its owner does. Both homepages in the brief
        (petradesigns.io, sandeep.design) spend their h1 on the claim.
        """
        page = self.html("index.html")
        # A newline in heroClaim is an author's line break and renders as
        # its own .claim__line span, so the rendered h1 is not a
        # character-for-character copy of the source string. Compare line
        # by line instead. The last line carries the selection frame and
        # is marked for it; everything else is a plain line.
        claim = self.site["heroClaim"]
        lines = claim.split("\n")
        rendered = "".join(
            '<span class="claim__line%s">%s</span>'
            % (" claim__line--built" if i == len(lines) - 1 else "",
               html.escape(l, quote=True))
            for i, l in enumerate(lines))
        self.assertIn('<h1 class="opening__claim">%s</h1>' % rendered, page,
                      "the homepage h1 is no longer the visible claim")
        # The spans stack as blocks, so a <br> between them would render a
        # phantom empty line box between every pair.
        self.assertNotIn("<br>", re.search(
            r'<h1 class="opening__claim">.*?</h1>', page, re.S).group(0),
            "the claim stacks with blocks; a <br> adds a phantom line")
        h1s = re.findall(r"<h1[^>]*>", page)
        self.assertEqual(len(h1s), 1, "expected exactly one h1, found %r" % h1s)
        self.assertNotIn("visually-hidden", h1s[0],
                         "the homepage h1 is hidden again: %r" % h1s[0])


class TestContentColumnAlignment(BuildCase):
    """The hero statement must share the site's content column.

    It did not. `.hero__statement` was a single <p class="hero__statement
    shell"> that also declared `margin: 0` and `max-width: 46ch`. Both
    override .shell -- which is the entire alignment mechanism, supplying
    `max-width: var(--max-width)` and `margin-inline: auto`. On an
    absolutely-positioned box with `inset-inline: 0` the result was a
    viewport-flush element: measured at 1440px wide, its text began at 24px
    while the nav, tagline, band headings, cards and footer all began at
    144px. The one sentence a recruiter actually reads was the one element
    120px out of line.

    Geometry needs a browser, so these tests pin the structural contract
    that produces it instead: a .shell wrapper for position and column, an
    inner element for the measure. Verified by measurement at 375, 1024 and
    1440px -- all content sharing one left edge at each.

    The element moved in the redesign -- `.hero__statement` became `.opening`,
    a section in normal flow rather than a box absolutely positioned over a
    marquee -- but the contract did not, and it is still the easiest thing
    on the page to get wrong. A rebuilt hero reintroduced this exact bug
    once already, putting the opening at left edge 0 against 32px for
    everything else, and this class is what caught it.
    """

    def test_the_opening_sits_in_one_gutter_not_two(self):
        """.hero-card is gone; .shell is still the only gutter.

        The hero used to be a card inside the shell, and the failure this
        guards against survived that change: if .opening carried .shell
        itself while sitting inside one, the gutter applied twice and the
        hero indented further than everything below it.
        """
        page = self.html("index.html")
        self.assertRegex(
            page,
            r'<div class="shell hero-band">\s*<section class="opening">',
            "the opening is no longer directly inside its .shell wrapper")
        self.assertNotIn('<section class="opening shell">', page,
                         "the opening carries .shell AND sits in one, so the "
                         "gutter is applied twice")

    def test_the_page_keeps_exactly_two_left_edges(self):
        """A card insets its own content. That is fine; drifting is not.

        Measured at 1024px: card outer edges (the hero panel, the about
        card) sit on the page column at 24, and their content sits one
        padding step in at 56, as does every other card's. Content that is
        not in a card stays at 24. Two edges, each internally consistent.

        This is asserted structurally rather than geometrically, because the
        way it goes wrong is a card being given a different padding step
        from the others -- which produces a third edge nobody chose.
        """
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        pads = {}
        for sel in (".hero-card", ".aboutblock__card", ".about__card"):
            block = re.search(re.escape(sel) + r"\s*\{([^}]*)\}", css)
            self.assertIsNotNone(block, "no %s rule" % sel)
            pad = re.search(r"padding:\s*var\(--(space-\d+)\)", block.group(1))
            self.assertIsNotNone(pad, "%s has no single-step padding" % sel)
            pads[sel] = pad.group(1)
        self.assertEqual(
            len(set(pads.values())), 1,
            "the cards inset their content by different amounts (%s), which "
            "puts their contents on different left edges" % pads)

    def test_measure_lives_on_the_inner_element(self):
        page = self.html("index.html")
        # The claim and the line under it each need their own measure, and
        # each is a separate chance to put it on the wrapper instead.
        # .opening__support was the third; the brief removed it.
        self.assertIn('class="opening__claim"', page)
        self.assertIn('class="opening__meta"', page)
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        for sel in (".opening__claim {", ".opening__meta {"):
            self.assertIn(sel, css, "%s has no rule of its own" % sel)

    def test_statement_does_not_reintroduce_margin_or_max_width(self):
        """The regression is specifically these two properties coming back."""
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        block = css.split(".opening {", 1)[1].split("}", 1)[0]
        for prop in ("margin", "max-width"):
            self.assertNotIn(prop, block,
                             ".opening declares %s, which overrides .shell and "
                             "breaks the content column" % prop)

    def test_shell_still_defines_the_column(self):
        """If .shell stops centring, every page moves, not just the hero.

        The inline padding is matched on --gutter rather than on the whole
        declaration: it now adds the device safe-area insets alongside the
        gutter, so pinning the literal string would fail the moment a real
        fix touched it -- which is exactly what happened when it did. What
        has to hold is that the gutter is still what sets the column's
        edges, not the precise expression it sits in.
        """
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        block = css.split(".shell {", 1)[1].split("}", 1)[0]
        self.assertIn("max-width: var(--max-width)", block)
        self.assertIn("margin-inline: auto", block)
        inline = re.search(r"padding-inline:([^;]+);", block)
        self.assertIsNotNone(inline, ".shell no longer sets padding-inline")
        self.assertIn("var(--gutter)", inline.group(1),
                      "the content column's edge is no longer the gutter: %r"
                      % inline.group(1).strip())

    def test_no_page_claims_specialising_in_ai(self):
        for page in ("index.html", "about.html"):
            self.assertNotIn("specialising in AI", self.html(page),
                             "%s still narrows the practice to AI" % page)


class TestCV(BuildCase):
    """The CV has to be a real text document, not a picture of one.

    The previous CV was a Figma export using Type3 fonts. Type3 glyphs are
    drawn procedures rather than characters, and its encoding was wrong on
    top of that: decoded with the file's own ToUnicode tables the body text
    came out as pure noise. Recruiters copy-paste from CVs and most
    applications pass through an ATS, so a CV nothing can read is a CV that
    silently fails before a human sees it. It was also 742KB.

    The replacement is a single A4 page with subset TrueType fonts and one
    ToUnicode table per font; its body text decodes cleanly. 55KB.

    One known wart in the current document, left as a note rather than a
    test because it is cosmetic to a human and marginal to a parser: the
    list bullets are drawn in non-embedded Helvetica, which carries no
    ToUnicode table, so each bullet extracts as U+007F rather than a real
    bullet character. Every other glyph -- including the accents in
    "Ingenierie" and "Multimedia" and the middot separators -- maps
    correctly.

    These tests pin the two properties worth keeping, not the wording: the
    document must stay machine-readable, and the link must stay versioned.
    """

    def cv_path(self):
        rel = self.site.get("cv")
        self.assertTrue(rel, "site.json no longer declares a cv")
        path = ROOT / rel
        self.assertTrue(path.is_file(), "%s is missing" % rel)
        return path

    def test_it_is_actually_a_pdf(self):
        self.assertEqual(self.cv_path().read_bytes()[:5], b"%PDF-",
                         "the CV is not a PDF")

    def unicode_mappings(self):
        """How many glyph codes the document can map back to characters."""
        import zlib
        raw = self.cv_path().read_bytes()
        mappings = 0
        for m in re.finditer(rb"stream\r?\n", raw):
            start = m.end()
            end = raw.find(b"endstream", start)
            if end < 0:
                continue
            try:
                data = zlib.decompress(raw[start:end])
            except Exception:
                continue
            if b"beginbfchar" in data or b"beginbfrange" in data:
                mappings += len(re.findall(rb"<[0-9A-Fa-f]+>\s*<[0-9A-Fa-f]+>", data))
        return mappings

    def test_it_does_not_use_type3_fonts(self):
        """Back to a flat ban, because the file that needed the exception
        is gone.

        Type3 draws each glyph as a procedure. Without a ToUnicode table
        that is a picture of words, which is what made the ORIGINAL CV
        unreadable and earned this rule in the first place.

        It was narrowed once, for a real reason: the CV supplied on
        2026-10-16 had 14 Type3 references AND 238 glyph-to-unicode
        mappings, and extracting it returned 4,787 clean characters. A
        flat ban would have rejected a document whose text was provably
        fine, so the rule became "Type3 only with a dense mapping table".

        That document has been replaced by one with no Type3 at all, so
        the exception has nothing left to protect and the stricter rule
        comes back. A crude ATS parser can skip a Type3 font it could
        have read; not shipping one is strictly safer than arguing about
        whether this one is readable.
        """
        raw = self.cv_path().read_bytes()
        self.assertNotIn(b"/Type3", raw,
                         "the CV uses Type3 fonts again -- some ATS parsers "
                         "skip them even when a ToUnicode table makes the "
                         "text recoverable")


    def test_its_text_can_be_mapped_back_to_characters(self):
        """Embedded fonts are useless without a ToUnicode table."""
        mappings = self.unicode_mappings()
        self.assertGreater(mappings, 50,
                           "the CV carries %d glyph-to-unicode mappings, too "
                           "few for a page of text to be extractable" % mappings)

    def test_it_is_a_reasonable_download(self):
        """The old one was 742KB, heavier than every page on the site."""
        size = self.cv_path().stat().st_size
        self.assertLess(size, 400_000,
                        "the CV is %d bytes; a CV should not be the heaviest "
                        "thing a visitor downloads" % size)

    def test_every_cv_link_opens_in_a_new_tab(self):
        """Clicking the CV used to replace the portfolio with a PDF.

        The tab navigated to the document, so the visitor got a browser PDF
        viewer where the site had been, with the back button as the only
        way back to it. A recruiter who opens the CV is the one visitor you
        least want to have left the page.

        Announced as well as opened. A new tab is a change of context, and
        one that happens without warning is disorienting if you cannot see
        that a tab appeared -- the back button simply stops going back
        (WCAG 3.2.5). The note rides in the accessible name and nowhere on
        screen, because for everyone else the new tab IS the cue.

        Checked on every page that links it, not just the obvious three:
        the footer carries the CV on all nine, and the footer is generated
        once, so one missed branch there is eight broken links.
        """
        base = re.escape(self.site["cv"].split("/")[-1])
        pattern = re.compile(r"<a\b([^>]*%s[^>]*)>(.*?)</a>" % base, re.S)
        pages = ["index.html", "about.html", "work.html"]
        pages += ["projects/%s.html" % d["slug"] for _, d in self.live_projects()]
        found = 0
        for name in pages:
            links = pattern.findall(self.html(name))
            self.assertTrue(links, "%s links no CV at all" % name)
            for attrs, body in links:
                found += 1
                with self.subTest(page=name, attrs=attrs.strip()[:60]):
                    self.assertIn('target="_blank"', attrs,
                                  "%s has a CV link that replaces the page" % name)
                    self.assertIn('rel="noopener"', attrs,
                                  "%s opens the CV in a new tab without "
                                  "rel=noopener" % name)
                    self.assertIn("opens in a new tab", body,
                                  "%s opens a new tab without telling anyone "
                                  "who cannot see it happen" % name)
        self.assertGreaterEqual(found, len(pages),
                                "expected at least one CV link per page, "
                                "found %d across %d pages" % (found, len(pages)))

    def test_every_cv_link_is_versioned(self):
        """The CV is replaced under the same name, so caches serve the old one.

        Unlike other assets it is not renamed when it changes, which makes
        the content hash the only thing forcing a returning visitor -- or a
        recruiter who opened the page last week -- to get the new document.
        """
        rel = re.escape(self.site["cv"])
        for page in ("index.html", "about.html"):
            markup = self.html(page)
            self.assertIn(self.site["cv"], markup,
                          "%s does not link the CV at all" % page)
            for href in re.findall(r'href="([^"]*%s[^"]*)"' % rel, markup):
                self.assertRegex(href, r"\?v=[0-9a-f]+",
                                 "%s links the CV without a version: %s"
                                 % (page, href))


class TestFontFamilies(BuildCase):
    """Three downloaded families. Not four.

    Every extra family is a separate network request on first paint and a
    fourth voice in a type system that only needs three, and families creep
    in one plausible-looking @font-face at a time. The count is currently
    three; this makes that a rule rather than a coincidence.

    Measured with document.fonts across every page type rather than read
    off the CSS, because @font-face is lazy: eight weight files are declared
    and only five are ever fetched. Weights are a separate question from
    families and are deliberately not capped here -- a family earns its
    download once, and extra weights of a family already being fetched are
    much cheaper than a new family.

    --font-mono is excluded on purpose. It is a system stack -- 'SF Mono',
    ui-monospace, Menlo, monospace -- so it costs no request and ships no
    file. If it is ever pointed at a webfont, the first test below starts
    counting it.
    """

    MAX_FAMILIES = 3

    #: Generic CSS families plus the system faces this project names. A token
    #: resolving to one of these downloads nothing.
    SYSTEM = {
        "sf mono", "ui-monospace", "menlo", "monospace", "sans-serif",
        "serif", "system-ui", "-apple-system", "blinkmacsystemfont",
        "segoe ui", "helvetica", "arial", "arial narrow",
        "haettenschweiler", "cursive", "fantasy",
    }

    def faces(self):
        """{family: [weights]} from every @font-face block."""
        css = (ROOT / "assets" / "fonts.css").read_text(encoding="utf-8")
        out = {}
        for body in re.findall(r"@font-face\s*\{([^}]*)\}", css, re.S):
            fam = re.search(r"font-family:\s*['\"]([^'\"]+)['\"]", body)
            self.assertIsNotNone(fam, "an @font-face block names no family")
            weight = re.search(r"font-weight:\s*(\d+)", body)
            out.setdefault(fam.group(1), []).append(
                weight.group(1) if weight else "normal")
        return out

    def test_at_most_three_downloaded_families(self):
        fams = self.faces()
        self.assertLessEqual(
            len(fams), self.MAX_FAMILIES,
            "%d webfont families are declared, over the %d the type system "
            "is meant to use: %s" % (len(fams), self.MAX_FAMILIES,
                                     ", ".join(sorted(fams))))

    def test_no_token_smuggles_in_a_fourth_family(self):
        """A --font-* token can name a family nothing declares.

        That is the sneaky version of the same problem: the family is not in
        fonts.css, so the count above still reads three, but the browser
        goes looking for it and falls back to whatever is installed --
        meaning the site renders differently per machine with no warning.
        """
        declared = {f.lower() for f in self.faces()}
        tokens = (ROOT / "assets" / "tokens.css").read_text(encoding="utf-8")
        for name, value in re.findall(r"(--font-[a-z]+):\s*([^;]+);", tokens):
            first = value.split(",")[0].strip().strip("'\"").lower()
            self.assertTrue(
                first in declared or first in self.SYSTEM,
                "%s leads with %r, which is neither declared in fonts.css "
                "nor a system face -- it would silently fall back" % (name, first))

    def test_every_declared_family_is_actually_referenced(self):
        """A family nobody uses is a dead @font-face taking up the budget."""
        tokens = (ROOT / "assets" / "tokens.css").read_text(encoding="utf-8").lower()
        styles = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8").lower()
        for fam in self.faces():
            self.assertTrue(
                fam.lower() in tokens or fam.lower() in styles,
                "%r is downloaded but referenced nowhere, so it spends one of "
                "the %d family slots on nothing" % (fam, self.MAX_FAMILIES))

    def test_every_declared_face_has_its_file(self):
        """A missing file falls back silently -- no error, just wrong type."""
        css = (ROOT / "assets" / "fonts.css").read_text(encoding="utf-8")
        for src in re.findall(r"url\(['\"]?([^'\")]+)['\"]?\)", css):
            rel = src.lstrip("./").split("?", 1)[0]
            if rel.startswith("assets/"):
                path = ROOT / rel
            else:
                path = ROOT / "assets" / rel
            self.assertTrue(path.is_file(),
                            "fonts.css points at %s, which is not on disk" % src)


class TestFavicon(BuildCase):
    """The mark: the owner's portrait, cropped and scaled DOWN to each size.

    This was an "AY" monogram re-set in Anton. The owner asked for their
    face instead, so tools/make-favicon.py now crops
    site/_src/favicon-portrait.webp and scales down from 860px.

    The shape rules did not change with the source and are the part worth
    guarding: the browser icons are a transparent disc, and the touch icon
    is an opaque square because iOS composites onto black before masking.
    Both are asserted below, because both fail silently -- in a tab strip
    and on someone's home screen, which is to say nowhere anyone looks
    during development.
    """

    @staticmethod
    def png_header(path):
        """(width, height, colour_type) straight out of IHDR."""
        raw = path.read_bytes()
        assert raw[:8] == b"\x89PNG\r\n\x1a\n", path
        w = int.from_bytes(raw[16:20], "big")
        h = int.from_bytes(raw[20:24], "big")
        return w, h, raw[25]

    def test_no_svg_icon_survives(self):
        """An SVG icon outranks a PNG in Chrome and Firefox.

        This is the whole reason the old favicon.svg had to go rather than
        just sit there: leaving it declared would have kept showing the
        previous mark in most browsers while every file on disk said the
        icon had been replaced. Silent, and only visible in a tab strip.
        """
        for page in ("index.html", "about.html",
                     "projects/steer.html"):
            markup = self.html(page)
            self.assertNotIn("favicon.svg", markup,
                             "%s still declares an SVG icon, which wins over "
                             "the PNG and shows the old mark" % page)
        self.assertFalse((ROOT / "assets" / "favicon.svg").exists(),
                         "assets/favicon.svg is back on disk")

    def test_the_three_sizes_exist_and_are_the_sizes_they_claim(self):
        for name, size in (("favicon-32.png", 32), ("favicon-192.png", 192),
                           ("apple-touch-icon.png", 180)):
            path = ROOT / "assets" / name
            self.assertTrue(path.is_file(), "assets/%s is missing" % name)
            w, h, _ = self.png_header(path)
            self.assertEqual((w, h), (size, size),
                             "assets/%s is %dx%d, not %dx%d" % (name, w, h, size, size))

    def test_the_touch_icon_is_opaque(self):
        """iOS composites a touch icon onto BLACK before masking it.

        A transparent corner therefore arrives as a black corner, and the
        white disc would sit in a dark box on the home screen. So the touch
        icon alone is a full-bleed square with no alpha, and iOS applies its
        own rounding. Colour type 6 is RGBA, 2 is RGB.
        """
        _, _, colour_type = self.png_header(ROOT / "assets" / "apple-touch-icon.png")
        self.assertNotIn(colour_type, (4, 6),
                         "apple-touch-icon.png carries an alpha channel; iOS "
                         "will render its transparent corners black")

    def test_the_browser_icons_keep_their_transparency(self):
        """The disc is a disc -- square corners would show as white boxes."""
        for name in ("favicon-32.png", "favicon-192.png"):
            _, _, colour_type = self.png_header(ROOT / "assets" / name)
            self.assertIn(colour_type, (4, 6),
                          "assets/%s lost its alpha channel, so the disc now "
                          "sits in a white square" % name)

    def test_every_page_declares_them_at_the_right_depth(self):
        for page, up in (("index.html", ""), ("about.html", ""),
                         ("projects/steer.html", "../")):
            markup = self.html(page)
            for name in ("favicon-32.png", "favicon-192.png",
                         "apple-touch-icon.png"):
                self.assertIn('href="%sassets/%s' % (up, name), markup,
                              "%s does not reference %s correctly" % (page, name))

    def test_the_icons_are_cache_busted(self):
        """Browsers cache a favicon far past any sane TTL.

        Without a content hash in the URL, a visitor who has been to the
        site before keeps the old mark more or less indefinitely. This
        project has already lost time to exactly that, four separate times,
        on other assets.
        """
        markup = self.html("index.html")
        for name in ("favicon-32.png", "favicon-192.png", "apple-touch-icon.png"):
            self.assertRegex(markup, r'assets/%s\?v=[0-9a-f]+' % re.escape(name),
                             "%s is declared without a version, so a returning "
                             "visitor keeps the old icon" % name)

    def test_the_generator_is_committed(self):
        """The mark is derived, so the derivation has to be re-runnable."""
        gen = ROOT / "tools" / "make-favicon.py"
        self.assertTrue(gen.is_file(), "tools/make-favicon.py is missing")
        src = gen.read_text(encoding="utf-8")
        self.assertIn("favicon-portrait.webp", src,
                      "the generator no longer names its source image")
        self.assertRegex(src, r"CROP = \(\d+, \d+, \d+\)",
                         "the crop box is what frames the face; it has to "
                         "stay a named constant, not a number inside a call")

    def test_the_source_photograph_is_committed(self):
        """A derived mark is only re-runnable if its source ships with it.

        The generator reads one file. If it is not in the repo, the three
        PNGs become unreproducible the moment anyone wants the crop moved
        by ten pixels.
        """
        src = ROOT / "site" / "_src" / "favicon-portrait.webp"
        self.assertTrue(src.is_file(),
                        "site/_src/favicon-portrait.webp is missing, so the "
                        "icons cannot be regenerated")
        self.assertGreater(src.stat().st_size, 10_000,
                           "the source looks like a placeholder")

    def test_the_tab_icon_stays_small(self):
        """favicon-32 is fetched on every first visit; the others are not.

        A photograph costs more bytes than two letterforms, and the 192 and
        180 are only fetched when someone adds the site to a home screen.
        The 32 is the one that is actually on the critical path, so it is
        the one with a ceiling.
        """
        size = (ROOT / "assets" / "favicon-32.png").stat().st_size
        self.assertLess(size, 8_000,
                        "favicon-32.png is %d bytes; it loads on every first "
                        "visit" % size)


class TestCleanUrls(BuildCase):
    """/work and /about, not index.html#work.

    GitHub Pages serves any foo.html at /foo, which was already true and
    unused: /about returned the about page while every link on the site
    still said about.html, so nobody ever saw the clean form. Verified
    against the live host before building any of this -- /about and
    /projects/steer already returned 200, /work and /contact returned 404.

    The homepage is written twice, to index.html and work.html, with one
    canonical naming /work. A redirect at / would have been the tidier
    model on paper and the wrong one here: / is what people type and what
    gets shared, and on a static host the redirect would be a meta-refresh,
    so the most-shared URL on the site would flash a blank page. Two files
    of identical bytes and one canonical costs nothing at runtime.

    What this gave up: extensionless links do not resolve on file://, so
    the site can no longer be navigated by double-clicking index.html.
    Each page still renders completely from disk -- nothing fetches at
    runtime -- and the Portfolio case study was rewritten to say exactly
    that rather than keep claiming the whole site works from a filesystem.
    """

    PAGES = ("index.html", "work.html", "about.html")

    def test_the_homepage_is_byte_identical_at_both_urls(self):
        """If they drift, / and /work start showing different sites."""
        self.assertEqual(
            (ROOT / "index.html").read_bytes(),
            (ROOT / "work.html").read_bytes(),
            "index.html and work.html have diverged -- they are meant to be "
            "one page served at two addresses")

    def test_both_copies_name_work_as_the_canonical(self):
        """Two URLs, one canonical, or a crawler splits the page's ranking."""
        for page in ("index.html", "work.html"):
            self.assertIn(
                'rel="canonical" href="%s/work"' % self.site["url"].rstrip("/"),
                self.html(page),
                "%s does not canonicalise to /work" % page)

    def test_no_internal_link_anywhere_carries_a_page_extension(self):
        """The whole point: what shows in the address bar as you browse.

        Every page, not just the nav, and not just the four root pages --
        the homepage cards, the about page's employment history and the
        prev/next pager all link to case studies too. Asset hrefs are
        excluded: .css, .svg, .png, .pdf and .mp4 are files, and their
        extensions are real.

        The files on disk keep .html. That is what GitHub Pages needs in
        order to serve the extensionless form, so the rule is about links,
        never about filenames.
        """
        import glob, pathlib as pl
        pages = glob.glob(str(ROOT / "*.html")) + glob.glob(str(ROOT / "projects" / "*.html"))
        self.assertTrue(pages, "no built pages found")
        asset_ext = (".css", ".svg", ".png", ".jpg", ".webp", ".pdf",
                     ".mp4", ".ico", ".xml", ".json", ".txt")
        offenders = []
        for path in pages:
            rel = pl.Path(path).relative_to(ROOT)
            for href in re.findall(r'href="([^"]+)"', pl.Path(path).read_text(encoding="utf-8")):
                if href.startswith(("http", "mailto:", "#")):
                    continue
                bare = href.split("?", 1)[0].split("#", 1)[0]
                if bare.endswith(asset_ext):
                    continue
                if bare.endswith(".html"):
                    offenders.append("%s -> %s" % (rel, href))
        self.assertEqual(offenders, [],
                         "these internal links still carry .html: %s"
                         % ", ".join(offenders))

    def test_nested_pages_reach_the_clean_urls(self):
        """A project page is one level down, so every href needs ../.

        Contact dropped out of this list when the nav's button became
        "Book a call": the nav holds two page links now, and the third
        href goes to an absolute calendar URL that needs no prefix.
        """
        for slug in ("steer", "instadeep"):
            head = self.html("projects/%s.html" % slug).split("</header>", 1)[0]
            for target in ("work", "about"):
                self.assertIn('href="../%s"' % target, head,
                              "projects/%s.html cannot reach /%s" % (slug, target))

    def test_the_homepage_keeps_the_contact_anchor(self):
        """/contact is gone and #contact is what replaced it.

        The page existed to host the Cal embed. The embed is gone --
        see CAL_LINK in build.py -- and with it the only reason for a
        route whose whole content was a third-party iframe. The closing
        band carries the id, so every old #contact link still lands.
        """
        self.assertIn('id="contact"', self.html("index.html"),
                      "the homepage lost the #contact anchor old links use")
        self.assertFalse((ROOT / "contact.html").exists(),
                         "contact.html is back; the booker page was removed")


    def test_the_two_actions_have_one_source(self):
        """The loud ask appears on two pages and is emitted once.

        It was three: /contact carried the row without its booking
        button, because a button linking to the page you are reading is
        furniture. /contact has gone with the Cal embed it existed to
        hold, so the two that remain have to match byte for byte with
        nothing stripped.
        """
        def actions(page):
            m = re.search(r'<div class="actions[^"]*">(.*?)</div>',
                          self.html(page), re.S)
            self.assertIsNotNone(m, "%s has no actions row" % page)
            return m.group(1)
        self.assertEqual(actions("about.html"), actions("index.html"),
                         "/about's actions differ from the homepage's")


    def test_every_page_with_the_actions_has_exactly_one_h1(self):
        """The rank question the old contact band raised, asked properly.

        contact_band took a `level` argument because the same block was an
        h2 under the homepage's h1 and the h1 on /contact. There is no
        shared heading any more -- /contact's h1 is its own, and hidden,
        because the brief for that page is the two actions and nothing
        else. What still matters is that no page starts its heading order
        at h2.
        """
        for page in ("index.html", "about.html"):
            with self.subTest(page=page):
                self.assertEqual(len(re.findall(r"<h1[ >]", self.html(page))), 1,
                                 "%s does not have exactly one h1" % page)

    def test_the_preview_server_matches_the_host(self):
        """Local preview has to resolve URLs the way GitHub Pages does.

        `python3 -m http.server` looks for a file called exactly "work",
        finds nothing and 404s, so previewing with the stock server breaks
        every link in the nav while the deployed site is fine. That split
        is worse than either state on its own: it means testing something
        that is not what ships.

        It also has to be committed. The .gitignore carried a bare
        `serve.py`, which git matches at any depth, and it swallowed this
        file on the first attempt.
        """
        server = ROOT / "tools" / "serve.py"
        self.assertTrue(server.is_file(),
                        "tools/serve.py is missing -- local preview 404s on "
                        "every extensionless URL")
        src = server.read_text(encoding="utf-8")
        self.assertIn('".html"', src,
                      "the preview server no longer resolves extensionless "
                      "paths to .html")
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertNotIn("\nserve.py", ignore,
                         "an unanchored serve.py pattern is back in "
                         ".gitignore and will untrack tools/serve.py")

    def test_the_sitemap_lists_clean_urls_only(self):
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        base = self.site["url"].rstrip("/")
        for target in ("work", "about"):
            self.assertIn("<loc>%s/%s</loc>" % (base, target), sitemap)
        self.assertNotIn("<loc>%s/index.html</loc>" % base, sitemap,
                         "the sitemap lists both / and /work, which asks a "
                         "crawler to decide what the canonical decided")


class TestSafeAreas(BuildCase):
    """The page must own the whole phone screen, insets and all.

    Reported on a Dynamic Island iPhone: scrolling left page content
    visible in the strip above the sticky header. Measured off the
    screenshot -- 692px wide at a 2.168 ratio is a 393pt iPhone Pro, and
    the header's top edge sat 59.6 CSS px down, exactly that device's
    safe-area inset. The site had no safe-area handling and no
    viewport-fit, so Safari was deciding for it.

    These two halves only work together, which is why they are one class.
    viewport-fit=cover alone puts content under the notch and the home
    indicator -- it makes things worse on its own. The CSS insets alone do
    nothing, because iOS reports 0 for env() until viewport-fit is cover.

    Verified at 393x852 by overriding the four properties on :root to a
    real iPhone's values (59/21/34) and re-reading the computed styles: the
    header stayed pinned at top 0 while growing 76 -> 135, its nav moved
    24 -> 83 and so cleared the status bar, the column gained the notch
    inset, the hero lost the strip from its min-height and scroll-margin
    gained it. With no insets every one of those numbers is what it was
    before the change, so desktop and Android are untouched. Probed
    elementFromPoint across the whole 0-59 strip at three x positions with
    the page scrolled: header at every point.
    """

    ROOT_CSS = None

    def css(self):
        return (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")

    def rule(self, selector):
        css = self.css()
        self.assertIn(selector, css, "%s is gone" % selector)
        return css.split(selector, 1)[1].split("}", 1)[0]

    def test_every_page_opts_into_the_full_screen(self):
        """Without viewport-fit=cover iOS reports every inset as zero."""
        for page in ("index.html", "about.html", "projects/steer.html"):
            meta = re.search(r'<meta name="viewport" content="([^"]+)"',
                             self.html(page))
            self.assertIsNotNone(meta, "%s has no viewport meta" % page)
            self.assertIn("viewport-fit=cover", meta.group(1),
                          "%s does not cover the screen, so every env() "
                          "inset below resolves to 0 on iOS" % page)

    def test_the_four_insets_are_declared_with_zero_fallbacks(self):
        """A browser that reports nothing must get 0px, not an invalid calc."""
        block = self.rule(":root {")
        for side in ("top", "right", "bottom", "left"):
            decl = "--inset-%s: env(safe-area-inset-%s, 0px);" % (side, side)
            self.assertIn(decl, block,
                          "missing or fallback-less inset: expected %r" % decl)

    def test_the_header_pads_rather_than_offsets(self):
        """Padding keeps the blurred background covering the strip.

        margin-top would move the whole header down and leave the strip
        transparent -- which is the reported bug, just caused deliberately.
        """
        block = self.rule(".site-head {")
        self.assertIn("padding-top: var(--inset-top)", block,
                      "the header no longer clears the status bar")
        self.assertIn("top: 0", block,
                      "the header must stick to the real top of the screen")
        self.assertNotIn("margin-top", block,
                         "margin moves the header down and leaves the strip "
                         "uncovered, which is the bug this fixes")

    def test_the_column_clears_a_landscape_notch(self):
        """viewport-fit=cover creates this problem; .shell has to answer it."""
        inline = re.search(r"padding-inline:([^;]+);", self.rule(".shell {"))
        self.assertIsNotNone(inline)
        for side in ("left", "right"):
            self.assertIn("var(--inset-%s)" % side, inline.group(1),
                          "the content column does not clear the %s inset, "
                          "so the notch overlaps it in landscape" % side)

    def test_the_footer_clears_the_home_indicator(self):
        self.assertIn("var(--inset-bottom)", self.rule(".site-foot__inner {"),
                      "the footer sits under the home indicator")

    def test_anchors_still_land_below_the_taller_header(self):
        """The header grows by the inset, so the jump offset must too."""
        css = self.css()
        block = css.split("scroll-margin-top:", 1)[1].split(";", 1)[0]
        self.assertIn("var(--header-height)", block)
        self.assertIn("var(--inset-top)", block,
                      "jump targets do not account for the inset, so on a "
                      "notched phone every anchor lands under the header")

    def test_the_hero_stops_overflowing_by_the_inset(self):
        """100dvh now includes the strip the header occupies."""
        for block in re.findall(r"min-height: calc\(100dvh[^;]*;", self.css()):
            self.assertIn("var(--inset-top)", block,
                          "hero height ignores the inset and overflows by "
                          "it on a notched phone: %r" % block)

    def test_no_env_is_used_without_a_fallback(self):
        """A bare env() in a calc invalidates the whole declaration.

        Comments are stripped first. The first version of this scanned the
        raw file and flagged the prose in the block above, which discusses
        env() by name -- a failure that said nothing about the CSS.
        """
        code = re.sub(r"/\*.*?\*/", "", self.css(), flags=re.S)
        bare = [m for m in re.findall(r"env\([^)]*\)", code) if "," not in m]
        self.assertEqual(bare, [],
                         "env() without a fallback voids its declaration in "
                         "browsers that do not report insets: %s" % bare)


class TestTocHistory(BuildCase):
    """Jumping around the index must not hijack the Back button.

    Reported behaviour: open a case study, click through "On this page",
    then press Back -- and it retraces the sections one at a time instead
    of returning to the work. Measured in a browser before the fix: eight
    index links, eight history entries, nine Back presses to leave the
    page. After: zero and one.

    The cause is that a fragment link pushes a history entry, which is the
    right default for a document but wrong for a table of contents, where
    every entry is the same page at a different scroll offset.

    Behaviour needs a browser, so these pin the mechanism that produces it.
    Verified by measurement at 1440x900: eight clicks grew history.length
    by 0, the hash still tracked the section, and one Back returned to
    index.html.
    """

    def enhance(self):
        return (ROOT / "assets" / "enhance.js").read_text(encoding="utf-8")

    def toc_block(self):
        """Just the click handler, so a match elsewhere cannot stand in."""
        js = self.enhance()
        self.assertIn("targets.forEach", js, "the toc click handler is gone")
        return js.split("targets.forEach", 1)[1]

    def test_the_jump_replaces_rather_than_pushes(self):
        block = self.toc_block()
        self.assertIn("history.replaceState", block,
                      "the toc jump no longer replaces the history entry, so "
                      "Back walks the sections again")
        self.assertNotIn("pushState", block,
                         "the toc jump pushes a history entry")
        self.assertNotIn("location.hash =", block,
                         "assigning location.hash pushes an entry, which is "
                         "the whole bug")

    def test_keyboard_focus_follows_the_jump(self):
        """preventDefault cancels the browser's own focus move.

        Without replacing it, Tab after clicking an index item resumes from
        the link rather than the section, so a keyboard visitor is silently
        left at the top of the page they just navigated away from.
        """
        block = self.toc_block()
        self.assertIn("tabindex", block,
                      "the jump target is never made focusable")
        self.assertIn(".focus(", block, "focus is never moved to the section")
        self.assertIn("preventScroll", block,
                      "focus() without preventScroll fights the smooth "
                      "scroll and jumps the page")

    def test_modified_clicks_are_left_alone(self):
        """cmd/ctrl/shift-click opens a new tab. That is a navigation.

        Asserted as a whole early return, not as four names appearing
        somewhere in the block. The first version of this test only checked
        that the strings were present, and `if (false && e.metaKey || ...)`
        sailed straight through it -- the names were all still there while
        the guard did nothing. Matching the return makes the sabotage fail.
        """
        guard = re.search(
            r"if\s*\(\s*e\.metaKey\s*\|\|\s*e\.ctrlKey\s*\|\|"
            r"\s*e\.shiftKey\s*\|\|\s*e\.altKey\s*\)\s*return;",
            self.toc_block())
        self.assertIsNotNone(
            guard,
            "no early return on modified clicks -- cmd/ctrl/shift-click is "
            "swallowed instead of opening the section in a new tab")

    def test_a_plain_left_click_is_the_only_one_handled(self):
        """A middle click or a handler that already ran must pass through."""
        block = self.toc_block()
        self.assertIn("e.button !== 0", block,
                      "non-left clicks are being intercepted")
        self.assertIn("e.defaultPrevented", block,
                      "a click another handler already dealt with is being "
                      "handled a second time")
        self.assertIn("if (!history.replaceState) return;", block,
                      "a browser without replaceState should fall through to "
                      "the native jump, not get a broken preventDefault")

    def test_offset_and_easing_stay_in_the_stylesheet(self):
        """scrollIntoView takes no arguments on purpose.

        The header offset lives in scroll-margin-top and the easing in
        scroll-behavior, including the reduced-motion override. Passing
        options here would fork both decisions into a second place.
        """
        self.assertIn("t.el.scrollIntoView();", self.toc_block(),
                      "scrollIntoView is being passed options, which forks "
                      "the offset and easing away from the stylesheet")
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        self.assertIn("scroll-margin-top", css,
                      "nothing offsets the jump for the sticky header")
        self.assertIn("scroll-behavior: smooth", css)

    def test_the_index_still_ships_plain_anchors(self):
        """The whole thing degrades to a native jump without JS."""
        markup = self.html("projects/steer.html")
        toc = markup.split('class="toc__list"', 1)[1].split("</ol>", 1)[0]
        self.assertIn('<a href="#', toc,
                      "the index no longer ships real anchors, so it stops "
                      "working when the script does not load")
        self.assertNotIn("javascript:", toc)
        self.assertNotIn('href="#"', toc)


class TestCustomDomain(BuildCase):
    """The CNAME file and site.json's url must name the same host.

    GitHub Pages reads the custom domain from a CNAME file in the published
    branch's root -- nowhere else. Delete the file and Pages silently falls
    back to kami-abdou.github.io and the domain stops resolving, with no
    error anywhere. It is a one-line file that nothing in build.py writes,
    which makes it exactly the kind of thing a branch merge drops.

    It nearly was dropped: GitHub committed CNAME to main on its own, so for
    a while the file existed on main and on no other branch, while the
    publish step was `git push origin Portfolio0.1:main`. That push would
    have deleted it.

    site.json's url is the other half. It drives every canonical tag, the
    og:url on every page, all ten sitemap entries and the robots.txt sitemap
    line. If the two disagree, the site serves one domain while telling
    crawlers the real one is somewhere else.
    """

    def cname(self):
        path = ROOT / "CNAME"
        self.assertTrue(
            path.is_file(),
            "CNAME is missing from the repo root -- GitHub Pages will drop "
            "the custom domain and serve kami-abdou.github.io instead")
        return path.read_text(encoding="utf-8").strip()

    def test_cname_is_a_bare_host(self):
        """Pages wants the host alone. A scheme or path silently breaks it."""
        host = self.cname()
        self.assertNotIn("://", host, "CNAME carries a scheme: %r" % host)
        self.assertNotIn("/", host, "CNAME carries a path: %r" % host)
        self.assertEqual(host, host.strip().lower(),
                         "CNAME has stray case or whitespace: %r" % host)
        self.assertEqual(len(host.splitlines()), 1,
                         "CNAME holds more than one line: %r" % host)

    def test_cname_matches_the_url_in_site_json(self):
        url = self.site.get("url", "")
        host = url.split("://", 1)[-1].split("/", 1)[0]
        self.assertEqual(
            self.cname(), host,
            "CNAME says %r but site.json's url says %r -- the site would "
            "serve one domain and declare another as canonical"
            % (self.cname(), host))

    def test_canonical_urls_use_the_custom_domain(self):
        """Checked on the rendered pages, which is what a crawler reads."""
        for page in ("index.html", "about.html", "projects/steer.html"):
            markup = self.html(page)
            self.assertIn('rel="canonical" href="https://%s/' % self.cname(),
                          markup, "%s does not canonicalise to the custom "
                          "domain" % page)

    def test_no_shipped_file_still_points_at_the_pages_subdomain(self):
        """The old host appearing anywhere shippable means a stale build.

        docs/ is excluded: it holds dated planning notes that record what the
        URL was at the time, and rewriting history there would be a lie.
        """
        stale = []
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if rel.parts[0] in (".git", "_archive", "docs", "site"):
                continue
            if path.suffix not in (".html", ".xml", ".txt", ".json"):
                continue
            if "kami-abdou.github.io" in path.read_text(
                    encoding="utf-8", errors="ignore"):
                stale.append(str(rel))
        self.assertEqual(stale, [],
                         "these still point at the old Pages subdomain: %s"
                         % ", ".join(stale))


class TestCollapsibleSections(BuildCase):
    """Case-study sections are <details>, and the figures are inside them.

    Fixerloop rendered at 26,747px -- about 35 screens for one project --
    which is what prompted this. Collapsing took it to 5,060.

    The failure worth guarding is not that the markup disappears; it is
    that the FIGURES drift back out. They were siblings following each
    section before this, so a <details> wrapping the section alone would
    collapse 500 words and leave 21 screenshots exactly where they were.
    The page would still look collapsible and save almost nothing, and
    nothing else in this suite would notice.
    """

    def pages(self):
        return ["projects/%s.html" % c["slug"] for _, c in self.live_projects()]

    def body(self, page):
        return re.sub(r"<!--.*?-->", "", self.html(page), flags=re.S)

    def test_sections_are_details_with_a_summary(self):
        for page in self.pages():
            src = self.body(page)
            opens = len(re.findall(r'<details class="project__section"', src))
            self.assertTrue(opens, "%s has no collapsible sections" % page)
            self.assertEqual(
                opens, src.count('<summary class="section__summary">'),
                "%s has a details without a summary, which is a section that "
                "cannot be opened by keyboard or by click" % page)
            self.assertNotIn(
                '<section class="project__section"', src,
                "%s still renders a plain <section>, so that one does not "
                "collapse with the rest" % page)

    def test_the_figures_collapse_with_their_section(self):
        """The whole point. Figures outside the body save nothing."""
        for page in self.pages():
            src = self.body(page)
            for block in re.findall(
                    r'<details class="project__section".*?</details>', src, re.S):
                shots = block.count('<div class="shots')
                if not shots:
                    continue
                body = block.split('<div class="section__body">', 1)
                self.assertEqual(
                    len(body), 2,
                    "%s: a section has figures but no collapsible body" % page)
                self.assertEqual(
                    body[1].count('<div class="shots'), shots,
                    "%s: a section's figures sit outside .section__body, so "
                    "collapsing it hides the prose and leaves the screenshots"
                    % page)

    def test_no_page_opens_entirely_collapsed(self):
        """A page of shut headings reads as empty, not as tidy."""
        for page in self.pages():
            src = self.body(page)
            opened = re.findall(
                r'<details class="project__section" id="[^"]*" open>', src)
            self.assertTrue(
                opened,
                "%s opens with every section collapsed, so a visitor lands "
                "on a list of headings and no content" % page)

    def test_the_outcome_section_is_never_collapsed(self):
        """The payoff is what a recruiter came for; it does not get hidden."""
        for page in self.pages():
            src = self.body(page)
            match = re.search(
                r'<details class="project__section" id="outcome"( open)?>', src)
            if not match:
                continue
            self.assertTrue(
                match.group(1),
                "%s collapses its outcome section, which buries what came of "
                "the work behind a disclosure control" % page)

    def test_the_expand_all_control_ships_hidden(self):
        """Same contract as every other enhancement on this site."""
        for page in self.pages():
            src = self.body(page)
            if "sections__control" not in src:
                continue
            self.assertIn(
                'class="sections__control" hidden', src,
                "%s ships the expand-all control visible, so with JS off it "
                "is a button that does nothing" % page)

    def test_the_eyebrow_is_phrasing_content(self):
        """<summary> takes phrasing content plus optional heading content.

        The eyebrow was a <p>, which is flow content: it renders fine and
        is invalid in the parser's content model, and an invalid <p>
        inside <summary> is the kind of thing that gets silently
        reparented.
        """
        for page in self.pages():
            src = self.body(page)
            for summary in re.findall(r"<summary[^>]*>(.*?)</summary>", src, re.S):
                self.assertNotIn(
                    "<p", summary,
                    "%s has a <p> inside a <summary>" % page)


class TestNoDeadAnchors(BuildCase):
    """Every in-page link points at an id that exists on that page.

    A fragment that matches nothing does not error -- the browser stays
    exactly where it is, which is indistinguishable from a link that did
    not register the click. It has happened twice here: the hero's third
    card pointed at `#how` after the band carrying that id was replaced,
    and survived a restructure plus a round of cutting because nothing
    looks wrong until you click it.
    """

    def pages(self):
        pages = ["index.html", "work.html", "about.html"]
        for path in sorted((ROOT / "projects").glob("*/content.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("published") is not False:
                pages.append("projects/%s.html" % data["slug"])
        return pages

    def test_every_fragment_link_has_a_target(self):
        for page in self.pages():
            src = re.sub(r"<!--.*?-->", "", self.html(page), flags=re.S)
            ids = set(re.findall(r'id="([^"]+)"', src))
            dead = []
            for href in re.findall(r'href="(#[^"]*)"', src):
                target = href[1:]
                if target and target not in ids:
                    dead.append(href)
            self.assertEqual(
                dead, [],
                "%s links to fragment(s) that do not exist on it: %s"
                % (page, sorted(set(dead))))


class TestRetiredProjects(BuildCase):
    """`"published": false` retires a project without deleting anything.

    Retiring is a judgement call that gets revisited -- Smarthub and this
    site were both cut from the bands after a review of what the portfolio
    was claiming. Deleting the folders would make that permanent and take
    the only copy of the _src originals with it.

    So the flag has to do four things, and all four are asserted: no page,
    no sitemap entry, no band listing, and every file still on disk.
    """

    def retired(self):
        out = []
        for path in sorted((ROOT / "projects").glob("*/content.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("published") is False:
                out.append((path.parent, data))
        return out

    def test_a_retired_project_builds_no_page(self):
        for folder, data in self.retired():
            page = ROOT / "projects" / ("%s.html" % data["slug"])
            self.assertFalse(
                page.is_file(),
                "%s is retired but %s still exists -- a page nothing links "
                "to, still reachable and still indexable"
                % (data["slug"], page.name))

    def test_a_retired_project_leaves_the_sitemap(self):
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        for folder, data in self.retired():
            self.assertNotIn(
                "/projects/%s" % data["slug"], sitemap,
                "%s is retired but still in the sitemap, which invites a "
                "crawler to a page that is not there" % data["slug"])

    def test_a_retired_project_is_in_no_band(self):
        sel = self.site["sections"].get("selected") or {}
        listed = [i["slug"] for i in sel.get("items", [])] + list(sel.get("more", []))
        for folder, data in self.retired():
            self.assertNotIn(
                data["slug"], listed,
                "%s is retired but still listed on the homepage, so the page "
                "links somewhere the build no longer writes" % data["slug"])

    def test_retiring_deletes_nothing(self):
        """The whole point. The content and the originals stay."""
        for folder, data in self.retired():
            self.assertTrue((folder / "content.json").is_file())
            assets = folder / "assets"
            self.assertTrue(
                assets.is_dir(),
                "%s lost its assets folder -- retiring is meant to be "
                "reversible" % data["slug"])
            src = assets / "_src"
            if src.exists():
                self.assertTrue(
                    any(src.iterdir()),
                    "%s's _src is empty. Those are the only copies of the "
                    "originals." % data["slug"])

    def test_a_retired_project_states_why(self):
        """So the next person does not have to guess, or undo it blindly."""
        for folder, data in self.retired():
            self.assertTrue(
                (data.get("_retired") or "").strip(),
                "%s is retired with no `_retired` note saying why"
                % data["slug"])


class TestStylesheetIsWellFormed(BuildCase):
    """Braces balance, and no rule is left without a body.

    Both of these were real and both were silent. A purge script that
    removed rules by matching selector text left a stray `}` behind, and
    from that brace onward the parser was out of sync -- the wordmark's
    font-family simply never applied, with no error anywhere and the
    whole suite green. A second pass left `.card:hover .card__tag,`
    dangling with no declaration block, which is the same shape as the
    bug that made every masked heading on the site invisible: a
    multi-selector group whose shared body was deleted with its last
    selector.

    Neither is visible in a diff and neither throws. CSS has no parse
    errors to speak of -- it discards what it cannot read and carries on.
    """

    def css(self):
        return (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")

    def stripped(self):
        """Comments blanked, newlines kept so line numbers stay true."""
        return re.sub(r"/\*.*?\*/",
                      lambda m: re.sub(r"[^\n]", " ", m.group(0)),
                      self.css(), flags=re.S)

    def test_every_brace_is_matched(self):
        depth, line, bad = 0, 1, []
        for ch in self.stripped():
            if ch == "\n":
                line += 1
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth < 0:
                    bad.append(line)
                    depth = 0
        self.assertEqual(bad, [], "unmatched '}' at line(s) %s -- every rule "
                                  "after the first one is being parsed in the "
                                  "wrong context" % bad)
        self.assertEqual(depth, 0,
                         "%d block(s) left open at the end of the file" % depth)

    def test_no_selector_is_left_without_a_body(self):
        """A group whose declaration block was deleted with its last member.

        Depth-tracked rather than line-matched. The first version of this
        scanned for lines ending in a comma and flagged nine multi-line
        `transition` values -- the commas inside a declaration block look
        exactly like the commas between selectors unless you know which
        side of a brace you are on.
        """
        text = self.stripped()
        depth, chunk, line, start_line = 0, [], 1, 1
        orphans = []
        for ch in text:
            if ch == "\n":
                line += 1
            if ch == "{":
                if depth == 0:
                    sel = "".join(chunk).strip()
                    if sel.endswith(","):
                        orphans.append((start_line, sel.splitlines()[-1][:60]))
                    chunk = []
                depth += 1
            elif ch == "}":
                depth -= 1
                chunk, start_line = [], line
            elif depth == 0:
                if not chunk and not ch.isspace():
                    start_line = line
                chunk.append(ch)

        # and the tail: anything after the last } that never reached a {
        tail = "".join(chunk).strip()
        if tail.endswith(","):
            orphans.append((start_line, tail.splitlines()[-1][:60]))

        self.assertEqual(
            orphans, [],
            "selector list(s) ending in a comma with no declaration block "
            "following -- the shared body was deleted with the last "
            "selector, and everything in the group silently stopped "
            "applying: %s" % orphans)


class TestScrollSnap(BuildCase):
    """Snapping must stay `proximity`, and must stay gated.

    The request was controlled stops rather than a scroll that ends
    wherever the flick dies. `mandatory` is the obvious way to get that
    and it is the wrong one here: it forces the container to rest on a
    snap point every time it settles, which is safe only while every
    snap-to-snap gap is shorter than the viewport. On this site they are
    not. A case-study band runs 3591px, project pages average an 845px
    gap against a 768px viewport, and the source images go up to 900x4009.
    Under mandatory the middle of those is unreachable: the browser drags
    the scroll to the next boundary.

    Verified in a browser both ways. With proximity, four consecutive
    wheel scrolls on the homepage each came to rest with a snap target's
    top at exactly 104px -- the scroll-padding line, offset 0 every time,
    so the controlled-stop behaviour is real. And scrolling to the middle
    of the tallest image on /projects/konnect held at that position with
    zero drift, which is the half mandatory would have broken.
    """

    def test_the_first_section_is_not_a_snap_target(self):
        """A snap point in the first screen takes the top of the page away.

        `.opening` was the first entry in the target list. With
        scroll-padding-top at 104px, a target whose box starts at 230
        snaps to scrollY 126 -- and on a fresh load the page came to rest
        there and would NOT return to 0. scrollTo(0, 0) read back 126
        immediately. The visible symptom was the floating nav sitting on
        top of the hero panel, 24px over its rounded top edge.

        It was wrong before the panel existed and merely too small to
        notice: .opening started at 134 and snapped to 30. Wrapping the
        opening in a card moved its border box to 230 and turned 30 into
        126, which is why this surfaced as a layout bug rather than a
        scrolling one.

        The top of a page is already a resting position. Giving it a snap
        point can only move the rest position off it.
        """
        css = self.css()
        start = css.index("scroll-snap-align: start")
        # the selector list immediately above the declaration
        selectors = css[:start].rsplit("}", 1)[-1]
        selectors = selectors.rsplit("*/", 1)[-1]
        names = [x.strip() for x in selectors.split(",") if x.strip()]
        self.assertNotIn(
            ".opening", names,
            "`.opening` is a snap target again; the page will rest below "
            "its own top and the nav will overlap the hero panel")

    def css(self):
        return (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")

    def snap_block(self):
        css = self.css()
        marker = "scroll-snap-type"
        self.assertIn(marker, css, "the site no longer snaps at all")
        start = css.index(marker)
        return css[start:start + 400]

    def test_snapping_is_proximity_not_mandatory(self):
        block = self.snap_block()
        self.assertIn("proximity", block,
                      "scroll-snap-type is not proximity: %r" % block[:80])
        self.assertNotIn(
            "mandatory", block,
            "scroll-snap-type is mandatory. Gaps between snap points on "
            "this site exceed the viewport -- a 3591px band, an 845px "
            "average on project pages -- so mandatory makes their middles "
            "unreachable.")

    def test_snapping_is_behind_a_reduced_motion_gate(self):
        """A scroll position the browser moves after you stopped is motion."""
        css = self.css()
        idx = css.index("scroll-snap-type")
        before = css[:idx]
        query = before[before.rindex("@media"):]
        self.assertIn("prefers-reduced-motion: no-preference", query,
                      "scroll snapping is not gated on reduced motion: %r"
                      % query[:120])

    def test_the_header_does_not_cover_a_snap_target(self):
        """scroll-padding-top, or every stop lands under the sticky header."""
        css = self.css()
        block = css.split("html {", 1)
        found = [chunk.split("}", 1)[0] for chunk in css.split("html {")[1:]]
        owners = [b for b in found if "scroll-padding-top" in b]
        self.assertEqual(
            len(owners), 1,
            "expected exactly one html rule to set scroll-padding-top, "
            "found %d" % len(owners))
        self.assertIn("var(--header-height)", owners[0],
                      "scroll-padding-top no longer tracks the header "
                      "height: %r" % owners[0])

    def test_a_band_is_not_a_snap_target_alongside_its_own_rows(self):
        """Two candidates 141px apart resolved to neither of them.

        Listing `.band` and `.grid > li` together put a parent and its
        first child inside a sixth of a viewport of each other, and the
        resting position came out 13-50px off a target instead of on one.
        """
        css = self.css()
        idx = css.index("scroll-snap-align")
        selectors = css[:idx].rsplit("}", 1)[-1]
        self.assertIn(".entry", selectors,
                      "work rows are not snap targets, so the stops are only "
                      "every section and proximity mostly will not engage")
        self.assertNotRegex(
            selectors, r"(?m)^\s*\.band,",
            "`.band` is a snap target alongside its own cards again")


class TestHeadingOutline(BuildCase):
    """Every page: exactly one h1, and no level skipped under it.

    /contact had NO h1 at all. The "Let's talk" block is shared with the
    homepage, where it is correctly an h2 under the page's own h1 -- and
    the level was hardcoded, so the page that consists of nothing but that
    block had a document outline starting at level two with no level one
    above it. One heading on the whole page, and it was the wrong rank.

    Comments are stripped first. build.py writes an explanatory comment
    containing the literal text "<h1" next to every project cover, and
    counting raw matches reports two h1s on all eight project pages.
    """

    PAGES = ("index.html", "work.html", "about.html")

    def outline(self, page):
        html_src = re.sub(r"<!--.*?-->", "", self.html(page), flags=re.S)
        return [int(m.group(1)) for m in re.finditer(r"<h([1-6])\b", html_src)]

    def pages(self):
        slugs = sorted(c["slug"] for _, c in self.live_projects())
        return list(self.PAGES) + ["projects/%s.html" % s for s in slugs]

    def test_every_page_has_exactly_one_h1(self):
        for page in self.pages():
            levels = self.outline(page)
            self.assertEqual(
                levels.count(1), 1,
                "%s has %d h1 elements (outline: %r)"
                % (page, levels.count(1), levels))

    def test_the_h1_comes_first(self):
        for page in self.pages():
            levels = self.outline(page)
            self.assertTrue(levels, "%s has no headings at all" % page)
            self.assertEqual(
                levels[0], 1,
                "%s opens at h%d, so its outline has no root: %r"
                % (page, levels[0], levels))

    def test_no_level_is_skipped(self):
        for page in self.pages():
            levels = self.outline(page)
            for before, after in zip(levels, levels[1:]):
                self.assertLessEqual(
                    after, before + 1,
                    "%s jumps from h%d straight to h%d, which leaves a gap "
                    "in the outline a screen-reader user navigates by: %r"
                    % (page, before, after, levels))


class TestPortfolioMetricsAreTrue(BuildCase):
    """The portfolio project's numbers describe THIS repository.

    Every other case study quotes a figure from work done elsewhere, which
    nothing here can check. These three are different: they are claims
    about the files in this checkout, made on a page inside it, and they
    are the only metrics on the site that can be verified rather than
    trusted.

    They had gone stale, which is the whole argument for this class. The
    page claimed "42" tests while the suite had grown past 150, and
    "7.3 KB" of JavaScript while the real figure had grown by nearly half.
    Both were true when written. Neither had any way to say so afterwards.
    """

    def metric(self, label_fragment):
        path = ROOT / "projects" / "09-portfolio" / "content.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for m in data.get("metrics", []):
            if label_fragment.lower() in m["label"].lower():
                return m
        self.fail("no portfolio metric whose label mentions %r" % label_fragment)

    def test_the_test_count_is_the_real_one(self):
        claimed = self.metric("tests")["value"]
        src = (ROOT / "tools" / "test_build.py").read_text(encoding="utf-8")
        actual = len(re.findall(r"^\s+def test_", src, re.M))
        self.assertEqual(
            claimed, str(actual),
            "the portfolio page claims %s tests and there are %d. This is "
            "the number describing the file it is counted from, so it goes "
            "stale every time the suite grows." % (claimed, actual))

    def test_the_javascript_weight_is_the_real_one(self):
        """Gzipped, because that is what 'shipped' means over the wire."""
        import gzip
        claimed = self.metric("javascript")["value"]
        total = sum(len(gzip.compress(f.read_bytes(), 9))
                    for f in sorted((ROOT / "assets").glob("*.js")))
        actual = "%.1f KB" % (total / 1024)
        self.assertEqual(
            claimed, actual,
            "the portfolio page claims %s of JavaScript and the files in "
            "assets/ gzip to %s" % (claimed, actual))

    def test_the_dependency_count_is_still_zero(self):
        """The claim the whole site is built around, so it gets a check.

        Not a string comparison against the metric alone: the number is
        only meaningful if nothing has quietly appeared to contradict it.
        """
        self.assertEqual(self.metric("dependencies")["value"], "0")
        for name in ("package.json", "package-lock.json", "node_modules",
                     "yarn.lock", "pnpm-lock.yaml", "requirements.txt"):
            self.assertFalse(
                (ROOT / name).exists(),
                "%s exists, so '0 runtime dependencies' is no longer a "
                "claim this repository supports" % name)


class TestInstaDeepEntry(BuildCase):

    def test_page_exists(self):
        self.assertTrue((ROOT / "projects" / "instadeep.html").is_file())

    def test_names_all_three_products(self):
        page = self.html("projects/instadeep.html")
        for product in ("DeepPCB", "Design system", "InstaNovo"):
            self.assertIn(product, page, "instadeep.html omits %s" % product)

    def test_instanovo_is_rendered_now_that_the_screens_exist(self):
        """This test used to assert the opposite.

        InstaNovo was named in the summary and all three meta descriptions --
        so the entry was honest about the scope of the role -- while its
        section was a `TODO` body with no images, which build.py correctly
        dropped. The page therefore promised three product surfaces and
        showed two, and the old test pinned that stub as WIRED rather than
        broken: "the block appears when the screens land, with no template
        change."

        The screens landed. Nothing in the template changed, which is what
        the old test was really protecting. It is inverted here rather than
        deleted, so the history of the claim stays visible.
        """
        page = self.html("projects/instadeep.html")
        content = self.content("10-instadeep")
        section = next(s for s in content["sections"] if s["id"] == "instanovo")

        self.assertFalse(section["body"].startswith("TODO"),
                         "the InstaNovo stub is back")
        self.assertGreater(len(section["body"].split()), 80,
                           "InstaNovo has a section but barely any write-up")
        self.assertIn("InstaNovo", page)
        self.assertIn('id="instanovo"', page)
        self.assertIn("in1-landing", page)
        # the page's own tagline promises three surfaces; hold it to that
        self.assertIn("DeepPCB", page)
        self.assertNotIn("TODO", page)

    def test_component_boards_still_auto_populate(self):
        """assets/components/ is globbed by autoImages, not listed in JSON.

        If the folder failed to move, auto_images() returns [] and the section
        silently vanishes -- the exact failure this guards. Asserts the path,
        that the folder is not empty, and that EVERY board on disk reaches the
        page, because a partial glob is the quieter bug.

        This used to pin the count at a literal 7, which had to be edited by
        hand every time an export was dropped in -- against the whole promise
        of the folder, whose README says "no JSON to edit, no code to change".
        A test that must be edited to add a file makes the feature not
        automatic. The per-file loop below already catches a partial glob
        outright, so the only thing the literal caught that the loop does not
        is an empty folder, and the non-empty assertion covers that without
        going stale. The set comparison keeps the other direction honest: a
        board referenced by the page but absent from disk is still a failure.

        This used to assert `class="viewer"`. InstaDeep became a gallery, and
        highlights pages drop the tabbed browser: it shows one board at a time,
        which earns its keep only when prose is walking the reader through
        them. What matters either way is that every board reaches the page.
        """
        page = self.html("projects/instadeep.html")
        self.assertIn("assets/components/", page)
        folder = ROOT / "projects" / "10-instadeep" / "assets" / "components"
        boards = sorted(p.name for p in folder.glob("*.png"))
        self.assertTrue(boards, "no component boards on disk at all")
        for name in boards:
            self.assertIn("components/%s" % name, page,
                          "%s never made it onto the page" % name)
        # Each board is referenced twice -- once as src, once as the lightbox
        # target -- so compare the distinct set, not the raw list.
        refs = sorted(set(re.findall(r"components/([\w.-]+\.png)", page)))
        self.assertEqual(refs, boards,
                         "the page references a different set of boards than "
                         "the folder holds:\n  page   %s\n  folder %s"
                         % (refs, boards))

    #: A tablist is a reasonable way to show a handful of related views and
    #: a bad way to show a set. Past this, the control is hiding a gallery.
    MAX_VIEWER_PANELS = 4

    def test_a_tabbed_browser_never_hides_a_board_set(self):
        """A tablist with no prose hides most of a set behind controls the
        visitor has no reason to click.

        This asserted that InstaDeep's page contained no viewer at all,
        which was right while the only candidate was the component boards:
        nine of them, one visible at a time, and no narrative walking
        anyone through them.

        The page now has a two-panel viewer over the DeepPCB app, and none
        of that holds for it -- two panels rather than nine, prose above
        describing both, a caption on each panel, and tabs named "Boards"
        and "Editor" rather than "View 1". So the assertion moves to the
        property it was always about: a viewer has to be small and
        explained, and a set of boards never goes behind one.

        Asserted against the content rather than the markup, because the
        rule is about what a section is allowed to do, and matching nested
        divs with a regex is how a test like this quietly stops checking.
        """
        project = self.content("10-instadeep")
        for section in project.get("sections", []):
            if not section.get("viewer"):
                continue
            label = section.get("id") or section.get("heading")

            self.assertFalse(
                section.get("autoImages"),
                "section %r puts an auto-loaded folder behind a tablist. "
                "That is a set, and a set does not go behind tabs." % label)

            body = section.get("body") or ""
            self.assertTrue(
                body.strip() and not body.startswith("TODO"),
                "section %r is a tablist with no prose, so nothing tells a "
                "visitor why they would click the second tab" % label)

            images = section.get("images") or []
            self.assertLessEqual(
                len(images), self.MAX_VIEWER_PANELS,
                "section %r hides %d views behind a tablist; past %d this is "
                "a gallery wearing a control"
                % (label, len(images), self.MAX_VIEWER_PANELS))

            for img in images:
                self.assertTrue(
                    img.get("label"),
                    "a panel in %r has no tab label, so its tab falls back to "
                    "the caption or to \"View N\"" % label)
                self.assertTrue(
                    img.get("caption"),
                    "a panel in %r has no caption, which is the only thing "
                    "telling a visitor what they are looking at" % label)

    def test_the_component_boards_stay_out_of_a_tablist(self):
        """The original concern, kept as its own assertion."""
        page = self.html("projects/instadeep.html")
        folder = ROOT / "projects" / "10-instadeep" / "assets" / "components"
        boards = sorted(p.name for p in folder.glob("*.png"))
        self.assertTrue(boards, "no component boards on disk at all")
        for name in boards:
            where = page.index("components/%s" % name)
            # Walk back to the nearest container and check it is a plain
            # figure rather than a viewer panel.
            before = page[:where]
            self.assertGreater(
                before.rindex("<figure"), before.rfind('class="viewer__panel'),
                "%s is inside a tablist panel" % name)

    def test_cover_is_landscape(self):
        """The card media is aspect-ratio 3/2; a 900x2708 cover crops to a band."""
        sys.path.insert(0, str(ROOT))
        from build import png_size
        project = self.content("10-instadeep")
        size = png_size(ROOT / "projects" / "10-instadeep" / project["cover"])
        self.assertIsNotNone(size, "cover has unreadable dimensions")
        width, height = size
        self.assertGreater(width, height, "cover %s is portrait" % project["cover"])


class TestConsolidation(BuildCase):

    def test_absorbed_pages_are_gone(self):
        for stale in ("deeppcb.html", "design-system.html"):
            self.assertFalse((ROOT / "projects" / stale).is_file(),
                             "projects/%s should have been absorbed" % stale)

    def test_nothing_links_to_the_absorbed_pages(self):
        for page in ("index.html", "about.html"):
            body = self.html(page)
            for stale in ("deeppcb.html", "design-system.html"):
                self.assertNotIn(stale, body, "%s still links %s" % (page, stale))

    def test_about_page_links_the_merged_entry(self):
        self.assertIn('href="projects/instadeep"', self.html("about.html"))

    def test_orders_are_contiguous_from_one(self):
        """order is visible: project_card renders it as the card number, and it
        drives the prev/next pager. Gaps and a stray 99 show up on screen."""
        import glob
        orders = sorted(
            json.loads(pathlib.Path(f).read_text(encoding="utf-8"))["order"]
            for f in glob.glob(str(ROOT / "projects" / "*" / "content.json")))
        self.assertEqual(orders, list(range(1, len(orders) + 1)))

    def test_eight_project_pages_and_ten_sitemap_urls(self):
        """UnDrive then PharmaDrive were removed; `portfolio` was added.

        The sitemap total is the project pages plus /work and /about.
        /contact left with the Cal embed it existed to hold. index.html
        is deliberately not listed: it is the same bytes as /work, which
        is the canonical of the pair, so listing both would ask a crawler
        to decide what the canonical already decided.
        """
        # Derived, because retiring a project legitimately changes both and
        # a literal here just means editing a test to record what happened.
        live = len(self.live_projects())
        self.assertIn("%d pages" % live, self.stdout,
                      "the build wrote a different number of project pages "
                      "than there are published projects")
        # the project pages, plus /work and /about
        self.assertIn("%d URLs" % (live + 2), self.stdout)


class TestHighlightsFormat(BuildCase):

    TIER2 = [("03-fissa3", "fissa3"), ("04-groupado", "groupado"),
             ("08-smarthub", "smarthub"), ("09-portfolio", "portfolio")]

    def test_all_four_are_flagged(self):
        for folder, _ in self.TIER2:
            self.assertEqual(self.content(folder).get("format"), "highlights",
                             "%s is not flagged" % folder)

    def test_tier_one_is_not_flagged(self):
        for folder in ("01-steer", "02-konnect", "06-fixerloop", "10-instadeep"):
            self.assertIsNone(self.content(folder).get("format"),
                              "%s should stay a full case study" % folder)

    def test_prose_is_not_deleted_only_unrendered(self):
        """The whole point of the flag: reversible by removing one field."""
        fissa3 = self.content("03-fissa3")
        bodies = [s.get("body") for s in fissa3["sections"] if s.get("body")]
        self.assertGreater(len(bodies), 4,
                           "Fissa3's narrative was deleted, not just hidden")

    def test_highlights_pages_render_images_but_not_body_prose(self):
        page = self.html("projects/fissa3.html")
        self.assertIn('class="shots', page)
        body = [s["body"] for s in self.content("03-fissa3")["sections"]
                if s.get("body") and not s["body"].startswith("TODO")][0]
        first_sentence = body.split(".")[0]
        self.assertNotIn(first_sentence, page,
                         "highlights page still renders section prose")

    def test_eyebrow_follows_tier_not_category(self):
        """Fissa3 and Groupado are category:case-study but Tier 2."""
        for slug in [c["slug"] for _, c in self.live_projects()
                     if c.get("format") == "highlights"]:
            self.assertIn(">Project<", self.html("projects/%s.html" % slug),
                          "%s does not read as a Tier-2 page" % slug)
        for slug in [c["slug"] for _, c in self.live_projects()
                     if c.get("format") != "highlights"]:
            self.assertIn(">Case study<", self.html("projects/%s.html" % slug),
                          "%s does not read as a case study" % slug)

    def test_highlights_pages_have_no_table_of_contents(self):
        """A TOC over image blocks with no prose is navigation to nothing."""
        self.assertNotIn('class="toc"', self.html("projects/fissa3.html"))

    def test_no_section_is_numbered(self):
        """Section-number eyebrows are gone, on every page, not just lone ones.

        This used to assert the narrower rule: a page with ONE live section
        must not print "01", because a leading number claims a position in a
        sequence that does not exist. Multi-section pages were required TO be
        numbered.

        The wider rule replaced it. Section-number eyebrows are banned
        outright: if the reader can count, the number tells them nothing, and
        the ordered table of contents beside the sections already carries the
        sequence. The phase label stays, because an eyebrow that NAMES the
        topic in plain language -- "Product", "System", "States" -- is the
        thing numbering was standing in for.

        Asserted as a property over every page rather than against a named
        slug, so it keeps holding as projects come and go.
        """
        import glob
        checked = 0
        for path in sorted(glob.glob(str(ROOT / "projects" / "*.html"))):
            name = "projects/" + pathlib.Path(path).name
            page = self.html(name)
            if not page.count('class="project__section"'):
                continue
            checked += 1
            self.assertNotIn(
                "project__num", page,
                "%s prints a section-number eyebrow" % name)
        self.assertGreater(checked, 0, "no case-study page left to check")

    def test_the_phase_eyebrow_survives(self):
        """Removing the number must not take the topic label with it.

        The number and the phase were siblings in one eyebrow, so deleting
        the wrong half would leave section headers with no label at all.
        """
        page = self.html("projects/instadeep.html")
        self.assertIn("project__phase", page,
                      "section headers lost their topic label along with "
                      "the number")


class TestHeroPortrait(BuildCase):
    """The hero portrait must actually be visible.

    It was not, for a day. An AVIF <source> was added to cut the LCP weight,
    encoded with `sips -s format avif`. The file passed every cheap check --
    `ftyp avif` magic, correct dimensions read back by sips, `file` reporting
    "ISO Media, AVIF Image", 60% smaller than the JPEG -- and Chrome decoded
    it to pure black: max luminance 0 across the frame against 238 for the
    JPEG. The portrait vanished and the only symptom was a dark rectangle
    behind dark type, which is invisible on this palette.

    Decoding AVIF needs a browser, so these pin the two things that are
    checkable from stdlib: no AVIF is referenced from the hero at all, and
    the JPEG that IS referenced is a real, non-trivial image.
    """

    def test_hero_references_no_avif(self):
        import re
        index = self.html("index.html")
        hero = re.search(r'<figure class="opening__portrait">.*?</figure>',
                         index, re.S)
        self.assertIsNotNone(hero, "the portrait figure is gone from the page")
        self.assertNotIn(".avif", hero.group(0),
                         "an AVIF source is back on the portrait -- verify its "
                         "PIXELS in a browser, not its bytes, before shipping")

    def test_hero_image_exists_and_is_a_real_jpeg(self):
        import re, struct
        index = self.html("index.html")
        src = re.search(r'<figure class="opening__portrait">.*?<img src="([^"?]+)',
                        index, re.S).group(1)
        path = ROOT / src
        self.assertTrue(path.is_file(), "portrait missing: %s" % src)
        head = path.read_bytes()[:2]
        self.assertEqual(head, b"\xff\xd8", "%s is not a JPEG" % src)
        # A black or empty encode compresses to almost nothing. The check
        # used to be "over 20 KB", which was a fact about a 1702x2062
        # photograph and not about the picture being real -- the portrait
        # is cropped to 280x280 on the way in now, and a perfectly good
        # one weighs 19.8 KB. Bytes PER PIXEL survives a change of
        # dimensions: this file is 0.25, a black JPEG is under 0.02.
        size = path.stat().st_size
        import struct as _s
        w = h = None
        raw = path.read_bytes()
        i = 2
        while i < len(raw) - 9:
            if raw[i] != 0xFF:
                i += 1; continue
            m = raw[i + 1]
            if m in (0xC0, 0xC1, 0xC2):
                h, w = _s.unpack(">HH", raw[i + 5:i + 9]); break
            i += 2 + _s.unpack(">H", raw[i + 2:i + 4])[0]
        self.assertTrue(w and h, "could not read the portrait's dimensions")
        self.assertGreater(size / (w * h), 0.05,
                           "%s is %d bytes for %dx%d (%.3f per pixel) -- that "
                           "is about what a black or empty encode weighs"
                           % (src, size, w, h, size / (w * h)))

    def test_hero_portrait_is_cropped_to_include_the_subject(self):
        """object-position must stay biased down.

        portrait.jpg is 0.56 aspect going into a taller frame, so `cover`
        throws away height. At the default 50% the crop centres on the
        buildings and cuts the subject off at the frame edge -- the one
        thing the portrait exists to show.

        The portrait has moved twice -- out of the marquee band into "How
        I work", and then into the homepage's "A bit about me" block when
        that replaced it. The requirement moved with it both times.
        """
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        block = css.split(".aboutblock__portrait img {", 1)[1].split("}", 1)[0]
        self.assertIn("object-position", block,
                      "the portrait lost its downward crop bias")


class TestPrimaryNav(BuildCase):
    """Work / About / Contact must be findable, markable and hittable.

    The owner asked whether the nav should be "highlighted more". Measured
    first: 15px text at 6.47:1 against the page, which is comfortably past
    WCAG AA, so visibility was not the problem. Three other things were.
    """

    def test_current_page_is_marked(self):
        """aria-current appeared NOWHERE on the site before this.

        A visitor on /about saw a nav identical to the homepage's. The only
        is-current rule in the stylesheet was for the project-page TOC.

        Contact is not in this list any more. The nav's third control is a
        link to an external calendar, and marking it aria-current on
        /contact would tell a screen reader that an off-site URL is the
        page being read.
        """
        self.assertIn('href="work" aria-current="page"',
                      self.html("index.html"))
        self.assertIn('href="about" aria-current="page"',
                      self.html("about.html"))

    def test_work_goes_to_the_top_of_the_homepage(self):
        """Work used to jump to #work, landing past the hero.

        The nav's first item dropped a visitor into the middle of a page
        they had never seen the top of. It now shares the wordmark's href
        exactly, on every page, which is the behaviour that was asked for
        -- so this asserts the two are equal rather than hardcoding a
        string, and a change to one that misses the other fails.
        """
        for name, depth in (("index.html", 0), ("about.html", 0),
                            ("projects/steer.html", 1),
                            ("projects/konnect.html", 1)):
            page = self.html(name)
            logo = re.search(r'<a class="site-head__name" href="([^"]+)"', page)
            self.assertIsNotNone(logo, "%s lost its wordmark" % name)
            nav = page.split('<nav class="site-nav" aria-label="Primary">', 1)[1].split("</nav>", 1)[0]
            work = re.search(r'<a href="([^"]+)"[^>]*>Work</a>', nav)
            self.assertIsNotNone(work, "%s lost its Work link" % name)
            self.assertEqual(
                work.group(1), logo.group(1),
                "%s: Work points at %r but the wordmark goes to %r -- they "
                "are meant to be the same destination"
                % (name, work.group(1), logo.group(1)))
            self.assertNotIn("#", work.group(1),
                             "%s: Work carries a fragment again, so it skips "
                             "the hero" % name)

    def test_project_pages_mark_nothing(self):
        """A project page sits under Work but is not Work, and marking it
        current would be a claim a screen reader reads out loud."""
        for _, data in self.live_projects():
            slug = data["slug"]
            page = self.html("projects/%s.html" % slug)
            nav = page.split('<nav class="site-nav" aria-label="Primary">', 1)[1].split("</nav>", 1)[0]
            self.assertNotIn("aria-current", nav,
                             "%s marks a nav item as the current page" % slug)

    def test_the_nav_never_fires_a_mail_client(self):
        """Contact was a mailto: sitting between two page links.

        In a nav that is a surprise -- it opens a mail client, or on a
        machine with none configured it appears to do nothing at all.
        It became /contact, then a booker page, and now a direct link
        to cal.com in a new tab. The mailto lives on the page, inside
        the actions, where a visitor expects one.
        """
        import glob, pathlib as pl
        for path in glob.glob(str(ROOT / "*.html")) + glob.glob(str(ROOT / "projects" / "*.html")):
            rel = pl.Path(path).relative_to(ROOT)
            up = "../" * (len(rel.parts) - 1)
            page = pl.Path(path).read_text(encoding="utf-8")
            nav = re.search(r'<nav class="site-nav" aria-label="Primary">(.*?)</nav>', page, re.S)
            self.assertIsNotNone(nav, "%s lost its primary nav" % rel)
            with self.subTest(page=str(rel)):
                self.assertNotIn("mailto:", nav.group(1),
                                 "%s still fires a mail client from the nav" % rel)
                self.assertIn('href="https://cal.com/', nav.group(1),
                              "%s has no route to the booker" % rel)


    def test_nav_links_have_a_real_hit_area(self):
        """They had zero padding, so the target was the text box: 24px tall,
        the bare WCAG 2.5.8 minimum and well under the 44px platform norm.
        Measured after the fix: 48px tall, header height unchanged at 76px
        because the padding is offset by a negative margin."""
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        block = css.split(".site-head nav a {", 1)[1].split("}", 1)[0]
        self.assertIn("padding", block, "nav links lost their hit area")

    def test_the_closing_ask_offers_both_ways_in(self):
        """The homepage's last section is the same ask as its first.

        It used to be a band carrying the email as selectable text, the
        CV and a row of link buttons. It is the two actions now, and the
        thing worth asserting is unchanged: a visitor who reads to the
        bottom can get in touch without scrolling back.
        """
        close = self.html("index.html").split('id="contact"', 1)[1].split("</section>", 1)[0]
        self.assertIn('href="https://cal.com/', close,
                      "no way to reach the booker at the foot")
        self.assertIn("mailto:", close, "no way to reach the address at the foot")


class TestToolIcons(BuildCase):
    """Tool chips: a real mark when one exists, a monogram when it does not.

    The lookup accepted only .svg, so every raster mark a vendor shipped
    fell back silently to a monogram with nothing to explain why. It now
    tries svg, then png, then webp.
    """

    def _chips(self, page):
        import re
        html_ = self.html(page)
        out = []
        for m in re.findall(r'<li class="tool">(.*?)</li>', html_, re.S):
            name = re.search(r'tool__name">([^<]+)', m).group(1)
            icon = re.search(r'class="tool__icon[^"]*" src="([^"?]+)', m)
            out.append((name, icon.group(1).split("/")[-1] if icon else None))
        return out

    def chips_everywhere(self):
        """Every tool chip the site renders, across the pages that have any."""
        out = []
        for _, data in self.live_projects():
            out += self._chips("projects/%s.html" % data["slug"])
        return out

    def test_supplied_marks_render_as_images(self):
        """A tool with a mark on disk renders that mark, not a monogram.

        This used to read the about page, which rendered the entire
        toolkit, and it asserted the stronger thing: that every mark on
        disk is referenced by some chip, so deleting a file failed the
        suite. The about page's toolkit is one line of plain text now, so
        the only chips left are the per-project ones, and six marks
        (claude-code, creative-cloud, git, mcp, notion, vwo) are
        referenced by nothing.

        Orphans are therefore no longer a failure -- they are a fact
        about an asset folder, recorded here so the next person does not
        read this test as proof that every file is in use. What is still
        asserted is the direction that can actually break a page: a chip
        that names a mark must name one that exists.
        """
        chips = self.chips_everywhere()
        self.assertTrue(chips, "no page renders a tool chip any more")
        on_disk = {f.name for f in (ROOT / "assets" / "tools").glob("*.png")}
        referenced = {f for _, f in chips if f}
        self.assertTrue(referenced, "no chip renders a supplied mark")
        for name, filename in chips:
            if filename:
                with self.subTest(tool=name):
                    self.assertIn(filename, on_disk,
                                  "%s references a mark that is not on disk: %s"
                                  % (name, filename))

    def test_tools_without_a_file_fall_back_to_a_monogram(self):
        """A tool with no mark on disk still renders, as its initial.

        This used to name Python, the one tool in the content with no
        supplied file -- and Python only ever appeared on the project that
        has since been retired, so the case vanished from the rendered
        site along with it.

        The mechanism still has to work: the next tool someone adds will
        not have a mark either. So it is tested against the function
        rather than against a page, which is also the version that cannot
        rot when the content changes.
        """
        sys.path.insert(0, str(ROOT))
        from build import tool_chips
        known = tool_chips(["Figma"])
        self.assertIn("assets/tools/figma.png", known,
                      "a tool WITH a mark stopped rendering it")
        unknown = tool_chips(["Kaleidoscope"])
        self.assertNotIn("<img", unknown,
                         "a tool with no mark on disk tried to render one")
        self.assertIn("Kaleidoscope", unknown,
                      "a tool with no mark lost its name as well")
        self.assertIn(">K<", unknown,
                      "a tool with no mark renders no monogram, so its chip "
                      "is a bare word where every neighbour has a glyph")

    def test_every_referenced_icon_exists_on_disk(self):
        """A missing file would render a broken image inside a chip.

        Scans EVERY page, at both depths. An earlier version matched only
        `../`-prefixed paths under projects/, so once the about page grew
        chips its root-relative icons were unchecked.
        """
        import glob, pathlib as pl, re
        pages = glob.glob(str(ROOT / "*.html")) + glob.glob(str(ROOT / "projects" / "*.html"))
        checked = 0
        for path in pages:
            page = pl.Path(path).read_text(encoding="utf-8")
            for rel in re.findall(r'class="tool__icon[^"]*" src="([^"?]+)', page):
                resolved = (pl.Path(path).parent / rel).resolve()
                self.assertTrue(resolved.is_file(),
                                "%s references missing %s" % (pl.Path(path).name, rel))
                checked += 1
        self.assertGreater(checked, 0, "no tool icons referenced anywhere")

    def test_the_plate_is_decided_by_measurement_not_by_hand(self):
        """A plate must IMPROVE a mark's contrast, or it must not be there.

        The plate was briefly applied to every icon. That fixed Framer
        (1.06:1 against the page) and broke the opposite case: a light mark
        measured 14.91:1 on the page and 1.20:1 on a white plate. Both
        directions are invisible, and neither announces itself.

        This used to assert a LIST -- Figma, Framer, VWO and MCP plated;
        Creative Cloud, Miro, Notion, Jira and Claude Code bare. That list
        was correct for a near-black page and became exactly wrong when the
        palette went to warm paper: twelve of the fourteen marks on the site
        flipped sides, because the plate decision is a function of the
        background and the background changed.

        So the assertion is now the property the list was standing in for,
        which holds under any palette: a plated mark reads better on the
        plate than on the page, and a bare mark does not. That is also the
        bug the list was written for -- plate-everything fails it on the
        first light mark it reaches.
        """
        sys.path.insert(0, str(ROOT))
        from build import (_png_pixels, _relative_luminance, _hex_luminance,
                           PAGE_LUMINANCE, TOKENS)

        def ink(path):
            total = count = 0.0
            for r, g, b, a in _png_pixels(path):
                if a > 128:
                    total += _relative_luminance(r, g, b)
                    count += 1
            return (total / count) if count else None

        def ratio(a, b):
            return (max(a, b) + 0.05) / (min(a, b) + 0.05)

        plate_lum = _hex_luminance(TOKENS["color"]["bgInverse"])

        # The floor comes from the function's own signature rather than a
        # copy of the number, so tuning it in one place moves both.
        src = (ROOT / "build.py").read_text(encoding="utf-8")
        threshold = float(re.search(r"def icon_needs_plate\([^)]*threshold=([\d.]+)",
                                    src).group(1))
        # Every page that still renders chips, concatenated. This read the
        # about page, which used to carry the whole toolkit; that section
        # is a line of plain text now, so the per-project chips are the
        # only ones left and they are spread across five pages.
        pages = "".join(self.html("projects/%s.html" % data["slug"])
                        for _, data in self.live_projects())

        plated = bare = 0
        for chip in re.findall(r'<li class="tool">(.*?)</li>', pages, re.S):
            src = re.search(r'tool__icon[^"]*"\s+src="([^"?]+)', chip)
            if not src:
                continue
            name = re.search(r'tool__name">([^<]+)', chip).group(1)
            path = ROOT / src.group(1).replace("../", "")
            if not path.is_file():
                continue
            i = ink(path)
            if i is None:
                continue

            on_page, on_plate = ratio(i, PAGE_LUMINANCE), ratio(i, plate_lum)
            has_plate = "tool__icon--plate" in chip

            if has_plate:
                plated += 1
                self.assertGreater(
                    on_plate, on_page,
                    "%s is plated but reads WORSE on the plate (%.2f:1) than "
                    "on the page (%.2f:1) -- the plate is erasing it"
                    % (name, on_plate, on_page))
                self.assertLess(
                    on_page, threshold,
                    "%s is plated but already clears the floor on the page "
                    "(%.2f:1 against %.1f) -- the plate is decoration"
                    % (name, on_page, threshold))
            else:
                bare += 1
                # Deliberately NOT "the page beats the plate". The rule is
                # that a bare mark is legible, not that it is optimal: Git
                # measures 3.53:1 on paper and 4.18:1 on a plate, so a
                # plate would be an improvement and is still not needed.
                # Asserting the stronger thing failed on a mark that is
                # perfectly fine, which is a test inventing a requirement.
                self.assertGreaterEqual(
                    on_page, threshold,
                    "%s is bare at %.2f:1 on the page, under the %.1f floor "
                    "-- it needs the plate it did not get"
                    % (name, on_page, threshold))

        # Neither direction may be empty, or the rule has collapsed into
        # "always" or "never" and stopped being a measurement.
        self.assertGreater(plated, 0, "no mark on the page carries a plate")
        self.assertGreater(bare, 0, "every mark carries a plate")

    def test_the_plate_class_still_carries_a_background(self):
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        block = css.split(".tool__icon--plate {", 1)[1].split("}", 1)[0]
        self.assertIn("background", block)


class TestWorkCards(BuildCase):
    """What a card is allowed to say, and how it is clicked.

    This replaces TestWorkRail. The rail carried category chips, a
    tagline, a summary paragraph and a "Read the case study" cue, and had
    two tiers that were asserted not to converge. The brief removed all
    of it: cover, name, tag, years.

    Three things from the old class are worth keeping and are kept: the
    whole thing is one control, the years are there, and every cover is
    cropped to a single ratio so the column does not lurch.
    """

    def rows(self):
        return re.findall(r'<li class="index__row">(.*?)</li>',
                          self.html("index.html"), re.S)

    def test_the_page_renders_one_row_per_project(self):
        expected = len(self.site["sections"]["selected"]["items"])
        self.assertEqual(len(self.rows()), expected)


    def test_the_whole_row_is_one_link(self):
        """One control per row, named by the project.

        The old rail needed a linked title plus an ::after stretched over
        the row, to keep its paragraphs out of the link's accessible
        name. A row's line is short enough to belong IN the name -- "01
        InstaDeep Three product surfaces and the design system they all
        run on. AI 2024-now" is a fair description of where the link
        goes -- so the link simply wraps it, and two links in one row
        would be the regression.
        """
        for i, row in enumerate(self.rows()):
            with self.subTest(row=i):
                self.assertEqual(row.count("<a "), 1,
                                 "row %d has %d links; it should be one"
                                 % (i, row.count("<a ")))
                self.assertIn('class="index__link"', row)


    def test_every_row_says_name_line_domain_and_year(self):
        for i, row in enumerate(self.rows()):
            with self.subTest(row=i):
                for cls in ("index__num", "index__name", "index__line",
                            "index__domain", "index__year", "index__arrow"):
                    self.assertIn(cls, row, "row %d has no %s" % (i, cls))


    def test_a_row_ships_no_image_of_its_own(self):
        """The covers are previews, not content.

        Five rows each carrying a cover <img> would be the card layout
        again with smaller pictures -- five requests for images most
        visitors never look at. The cover rides on an attribute and is
        fetched by the preview when a row is actually hovered.
        """
        for i, row in enumerate(self.rows()):
            with self.subTest(row=i):
                self.assertNotIn("<img", row,
                                 "row %d ships a cover image inline" % i)


    def test_the_cover_follows_the_cursor_instead_of_filling_the_page(self):
        """The covers were three stacked cards; they are one preview now.

        An image on a homepage earns its bytes at the moment someone has
        shown interest in a particular project, not before. The row holds
        its cover on an attribute and enhance.js draws it chasing the
        pointer, so a browser that never runs that script loses nothing
        it could read.
        """
        page = self.html("index.html")
        for row in self.rows():
            self.assertRegex(row, r'data-peek="[^"]+\.(jpg|png|webp)\?v=',
                             "a row carries no cover for the preview")
        self.assertNotIn('class="card__media"', page, "the cover cards are back")
        js = (ROOT / "assets" / "enhance.js").read_text(encoding="utf-8")
        self.assertIn("data-peek", js, "nothing reads the preview covers")
        # pointer-gated: a tap would only flash it on the way to the page
        self.assertIn("(hover: hover) and (pointer: fine)", js)
        self.assertIn("prefers-reduced-motion", js)


class TestAssetVersions(unittest.TestCase):
    """Every ?v= hash in the COMMITTED html must match the committed asset.

    asset_v exists because a browser keeps serving a cached styles.css or
    enhance.js after a deploy; its docstring records that costing real
    debugging time four separate times. Nothing checked the other half --
    that the HTML was rebuilt after the asset changed.

    It had not been. Caught in pre-flight before a sixteen-commit push: two
    commits each edited styles.css without a rebuild, so the CSS in the
    commit hashed to efaa2fef while the HTML in the same commit asked for
    e212c099. Each file was right on its own and the pair was wrong. Every
    test passed, the build exited clean, and it looked correct locally,
    because a fresh browser has nothing cached. The failure only reaches a
    RETURNING visitor, who keeps the old stylesheet and sees none of the
    work -- invisible locally, silent in the suite, wrong only for people
    who have been before.

    This reads from git rather than from disk, and does NOT extend
    BuildCase, both deliberately. BuildCase runs the build in setUpClass,
    so a test looking at the working tree sees freshly generated HTML and
    can never fail -- the first version of this test did exactly that and
    passed while being handed the known-bad hash. The question is whether
    the committed pair is coherent, so the committed pair is what it reads.
    It therefore goes green only once a rebuild is committed, which is the
    intended meaning.
    """

    def _show(self, path):
        import subprocess
        r = subprocess.run(["git", "show", "HEAD:%s" % path],
                           cwd=str(ROOT), capture_output=True)
        return r.stdout if r.returncode == 0 else None

    def test_every_versioned_asset_matches_its_committed_hash(self):
        import hashlib, subprocess
        listing = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD"],
                                 cwd=str(ROOT), capture_output=True, text=True).stdout
        pages = [p for p in listing.split() if re.fullmatch(r"(?:projects/)?[\w-]+\.html", p)]
        self.assertTrue(pages, "no committed pages found")
        checked, bad = 0, []
        for page in pages:
            html = (self._show(page) or b"").decode("utf-8", "replace")
            for ref, want in re.findall(r'(?:href|src)="([^"?]+)\?v=([0-9a-f]+)"', html):
                rel = re.sub(r"^(?:\.\./)+", "", ref)
                blob = self._show(rel)
                self.assertIsNotNone(
                    blob, "%s references %s?v=%s, which is not committed"
                          % (page, ref, want))
                got = hashlib.sha1(blob).hexdigest()[:len(want)]
                if got != want:
                    bad.append("%s -> %s asks %s, file is %s" % (page, ref, want, got))
                checked += 1
        self.assertEqual(
            bad, [],
            "the committed HTML asks for asset versions that do not match "
            "the committed assets, so a returning visitor keeps the cached "
            "old copy. Run build.py and commit the result.\n  "
            + "\n  ".join(bad[:6]))
        self.assertGreater(
            checked, 20,
            "only %d versioned references across %d committed pages, too few "
            "-- asset_v may have stopped being applied" % (checked, len(pages)))


class TestTargetSize(BuildCase):
    """The smallest thing on the site you have to hit with a pointer.

    "CV" in the footer is two characters and measured 17x24, the smallest
    target on any page. It already CONFORMED: WCAG 2.5.8 exempts an
    undersized target whose 24px-diameter circle does not reach another
    target, and tested with that actual circle against every other target's
    box, this one's did not -- its nearest neighbour is over 48px away
    centre to centre. So the min-width is not a conformance fix; it is a
    kinder target for an unsteady pointer, bought for 3.5px of padding.

    The one target still under 24 is the email address in the contact
    block, 19px tall. That one is exempt for a different and better reason:
    2.5.8's inline clause covers a target "in a sentence or otherwise
    constrained by the line-height of non-target text", and 19px IS its
    line-height. Padding it out would mean padding a word inside a
    paragraph, which moves the text around for no gain.
    """

    def test_the_footer_links_are_at_least_24px(self):
        css = re.sub(r"/\*.*?\*/", "",
                     (ROOT / "assets" / "styles.css").read_text(encoding="utf-8"),
                     flags=re.S)
        rule = css.split(".site-foot__links a {", 1)[1].split("}", 1)[0]
        m = re.search(r"min-width:\s*(\d+)px", rule)
        self.assertIsNotNone(
            m, "the footer links declare no minimum width, so a two-letter "
               "one like CV collapses to about 17px")
        self.assertGreaterEqual(
            int(m.group(1)), 24,
            "the footer link minimum is %spx, under the 24px that WCAG 2.5.8 "
            "asks of a target" % m.group(1))
        self.assertIn(
            "inline-block", rule,
            "min-width does nothing on an inline element; the link needs a "
            "block-level display for it to apply")


class TestCustomProperties(BuildCase):
    """Every var() in the stylesheet has to resolve to something.

    This exists because of a bug that shipped into a branch and was caught
    from a SCREENSHOT rather than from the code: `.grid--lg` was written
    with `gap: var(--space-20)`, and there is no --space-20. The scale is
    1,2,3,4,6,8,12,16,24,32.

    The failure mode is the nasty part. An undefined var() does not fall
    back to the previous declaration -- it makes the property "invalid at
    computed-value time", which resets it to its initial value. So `gap`
    became 0 rather than inheriting the 48px from the .grid rule above, the
    four case-study rows sat flush against each other, and one project's
    meta line touched the next project's title. Nothing warned; the
    stylesheet is valid CSS and the build was happy.

    A var() carrying a fallback is exempt: `var(--cols, 2)` is set per
    element from the HTML and is meant to be absent from the stylesheet.
    (`var(--dur, 30s)` was the other example until the marquee it timed
    was removed.)
    """

    def test_every_custom_property_resolves(self):
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        tokens = (ROOT / "assets" / "tokens.css").read_text(encoding="utf-8")
        generated = set(re.findall(r"(--[a-z0-9-]+)\s*:", tokens))
        local = set(re.findall(r"(--[a-z0-9-]+)\s*:", css))
        # var(--x) with no comma -- anything with a fallback is fine
        used = set(re.findall(r"var\(\s*(--[a-z0-9-]+)\s*\)", css))
        missing = sorted(used - generated - local)
        detail = []
        for name in missing:
            for i, line in enumerate(css.splitlines(), 1):
                if "var(%s)" % name in line:
                    detail.append("  %s  line %d: %s" % (name, i, line.strip()[:64]))
        self.assertEqual(
            missing, [],
            "these custom properties are referenced but never defined, and "
            "each one silently voids its whole declaration:\n%s"
            % "\n".join(detail))

    def test_the_spacing_scale_has_no_gaps_that_invite_the_mistake(self):
        """--space-20 was reached for because 16 and 24 sit either side of it.

        Not a demand that the scale be dense -- it is deliberately sparse.
        This just records which steps exist, so that the next person writing
        a spacing value checks the list instead of interpolating.
        """
        scale = json.loads(
            (ROOT / "tokens.json").read_text(encoding="utf-8"))["space"]
        self.assertEqual(
            sorted(scale, key=lambda k: float(k)),
            ["1", "2", "3", "4", "6", "8", "12", "16", "24", "32"],
            "the spacing scale changed; every var(--space-N) in the "
            "stylesheet needs rechecking against the new set")


class TestFigureWidth(BuildCase):
    """Case-study figures get the column; phone screens keep their grid.

    Manager feedback: "Donner plus d'espace aux images". Measured on Steer
    at a 1366 viewport, the prose column is 828px and the shots grid ran
    406px + 406px -- while a section holding a single figure already went
    the full 828px through the :only-child rule. The site had therefore
    already decided what a screenshot is worth; pairing was halving it.

    Phone screens are the exception and the reason this is a :not() rather
    than a blanket rule. They are portrait, narrow, and tagged from their
    intrinsic dimensions by build.py, so a 375-wide screen stretched to
    828px is only softer. Fixerloop is the case that proves it matters: 5
    of its 8 grids are phone grids.
    """

    def css(self):
        return (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")

    def test_landscape_figures_take_the_whole_column(self):
        self.assertIn(
            ".project__main .shots:not(.shots--phone) { grid-template-columns: 1fr; }",
            self.css(),
            "case-study figures are back to sharing the column two-up, at "
            "half the width the site gives a single figure")

    def test_phone_screens_keep_their_denser_grid(self):
        rule = self.css().split(".shots--phone {", 1)[1].split("}", 1)[0]
        self.assertIn("grid-template-columns", rule,
                      ".shots--phone no longer sets its own columns, so the "
                      "full-column rule will stretch phone screens")
        self.assertNotIn("1fr;", rule.replace("repeat", ""),
                         ".shots--phone looks like it went single-column")

    def figure_rules(self):
        """Every declaration block that styles a shot image.

        Comments are stripped FIRST. The prose around these rules quotes the
        old `object-fit: cover` and `max-height: 38vh` at length, explaining
        why they went -- scanning the raw file would match the explanation
        and fail on a correct stylesheet. That exact mistake has been made
        in this suite before, in the bare-env() test.
        """
        css = re.sub(r"/\*.*?\*/", "", self.css(), flags=re.S)
        # A LIST, not a dict keyed by selector. Two separate rules both use
        # the selector ".shot__btn img" -- a one-line base rule and a block
        # further down -- so a dict silently kept the last and dropped the
        # first. The first version of this helper did exactly that, and two
        # sabotages (cover and a cap put back on the BASE rule) passed a
        # green suite because the rule under test had been overwritten in
        # the collection step. Found by sabotaging it, not by reading it.
        out = []
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
            sel, body = m.group(1).strip(), m.group(2)
            if "shot__btn img" in sel:
                out.append((" ".join(sel.split()), body))
        self.assertTrue(out, "no rule styles a shot image any more")
        return out

    def test_there_is_exactly_one_height_cap(self):
        """Production had four, and which one a figure got was arbitrary.

        38vh by default, 56vh if the figure happened to be the only one in
        its section, 70vh and then 38vh again for anything over 2200px, 48vh
        for phones. Two figures of identical proportions rendered at
        different heights depending on how many siblings they had, which is
        the inconsistency the owner asked to fix. Cropping itself was asked
        for -- uncropping made InstaDeep 26,955px tall -- so this pins the
        count, not the absence.
        """
        caps = [(sel, v.strip()) for sel, body in self.figure_rules()
                for v in re.findall(r"max-height:\s*([^;]+)", body)
                if v.strip() != "none"]
        self.assertEqual(
            len(caps), 1,
            "expected exactly one height cap on a shot image, found %d: %s. "
            "Production's four caps are what made the figures inconsistent."
            % (len(caps), caps))

    def test_the_cap_scales_with_the_column_not_the_window(self):
        """A vh cap plus a wider column crops harder, silently.

        Production capped at 38vh while the column was 406px. Widening the
        column to 828px for "donner plus d'espace aux images" would have
        halved the fraction of each figure visible -- a change made to give
        images more room would have shown less of them. Measured against the
        53 non-phone figures, 5/6 of the frame width reproduces
        production's dominant geometry: 21 show in full and the median shows
        77% of itself, where production's paired treatment showed 21 and
        77%.
        """
        caps = [v.strip() for _, body in self.figure_rules()
                for v in re.findall(r"max-height:\s*([^;]+)", body)
                if v.strip() != "none"]
        self.assertTrue(caps, "the cap is gone entirely")
        self.assertRegex(
            caps[0], r"cqw",
            "the cap is %r, which is relative to the window rather than to "
            "the figure's own column. Change the column width and the crop "
            "changes with it, in the wrong direction." % caps[0])
        css = re.sub(r"/\*.*?\*/", "", self.css(), flags=re.S)
        self.assertIn(
            "container-type: inline-size", css,
            "nothing declares a container, so a cqw cap measures against "
            "the viewport and the scaling argument above does not hold")

    def test_phone_screens_are_exempt_from_the_cap(self):
        """A phone screenshot cropped at the waist is the agreed-wrong case.

        They are ~0.46 wide-to-tall, so 5/6 of their column would cut over
        half of each one off. They are also all the same proportion as one
        another, so they are consistent without any help.
        """
        rules = dict(self.figure_rules())
        phone = [body for sel, body in self.figure_rules() if "data-phone" in sel]
        self.assertTrue(phone, "phone screens no longer have their own rule")
        self.assertIn(
            "max-height: none", phone[0],
            "phone screens are not exempted from the height cap, so every "
            "one of them is now cut in half")
        self.assertIn(
            "max-width", phone[0],
            "phone screens have no width cap. build.py only tags a grid "
            ".shots--phone when EVERY image in it is a phone, so a phone in "
            "a mixed section inherits the full single-column width: "
            "f04-settings.png rendered 1754px tall beside siblings of "
            "383-735px until this was added.")

    def test_the_phone_variant_and_its_emitter_agree(self):
        """The styles and the code that emits the class travel together.

        This used to assert that some page currently rendered
        shots--phone, on the reasoning that a :not() guarding nothing is a
        comment pretending to be code. That was right about the failure
        and wrong about the test: the class is not opted into per project,
        it is DERIVED -- build.py measures each image and tags a section
        whose shots are mostly narrow portraits. So "no project happens to
        have phone screenshots right now" is a fact about the content, not
        a defect, and retiring the one project that had them (Fixerloop)
        made the old assertion fail without anything being wrong.

        What would actually be broken is the two halves disagreeing: an
        emitter with no styles renders phone screens in the wide grid, and
        styles with no emitter are unreachable. So assert they agree.
        """
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        build = (ROOT / "build.py").read_text(encoding="utf-8")
        styled = "shots--phone" in css
        emitted = "shots--phone" in build or "is_phone" in build
        self.assertEqual(
            styled, emitted,
            "phone-grid styles present: %s, emitter present: %s -- one of "
            "them was removed without the other" % (styled, emitted))

    def test_the_phone_variant_is_reachable_when_it_exists(self):
        """If the styles are there, the full-column rule must still exempt
        them -- that exemption is the whole reason the variant works."""
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        if "shots--phone" not in css:
            self.skipTest("phone variant removed; nothing to exempt")
        self.assertIn(
            ".shots:not(.shots--phone)", css,
            "the full-column rule no longer exempts the phone grid, so a "
            "phone section would render one screenshot per row")


class TestShareCards(BuildCase):

    def test_every_referenced_share_card_is_tracked(self):
        """An untracked og:image 404s on the host and every link preview breaks.

        The file exists locally, so the build is happy and nothing warns.
        """
        proc = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "projects"],
            cwd=str(ROOT), capture_output=True, text=True)
        untracked = set(proc.stdout.split())
        import re
        referenced = set()
        for page in (ROOT / "projects").glob("*.html"):
            for match in re.finditer(r'(projects/[^"\']*share\.jpg)',
                                     page.read_text(encoding="utf-8")):
                referenced.add(match.group(1))
        self.assertTrue(referenced, "no share cards referenced -- test is vacuous")
        self.assertEqual(referenced & untracked, set())

    def test_instadeep_has_its_own_share_card(self):
        page = self.html("projects/instadeep.html")
        self.assertIn("projects/10-instadeep/assets/share.jpg", page)

    def test_instadeep_share_card_is_not_the_absorbed_deeppcb_card(self):
        """The merged entry inherited DeepPCB's card when DeepPCB was absorbed.

        That card carries the DeepPCB wordmark and "The smart, fast, easy way
        to design PCBs", so every preview of the InstaDeep page advertises a
        different product. Asserting the path alone cannot catch this -- the
        path is right and the pixels are wrong -- so pin the known-bad bytes.
        """
        import hashlib
        card = ROOT / "projects" / "10-instadeep" / "assets" / "share.jpg"
        self.assertTrue(card.is_file(), "InstaDeep share card is missing")
        digest = hashlib.sha256(card.read_bytes()).hexdigest()
        self.assertNotEqual(
            digest,
            "cfa7a4c9449454cf080ee51112e230e2ee9b1f5f99780a9c4422a23b19d97255",
            "InstaDeep's og:image is still the absorbed DeepPCB card")

    def test_a_wide_source_is_trimmed_in_width_not_squeezed(self):
        """Over-wide sources must be centre-trimmed, never forced into shape.

        make_card ends with `sips -z 630 1200`, which sets both dimensions and
        so does NOT preserve aspect ratio. The row-cutting logic guarantees a
        1.91:1 band for a TALL source, but for a source already wider than
        1.91:1 cutting rows only makes it wider -- the old code clamped the
        band to the full height and let the resize squeeze the difference out.

        Unreachable while every card came from a tall screenshot, and reached
        the moment InstaDeep's cover became a 1300x650 brand plate: forcing
        2.000 into 1.905 compresses horizontally by 4.75%, on a centred logo
        carrying a registered trademark.

        Asserts the arithmetic on the real source rather than eyeballing the
        JPEG: with the width trimmed to h * 1.905 first, the x and y scale
        factors into 1200x630 must be equal.
        """
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "make_share_cards", ROOT / "tools" / "make-share-cards.py")
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)

        assets = ROOT / "projects" / "10-instadeep" / "assets"
        # Read the cover name rather than hardcoding it: the file was renamed
        # cover.jpg -> cover-brand.jpg to change the URL and defeat caches,
        # and a literal here silently resolved to None and crashed.
        project = json.loads(
            (assets.parent / "content.json").read_text(encoding="utf-8"))
        src = gen.best_source(assets, project["cover"].split("/")[-1])
        self.assertIsNotNone(src, "no usable source for the InstaDeep cover")
        w, h = gen.img_size(src)
        self.assertGreater(w / h, gen.OG_RATIO,
                           "InstaDeep's cover is no longer wider than 1.91:1, "
                           "so this test no longer exercises the trim path")

        trimmed = round(h * gen.OG_RATIO)
        scale_x = gen.OG_W / trimmed
        scale_y = gen.OG_H / h
        self.assertAlmostEqual(
            scale_x, scale_y, places=3,
            msg="card scaling is non-uniform (%.5f vs %.5f) -- the logo is "
                "being distorted" % (scale_x, scale_y))

    def test_instadeep_card_is_reproducible_by_the_generator(self):
        """The committed card must be what make-share-cards.py produces.

        It was not, for a while. The card was made by a one-off script that
        transcoded cover.full.jpg in a tempdir and called make_card directly,
        because the generator skipped InstaDeep twice over: the cover's 1.67
        ratio cleared the "no card needed" gate, and best_source accepted only
        PNG while InstaDeep has nothing but JPEG. So a correct card sat in the
        tree that no command in the repo could rebuild -- harmless until
        someone regenerates and silently gets nothing.

        This pins both halves. The dry run proves the project is still
        selected and still resolves to the expected source; the digest proves
        the bytes come back identical.

        The source is now `_src/cover-brand.png`, the 1300x650 brand plate that
        replaced the old Design System board -- that board carried a "Contact
        Abdou on Slack" strip along its bottom edge and named one of the three
        products on the page.

        If it ever fails on the digest alone -- same source, same band, but a
        different hash -- suspect the sips JPEG encoder changed with the OS
        before suspecting the card.
        """
        import contextlib
        import hashlib
        import importlib.util
        import io
        import tempfile

        assets = ROOT / "projects" / "10-instadeep" / "assets"
        committed = assets / "share.jpg"
        self.assertTrue(committed.is_file(), "InstaDeep share card is missing")

        proc = subprocess.run(
            [sys.executable, "tools/make-share-cards.py",
             "--dry-run", "--only", "instadeep"],
            cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("no card needed", proc.stdout,
                         "the ratio gate is skipping InstaDeep again")
        self.assertIn("_src/cover-brand.png", proc.stdout,
                      "InstaDeep is no longer sourcing from _src/cover-brand.png")

        spec = importlib.util.spec_from_file_location(
            "make_share_cards", ROOT / "tools" / "make-share-cards.py")
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)

        project = json.loads(
            (assets.parent / "content.json").read_text(encoding="utf-8"))
        src = gen.best_source(assets, project["cover"].split("/")[-1])
        self.assertIsNotNone(src, "no usable source for the InstaDeep card")

        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            rebuilt = tmp / "share.jpg"
            # crop_band narrates to stdout; useful on the CLI, noise here.
            with contextlib.redirect_stdout(io.StringIO()):
                gen.make_card(gen.as_png(src, tmp), rebuilt,
                              int(project.get("shareOffset", 0)))
            self.assertEqual(
                hashlib.sha256(rebuilt.read_bytes()).hexdigest(),
                hashlib.sha256(committed.read_bytes()).hexdigest(),
                "regenerating no longer reproduces the committed card")

    def test_every_share_card_is_exactly_1200x630(self):
        """Platforms crop to ~1.91:1; a card that is not 1200x630 is not a card."""
        sys.path.insert(0, str(ROOT))
        from build import png_size
        cards = sorted((ROOT / "projects").glob("*/assets/share.jpg"))
        self.assertTrue(cards, "no share cards on disk -- test is vacuous")
        for card in cards:
            self.assertEqual(png_size(card), (1200, 630),
                             "%s is %s, not 1200x630"
                             % (card.name, png_size(card)))




class TestContainerTints(BuildCase):
    """Every project names a container tint, and it reaches the page.

    The reason this is an invariant rather than a nicety: measured at their
    borders, all six covers are COOLER than the paper (warmth R-B: paper
    +12, covers 0 to -143). An untinted container means an image meets the
    page with nothing in between, which is the "feels pasted on" problem
    this was built to fix. A project added later with no tint would
    reintroduce it silently -- the page would still build, still pass every
    other test, and just look wrong.

    The CSS fallback keeps that from being a crash, so this test is what
    keeps it from being invisible.
    """

    TINTS = ("sand", "clay", "ash")

    def test_every_live_project_declares_a_known_tint(self):
        for folder, data in self.live_projects():
            with self.subTest(project=folder):
                self.assertIn(
                    data.get("tint"), self.TINTS,
                    "%s has tint %r; expected one of %s"
                    % (folder, data.get("tint"), ", ".join(self.TINTS)))

    def test_retired_projects_also_carry_one(self):
        # Un-retiring should be flipping one flag, not two.
        for path in sorted((ROOT / "projects").glob("*/content.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("published") is False:
                with self.subTest(project=path.parent.name):
                    self.assertIn(data.get("tint"), self.TINTS)

    def test_each_tint_is_defined_in_the_stylesheet(self):
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        for tint in self.TINTS:
            with self.subTest(tint=tint):
                self.assertIn('[data-tint="%s"]' % tint, css)
                self.assertRegex(
                    css,
                    r'\[data-tint="%s"\]\s*\{\s*--tint:\s*var\(--color-media-\w+\);?\s*\}'
                    % tint)

    def test_every_media_tint_steps_toward_the_screenshot(self):
        """The frame sits BETWEEN the page and the image. That is its job.

        On the warm-paper build this read as "every tint must be warm",
        because every screenshot was cooler than the page and the frame had
        to meet it halfway. The site is near-black now and the direction
        inverted: screenshots are LIGHTER than the page, so a frame that is
        darker than the page leans away from the thing it frames and the
        hard edge comes back.

        So the rule is stated in the general form it always had. For the
        default (dark) theme every media tint is lighter than the page; for
        the light theme every one is darker.
        """
        tokens = json.loads(
            (ROOT / "tokens.json").read_text(encoding="utf-8"))

        def luma(h):
            def ch(c):
                c /= 255
                return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
            r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
            return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)

        for group, lighter in (("color", True), ("colorLight", False)):
            palette = tokens[group]
            page = luma(palette["bg"])
            for name, hexv in palette.items():
                if not name.startswith("media"):
                    continue
                with self.subTest(theme=group, token=name):
                    if lighter:
                        self.assertGreater(
                            luma(hexv), page,
                            "%s (%s) is darker than the page it frames, so it "
                            "leans away from the screenshot" % (name, hexv))
                    else:
                        self.assertLess(
                            luma(hexv), page,
                            "%s (%s) is lighter than the page it frames"
                            % (name, hexv))

    def test_the_media_family_holds_one_lightness(self):
        """Hue is the only variable; otherwise the page pulses as it scrolls.

        Five covers each carrying a different tint means five frames down
        one column. If their lightness varied too, scrolling would visibly
        brighten and dim and the tints would read as a mistake.
        """
        tokens = json.loads(
            (ROOT / "tokens.json").read_text(encoding="utf-8"))

        def luma(h):
            def ch(c):
                c /= 255
                return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
            r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
            return (0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)) * 100

        for group in ("color", "colorLight"):
            vals = [(k, luma(v)) for k, v in tokens[group].items()
                    if k.startswith("media")]
            spread = max(l for _, l in vals) - min(l for _, l in vals)
            with self.subTest(theme=group):
                self.assertLess(
                    spread, 1.5,
                    "%s media tints span %.2f of luma (%s)"
                    % (group, spread, ", ".join("%s %.2f" % x for x in vals)))

    def test_the_tint_reaches_every_case_study_article(self):
        for folder, data in self.live_projects():
            page = (ROOT / "projects" / ("%s.html" % data["slug"])
                    ).read_text(encoding="utf-8")
            with self.subTest(project=folder):
                self.assertIn(
                    '<article class="project" data-tint="%s">' % data["tint"],
                    page)

    def css(self):
        return (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")

    def test_every_case_study_declares_a_tint(self):
        """The tint moved off the homepage, because its covers did.

        It used to be asserted on every cover in the work rail, where the
        image sat inset inside a tinted frame. The homepage renders cards
        with full-bleed covers now, so a tint there would be a colour
        nobody ever sees and the attribute was removed from them.

        Where it still earns its place is the case studies: the article
        declares the tint and every inset screenshot inside it sits on it.
        """
        for _, data in self.live_projects():
            page = "projects/%s.html" % data["slug"]
            with self.subTest(page=page):
                m = re.search(r'<article class="project"([^>]*)>', self.html(page))
                self.assertIsNotNone(m, "%s has no project article" % page)
                self.assertRegex(m.group(1), r'data-tint="(sand|clay|ash)"',
                                 "%s declares no tint" % page)


    def test_the_image_is_inset_so_the_tint_is_actually_visible(self):
        """A tint behind a full-bleed image is a colour nobody sees.

        .shot__btn is the frame that holds an inset screenshot on a case
        study. Remove its padding and the image covers the tint exactly,
        which is the state this replaced: warm paper, a hard rule, then a
        cool screenshot with nothing between them.
        """
        rule = re.search(r"\.shot__btn\s*\{([^}]*)\}", self.css())
        self.assertIsNotNone(rule, "no inset frame in the stylesheet")
        self.assertRegex(rule.group(1), r"padding:\s*var\(--space-\d+\)",
                         "the frame has no inset, so no tint shows")


    def test_no_container_still_paints_itself_white(self):
        """bg-raised is #FFFFFF -- the one value that cannot merge with paper."""
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        for selector in (r"\.card__media\s*\{", r"\.shot__btn\s*\{"):
            bodies = "".join(m.group(1) for m in
                             re.finditer(selector + r"([^}]*)\}", css))
            with self.subTest(selector=selector):
                self.assertNotIn("--color-bg-raised", bodies)


class TestMaskedHeadingsHaveNoPhantomLine(BuildCase):
    """A <br> between two masked lines renders an EMPTY line box.

    .mask and .mask__in are both display:block, so masked lines already
    stack. Joining them with <br> as well puts a line break between two
    block boxes, and the browser gives that break its own line -- a full
    line-height of nothing.

    On the about page that was 90px of phantom gap in an 87px heading: two
    lines of type measured 370px tall where they should measure 181. It is
    invisible in the markup, survives every other test, and just looks like
    someone chose a bad leading.
    """

    def pages(self):
        names = ["index.html", "work.html", "about.html"]
        for folder, data in self.live_projects():
            names.append("projects/%s.html" % data["slug"])
        return names

    def test_no_br_sits_between_two_masked_lines(self):
        pattern = re.compile(r'</span>\s*<br\s*/?>\s*<span class="mask"')
        for name in self.pages():
            with self.subTest(page=name):
                self.assertIsNone(
                    pattern.search(self.html(name)),
                    "%s joins masked lines with <br>, which renders an empty "
                    "line between them" % name)

    def test_the_about_statement_is_two_stacked_masks(self):
        html = self.html("about.html")
        statement = re.search(r'<h1 class="about__statement">(.*?)</h1>',
                              html, re.S)
        self.assertIsNotNone(statement)
        inner = statement.group(1)
        self.assertEqual(inner.count('<span class="mask">'), 2)
        self.assertNotIn("<br>", inner)


class TestCursorLabel(BuildCase):
    """The contextual label that replaced the cursor trail.

    The trail it replaced was always on, drew under the pointer wherever it
    went, and at 6% ink under a 9px blur left grey smudges across the
    headline. Every assertion here is one of the ways that could come back.
    """

    def js(self):
        return (ROOT / "assets" / "enhance.js").read_text(encoding="utf-8")

    def css(self):
        return (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")

    def block(self):
        """Just this module. Bounded by the one that follows it, because an
        unbounded split runs into unrelated code and makes the assertions
        below lie about what the cursor label does."""
        js = self.js()
        self.assertIn("contextual cursor label", js, "the module is gone")
        after = js.split("contextual cursor label", 1)[1]
        end = after.find("theme toggle")
        self.assertGreater(end, 0, "cannot find the end of the cursor module")
        return after[:end]

    def rule(self):
        css = self.css()
        self.assertIn(".cursor-label {", css, "the label has no styles")
        return css.split(".cursor-label {", 1)[1].split("}", 1)[0]

    def test_it_cannot_intercept_a_click(self):
        """It tracks the pointer, so without this it would eat every click."""
        self.assertIn("pointer-events: none", self.rule())

    def test_it_is_hidden_from_assistive_tech(self):
        """It restates an affordance the page already gives in text."""
        self.assertIn('setAttribute(\'aria-hidden\', \'true\')', self.block())

    def test_it_never_renders_at_rest(self):
        """The trail's defining flaw was being visible with nothing to say.

        Hidden is the default state in CSS; the class is added only when a
        target is under the pointer.
        """
        rule = self.rule()
        self.assertIn("opacity: 0", rule)
        self.assertIn("visibility: hidden", rule)
        self.assertIn(".cursor-label.is-on", self.css(),
                      "nothing ever shows it")

    def test_it_is_offset_so_it_cannot_cover_what_it_labels(self):
        """Drawn ON the hotspot it would be the smudge again, just sharper."""
        rule = self.rule()
        margin = re.search(r"margin:\s*(\d+)px\s+\d+\s+\d+\s+(\d+)px", rule)
        self.assertIsNotNone(margin, "no offset from the pointer")
        self.assertGreater(int(margin.group(1)), 0, "sits on the pointer vertically")
        self.assertGreater(int(margin.group(2)), 0, "sits on the pointer horizontally")

    def test_nothing_is_built_without_a_fine_pointer(self):
        """A touch screen has no hover, so there is nothing to label."""
        block = self.block()
        guard = block.split("createElement", 1)[0]
        self.assertIn("(pointer: fine)", guard,
                      "the element is created before the pointer is checked")

    def test_reduced_motion_keeps_the_label_and_drops_the_easing(self):
        """The label is information; the easing is the only motion in it."""
        css = self.css()
        self.assertRegex(
            css,
            r"@media \(prefers-reduced-motion: reduce\) \{[^}]*\.cursor-label",
            "the label does not respond to reduced motion at all")
        block = css.split("prefers-reduced-motion: reduce", 1)[1]
        block = block[:block.index("\n}\n")]
        self.assertNotIn("display: none", block,
                         "reduced motion hides the label outright, which "
                         "removes information rather than movement")

    def test_it_says_nothing_inside_the_lightbox(self):
        """The image is already full screen there, so 'Open' would be a lie."""
        self.assertIn("closest('.lb')", self.block())

    def test_the_transform_is_batched_to_one_frame(self):
        """pointermove fires far faster than the screen repaints."""
        block = self.block()
        self.assertIn("requestAnimationFrame", block)
        self.assertIn("if (!pframe)", block,
                      "a frame is requested per event rather than per paint")

    def test_it_labels_only_the_non_obvious_targets(self):
        """Buttons and nav links already read as pressable.

        Labelling them would be the trail's other mistake -- decoration
        dressed as help -- so the list stays short and specific.
        """
        block = self.block()
        self.assertIn(".shot__btn", block)
        self.assertIn(".card__link", block)
        for noise in ("'.btn'", '".btn"', ".site-nav", ".fan__card"):
            self.assertNotIn(
                noise, block,
                "%s is in the cursor-label target list, but it already "
                "looks clickable" % noise)


class TestNoEmDashes(BuildCase):
    """Zero em-dashes and en-dashes in anything a visitor can see.

    The site shipped 71 em-dashes and 9 en-dashes. They are the clearest
    signal that copy was machine-written, which matters more than usual
    here: reviewers now discount case studies precisely because authorship
    is hard to verify, so the punctuation that reads as AI is a cost the
    work does not need to carry.

    Attributes are checked as well as text. A dash in a <title> shows in
    the tab, the bookmark and the search result; a dash in alt text is
    read aloud. Both are visible, just not in the body.

    Comments are stripped before checking. A dash inside a CSS or HTML
    comment reaches nobody.
    """

    DASHES = ("—", "–")

    def pages(self):
        names = ["index.html", "work.html", "about.html"]
        for _, data in self.live_projects():
            names.append("projects/%s.html" % data["slug"])
        return names

    def stripped(self, name):
        h = self.html(name)
        for pattern in (r"<script.*?</script>", r"<style.*?</style>", r"<!--.*?-->"):
            h = re.sub(pattern, " ", h, flags=re.S)
        return h

    def test_no_page_ships_a_dash(self):
        for name in self.pages():
            h = self.stripped(name)
            with self.subTest(page=name):
                found = sum(h.count(d) for d in self.DASHES)
                if found:
                    ctx = []
                    for d in self.DASHES:
                        for m in re.finditer(re.escape(d), h):
                            ctx.append(" ".join(
                                h[max(0, m.start()-40):m.end()+40].split()))
                    self.fail("%s ships %d dash(es): %s"
                              % (name, found, " | ".join(ctx[:3])))

    def test_the_source_is_clean_too(self):
        """Fixing the HTML and not the JSON means the next build undoes it."""
        import glob
        for path in sorted(glob.glob(str(ROOT / "projects" / "*" / "content.json"))):
            data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
            if data.get("published") is False:
                continue
            blob = json.dumps(data, ensure_ascii=False)
            with self.subTest(project=pathlib.Path(path).parent.name):
                for d in self.DASHES:
                    self.assertNotIn(d, blob)
        site = json.dumps(self.site, ensure_ascii=False)
        for d in self.DASHES:
            self.assertNotIn(d, site, "site.json still holds a dash")


class TestDarkMode(BuildCase):
    """The site has two themes, and they stay in step.

    It was light-only. A portfolio read on a dark-mode machine rendered a
    bright cream page in a dark browser, which is the one place the craft
    was working against itself.
    """

    def tokens(self):
        return json.loads((ROOT / "tokens.json").read_text(encoding="utf-8"))

    def css(self):
        return (ROOT / "assets" / "tokens.css").read_text(encoding="utf-8")

    def test_the_two_palettes_are_one_to_one(self):
        """A missing value is one element lit from the wrong palette.

        It does not raise and it does not look obviously broken, which is
        exactly why it needs a test.
        """
        t = self.tokens()
        default, alt = set(t["color"]), set(t.get("colorLight", {}))
        self.assertEqual(default, alt,
                         "default-only: %s. light-only: %s"
                         % (sorted(default - alt), sorted(alt - default)))

    def test_both_selectors_are_emitted(self):
        """System preference AND an explicit choice, and the guard between.

        Without :not([data-theme="light"]) a visitor who picks light on a
        dark-system machine gets the media query applied anyway, and the
        toggle appears broken.
        """
        css = self.css()
        # Dark is the DEFAULT, so :root carries it and light is the override.
        # Emitting light in :root would flash white on every cold load.
        # Read from tokens.json, not typed. This asserted "#060C0B" -- the
        # near-black of the teal palette -- and went on asserting it after
        # the palette moved to ember, because this class sat below
        # unittest.main() and was never collected. A literal here is a
        # second copy of a value that has exactly one source.
        expected = json.loads(
            (ROOT / "tokens.json").read_text(encoding="utf-8"))["color"]["bg"]
        self.assertIn("--color-bg: %s" % expected, css.split("@media", 1)[0],
                      "the dark palette is not the :root default")
        self.assertIn("@media (prefers-color-scheme: light)", css)
        self.assertIn(':root:not([data-theme="dark"])', css)
        self.assertIn(':root[data-theme="light"]', css)

    def test_color_scheme_lets_the_browser_follow(self):
        """Form controls, scrollbars and spinners are drawn by the browser.

        Without this they stay light on a dark page.
        """
        self.assertIn("color-scheme: dark light", self.css())

    def test_styles_hold_no_colour_literals(self):
        """A literal cannot follow the theme, so it is a dark-mode bug.

        The six tinted shadows were the last of them: ink-coloured, which
        on a dark page means a shadow the same colour as the surface.
        """
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        lits = re.findall(r"(#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\))", css)
        self.assertEqual(lits, [],
                         "styles.css holds colour literals that cannot "
                         "follow the theme: %s" % lits[:5])

    def test_the_no_flash_script_runs_before_paint(self):
        """Deferred, it runs after the first frame, and that frame IS the flash."""
        for page in ("index.html", "about.html"):
            h = self.html(page)
            head = h.split("</head>", 1)[0]
            with self.subTest(page=page):
                self.assertIn('localStorage.getItem("theme")', head,
                              "the theme is not restored before paint")
                # the <script> that holds it must be inline and synchronous
                tag = None
                for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>",
                                     head, re.S):
                    if "localStorage" in m.group(2):
                        tag = m
                        break
                self.assertIsNotNone(tag, "no inline script restores the theme")
                attrs, body = tag.group(1), tag.group(2)
                self.assertNotIn("defer", attrs,
                                 "a deferred script runs after the first "
                                 "frame, and that frame is the flash")
                self.assertNotIn("async", attrs)
                self.assertNotIn("src=", attrs,
                                 "an external script is a round trip before "
                                 "the page can paint its own theme")
                self.assertIn("try", body,
                              "localStorage throws in Safari private mode; "
                              "an unguarded read takes the head with it")


class TestThemeToggle(BuildCase):
    """The control that lets a visitor override the system.

    The warm paper is most of what this site's identity is. Following the
    system alone means a visitor on a dark machine never sees it.
    """

    def test_it_is_on_every_page(self):
        for page in ("index.html", "work.html", "about.html"):
            with self.subTest(page=page):
                self.assertIn('class="theme-toggle"', self.html(page))

    def test_it_is_a_button_not_a_link(self):
        """It changes the page's state; it does not navigate."""
        h = self.html("index.html")
        m = re.search(r'<button class="theme-toggle"[^>]*>', h)
        self.assertIsNotNone(m, "the toggle is not a <button>")
        self.assertIn('type="button"', m.group(0),
                      "a button without type defaults to submit")
        self.assertIn("aria-pressed", m.group(0),
                      "nothing tells a screen reader the state")
        self.assertIn("aria-label", m.group(0),
                      "the control is a shape with no accessible name")

    def test_the_target_is_large_enough(self):
        """WCAG 2.5.8 asks 24x24; the platform norm for touch is 44."""
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        block = re.search(r"\.theme-toggle\s*\{([^}]*)\}", css)
        self.assertIsNotNone(block)
        w = re.search(r"width:\s*(\d+)px", block.group(1))
        self.assertIsNotNone(w, "no explicit width on the toggle")
        self.assertGreaterEqual(int(w.group(1)), 44)

    def test_nothing_is_stored_until_the_visitor_chooses(self):
        """Stamping a theme on first visit means never following the system again."""
        js = (ROOT / "assets" / "enhance.js").read_text(encoding="utf-8")
        block = js.split("theme toggle", 1)[1].split("/* ──", 1)[0]
        setter = block.index("localStorage.setItem")
        click = block.index('addEventListener("click"')
        self.assertLess(click, setter,
                        "the theme is written to storage outside the click "
                        "handler, so a first visit pins the theme forever")


class TestViewTransitions(BuildCase):
    """Navigation reads as one site rather than a stack of documents."""

    def css(self):
        return (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")

    def test_the_at_rule_is_present(self):
        self.assertIn("@view-transition", self.css())
        self.assertIn("navigation: auto", self.css())

    def test_exactly_one_element_is_named(self):
        """Naming several turns a transition into a slideshow."""
        names = re.findall(r"view-transition-name:\s*([\w-]+)", self.css())
        self.assertEqual(len(names), 1,
                         "expected one named element, got %s" % names)

    def test_reduced_motion_stops_the_animation(self):
        """WCAG 2.3.3: motion the visitor did not ask for."""
        css = self.css()
        blocks = re.findall(
            r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", css, re.S)
        self.assertTrue(
            any("view-transition" in b for b in blocks),
            "view transitions ignore prefers-reduced-motion")


class TestScrollDrivenMotion(BuildCase):
    """The motion layer, and the one way it can hide the work.

    Scroll-driven animation fails in a specific, expensive way: an element
    whose keyframes start at `opacity: 0` and whose timeline never runs
    stays at zero forever. On a portfolio that means a blank page where the
    work should be, in exactly the browsers that cannot report it.
    """

    def css(self):
        return (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")

    def test_every_timeline_is_behind_a_supports_guard(self):
        """Unsupported browsers must get the page, not an empty column."""
        css = re.sub(r"/\*.*?\*/", "", self.css(), flags=re.S)   # comments out
        self.assertIn("animation-timeline", css, "the motion layer is gone")
        guards = re.findall(r"@supports \(animation-timeline:", css)
        self.assertTrue(guards, "no @supports guard around scroll-driven motion")
        # Every DECLARATION must sit inside a guard. Scanned per line and
        # skipping @supports lines, because the guard's own CONDITION reads
        # `@supports (animation-timeline: view())` -- matching the bare
        # string, or a regex that runs to the next semicolon, counts the
        # guard as the thing it is guarding against.
        guards_seen = 0
        for line in css.splitlines():
            stripped = line.strip()
            if stripped.startswith("@supports") and "animation-timeline" in stripped:
                guards_seen += 1
                continue
            if re.match(r"animation-timeline\s*:", stripped):
                self.assertGreater(
                    guards_seen, 0,
                    "%r is declared before any @supports guard, so an "
                    "unsupporting browser would hold the element at its "
                    "from-state" % stripped)

    def test_the_resting_state_is_the_visible_one(self):
        """Outside the guard every element must already be in its end state.

        The keyframes animate FROM transparent TO solid. Nothing may set
        opacity: 0 on these elements outside the guarded block, or the
        fallback is a blank element rather than a static one.
        """
        css = self.css()
        outside = re.sub(
            r"@supports \(animation-timeline: view\(\)\)\s*\{.*?\n\}",
            "", css, flags=re.S)
        for sel in (r"\.card__media", r"\.shot\b"):
            blocks = "".join(m.group(1) for m in
                             re.finditer(sel + r"\s*\{([^}]*)\}", outside))
            with self.subTest(selector=sel):
                self.assertNotRegex(
                    blocks, r"opacity:\s*0\s*;",
                    "%s is transparent outside the @supports guard" % sel)

    def test_reduced_motion_is_honoured(self):
        """Scroll-linked movement is movement nobody asked for."""
        css = self.css()
        guard = css.split("@supports (animation-timeline: view())", 1)[1]
        head = guard[:400]
        self.assertIn("prefers-reduced-motion: no-preference", head,
                      "scroll-driven motion is not gated on reduced motion")

    def test_the_hero_cascade_holds_its_end_state(self):
        """`both` is what stops the hero snapping back after it lands."""
        css = self.css()
        block = re.search(r"\.opening__status,(.*?)\n\}", css, re.S)
        self.assertIsNotNone(block, "the hero cascade is gone")
        self.assertIn("both", block.group(1),
                      "the hero animation has no fill-mode, so it reverts "
                      "to transparent when it finishes")

    def test_motion_adds_no_library(self):
        """The layer is declarative: no animation library on the main thread."""
        js = (ROOT / "assets" / "enhance.js").read_text(encoding="utf-8")
        self.assertNotIn("ScrollTrigger", js)
        self.assertNotIn("gsap", js.lower())

    def test_no_scroll_listener_drives_an_animation(self):
        """A scroll handler runs on every scroll frame. CSS timelines do not.

        Counted rather than matched, so a failure names the number instead
        of printing the whole file.

        One listener remains and is allowed: the table-of-contents marker
        reads the position of several headings to decide which is current.
        That is a QUERY, not an animation, and no declarative timeline
        expresses "whichever of these is nearest the top".
        """
        js = (ROOT / "assets" / "enhance.js").read_text(encoding="utf-8")
        listeners = len(re.findall(r"addEventListener\(\s*['\"]scroll['\"]", js))
        self.assertLessEqual(
            listeners, 1,
            "%d scroll listeners; anything that drives an animation belongs "
            "on an animation-timeline instead" % listeners)


class TestTheClaimAssembles(BuildCase):
    """The hero's selection frame, and the two ways it could cost more than
    it is worth.

    The last line of the h1 is framed on load the way a design tool frames
    a selected layer: edges, four corner handles, and a label naming it.
    It holds for about a second and releases.

    Failure one is the same shape as the scroll-driven case next door. The
    decorations are drawn by an animation, so if the animation never runs
    -- old browser, reduced motion, anything -- whatever they rest at is
    what the visitor gets forever. They rest at opacity 0, which means the
    failure mode is the finished page rather than a permanent orange box
    around the headline.

    Failure two is the accessibility tree. A frame is decoration, and
    decoration that reaches a screen reader as content is worse than no
    frame at all. It is drawn entirely on ::before and ::after, so the
    heading's text is still exactly the sentence.
    """

    def css(self):
        return (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")

    def test_only_the_last_claim_line_is_framed(self):
        page = self.html("index.html")
        lines = self.site["heroClaim"].split("\n")
        self.assertEqual(page.count('class="claim__line"'), len(lines) - 1)
        self.assertEqual(page.count('class="claim__line claim__line--built"'), 1)
        # and it is the LAST one, not whichever line happens to match
        last = html.escape(lines[-1], quote=True)
        self.assertIn('claim__line--built">%s</span></h1>' % last, page)

    def test_the_decorations_rest_invisible(self):
        """So a browser that ignores the animation gets the end state."""
        css = self.css()
        rest = re.search(
            r"\.claim__line--built::before,\s*\n\s*\.claim__line--built::after\s*\{([^}]*)\}",
            css)
        self.assertIsNotNone(rest, "the two decoration layers share no resting rule")
        self.assertIn("opacity: 0", rest.group(1),
                      "the frame does not rest invisible, so a browser that "
                      "never runs the animation keeps it on screen forever")

    def test_the_animation_is_behind_a_reduced_motion_guard(self):
        css = self.css()
        for name in ("claim-frame", "claim-tag"):
            decl = re.search(r"animation:\s*%s\b[^;]*;" % name, css)
            self.assertIsNotNone(decl, "%s is never used" % name)
            before = css[:decl.start()]
            opened = before.rfind("@media (prefers-reduced-motion: no-preference)")
            self.assertNotEqual(opened, -1,
                                "%s is not inside a reduced-motion guard" % name)
            # the guard must still be open where the declaration sits
            self.assertGreater(before.count("{", opened), before.count("}", opened),
                               "%s sits after its guard closed" % name)

    def test_both_keyframes_end_invisible(self):
        """Nothing is left drawn on the headline when the beat is over."""
        css = self.css()
        for name in ("claim-frame", "claim-tag"):
            body = re.search(r"@keyframes %s\s*\{(.*?)\n\}" % name, css, re.S)
            self.assertIsNotNone(body, "@keyframes %s is missing" % name)
            end = re.search(r"100%\s*\{([^}]*)\}", body.group(1))
            self.assertIsNotNone(end, "%s has no 100%% stop" % name)
            self.assertIn("opacity: 0", end.group(1),
                          "%s ends with something still on screen" % name)

    def test_the_frame_can_be_brought_back(self):
        """The one-shot problem, and the one-word cause of it.

        As first written the beat played once per page load and could
        never be seen again: arrive, look at the nav for a second, and
        the only motion on the site has already happened to you.

        Hovering the sentence selects it again. The subtle part is the
        fill mode. An animation beats a normal declaration in the
        cascade, so while `both` or `forwards` holds the end state the
        :hover rule cannot win and hover is silently dead -- the CSS
        looks right and does nothing. `backwards` fills the delay only
        and then lets go, which is what hands control back.
        """
        css = self.css()
        for name in ("claim-frame", "claim-tag"):
            decl = re.search(r"animation:\s*%s\b[^;]*;" % name, css).group(0)
            self.assertIn("backwards", decl,
                          "%s must fill backwards only" % name)
            self.assertNotIn("forwards", decl)
            self.assertNotRegex(decl, r"\bboth\b",
                                "%s holds its end state, which kills the "
                                "hover rule silently" % name)
        hover = re.search(
            r"\.claim__line--built:hover::before,\s*\n\s*"
            r"\.claim__line--built:hover::after\s*\{([^}]*)\}", css)
        self.assertIsNotNone(hover, "nothing brings the frame back")
        self.assertIn("opacity: 1", hover.group(1))
        # and the way back has to be a transition, since the animation
        # has finished by then and will not run again
        rest = re.search(
            r"\.claim__line--built::before,\s*\n\s*"
            r"\.claim__line--built::after\s*\{([^}]*)\}", css).group(1)
        self.assertIn("transition: opacity", rest)

    def test_the_frame_adds_nothing_to_the_heading_text(self):
        """Decoration on pseudo-elements, so the h1 still reads as a sentence."""
        page = self.html("index.html")
        h1 = re.search(r"<h1 class=\"opening__claim\">(.*?)</h1>", page, re.S).group(1)
        text = re.sub(r"<[^>]+>", "", h1)
        self.assertEqual(text, html.escape("".join(self.site["heroClaim"].split("\n")),
                                           quote=True),
                         "the h1 carries something other than the claim")
        self.assertNotIn("aria-", h1, "the frame should need no aria patching")


class TestTheAsk(BuildCase):
    """"Book a call" and "Copy email" -- the site's only two controls.

    They replaced a contact band, a nav link, three fanned cards and a
    row of link buttons, so between them they now carry every ask on the
    site. That concentration is the point and it is also the risk: one
    broken control is no way to get in touch at all.
    """

    def actions(self, page):
        # class="actions" OR "actions actions--single" -- /contact drops the
        # booking button and takes a modifier with it.
        m = re.search(r'<div class="actions[^"]*">(.*?)</div>', self.html(page), re.S)
        self.assertIsNotNone(m, "%s has no actions row" % page)
        return m.group(1)

    def test_copy_email_is_a_real_button(self):
        """Not a link, not a div.

        It acts on the page instead of going anywhere, so it is a
        <button>: that is what gives it the Space key, the right role and
        a form of focus the browser draws for free.
        """
        row = self.actions("index.html")
        self.assertRegex(row, r'<button[^>]*class="[^"]*js-copy[^"]*"[^>]*type="button"',
                         "Copy email is not a real <button type=button>")

    def test_book_a_call_goes_straight_to_cal_in_a_new_tab(self):
        """It pointed at /contact while the booker was embedded there.

        The embed is gone -- see CAL_LINK in build.py -- so this is an
        outbound link again, and an outbound link that replaces the tab
        makes the back button the only way back to the work.
        """
        sys.path.insert(0, str(ROOT))
        from build import CAL_LINK
        row = self.actions("index.html")
        book = re.search(r'<a class="btn btn--solid"[^>]*>', row).group(0)
        self.assertIn('href="%s"' % CAL_LINK, book)
        self.assertIn('target="_blank"', book)
        self.assertIn('rel="noopener"', book)


    def test_the_address_travels_with_the_button(self):
        row = self.actions("index.html")
        self.assertIn('data-copy="%s"' % self.site["email"], row,
                      "the copy button does not know what to copy")

    def test_the_result_is_announced(self):
        """A button's label changing under its own focus is not reliably
        announced, so the word "Copied" is written into a live region
        instead and the visible label changes for everyone else."""
        row = self.actions("index.html")
        self.assertIn('role="status"', row)
        self.assertIn('aria-live="polite"', row)
        self.assertIn("data-copy-status", row)

    def test_there_is_a_mailto_for_when_copying_is_not_possible(self):
        row = self.actions("index.html")
        self.assertIn('href="mailto:%s"' % self.site["email"], row,
                      "nothing to fall back to when the Clipboard API is absent")
        self.assertIn("js-copy-fallback", row)

    def test_the_fallback_is_hidden_until_it_is_needed(self):
        """Hidden in CSS, revealed by <noscript> or by the script.

        Without the noscript rule a visitor with JavaScript off gets a
        button that cannot copy and no link at all, which is strictly
        worse than the mailto this site shipped before.
        """
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.js-copy-fallback\s*\{\s*display:\s*none")
        page = self.html("index.html")
        noscript = re.search(r"<noscript>(.*?)</noscript>", page, re.S)
        self.assertIsNotNone(noscript, "no <noscript> rule swaps the control")
        self.assertIn(".js-copy{display:none}", noscript.group(1))
        self.assertIn(".js-copy-fallback{display:inline-flex}", noscript.group(1))

    def test_copy_email_is_not_a_system_button(self):
        """.btn dresses an <a> and a <button> as the same control.

        Only the <a> was getting dressed. A <button> with no reset keeps
        the user agent's own chrome, so "Copy email" shipped for months
        as a SYSTEM button: Arial instead of Instrument Sans, a flat
        #6B6B6B fill handed down by `color-scheme: dark`, appearance
        auto, and the arrow cursor -- sitting beside an ember pill that
        shared none of it.

        It survived because in the light theme the system grey passes
        for a designed grey, and because nothing here was looking. The
        reset is four properties and this is the test that keeps them.
        """
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        m = re.search(r"\n\.btn \{(.*?)\n\}", css, re.S)
        self.assertIsNotNone(m, "there is no .btn rule")
        block = m.group(1)
        for prop in ("appearance", "background", "font-family", "cursor"):
            with self.subTest(property=prop):
                self.assertRegex(block, r"\b%s:" % prop,
                                 ".btn does not reset %s, so a <button> "
                                 "keeps the browser's own" % prop)
        # The shorthand would wipe the font-size set two lines later.
        self.assertNotRegex(block, r"\bfont:\s",
                            "`font: inherit` resets font-size too")

    def test_the_script_checks_for_the_api_before_using_it(self):
        js = (ROOT / "assets" / "enhance.js").read_text(encoding="utf-8")
        self.assertIn("navigator.clipboard", js)
        self.assertRegex(js, r"navigator\.clipboard\s*&&\s*navigator\.clipboard\.writeText",
                         "the script uses the Clipboard API without checking "
                         "for it; it is undefined on plain http, which is how "
                         "this site is previewed")
        self.assertIn("2000", js, "the label never returns to normal")

    def test_the_calendar_url_has_exactly_one_source(self):
        """Swapping it must be a one-line edit, which it is not if the
        string is written out at each of the five places it appears."""
        src = (ROOT / "build.py").read_text(encoding="utf-8")
        literals = re.findall(r'"https://cal\.com/[^"]*"', src)
        self.assertEqual(len(literals), 1,
                         "the calendar URL is written %d times in build.py; "
                         "it should be CAL_LINK and nothing else" % len(literals))
        self.assertRegex(src, re.compile(r"^CAL_LINK = ", re.M))

    def test_every_page_carrying_the_actions_offers_both(self):
        """There is no page left that is the booker, so there is no page
        left that should drop the booking button."""
        for page in ("index.html", "about.html"):
            with self.subTest(page=page):
                row = self.actions(page)
                self.assertIn("Book a call", row)
                self.assertIn("Copy email", row)


class TestCopyBudget(BuildCase):
    """The word budgets from the brief, measured rather than estimated.

    The homepage said 557 words before this redesign and the about page
    said 478. A budget nobody measures is a budget nobody keeps, so the
    counter lives in build.py, runs on every build, and is asserted here
    against the numbers the brief set.

    Counted: everything a visitor can see except the nav and the footer.
    Not counted on the homepage: project names, which the brief excludes,
    and the mailto fallback, which is display:none for anyone whose
    browser can copy.
    """

    def words(self, page, drop):
        sys.path.insert(0, str(ROOT))
        from build import body_words
        return body_words(ROOT / page, drop=drop)

    def test_the_homepage_stays_lean(self):
        """The cap was 60, then 130, and is 150. Each step is argued.

        60 was right for a page whose three cards said "AI . Design
        system . 2024-now" and relegated two projects to a footnote. The
        index replaced them with five rows that each say what the
        project WAS, which is the whole content argument of the
        redesign, and that is worth about 60 words on its own. That
        bought 130.

        150 is what the recruiter pass cost, and the list is short
        enough to audit:

          +3   "acquired by BioNTech" in the hero meta line -- the one
               name on this site a hiring manager outside Tunisia
               recognises, and it was only in a case study
          +5   the availability badge
          +1   the "or" joining the hero's two controls
          +16  the proof line in the closing band: the h1 claims "I
               build what I design" and until now the page asserted it
               and changed the subject
          +8   the address in plain text and the reply time

        Every one of those is a thing somebody looking to hire or brief
        you came here to find out. That is the bar for spending from
        this budget, and it is still a cap: 150 leaves room for one
        more project row and nothing else. Prose creeping back onto
        this page fails here.
        """
        sys.path.insert(0, str(ROOT))
        from build import HOME_NOT_COPY
        n = self.words("index.html", HOME_NOT_COPY)
        self.assertLess(n, 150, "the homepage body copy is %d words" % n)


    def test_the_about_page_is_under_a_hundred_and_sixty_words(self):
        n = self.words("about.html", {"js-copy-fallback"})
        self.assertLess(n, 160, "the about page is %d words" % n)

    def test_the_counter_excludes_the_chrome_it_claims_to(self):
        """Guards the measurement itself.

        A counter that stopped dropping the footer would report a bigger
        number and the budgets would fail for a reason that has nothing
        to do with the copy. One that stopped dropping the nav would
        quietly make the budget easier to blow.

        Counted twice: once as the budget counts it, and once with the
        chrome allowed back in. The second has to be larger, or nothing
        is being dropped at all.
        """
        sys.path.insert(0, str(ROOT))
        from build import body_words
        budget = body_words(ROOT / "index.html")
        visible = re.sub(r"<(script|style|head)\b.*?</\1>", " ",
                         self.html("index.html"), flags=re.S)
        visible = re.sub(r"<[^>]+>", " ", visible)
        raw = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019@./+-]*", visible))
        self.assertGreater(raw, budget,
                           "the counter is not dropping the nav and footer: "
                           "it reports %d words of %d visible" % (budget, raw))




class TestTheRecruiterPass(BuildCase):
    """What a visitor who is deciding whether to contact you must find.

    The redesign cut the homepage from 601 words to 105 and the craft
    improved for it, but seven things went out with the prose that were
    not prose: they were the plumbing that turns a visitor into a
    message. Each one is cheap, none of them costs the design anything,
    and all seven are easy to drop again in the next tidy-up -- which is
    what this class is for.
    """

    PAGES = {"index.html": "home", "about.html": "about"}

    def test_every_page_carries_its_own_description(self):
        """Three pages shared one forty-character string.

        It was "Product designer. I build what I design." -- the h1
        again. That is the line Google prints under the result and the
        line Slack and LinkedIn print on the card when the URL is pasted
        into a hiring thread, so three pages were spending their one
        sentence saying nothing searchable.
        """
        seen = {}
        for page in self.PAGES:
            with self.subTest(page=page):
                m = re.search(r'<meta name="description" content="([^"]*)"',
                              self.html(page))
                self.assertIsNotNone(m, "%s has no description" % page)
                desc = m.group(1)
                self.assertNotIn(desc, seen,
                                 "%s repeats %s's description verbatim"
                                 % (page, seen.get(desc)))
                seen[desc] = page
                # Google truncates around 155. Under 40 is the old stub.
                self.assertGreater(len(desc), 60,
                                   "%s's description is %d chars, which is "
                                   "the stub again" % (page, len(desc)))
                self.assertLess(len(desc), 158,
                                "%s's description is %d chars and will be cut"
                                % (page, len(desc)))

    def test_the_description_is_not_the_h1_again(self):
        """A description that repeats the headline wastes the slot."""
        for page in self.PAGES:
            with self.subTest(page=page):
                html = self.html(page)
                desc = re.search(r'<meta name="description" content="([^"]*)"',
                                 html).group(1)
                self.assertNotIn("I build what I design.", desc)

    def test_the_homepage_names_biontech(self):
        """The one name on this site that travels.

        "Senior Product Designer at InstaDeep" means a great deal in
        Tunis and very little to a hiring manager in Berlin. "Acquired
        by BioNTech" is the fact that makes the same sentence legible
        anywhere, and the redesign left it in a case study two clicks
        down.
        """
        self.assertIn("BioNTech", self.html("index.html"),
                      "the homepage never says what InstaDeep is")

    def test_the_hero_asks_quietly_and_the_close_asks_loudly(self):
        """One .ask on the homepage, above its one .actions.

        The rule is deliberate -- a filled pill above the fold asks for
        the meeting before the visitor has seen anything -- and it is
        the kind of rule that reads later as two components that
        drifted. So it is asserted: the quiet one is first, the loud one
        is last, and no other page gets the quiet one.
        """
        home = self.html("index.html")
        self.assertEqual(home.count('<p class="ask">'), 1)
        self.assertLess(home.index('<p class="ask">'),
                        home.index('<div class="actions'),
                        "the loud ask comes before the quiet one")
        for page in ("about.html",):
            with self.subTest(page=page):
                self.assertNotIn('<p class="ask">', self.html(page),
                                 "%s uses the hero's ask" % page)

    def test_the_quiet_ask_keeps_all_four_parts(self):
        """Dressing the controls as text must not cost them anything.

        enhance.js finds the fallback and the live region through
        btn.parentNode, so all four have to be siblings inside the <p>
        or the copy button degrades into a button that does nothing.
        """
        m = re.search(r'<p class="ask">(.*?)</p>', self.html("index.html"), re.S)
        self.assertIsNotNone(m, "the homepage has no hero ask")
        row = m.group(1)
        sys.path.insert(0, str(ROOT))
        from build import CAL_LINK
        self.assertIn('href="%s"' % CAL_LINK, row)
        self.assertRegex(row, r'<button[^>]*class="[^"]*js-copy[^"]*"[^>]*type="button"')
        self.assertIn("js-copy-fallback", row, "no mailto fallback")
        self.assertIn('role="status"', row, "no live region")

    def test_the_fallback_follows_the_or(self):
        """With JavaScript off the sentence still has to read.

        The button hides and the mailto shows. Source order decides what
        is left: book, "or", [hidden button], mailto -- which reads
        "Book a call or Email me". Put the fallback before the "or" and
        it reads "Book a call Email me or".
        """
        row = re.search(r'<p class="ask">(.*?)</p>',
                        self.html("index.html"), re.S).group(1)
        self.assertLess(row.index('class="ask__or"'),
                        row.index("js-copy-fallback"))

    def test_the_availability_badge_is_in_the_ask_not_over_the_h1(self):
        """It was an eyebrow above the headline; it is a state now.

        Attached to the action it qualifies, it reads as a fact. Floated
        over the h1 it reads as a plea, which is the opposite of what it
        is for.
        """
        home = self.html("index.html")
        self.assertIn("ask__badge", home, "no availability badge")
        hero = home[:home.index("<h1")]
        self.assertNotIn("ask__badge", hero,
                         "the badge is back above the headline")

    def test_the_badge_dot_is_decoration(self):
        """A screen reader must not announce it twice.

        The label already says the thing. A dot with a role would make
        availability announce itself every time focus crossed the hero.
        """
        self.assertRegex(self.html("index.html"),
                         r'<span class="ask__dot" aria-hidden="true">')

    def test_the_address_is_readable_not_only_copyable(self):
        """"Copy email" serves the reader. It fails the relayer.

        The recruiter pasting an address into an applicant tracker, or
        forwarding you to the person who actually decides, needs the
        string on the page -- selectable, not behind a clipboard call
        that a webview may refuse.
        """
        sys.path.insert(0, str(ROOT))
        from build import SITE
        addr = SITE["email"]
        html = self.html("index.html")
        # Strip the places it hides: the copy payload and every href.
        hidden = re.sub(r'(data-copy|href)="[^"]*"', "", html)
        text = re.sub(r"<[^>]+>", " ", hidden)
        self.assertIn(addr, text,
                      "the address appears only inside attributes; nobody "
                      "can read it off the page")

    def test_the_page_says_what_happens_after_you_write(self):
        self.assertIn("reach__reply", self.html("index.html"),
                      "nothing on the page says whether you answer")

    def test_the_homepage_cashes_its_own_claim(self):
        """The h1 ends "I build what I design." and then said no more.

        It is the one sentence on this site that separates it from every
        other portfolio, and the redesign left it as an assertion with
        nothing behind it anywhere a visitor would see.
        """
        home = self.html("index.html")
        self.assertIn("close__proof", home, "the claim is never backed")
        proof = re.search(r'<p class="close__proof">(.*?)</p>', home, re.S).group(1)
        self.assertIn("test suite", proof)

    def test_the_footer_says_when_this_was_last_true(self):
        """A portfolio with no date on it is read as abandoned.

        "Is he still looking" is the first question, and the stamp
        answers it before anyone has to ask. It is derived from the
        newest mtime across the JSON sources, so it cannot claim a
        change nobody made.
        """
        sys.path.insert(0, str(ROOT))
        from build import content_updated
        _, stamp = content_updated()
        for page in self.PAGES:
            with self.subTest(page=page):
                foot = re.search(r'<p class="site-foot__note">(.*?)</p>',
                                 self.html(page), re.S).group(1)
                self.assertIn("Last updated %s" % stamp, foot)


class TestTheBooker(BuildCase):
    """"Book a call", which is a link now and not an embed.

    Cal's inline booker lived at /contact. Their free plan renders an
    attribution bar under it that no setting removes, and the bar is
    WHITE in both themes -- which on a near-black page was a bright slab
    with a logo on it, the least crafted thing on the site. The bar is
    cross-origin, so nothing here can style it (contentDocument is
    null), and clipping it would be dodging the attribution the free
    tier is paid for with. Measured first: cssVarsPerTheme DOES reach
    the iframe -- pushing cal-bg magenta recoloured the slots -- and the
    bar ignored it.

    So the booker moved to where it was always unremarkable: Cal's own
    page. That removed the last third-party script, and with it the last
    third-party request on the whole site.
    """

    PAGES = ("index.html", "work.html", "about.html")

    def pages(self):
        return list(self.PAGES) + ["projects/%s.html" % d["slug"]
                                   for _, d in self.live_projects()]

    def test_nothing_anywhere_loads_a_third_party_script(self):
        """The invariant the embed used to make expensive.

        It was "zero third-party requests on every page except one".
        There is no except now, and this is the test that keeps it: any
        embed, font, analytics tag or widget added later fails here
        before it reaches the page.
        """
        for page in self.pages():
            with self.subTest(page=page):
                html = self.html(page)
                for src in re.findall(r'<script[^>]*\bsrc="([^"]+)"', html):
                    self.assertFalse(
                        src.startswith("http") or src.startswith("//"),
                        "%s loads %s from another origin" % (page, src))
                self.assertNotIn("<iframe", html,
                                 "%s embeds a third-party frame" % page)

    def test_book_a_call_goes_straight_to_cal(self):
        """Three asks, one destination, one string in the source.

        The nav CTA, the hero's quiet ask and the closing band's loud
        one. They used to point at /contact and that page pointed at
        Cal, so the booking URL could rot in one place and look fine in
        the other two.
        """
        sys.path.insert(0, str(ROOT))
        from build import CAL_LINK
        self.assertTrue(CAL_LINK.startswith("https://cal.com/"))
        home = self.html("index.html")
        self.assertEqual(home.count('href="%s"' % CAL_LINK), 3,
                         "the homepage does not have exactly three routes "
                         "to the booker")
        self.assertNotIn("REPLACE-ME", home, "the placeholder link shipped")

    def test_the_booking_link_opens_in_its_own_tab(self):
        """Booking is a detour, not a destination.

        Sent off-site in the tab they were reading in, a visitor's way
        back to the work is the back button. Every one of the three says
        so in its accessible name too, because a new tab that announces
        itself only by appearing is WCAG 3.2.5.
        """
        sys.path.insert(0, str(ROOT))
        from build import CAL_LINK
        for page in self.pages():
            with self.subTest(page=page):
                html = self.html(page)
                for m in re.finditer(
                        r'<a[^>]*href="%s"[^>]*>(.*?)</a>' % re.escape(CAL_LINK),
                        html, re.S):
                    tag = m.group(0)[:m.group(0).index(">") + 1]
                    self.assertIn('target="_blank"', tag)
                    self.assertIn('rel="noopener"', tag)
                    self.assertIn("opens in a new tab", m.group(1),
                                  "a booking link changes context silently")

    def test_the_contact_route_is_gone_and_nothing_still_points_at_it(self):
        """A dead internal link is worse than no link.

        /contact was never published -- the live site has no such URL --
        so there is nothing to redirect and no inbound link to keep
        alive. What matters is that no page still offers the route.
        """
        self.assertFalse((ROOT / "contact.html").exists())
        for page in self.pages():
            with self.subTest(page=page):
                html = self.html(page)
                self.assertNotRegex(html, r'href="(\.\./)*contact"',
                                    "%s links to a page that no longer "
                                    "exists" % page)

    def test_no_booker_styles_outlived_the_booker(self):
        """Dead CSS is how a stylesheet stops describing the site."""
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        for sel in (".cal ", ".cal{", ".cal {", ".cal__", ".band--book",
                    ".actions--single"):
            with self.subTest(selector=sel):
                self.assertNotIn(sel, css)


# ── the runner ───────────────────────────────────────────────────────────
# This block MUST stay at the bottom of the file. It spent a long time in
# the middle of it, and unittest.main() runs at the point it is reached:
# every class defined below it was never collected. That was 13 classes
# and 66 test methods, among them the em-dash ban, the dark-mode set, the
# theme toggle, the scroll-driven motion guards and the hero animation --
# all reported green by a runner that had never seen them.
#
# It is also why this file counted 207 tests while the runner said 141.
if __name__ == "__main__":
    unittest.main(verbosity=2)
