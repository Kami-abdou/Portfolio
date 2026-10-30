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


    def row(self, slug):
        m = re.search(r'<li class="index__row">.*?projects/%s".*?</li>'
                      % re.escape(slug), self.html("index.html"), re.S)
        self.assertIsNotNone(m, "%s has no row" % slug)
        return m.group(0)

    def test_a_row_says_what_the_project_was(self):
        """Each row carries a line, a domain and a year -- and takes all
        three from the project itself.

        The homepage used to author its own tag and years per project,
        which is the same fact written in two files. The row reads what
        the case study already has, so the two cannot drift. That is the
        invariant; which key supplies the line is not.
        """
        for _, data in self.live_projects():
            with self.subTest(slug=data["slug"]):
                body = self.row(data["slug"])
                line = data.get("indexLine") or data["tagline"]
                self.assertIn(html.escape(line, quote=True), body,
                              "%s's row does not carry its own line"
                              % data["slug"])
                for cls in ("index__domain", "index__year", "index__num"):
                    self.assertIn(cls, body)

    def test_the_row_line_and_the_page_subtitle_stay_separate(self):
        """They shared one string and should not again.

        On a case study the subtitle sits directly above the summary, so
        it says what the PROJECT was -- the paragraph underneath already
        covers the role and the outcome. In the index there is no
        paragraph underneath, so the one line has to carry both.

        Sharing a string meant the index inherited copy written for a
        context that supplies the rest: "End-to-end solutions to
        reinvent the automotive retail industry" reads fine above a
        summary and is agency boilerplate standing alone. If a later
        tidy-up collapses indexLine back into tagline, this fails.
        """
        for _, data in self.live_projects():
            if not data.get("indexLine"):
                continue
            with self.subTest(slug=data["slug"]):
                page = self.html("projects/%s.html" % data["slug"])
                sub = re.search(r'<p class="project__tagline">(.*?)</p>',
                                page, re.S)
                self.assertIsNotNone(sub, "%s lost its subtitle" % data["slug"])
                self.assertEqual(sub.group(1), html.escape(data["tagline"]),
                                 "%s's case study shows the index line "
                                 "instead of its own subtitle" % data["slug"])
                self.assertNotIn(html.escape(data["indexLine"]), sub.group(1))

    def test_the_rows_carry_evidence_not_description(self):
        """The content argument of the index, asserted.

        A row is the only thing most visitors read about a project, and
        three of the five used to spend it describing the product:
        "A platform where anyone with a skill can teach it" tells a
        hiring manager nothing they could not guess from the company
        name. The rewrite put a figure in most of them -- fifteen
        engineers, $1.5M, eight months, ten-plus demos.

        Asserted as a majority rather than all five, because a project
        whose honest answer has no number in it should not be made to
        invent one.
        """
        slugs = [d["slug"] for _, d in self.live_projects()]
        withnum = [s for s in slugs
                   if re.search(r"\d", re.search(
                       r'<span class="index__line">(.*?)</span>',
                       self.row(s), re.S).group(1))]
        self.assertGreaterEqual(
            len(withnum), (len(slugs) // 2) + 1,
            "only %d of %d rows carry a figure (%s); the index is back to "
            "describing the products" % (len(withnum), len(slugs), withnum))


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
        # Each line is wrapped in a .claim__reveal that clips it, so it
        # can slide up from behind one. The clip is a separate element
        # from the thing that moves -- it has to be, since one cannot
        # both clip its contents and be translated by them.
        rendered = "".join(
            '<span class="claim__reveal">'
            '<span class="claim__line%s">%s</span></span>'
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
        """/contact redirects here, so the anchor has to exist.

        The PAGE existed to host the Cal embed and went with it. The
        URL is published -- 200 on the deployed site, in its sitemap,
        with its own canonical -- so contact.html stays as a redirect
        and this is the target it points at.
        """
        self.assertIn('id="contact"', self.html("index.html"),
                      "the homepage lost the #contact anchor old links use")


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
        self.assertIn("404.html", src,
                      "the preview server shows Python's error page where "
                      "the host shows the site's 404, so the one page you "
                      "reach only by mistake is the one never previewed")
        self.assertIn('".html"', src,
                      "the preview server no longer resolves extensionless "
                      "paths to .html")
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertNotIn("\nserve.py", ignore,
                         "an unanchored serve.py pattern is back in "
                         ".gitignore and will untrack tools/serve.py")

    def test_the_contact_url_still_resolves(self):
        """It is live, and the commit that deleted the page said it was not.

        /contact returns 200 on the deployed site, sits in the published
        sitemap and carries its own canonical. The page behind it went
        with the Cal embed; the URL cannot, or every link anyone holds
        to it breaks and an indexed page starts 404ing.
        """
        f = ROOT / "contact.html"
        self.assertTrue(f.is_file(), "/contact would 404; it is a live URL")
        h = f.read_text(encoding="utf-8")
        self.assertRegex(h, r'<meta http-equiv="refresh" content="0; url=/#contact">')
        self.assertRegex(h, r'<link rel="canonical" href="https?://[^"]+/work">')
        # A visitor whose browser honours neither still needs a way out.
        self.assertIn('href="/#contact"', h.split("<body", 1)[1])
        self.assertNotIn("noindex", h,
                         "noindex stops the canonical passing the signal on")
        self.assertIn('id="contact"', self.html("index.html"),
                      "the redirect points at an anchor that does not exist")

    def test_the_redirect_and_the_error_page_are_not_destinations(self):
        """Neither belongs in a sitemap, which lists places to go."""
        sm = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        for path in ("/contact", "/404"):
            with self.subTest(path=path):
                self.assertNotIn("<loc>%s%s<" % (self.site["url"].rstrip("/"), path), sm)

    def test_the_error_page_exists_and_is_whole(self):
        """GitHub Pages serves /404.html for anything it cannot find.

        Without one it serves its own, which carries GitHub's branding
        and no route back here. /projects/fixerloop already 404s today.
        """
        f = ROOT / "404.html"
        self.assertTrue(f.is_file(), "a bad link lands on GitHub's page")
        h = f.read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"<h1[ >]", h)), 1)
        for route in ('href="/work"', 'href="/about"'):
            self.assertIn(route, h, "the error page is a dead end")

    def test_every_path_on_the_error_page_is_absolute(self):
        """It renders at /anything, including /deep/missing/path.

        A relative "assets/styles.css" there resolves against the
        directory that was missed, so the stylesheet 404s too and the
        one page that cannot afford to arrive broken arrives unstyled.
        """
        h = (ROOT / "404.html").read_text(encoding="utf-8")
        rel = [u for u in re.findall(r'(?:href|src)="([^"]+)"', h)
               if not re.match(r"(/|https?:|mailto:|#|data:)", u)]
        self.assertEqual(rel, [],
                         "404.html has relative paths that break at depth: %s"
                         % rel)

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
    """The short format, and who is still on it.

    `format: "highlights"` renders cover, images, metrics and links and
    hides the section prose, which stays in the JSON. It was applied to
    four projects as a tiering decision.

    GROUPADO CAME OFF IT (and Fissa3 did too, before being retired
    outright), because the decision stopped being
    coherent with the index. It was made when the homepage showed cards
    reading "Skills marketplace · 2021" -- a card that vague is
    honestly served by a page of screens. The index now promises "Web
    and mobile shipped in 8 months, homepage built for search", and a
    reader who clicks that is owed the story behind it.

    Nothing was written to do it. The prose had been sitting in the
    JSON the whole time, which is what the format was designed for:
    reversible by removing one field. Groupado went 155 -> 566 words
    and Fissa3 223 -> 885.

    The format itself stays, on the two retired projects, because it is
    the right treatment for work that is listed but not argued for.
    """

    TIER2 = [("08-smarthub", "smarthub"), ("09-portfolio", "portfolio")]
    LIVE_CASE_STUDIES = ("01-steer", "02-konnect",
                         "04-groupado", "06-fixerloop", "10-instadeep")

    def test_the_retired_projects_are_flagged(self):
        for folder, _ in self.TIER2:
            self.assertEqual(self.content(folder).get("format"), "highlights",
                             "%s is not flagged" % folder)

    def test_every_live_project_is_a_full_case_study(self):
        """A row that makes a specific claim must open onto the evidence."""
        for folder in self.LIVE_CASE_STUDIES:
            self.assertIsNone(self.content(folder).get("format"),
                              "%s is back on the short format, so its index "
                              "row promises more than the page delivers"
                              % folder)

    def test_the_promoted_pages_actually_carry_their_prose(self):
        """The point of the promotion, measured rather than assumed.

        Both pages rendered two or three sections while five and six sat
        written in the JSON. Asserting section COUNT rather than a word
        total, because the failure mode is prose being dropped at render
        time, not prose being short.
        """
        for folder, slug in (("04-groupado", "groupado"),):
            with self.subTest(slug=slug):
                written = len([x for x in self.content(folder)["sections"]
                               if x.get("body")])
                rendered = len(re.findall(r"<h2[ >]",
                                          self.html("projects/%s.html" % slug)))
                self.assertGreaterEqual(
                    rendered, written,
                    "%s has %d written sections and renders %d"
                    % (slug, written, rendered))

    def test_prose_is_not_deleted_only_unrendered(self):
        """The property that made the promotion a one-field edit.

        Hiding prose must never mean deleting it, or the decision is not
        reversible and a tiering call becomes a rewrite. Checked on a
        project still ON the format.
        """
        c = self.content("09-portfolio")
        bodies = [s.get("body") for s in c.get("sections", []) if s.get("body")]
        self.assertGreater(len(bodies), 1,
                           "a highlights page had its narrative deleted "
                           "rather than hidden; the flag is now one-way")

    def test_the_short_format_still_exists_to_come_back_to(self):
        """No LIVE page uses it now, which is the risk this guards.

        Both remaining highlights projects are retired, so nothing is
        built from the format and no rendered page can be asserted
        against. A capability with no live user is a capability someone
        deletes as dead code -- and the next project that deserves a
        page of screens rather than an argument would then need it
        rebuilt.

        So the branch is asserted in the source instead: build.py must
        still read the flag and still drop prose because of it.
        """
        src = (ROOT / "build.py").read_text(encoding="utf-8")
        self.assertIn('page_format(project) == "highlights"', src,
                      "build.py no longer branches on the highlights "
                      "format; the short treatment was deleted rather "
                      "than left unused")
        self.assertFalse(
            [c["slug"] for _, c in self.live_projects()
             if c.get("format") == "highlights"],
            "a live project is back on the short format")

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

    def test_the_promoted_pages_got_their_table_of_contents(self):
        """The TOC was suppressed on the short format, correctly: it is
        navigation to nothing over image blocks with no prose. Now that
        both pages carry prose again, they should have one."""
        for slug in ("groupado",):
            with self.subTest(slug=slug):
                self.assertIn('class="toc"', self.html("projects/%s.html" % slug),
                              "%s has prose again but no way to navigate it"
                              % slug)

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


class TestAccentOnItsOwnWash(BuildCase):
    """The pairing the contrast sweep never makes.

    Three components put accent-coloured TEXT on the accent-soft WASH:
    the nav's current-page pill, the availability badge, and the tool
    chips. The sweep checks ink against page surfaces; it never thought
    to check the accent against a tint of itself.

    That gap stayed invisible for as long as the accent was ember, which
    cleared it at 5.66:1 by luck. Swapping to crimson dropped the same
    pairing to 4.44 -- under AA -- and the whole suite stayed green. The
    fix is accent-BRIGHT as the ink, which reads 6.24 dark and 7.47
    light, and this is the test that would have caught it.
    """

    FLOOR = 4.5

    @staticmethod
    def _lum(rgb):
        c = [v / 255 for v in rgb]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    @classmethod
    def _ratio(cls, a, b):
        x, y = cls._lum(a), cls._lum(b)
        if x < y:
            x, y = y, x
        return (x + 0.05) / (y + 0.05)

    @staticmethod
    def _hex(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    def _over(self, rgba, bg):
        m = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", rgba)
        self.assertIsNotNone(m, "accentSoft is not an rgba(): %r" % rgba)
        r, g, b, a = int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4))
        B = self._hex(bg)
        return tuple(round(c * a + B[i] * (1 - a)) for i, c in enumerate((r, g, b)))

    def test_the_ink_on_the_accent_wash_clears_aa(self):
        tokens = json.loads((ROOT / "tokens.json").read_text(encoding="utf-8"))
        for key, label in (("color", "dark"), ("colorLight", "light")):
            grp = tokens[key]
            wash = self._over(grp["accentSoft"], grp["bg"])
            with self.subTest(theme=label):
                got = self._ratio(self._hex(grp["accentBright"]), wash)
                self.assertGreaterEqual(
                    got, self.FLOOR,
                    "%s: accent-bright on the accent-soft wash is %.2f:1, "
                    "under AA. The badge and the nav pill are unreadable."
                    % (label, got))

    def test_no_component_puts_the_plain_accent_on_that_wash(self):
        """It is the plain accent that fails, so nothing may use it there."""
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        bad = re.findall(
            r"background:\s*var\(--color-accent-soft\);"
            r"(?:(?!\n\s*\})[\s\S]){0,400}?"
            # (?<![-\w]) so "border-color" does not match: a border on the
            # wash is non-text and answers to 3:1, not 4.5.
            r"(?<![-\w])color:\s*var\(--color-accent\)\s*;",
            css)
        self.assertEqual(
            bad, [],
            "%d rule(s) put the plain accent on the accent-soft wash; it "
            "measures under AA on the dark theme. Use accent-bright."
            % len(bad))


class TestStickyHeaderBackdrop(BuildCase):
    """The header is sticky, so the page runs underneath it.

    What stops that being readable through the bar is a gradient: opaque
    down to near the bottom, then a short fade so there is no hard edge
    against the page.
    """

    def head_rule(self):
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        blocks = [b for b in re.findall(r"\.site-head \{(.*?)\n\}", css, re.S)
                  if "linear-gradient" in b]
        self.assertTrue(blocks, "the header has no backdrop at all")
        return blocks[-1]

    def test_the_fade_is_a_fixed_length_not_a_percentage(self):
        """A percentage stop is a distance that grows with the header,
        and the header is a different height at every breakpoint because
        the nav wraps to its own row on a phone.

        It was 74%. Measured at 375: header 193px, so the bar began
        going transparent at 143px -- and the nav's own bottom edge is
        at 145. It started fading TWO PIXELS ABOVE THE NAV IT BACKS, and
        50px of page scrolled visibly through the header on every phone,
        which is how it was reported.

        An absolute length cannot do that. The clearance below the nav
        measured 16px at both 375 and 1280 after the change -- the same
        number at both, which is the property a percentage cannot have.
        """
        block = self.head_rule()
        grad = re.search(r"linear-gradient\((.*?)\);", block, re.S).group(1)
        stops = re.findall(r"var\(--color-bg\)\s+([^,\n]+)", grad)
        self.assertTrue(stops, "the gradient no longer starts from the page colour")
        last = stops[-1].strip()
        self.assertNotRegex(
            last, r"^\d+(\.\d+)?%$",
            "the header's opaque stop is %r -- a percentage of a height "
            "that changes with the breakpoint. On a phone the nav wraps, "
            "the header grows, and the fade climbs up behind the nav." % last)
        self.assertIn("calc(100% -", last,
                      "the opaque stop should be measured back from the "
                      "bottom edge, where the fade belongs")

    def test_the_phone_header_is_solid(self):
        """No gradient and no blur below 640px.

        The fade is a refinement a phone cannot afford. Two things
        compound there: the nav wraps to its own row so the header is
        ~250px tall once the safe-area inset is in, and the viewport is
        375px wide so whatever sits behind the fade is large text rather
        than the middle of a line.

        Reported twice from a real handset. Reproduced with the inset
        forced to 59px: even with the fade clearing the nav by 30px, a
        32px band of half-transparent page is simply legible at that
        scale. Moving the stop again would have been tuning the wrong
        variable.

        backdrop-filter goes too: behind an opaque fill it draws
        nothing, and it costs a GPU layer on a sticky bar, which is
        where iOS is fussiest about compositing.
        """
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        # Three separate blocks share this breakpoint, so every one of
        # them has to be searched -- matching only the first is how the
        # first version of this test reported the rule missing when it
        # was sitting in the third.
        blocks = []
        for m in re.finditer(r"@media \(max-width: 639px\) \{", css):
            i, depth = m.end(), 1
            while i < len(css) and depth:
                depth += {"{": 1, "}": -1}.get(css[i], 0)
                i += 1
            blocks.append(css[m.end():i - 1])
        self.assertTrue(blocks, "the phone breakpoint is gone")
        rule = re.search(r"\n  \.site-head \{(.*?)\n  \}",
                         "\n".join(blocks), re.S)
        self.assertIsNotNone(
            rule, "the phone header has no rule of its own, so it inherits "
                  "the desktop gradient and the page shows through it")
        body = rule.group(1)
        self.assertNotIn("gradient", body,
                         "the phone header is back to a gradient")
        self.assertRegex(body, r"background:\s*var\(--color-bg\)\s*;",
                         "the phone header is not a solid fill")
        self.assertRegex(body, r"backdrop-filter:\s*none",
                         "an opaque bar is still paying for a blur")

    def test_the_backdrop_reaches_the_top_of_the_screen(self):
        """Padding, not margin, so the bar extends behind the status bar
        on a notched phone instead of leaving a strip the page shows
        through above it."""
        block = self.head_rule()
        self.assertIn("--inset-top", block,
                      "the header no longer accounts for the safe-area "
                      "inset, so content shows above it on a notched phone")


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
        # contact.html is a redirect stub: no nav, nothing to check, and
        # a visitor is on it for zero frames.
        for path in glob.glob(str(ROOT / "*.html")) + glob.glob(str(ROOT / "projects" / "*.html")):
            rel = pl.Path(path).relative_to(ROOT)
            if rel.name == "contact.html":
                continue
            up = "../" * (len(rel.parts) - 1)
            page = pl.Path(path).read_text(encoding="utf-8")
            nav = re.search(r'<nav class="site-nav" aria-label="Primary">(.*?)</nav>', page, re.S)
            self.assertIsNotNone(nav, "%s lost its primary nav" % rel)
            with self.subTest(page=str(rel)):
                self.assertNotIn("mailto:", nav.group(1),
                                 "%s still fires a mail client from the nav" % rel)
                cta = re.search(r'<a class="site-nav__cta"[^>]*href="([^"]*)"',
                                nav.group(1))
                self.assertIsNotNone(cta, "%s has no route to the booker" % rel)
                # Depth-agnostic on purpose: "call/", "../call/" and
                # "/call/" are all correct, one per page depth, and
                # 404.html is absolute because it renders at any path.
                self.assertTrue(cta.group(1).endswith("call/"),
                                "%s nav points at %s, not /call"
                                % (rel, cta.group(1)))
                self.assertNotIn("//", cta.group(1),
                                 "%s nav links the booking host directly; it "
                                 "should go through /call so the provider is "
                                 "swappable in one place" % rel)


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
        self.assertIn('href="call/"', close,
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


    def test_a_row_carries_its_cover_for_devices_that_cannot_hover(self):
        """This asserted the opposite until an outside reviewer read the
        site on a phone.

        The old rule was "the covers are previews, not content": five
        inline covers would be the card layout again, five requests for
        images most visitors never look at. That reasoning holds for a
        visitor with a cursor, who gets the peek preview on demand.

        It was wrong for everyone else. The peek is gated on `(hover:
        hover) and (pointer: fine)`, so on a phone the homepage rendered
        ONE image -- the portrait -- and a product designer's portfolio
        showed no work at all.

        The cost objection was real and is answered with bytes rather
        than by dropping the image: a 480px AVIF derivative, 170 KB for
        all five against 1.4 MB for the 900px grid files, lazy-loaded so
        the rows below the fold cost nothing until they are reached. CSS
        shows them only where the peek cannot run.
        """
        for i, row in enumerate(self.rows()):
            with self.subTest(row=i):
                self.assertIn("index__cover", row,
                              "row %d has no cover, so a phone visitor "
                              "sees no work" % i)
                self.assertIn('loading="lazy"', row,
                              "row %d fetches its cover eagerly" % i)
                self.assertRegex(row, r'<img[^>]*\bwidth="\d+"[^>]*\bheight="\d+"',
                                 "row %d reserves no space, so the list "
                                 "reflows as covers arrive" % i)

    def test_the_cover_pair_is_both_files_or_neither(self):
        """A <source> that 404s renders NOTHING. It does not fall back.

        This repo learned that once already, when a deleted AVIF left a
        cached page asking for a file that was gone and the <picture>
        showed empty. So the AVIF and its JPEG are shipped together and
        both are asserted on disk.

        THIS TEST USED TO ASSERT NOTHING. It gated on data["live"], a
        key no content.json has ever carried -- the field is
        "published" -- so the loop hit `continue` on every project and
        the suite reported it green for as long as it existed. It was
        found when the derivatives it names were renamed out from under
        it and it did not fail.

        It now walks the same ladder build.py reads, and it checks
        every width that exists rather than one fixed filename.
        """
        import json as _json
        sys.path.insert(0, str(ROOT))
        from build import COVER_WIDTHS
        checked = 0
        for content in sorted((ROOT / "projects").glob("*/content.json")):
            data = _json.loads(content.read_text(encoding="utf-8"))
            if data.get("published") is False:
                continue
            cover = data.get("indexImage") or data.get("cover")
            if not cover:
                continue
            stem = (content.parent / cover).with_suffix("")
            found = []
            for w in COVER_WIDTHS:
                pair = [stem.with_name("%s.card-%d.%s" % (stem.name, w, ext))
                        for ext in ("avif", "jpg")]
                if not any(f.is_file() for f in pair):
                    continue  # width skipped: the original is narrower
                with self.subTest(slug=data.get("slug"), width=w):
                    for f in pair:
                        self.assertTrue(f.is_file(),
                                        "%s is missing its other half; run "
                                        "tools/make-index-thumbs.py --apply"
                                        % f.relative_to(ROOT))
                found.append(w)
            with self.subTest(slug=data.get("slug")):
                self.assertTrue(found,
                                "%s has a cover and no derivatives at all"
                                % data.get("slug"))
                self.assertIn(COVER_WIDTHS[0], found,
                              "%s has no smallest rendering, which is what "
                              "the cursor peek loads" % data.get("slug"))
            checked += 1
        self.assertTrue(checked, "this test walked zero projects again")

    def test_the_covers_only_show_where_the_preview_cannot_run(self):
        """The two must be exact inverses, or a pointer device gets the
        cover twice and a touch device gets it never."""
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.index__cover\s*\{\s*display:\s*none",
                         "the inline cover is not hidden by default, so a "
                         "pointer device shows it and the peek together")
        self.assertRegex(css, r"@media \(hover: none\), \(pointer: coarse\)",
                         "nothing reveals the inline cover")


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
                # "../../x" from a project page and "/x" from 404.html
                # both mean the same file: the repo root IS the site root.
                # The leading-slash case arrived with 404.html, which has
                # to use absolute paths because it renders at any depth,
                # and this test could not resolve them -- it reported the
                # asset "not committed" when it was simply looking for
                # HEAD:/assets/... with the slash still on.
                rel = re.sub(r"^(?:\.\./)+|^/", "", ref)
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

    def pages(self):
        """Every page a person can land on and then share."""
        out = ["index.html", "work.html", "about.html"]
        for path in sorted((ROOT / "projects").glob("*/content.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("published") is not False:
                out.append("projects/%s.html" % data["slug"])
        return out

    def test_every_referenced_share_card_is_tracked(self):
        """An untracked og:image 404s on the host and every link preview breaks.

        The file exists locally, so the build is happy and nothing warns.
        """
        proc = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=str(ROOT), capture_output=True, text=True)
        untracked = set(proc.stdout.split())
        base = (self.site.get("url") or "").rstrip("/") + "/"
        referenced = set()
        for page in self.pages():
            for match in re.finditer(r'property="og:image" content="([^"]+)"',
                                     self.html(page)):
                # The URL carries a ?v= hash so scrapers refetch a
                # redrawn card; the file on disk does not.
                referenced.add(
                    match.group(1).replace(base, "").split("?", 1)[0])
        self.assertTrue(referenced, "no share cards referenced -- test is vacuous")
        self.assertEqual(referenced & untracked, set())
        for rel in referenced:
            with self.subTest(card=rel):
                self.assertTrue((ROOT / rel).is_file(),
                                "%s is advertised and not on disk" % rel)

    def test_one_card_previews_the_whole_site(self):
        """Every page, case studies included, previews as the site card.

        Each case study used to carry its own assets/share.jpg, and all
        three that had one were the CLIENT's asset rather than anything
        about this work: InstaDeep's corporate logo lockup, and
        screenshots of Steer's and Groupado's marketing homepages. A
        case study posted to LinkedIn previewed as that company's
        advertising with nothing on it to say whose portfolio it was.
        Konnect had none at all and fell through to a 900x640 product
        screenshot, which a scraper crops to 1.91:1 and shows a slice of.

        The files are still on disk. If a project is ever given a real
        card of its own, this is the test to change.
        """
        card = self.site.get("shareImage")
        self.assertTrue(card, "site.json names no shareImage")
        for page in self.pages():
            with self.subTest(page=page):
                self.assertRegex(
                    self.html(page),
                    r'property="og:image" content="[^"]*%s(?:\?v=[0-9a-f]+)?"'
                    % re.escape(card),
                    "%s previews as something other than the site card" % page)

    def test_every_page_this_build_writes_previews_as_something(self):
        """Including the two that are hops rather than destinations.

        /call and /contact are redirects and neither is in the sitemap,
        so neither carried Open Graph tags: nobody shares a hop. People
        share hops -- /call is the URL behind the header button, which
        makes it the one somebody copies from a right-click menu -- and
        a paste with no tags previews as a bare link with the domain
        under it. LinkedIn's Post Inspector reports that as exactly two
        warnings, which is how this was found.

        The list is the build's own outputs, not a glob: _proto/ and the
        scratch directories hold HTML nobody serves, and sweeping them
        in would make this fail for the wrong reason.
        """
        pages = ["index.html", "work.html", "about.html", "404.html",
                 "contact.html", "call/index.html"]
        pages += [p for p in self.pages() if p.startswith("projects/")]
        for page in pages:
            with self.subTest(page=page):
                html = self.html(page)
                for tag in ("og:title", "og:description", "og:image"):
                    self.assertIn(
                        'property="%s"' % tag, html,
                        "%s has no %s, so a pasted link to it previews as "
                        "a bare URL" % (page, tag))
                # ...and the tags have to say something.
                for tag in ("og:title", "og:description"):
                    m = re.search(
                        r'property="%s" content="([^"]*)"' % tag, html)
                    self.assertTrue(
                        m and m.group(1).strip(),
                        "%s has an empty %s" % (page, tag))

    def test_the_card_url_moves_when_the_card_does(self):
        """A scraper caches the preview against the URL and never returns.

        The card was redrawn and every link already posted -- and every
        new one -- kept showing the old picture, because LinkedIn, Slack
        and the rest key on the URL and the URL had not changed. There
        is no header, no meta tag and no "please refetch" that beats
        this; the URL has to move when the file does.

        Asserted against a hash of the file's own bytes, so editing the
        card and forgetting to rebuild cannot leave the two disagreeing.
        """
        sys.path.insert(0, str(ROOT))
        from build import asset_v
        card = self.site["shareImage"]
        want = asset_v(card)
        self.assertRegex(want, r"^\?v=[0-9a-f]{8}$",
                         "the card has no content hash to advertise")
        for page in self.pages():
            with self.subTest(page=page):
                m = re.search(r'property="og:image" content="([^"]+)"',
                              self.html(page))
                self.assertIsNotNone(m, "%s advertises no card" % page)
                self.assertTrue(
                    m.group(1).endswith(want),
                    "%s points social at %r, which is not the hash of the "
                    "file it will serve (%s) -- posted links keep the old "
                    "preview" % (page, m.group(1)[-24:], want))

    def test_the_site_card_is_the_size_it_claims(self):
        """og:image:width and height let a scraper lay the card out before
        the bytes arrive. Wrong numbers are worse than none: the preview
        reserves the wrong box and then jumps.

        1200x630 is also the size itself -- under 1.91:1 and a platform
        letterboxes it, over and it crops the sides off.
        """
        sys.path.insert(0, str(ROOT))
        from build import png_size
        card = ROOT / self.site["shareImage"]
        self.assertTrue(card.is_file(), "the site share card is missing")
        size = png_size(card)
        self.assertEqual(size, (1200, 630),
                         "the share card is %s, not 1200x630" % (size,))
        home = self.html("index.html")
        self.assertIn('<meta property="og:image:width" content="1200">', home)
        self.assertIn('<meta property="og:image:height" content="630">', home)

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
        self.assertIn('claim__line--built">%s</span></span></h1>' % last, page)

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

        The embed is gone -- see BOOKING_URL in build.py -- so this is
        an outbound link again, and an outbound link that replaces the
        tab makes the back button the only way back to the work. It
        goes via /call on this domain, which is the hop that keeps the
        provider out of every link ever written down.
        """
        row = self.actions("index.html")
        book = re.search(r'<a class="btn btn--solid"[^>]*>', row).group(0)
        self.assertIn('href="call/"', book)
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
                         "it should be BOOKING_URL and nothing else"
                         % len(literals))
        self.assertRegex(src, re.compile(r"^BOOKING_URL = ", re.M))
        # And nothing else in the repo may name the host either. One
        # generated page is allowed to: the redirect itself.
        import glob, pathlib as pl
        for path in (glob.glob(str(ROOT / "*.html"))
                     + glob.glob(str(ROOT / "projects" / "*.html"))
                     + glob.glob(str(ROOT / "call" / "*.html"))):
            rel = pl.Path(path).relative_to(ROOT)
            html = pl.Path(path).read_text(encoding="utf-8")
            if str(rel) == "call/index.html":
                self.assertIn("cal.com", html, "/call forwards nowhere")
                continue
            with self.subTest(page=str(rel)):
                self.assertNotIn("cal.com", html,
                                 "%s names the booking host; every link "
                                 "should go through /call" % rel)

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
        this budget.

        215 is what naming the engagements cost, and it is the largest
        single step this cap has taken:

          +55  "Ways to work together": a heading and three cards. The
               page was good at showing what the work WAS and silent on
               what hiring or briefing looks like, so the only move
               available to someone who liked it was to book a call and
               find out. No prices -- a number here answers a question
               nobody has asked yet.
          +9   four client and employer names under the ask. The
               nearest thing to social proof that is honest without
               asking anyone for a quote.
          +8   the quiet "Book a call" under the cards.
          +3   the greeting, which moved OUT of the h1 and into its own
               line, so these words are not new, they just stopped
               being a third of the largest type on the site.

        The bar is unchanged and so is the shape of the rule: prose
        creeping back onto this page still fails here. 215 leaves room
        for one more project row and nothing else.
        """
        sys.path.insert(0, str(ROOT))
        from build import HOME_NOT_COPY
        n = self.words("index.html", HOME_NOT_COPY)
        self.assertLess(n, 215, "the homepage body copy is %d words" % n)


    def test_the_about_page_stays_lean(self):
        """The cap was 160 and is 190, for one addition.

        What it bought: a positioning statement. The page opened with
        "Design is how I think. / Building is how I prove it." -- a
        slogan, which says nothing a reader can act on. It now opens
        with what the work is FOR: products where the interface has to
        carry trust, and why AI, blockchain and fintech all land in that
        gap. That sentence was on the old homepage and the redesign
        dropped it; this puts it back, where an About page should
        carry it.

        The counter-pressure is real and stays: this page was 478 words
        before the redesign, four paragraphs of intro and a note under
        every job. 190 leaves room for the positioning and nothing else.
        """
        n = self.words("about.html", {"js-copy-fallback"})
        self.assertLess(n, 190, "the about page is %d words" % n)

    def test_the_about_page_says_what_the_work_is_for(self):
        """A portfolio that does not position itself gets filtered out.

        The specific failure is an About page that describes a process
        instead of a market. "Design is how I think" is true of every
        designer alive; "products where the interface has to carry
        trust" is a claim only some can make, and it is the one this
        site can evidence -- fintech, a digital wallet, and AI.
        """
        page = self.html("about.html")
        self.assertIn("carry trust", page,
                      "the about page lost its positioning statement")
        self.assertNotIn("Design is how I think", page,
                         "the slogan is back in place of the position")

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

        It was "Product designer." and then the h1
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
                last = self.site["heroClaim"].split("\n")[-1]
                self.assertNotIn(last, desc,
                                 "%s's description just repeats the h1's "
                                 "last line" % page)

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

    def test_the_hero_asks_for_nothing_and_points_at_the_work(self):
        """The hero's one control goes INTO the page, not off it.

        It read "Book a call  or  Copy email" and was the first of four
        booking links on this page. A visitor who has read the headline
        wants to see the work, not to schedule a conversation about
        work they have not seen, so the hero offers exactly that and
        the asks wait until the work has made the argument.

        The copy-email control went with it. That is only safe because
        the closing band and /about each still carry their own button,
        mailto fallback and live region -- enhance.js reaches those
        through btn.parentNode, so a half-move would have left a button
        that silently does nothing.
        """
        m = re.search(r'<p class="ask">(.*?)</p>', self.html("index.html"), re.S)
        self.assertIsNotNone(m, "the homepage has no hero ask")
        row = m.group(1)
        self.assertIn('href="#work"', row, "the hero does not point at the work")
        self.assertNotIn('href="call/"', row, "the hero still books a call")
        self.assertNotIn("js-copy", row, "the hero still copies an address")
        # The arrow is decoration; the accessible name is the sentence.
        self.assertIn('aria-hidden="true"', row)
        self.assertIn("See the work", row)
        # ONE control, and nothing beside it. The row also carried an
        # "Open to new projects" pill on a pulsing dot -- a second thing
        # competing for the only line on the first screen that is not
        # the headline, and a sentence that asks rather than shows.
        # Removed at the owner's call; this is what keeps it gone.
        self.assertNotIn("ask__badge", row,
                         "the availability badge is back in the hero")
        self.assertEqual(
            row.count("<a "), 1,
            "the hero ask holds more than one link again")
        home = self.html("index.html")
        self.assertNotIn("ask__dot", home, "the pulsing dot is back")
        for word in ("Open to", "Available for", "open to work"):
            self.assertNotIn(word, home,
                             "the homepage pitches availability again "
                             "(%r)" % word)

    def test_the_work_the_hero_points_at_is_actually_there(self):
        """A fragment link is only as good as the id it names.

        #work is on the band and nothing in the nav uses it any more, so
        it is exactly the kind of id that gets tidied away by someone
        who greps for it and finds one reference. That reference is now
        the homepage's only above-the-fold control.
        """
        home = self.html("index.html")
        self.assertIn('id="work"', home, "the #work anchor is gone")
        self.assertLess(home.index('href="#work"'), home.index('id="work"'),
                        "the hero link comes after the thing it points at")

    def test_the_copy_control_still_exists_where_it_moved_to(self):
        """Removing it from the hero must not remove it from the site."""
        for page in ("index.html", "about.html"):
            with self.subTest(page=page):
                h = self.html(page)
                self.assertRegex(
                    h, r'<button[^>]*class="[^"]*js-copy[^"]*"[^>]*type="button"',
                    "%s lost its copy button" % page)
                self.assertIn("js-copy-fallback", h,
                              "%s lost the mailto fallback" % page)
                self.assertIn("data-copy-status", h,
                              "%s lost the live region" % page)

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
        """The h1 ends on the build claim and then said no more.

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

        THREE, and it was four. The nav CTA, the one under the ways
        cards and the closing band's loud one -- the hero's went, and
        the count is asserted so it cannot quietly come back. All three
        point at /call, and /call is the only thing that knows the
        provider.

        Four identical "Book a call" links on one page was what a CEO
        read as too many asks, and the hero's was the worst of them: it
        asked for a meeting above the fold, before the page had shown
        one thing that was designed.

        This used to assert the links pointed straight at Cal. That made
        the booking URL a string written into every generated page, so
        changing provider meant a rebuild of the whole site and a dead
        link in every email already sent.
        """
        sys.path.insert(0, str(ROOT))
        from build import BOOKING_URL
        self.assertTrue(BOOKING_URL.startswith("https://"))
        home = self.html("index.html")
        self.assertEqual(home.count('href="call/"'), 2,
                         "the homepage does not have exactly two routes "
                         "to the booker")
        hero = re.search(r'<section class="opening">(.*?)</section>',
                         home, re.S)
        self.assertIsNotNone(hero, "the homepage has no hero")
        self.assertNotIn('href="call/"', hero.group(1),
                         "the hero asks for a meeting again")
        self.assertNotIn("ways__ask", home,
                         "the ask under the Ways cards is back: that is "
                         "the third Book a call, and the closing band "
                         "with the fourth is one scroll below it")
        self.assertNotIn("REPLACE-ME", home, "the placeholder link shipped")
        # ...and the hop actually arrives. A redirect page that forgot
        # its destination is a dead end that every test above passes.
        stub = (ROOT / "call" / "index.html").read_text(encoding="utf-8")
        self.assertIn('content="0; url=%s"' % BOOKING_URL, stub,
                      "/call has no meta refresh to the booking URL")
        self.assertIn('href="%s"' % BOOKING_URL, stub,
                      "/call has no visible link for anything that "
                      "honours neither the refresh nor the script")
        self.assertIn('location.replace("%s")' % BOOKING_URL, stub)

    def test_the_booking_link_opens_in_its_own_tab(self):
        """Booking is a detour, not a destination.

        Sent off-site in the tab they were reading in, a visitor's way
        back to the work is the back button. Every one of the three says
        so in its accessible name too, because a new tab that announces
        itself only by appearing is WCAG 3.2.5.
        """
        for page in self.pages():
            with self.subTest(page=page):
                html = self.html(page)
                for m in re.finditer(
                        r'<a[^>]*href="(?:\.\./)*call/"[^>]*>(.*?)</a>',
                        html, re.S):
                    tag = m.group(0)[:m.group(0).index(">") + 1]
                    self.assertIn('target="_blank"', tag)
                    self.assertIn('rel="noopener"', tag)
                    self.assertIn("opens in a new tab", m.group(1),
                                  "a booking link changes context silently")

    def test_nothing_still_offers_the_contact_route(self):
        """No page should send anyone through the redirect.

        An earlier version of this asserted contact.html was absent, on
        the belief that /contact had never been published. It had: 200
        on the deployed site, in its sitemap, with its own canonical.
        The file stays, as a redirect. What matters is that no page
        here routes a visitor through it when it can link the
        destination directly.
        """
        self.assertTrue((ROOT / "contact.html").exists(),
                        "a published URL would start 404ing")
        for page in self.pages():
            with self.subTest(page=page):
                html = self.html(page)
                self.assertNotRegex(html, r'href="(\.\./)*contact"',
                                    "%s routes through the redirect instead "
                                    "of linking the destination" % page)

    def test_no_booker_styles_outlived_the_booker(self):
        """Dead CSS is how a stylesheet stops describing the site."""
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        for sel in (".cal ", ".cal{", ".cal {", ".cal__", ".band--book",
                    ".actions--single"):
            with self.subTest(selector=sel):
                self.assertNotIn(sel, css)



class TestTheSecondReviewPass(BuildCase):
    """Three facts a second outside review asked to be held to.

    Each one is here because a human had to notice it. A claim that
    quietly became untrue, a link class that quietly rots, and an image
    that renders without telling anyone what it is -- none of those
    break a build, so none of them surface without a test that fails.
    """

    def all_html(self):
        """Every generated page, redirects and the 404 included."""
        import glob, pathlib as pl
        out = []
        for pat in ("*.html", "projects/*.html", "call/*.html"):
            for path in sorted(glob.glob(str(ROOT / pat))):
                rel = pl.Path(path).relative_to(ROOT)
                out.append((str(rel), pl.Path(path).read_text(encoding="utf-8")))
        return out

    def test_the_funding_claim_is_gone(self):
        """Konnect raised after Abdou had left, so it was never his.

        The site carried it three times: the homepage row, a stat block
        on the case study, and a sentence naming six investors. The
        surrounding framing was always careful -- "what the company did
        afterwards is not my work" -- but a figure printed that large
        reads as a result regardless of the sentence around it, and the
        one next to it on the page WAS his.

        The Central Bank licence and the Visa accelerator stay. They
        are the same kind of fact and they are not denominated in
        money, so they cannot be mistaken for a number he moved.
        """
        for page, html in self.all_html():
            with self.subTest(page=page):
                for claim in ("1.5M", "1.5 M", "$1.5"):
                    self.assertNotIn(claim, html,
                                     "%s still claims %s" % (page, claim))
        # The source check used to be a bare `assertNotIn("1.5", ...)`.
        # That was broad on purpose and it held for a year, until the
        # portfolio page's own "JavaScript shipped, gzipped" metric --
        # which the suite keeps in sync with the real file sizes --
        # reached 21.5 KB and matched it. A test that fails because a
        # stylesheet grew is a test nobody trusts the next time.
        #
        # So: the money-shaped claims, exactly as on the page, plus any
        # bare 1.5 standing near funding language. A figure that is not
        # denominated and not next to the word "raised" is a size, not
        # a round.
        money = re.compile(r"\$\s*1\.5|1\.5\s*(?:M\b|million)", re.I)
        near = re.compile(
            r"1\.5(?:(?!1\.5).){0,60}?"
            r"(rais|fund|seed|round|investor|valuat|ARR|revenue)"
            r"|(rais|fund|seed|round|investor|valuat|ARR|revenue)"
            r"(?:(?!1\.5).){0,60}?1\.5", re.I | re.S)
        for path in sorted(ROOT.glob("projects/*/content.json")):
            with self.subTest(source=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(money.search(text),
                                  "%s carries a money-denominated 1.5"
                                  % path.name)
                m = near.search(text)
                self.assertIsNone(
                    m, "%s has 1.5 sitting next to funding language: %r"
                       % (path.name, m.group(0)[:80] if m else ""))

    def test_no_link_rots_through_a_redirect_or_the_booking_host(self):
        """Two classes of link that work today and rot differently.

        /contact is a redirect stub kept alive for inbound links. A page
        here linking it costs a visitor a hop for nothing, and the day
        the stub goes, so does the link.

        A cal.com address written into a page is worse: it outlives the
        page it is on. It goes into emails and LinkedIn messages, and
        changing provider -- or just claiming a readable slug, which
        this account has not done -- breaks every copy anyone kept.
        /call is the indirection that makes that a one-line change.
        """
        for page, html in self.all_html():
            if page == "contact.html" or page == "call/index.html":
                continue  # the redirects themselves
            with self.subTest(page=page):
                self.assertNotRegex(
                    html, r'href="(?:\.\./|/)*contact(?:\.html)?"',
                    "%s routes through the /contact redirect" % page)
                self.assertNotIn("cal.com", html,
                                 "%s writes the booking host into the page "
                                 "instead of linking /call" % page)

    def test_every_index_cover_is_described_and_reserved(self):
        """An image with no alt and no box is two bugs, not one.

        No alt and a screen reader announces a filename or nothing at
        all, on the one image a phone visitor sees above the fold. No
        width and height and the row reflows when the bytes land, which
        on a lazy-loaded list is the page jumping under a thumb that is
        already moving.
        """
        import glob
        pages = [p for p in ("index.html", "work.html")
                 if (ROOT / p).is_file()]
        self.assertTrue(pages, "no homepage to check")
        for page in pages:
            html = self.html(page)
            covers = re.findall(r'<picture class="index__cover">.*?</picture>',
                                html, re.S)
            self.assertTrue(covers,
                            "%s renders no covers; a phone sees no work" % page)
            for cover in covers:
                img = re.search(r"<img[^>]*>", cover).group(0)
                with self.subTest(page=page, img=img[:60]):
                    alt = re.search(r'alt="([^"]*)"', img)
                    self.assertIsNotNone(alt, "a cover has no alt attribute")
                    self.assertGreater(
                        len(alt.group(1).split()), 3,
                        "a cover's alt text says nothing: %r" % alt.group(1))
                    self.assertRegex(img, r'width="\d+"', "a cover has no width")
                    self.assertRegex(img, r'height="\d+"', "a cover has no height")
                    self.assertIn('loading="lazy"', img)
                    # The ladder, not one file. A single 480px source in
                    # a 327pt box is what shipped first and measured soft
                    # on any phone above DPR 1.5.
                    self.assertIn("srcset", cover, "a cover offers one width only")
                    self.assertIn("sizes=", cover,
                                  "a srcset with no sizes makes the browser "
                                  "guess the box at 100vw")


# ── the runner ───────────────────────────────────────────────────────────
# This block MUST stay at the bottom of the file. It spent a long time in
# the middle of it, and unittest.main() runs at the point it is reached:
# every class defined below it was never collected. That was 13 classes
# and 66 test methods, among them the em-dash ban, the dark-mode set, the
# theme toggle, the scroll-driven motion guards and the hero animation --
# all reported green by a runner that had never seen them.
#
# It is also why this file counted 207 tests while the runner said 141.

class TestTheFirstImpression(BuildCase):
    """The hero, after a CEO reported lost space and no first impression.

    Three complaints, all of them measurable and all of them true: the
    header ate a quarter of a phone screen, the page asked for a meeting
    four times, and the first screen showed a visitor no work at all.
    These pin the fixes so they cannot quietly come undone.
    """

    def css(self):
        return (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")

    def classes_in(self, page):
        """Every class name actually used in a page's markup."""
        out = set()
        for m in re.finditer(r'class="([^"]*)"', self.html(page)):
            out.update(m.group(1).split())
        return out

    def media_block(self, needle):
        """The @media block containing `needle`, by brace matching.

        Substring slicing would be close enough right up until a nested
        at-rule or a comment with a brace in it, both of which this
        stylesheet has.
        """
        css = self.css()
        i = css.index(needle)
        start = css.rindex("@media", 0, i)
        depth, j = 0, css.index("{", start)
        for k in range(j, len(css)):
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
                if depth == 0:
                    return css[start:k + 1]
        raise AssertionError("unbalanced braces around %r" % needle)

    def test_every_selector_in_the_hero_cascade_names_something(self):
        """THIS IS THE TEST THAT WAS MISSING, and the bug was live.

        The hero cascade named .opening__status, .opening__support,
        .opening__actions and .opening__facts -- the old hero's status
        row, supporting paragraph, button row and four stat blocks.
        Every one of them was deleted when the hero was cut back, and
        the animation stayed behind pointing at all four. Grepped
        against index.html at the time: 0, 0, 0, 0.

        So the stylesheet described a load cascade, the hero arrived
        with no motion whatsoever, and nothing failed. A selector that
        matches nothing is not a CSS error -- it is silence, which is
        why this has to be asserted rather than noticed.
        """
        block = self.media_block("animation: hero-step-in")
        names = set(re.findall(r'\.([a-z][a-z0-9_-]*)', block))
        self.assertTrue(names, "the cascade has no class selectors at all")
        markup = self.classes_in("index.html")
        # A class the page never carries in its source can still be real:
        # the hook's are added to <html> at runtime. The rule is that it
        # has to exist SOMEWHERE -- in the markup, or in a script that
        # puts it there. A typo still matches neither and still fails.
        js = "".join((ROOT / "assets" / f).read_text(encoding="utf-8")
                     for f in ("enhance.js", "hook.js", "signal.js"))
        js += (ROOT / "build.py").read_text(encoding="utf-8")
        missing = sorted(n for n in names
                         if n not in markup and '"%s"' % n not in js
                         and "'%s'" % n not in js)
        self.assertEqual(
            missing, [],
            "the hero cascade animates classes that are in neither the "
            "markup nor any script that could add them, so it animates "
            "nothing: %s" % missing)

    def test_the_headline_stagger_covers_every_authored_line(self):
        """The breaks are authored, so the stagger has to outlast them.

        heroClaim has been four lines and is three. A stagger with one
        delay per line and no spare leaves the next line it grows back
        arriving with no delay at all -- visibly out of step with the
        three above it, and only on the viewport where the copy fits.
        """
        lines = len(re.findall(r'class="claim__reveal"', self.html("index.html")))
        self.assertGreaterEqual(lines, 3, "the headline lost its line clips")
        block = self.media_block("animation: maskUp")
        delays = re.findall(
            r'\.claim__reveal:nth-child\((\d+)\) \.claim__line', block)
        self.assertGreaterEqual(
            len(set(delays)), lines,
            "%d authored lines but only %d stagger delays"
            % (lines, len(set(delays))))

    def test_the_headline_is_sized_by_height_as_well_as_width(self):
        """A hero measured against the fold cannot size on vw alone.

        The desktop headline was clamp(5.5rem, 10vw, 8.5rem), which is
        a function of width only. At 1280x800 -- an ordinary laptop --
        that is 128px, and 128px of headline plus the foot row needed
        875px of the 800 available: the foot landed 43px BELOW the fold
        it exists to sit on. Nothing failed, because every test here
        asserted markup and tokens and this was rendered geometry on one
        viewport shape.

        Fixed at 1280x800 and 1440x900 after: hero bottom 800 and 900,
        both exactly the fold.
        """
        css = self.css()
        rule = re.search(r"\.opening__claim\s*\{([^}]*font-size[^}]*)\}", css)
        self.assertIsNotNone(rule, ".opening__claim has no sized rule")
        # The desktop override is the one with a vh term; find whichever
        # block actually sets a font-size containing one.
        sized = [m.group(1) for m in
                 re.finditer(r"\.opening__claim\s*\{([^}]*)\}", css)
                 if "font-size" in m.group(1)]
        self.assertTrue(sized, "nothing sizes the headline")
        joined = "\n".join(sized)
        self.assertIn("vw", joined, "the headline does not respond to width")
        self.assertIn(
            "vh", joined,
            "the headline is sized on width alone, so a short laptop "
            "pushes the hero's own foot row past the fold")
        # And the two have to be combined by min(), not stacked -- the
        # smaller constraint is the one that must win.
        self.assertRegex(
            joined, r"min\s*\(",
            "the width and height terms are not reconciled with min()")

    def test_the_line_clip_does_not_shear_the_selection_frame(self):
        """overflow:hidden is the obvious way to do this and it is wrong.

        The reveal needs each line clipped to its own box. overflow:
        hidden clips to the PADDING box, and the last line carries the
        selection frame on pseudo-elements at
        `inset: -4px calc(-0.08em - 4px)` -- 4px outside the line box on
        all four sides, with handles on the corners. Clipping there
        shears every edge and handle off it, and nothing fails: the
        frame just quietly stops having corners.

        clip-path clips to the border box and takes negative insets, so
        -100% left and right turns horizontal clipping off entirely
        while the vertical padding gives the frame room. That is the
        only reason it is clip-path, so it is asserted rather than left
        to the next person to rediscover.
        """
        css = self.css()
        rule = re.search(r"\.claim__reveal\s*\{([^}]*)\}", css)
        self.assertIsNotNone(rule, ".claim__reveal has no rule")
        body = rule.group(1)
        self.assertNotIn(
            "overflow", body,
            "the line clip uses overflow, which shears the frame's edges "
            "and handles off the last line")
        clip = re.search(r"clip-path:\s*inset\(([^)]*)\)", body)
        self.assertIsNotNone(clip, "the line clip has no clip-path")
        sides = clip.group(1).split()
        self.assertEqual(len(sides), 4,
                         "the clip needs all four insets spelled out")
        self.assertTrue(
            sides[1].startswith("-") and sides[3].startswith("-"),
            "the clip is not open horizontally, so the frame's side "
            "handles are cut: %r" % clip.group(1))

    def test_the_hero_stops_growing_before_the_air_does(self):
        """The headline cannot grow past 136px, so a taller fold is air.

        The column is capped at 1152 and the longest line fills 1044 of
        it at that size, so above about an 886px fold the extra height
        has nowhere to go: measured at 1512x982 before the ceiling went
        in, 262px of empty page between the headline and the strip,
        which is the same hole this hero exists to close.

        Both halves are asserted. A ceiling with no fold term stops the
        strip reaching the fold on a laptop; a fold term with no ceiling
        is the 262px. And the ceiling has to clear the fold term at
        1440x900 -- 750px -- or the commonest desktop here loses its
        exact fit.
        """
        css = self.css()
        m = re.search(r"\.hero-band \{[^}]*?min-height: ([^;]+);", css, re.S)
        self.assertIsNotNone(m, "the hero has no min-height at all")
        rule = m.group(1)
        self.assertIn("100dvh", rule,
                      "the hero is a fixed height, so its strip stops "
                      "landing on the fold")
        self.assertIn("min(", rule,
                      "the hero grows with the viewport without a "
                      "ceiling, and the headline does not grow with it")
        ceiling = re.search(r"(\d+(?:\.\d+)?)rem", rule)
        self.assertIsNotNone(ceiling, "the ceiling is not a rem value")
        px = float(ceiling.group(1)) * 16
        self.assertGreaterEqual(
            px, 750,
            "the ceiling is %dpx and the fold term at 1440x900 is 750, "
            "so the strip stops short of the fold there" % px)
        self.assertLessEqual(
            px, 850,
            "a ceiling of %dpx lets about %dpx of air open up between "
            "the headline and the strip" % (px, px - 570))

    def test_the_phone_header_is_one_row(self):
        """193px of an 812px screen, and 29% of an SE, spent on a header.

        Two rows: the wordmark had one to itself and the nav had the
        other. One row is only possible with the booking button out of
        it, so both halves of that are asserted here together -- putting
        the button back silently costs the row 97px it does not have.
        """
        block = self.media_block(".site-head__inner { flex-wrap: nowrap")
        self.assertIn("flex-wrap: nowrap", block,
                      "the phone header is allowed to wrap to a second row")
        self.assertRegex(
            block, r"\.site-head nav a\.site-nav__cta \{\s*display: none",
            "the booking button is back in the phone header")

    def test_the_asks_clear_the_touch_minimum(self):
        """31px, 31px and 22px, on the three controls that matter most.

        The hero's ask, its copy button and the Ways link -- all under
        the 44px platform minimum. The Ways link is gone entirely now
        (it was the third Book a call), so what is left to check is the
        hero's one control and the buttons in the closing band, which is
        where every ask the page still makes lives.
        """
        css = self.css()
        rule = re.search(r"\.ask__act--see \{([^}]*)\}", css)
        self.assertIsNotNone(rule, ".ask__act--see has no rule")
        self.assertIn("min-height: 44px", rule.group(1),
                      "the hero's ask does not clear 44px")
        home = self.html("index.html")
        self.assertNotIn("ways__ask", home,
                         "the 22px Ways link is back")


class TestTheHookAndTheSignal(BuildCase):
    """The two seconds at the start and the trace down the page.

    Both are pure enhancement: the markup is the same page without them,
    and every rule that touches content is scoped to a class a script
    sets. These pin that scoping, because the failure mode is silent --
    a selector that stops being guarded does not error, it just leaves a
    reader looking at an outlined headline that never fills.
    """

    def css(self):
        return (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")

    def js(self, name):
        return (ROOT / "assets" / name).read_text(encoding="utf-8")

    def head_script(self):
        """The one inline script in <head>, which decides both."""
        home = self.html("index.html")
        m = re.search(r"<script>(.*?)</script>", home, re.S)
        self.assertIsNotNone(m, "the homepage has no inline head script")
        return m.group(1)

    def test_the_hook_is_decided_before_the_first_paint(self):
        """A deferred decision IS the flash it is trying to prevent.

        If the class went on after the first frame, the solid headline
        would paint and then be replaced by outlines, which reads as a
        rendering bug rather than as an intro. So the three conditions
        and the class are in the same synchronous inline script as the
        theme, above <body>.
        """
        script = self.head_script()
        for needle in ('prefers-reduced-motion: reduce',
                       'location.hash',
                       'sessionStorage.getItem("hook-seen")',
                       'sessionStorage.setItem("hook-seen", "1")',
                       'classList.add("hook-on")'):
            self.assertIn(needle, script,
                          "the before-paint script does not check %r" % needle)
        # Every condition is a bail-out, so the class can only be reached
        # after all three. If the add moved above any of them it would
        # fire for a reduced-motion reader on a deep link.
        self.assertLess(script.index('sessionStorage.getItem'),
                        script.index('classList.add("hook-on")'),
                        "the hook is switched on before it has checked "
                        "whether this session has already seen it")
        home = self.html("index.html")
        self.assertEqual(home.count("<script>"), 1,
                         "a second inline head script: both decisions "
                         "belong in the one that already blocks paint")

    def test_a_hook_that_never_loads_undoes_itself(self):
        """The head script can switch the hook on and hook.js can fail.

        The class hides the filled headline. If the file that removes it
        404s, a visitor is left reading outlines for the life of the
        page -- so the script that sets the class also schedules its
        removal, and hook.js cancels that timer when it starts.
        """
        script = self.head_script()
        self.assertIn("__hookFailsafe", script, "no failsafe is scheduled")
        tail = script[script.index("__hookFailsafe"):]
        self.assertIn('remove("hook-on")', tail,
                      "the failsafe does not remove the class")
        self.assertIn("setTimeout", tail, "the failsafe is not a timer")
        self.assertIn("window.__hookFailsafe", self.js("hook.js"))
        self.assertIn("clearTimeout(window.__hookFailsafe)", self.js("hook.js"),
                      "hook.js does not take the timing over from the "
                      "failsafe, so the class is pulled mid-sequence")

    def test_the_failsafe_outlasts_the_sequence_it_guards(self):
        """A failsafe shorter than the hook pulls the class mid-play.

        It only fires when hook.js never loaded -- hook.js clears it on
        its first line -- but the two numbers live in two different
        files, so slowing the sequence without moving the timer is a
        one-line change with no symptom until the day a fetch fails.

        The pace itself is also pinned. The first cut had the cursor
        clicking at 960ms and the whole thing done by 3.3s, which was
        over before a reader had registered that the headline was
        hollow. If someone tunes it back under four seconds they should
        have to say so here.
        """
        src = self.js("hook.js")
        ends = [int(m) for m in re.findall(r"later\(finish, (\d+)\)", src)]
        self.assertTrue(ends, "hook.js never schedules its own cleanup")
        finish = max(ends)
        self.assertGreaterEqual(
            finish, 4000,
            "the sequence is over in %dms; it is meant to be watchable, "
            "not merely present" % finish)
        guard = re.search(r"__hookFailsafe = setTimeout\(.*?\}, (\d+)\)",
                          self.head_script(), re.S)
        self.assertIsNotNone(guard, "no failsafe timer to read")
        self.assertGreater(
            int(guard.group(1)), finish,
            "the failsafe fires at %sms and the hook does not finish "
            "until %dms: on a page where hook.js failed to load, the "
            "outlines would be swapped for solid type part-way through "
            "a sequence that is still running" % (guard.group(1), finish))
        # The fill has to still fit inside the window the build gets.
        css = self.css()
        dur = re.search(r"\.hook-on\.hook-build \.claim__line \{\s*"
                        r"animation: hook-build ([\d.]+)s", css)
        self.assertIsNotNone(dur, "the build sweep has no duration")
        delays = [float(m) for m in re.findall(
            r"\.hook-on\.hook-build \.claim__reveal:nth-child\(\d+\) "
            r"\.claim__line \{ animation-delay: ([\d.]+)s", css)]
        build = max(int(m) for m in re.findall(
            r"root\.classList\.add\('hook-build'\);.*?\}, (\d+)\)",
            src, re.S))
        last = build + (max(delays) + float(dur.group(1))) * 1000
        self.assertLess(
            last, finish,
            "the last line is still filling at %dms and the hook tears "
            "itself down at %dms" % (last, finish))

    def test_no_delayed_animation_shows_the_element_where_it_starts(self):
        """A delay with no backwards fill paints the static style first.

        The cursor's glide had `delay: 120, fill: 'forwards'`. A
        forwards fill holds the LAST keyframe and only after the
        animation ends, so through those 120ms the element rendered at
        its own style -- no transform, no opacity rule -- which put a
        fully opaque pointer in the top-left corner of the hero. Then
        the animation began, snapped it to the right edge at opacity 0,
        and glided it back. Reported as the cursor jumping once, fast,
        from left to right on first open.

        Measured on the live page before the fix: transform "none",
        opacity "1", 24px left and 64px above the hero's own origin.

        Every delayed animation in this file has the same trap, so the
        check is on all of them rather than on the one that bit.
        """
        src = self.js("hook.js")
        calls = re.findall(r"\.animate\(\s*\[.*?\]\s*,\s*(\{[^}]*\})\)",
                           src, re.S)
        self.assertTrue(calls, "hook.js animates nothing")
        delayed = [o for o in calls if re.search(r"\bdelay:\s*[1-9]", o)]
        self.assertTrue(
            delayed,
            "no delayed animation left -- if that is deliberate, this "
            "test has nothing to guard and can go")
        for opts in delayed:
            with self.subTest(opts=" ".join(opts.split())[:70]):
                fill = re.search(r"fill:\s*'(\w+)'", opts)
                self.assertIsNotNone(
                    fill, "a delayed animation sets no fill at all, so the "
                          "element is drawn at its static style until the "
                          "delay is up")
                self.assertIn(
                    fill.group(1), ("both", "backwards"),
                    "a delayed animation fills %r: the element is visible "
                    "at its own position for the length of the delay and "
                    "then jumps to the first keyframe" % fill.group(1))

    def test_the_cursor_is_invisible_until_it_is_driven(self):
        """The belt to the fill, and it covers one more frame.

        hook.js appends the cursor, reads offsetWidth to decide which
        side the name tag goes on -- which forces layout -- and only
        then calls animate(). Nothing should be paintable in between.
        """
        i = self.css().index(".hook-cursor {")
        rule = self.css()[i:self.css().index("}", i)]
        self.assertIn("opacity: 0", rule,
                      "a cursor with no animation on it is visible")

    def test_the_hook_puts_the_page_back_exactly_as_it_found_it(self):
        """Its finished state has to be the page without it.

        Anything left behind -- the cursor node, a class, an inline
        style on a line -- is a difference between a first visit and a
        second one, which is a bug nobody sees because it only happens
        once per session.
        """
        src = self.js("hook.js")
        for needle in ("cursor.remove()",
                       "root.classList.add('hook-done')",
                       "root.classList.remove('hook-on', 'hook-build')",
                       "built.classList.remove('is-selected')"):
            self.assertIn(needle, src, "finish() does not do: %s" % needle)

    def test_the_hook_gets_out_of_the_way_when_asked(self):
        """Anything that looks like intent ends it at once.

        Not speeds it up -- jumps to the end. Someone who scrolls 600ms
        in has told you they are here for the page, not the performance.
        """
        src = self.js("hook.js")
        self.assertIn("['wheel', 'touchstart', 'keydown', 'pointerdown']", src,
                      "the hook cannot be skipped")
        self.assertIn("function skip() { finish(); }", src,
                      "skipping does something other than finishing")
        self.assertIn("if (window.scrollY > 8) { finish(); return; }", src,
                      "restored mid-page, the hook performs to an empty "
                      "screen")

    def test_a_reader_who_asked_for_less_motion_gets_neither(self):
        """Three layers, because any one of them can be the only one.

        The head script never sets the class; the stylesheet neutralises
        it if something else does; and the signal draws its finished
        diagram statically and does not touch the page at all.
        """
        self.assertIn("prefers-reduced-motion: reduce", self.head_script())
        css = self.css()
        self.assertRegex(
            css, r"@media \(prefers-reduced-motion: reduce\) \{\s*"
                 r"/\*[^*]*(?:\*(?!/)[^*]*)*\*/\s*\.hook-cursor \{ display: none",
            "the stylesheet has no reduced-motion belt for the hook")
        signal = self.js("signal.js")
        self.assertIn("if (!el || still) return;", signal,
                      "the signal marks up page content for a reader who "
                      "asked it not to move")
        self.assertIn(".signal.is-still .signal__head { display: none; }", css,
                      "the static diagram still shows a moving tip")

    def test_neither_file_is_loaded_where_it_has_nothing_to_do(self):
        """They are homepage code and they are most of the JavaScript.

        /about and the case studies have no claim to perform and no
        network to trace, so linking them there is two requests for two
        files that measure a page and then do nothing with it.
        """
        for page in ("index.html", "work.html"):
            with self.subTest(page=page):
                html = self.html(page)
                self.assertIn("assets/hook.js", html)
                self.assertIn("assets/signal.js", html)
                self.assertLess(html.index("assets/hook.js"),
                                html.index("assets/signal.js"),
                                "the signal is parsed before the hook it "
                                "waits for")
        for page in ("about.html", "404.html", "projects/instadeep.html"):
            with self.subTest(page=page):
                html = self.html(page)
                self.assertNotIn("assets/hook.js", html)
                self.assertNotIn("assets/signal.js", html)

    def test_the_two_clips_on_a_claim_line_do_not_shear_it(self):
        """The one interaction between the hook and this hero.

        Each line sits in a .claim__reveal that clips to the line box
        plus 0.07em. The hook paints the fill with background-clip: text,
        which only paints INSIDE the line box, so it grows each line by
        0.14em to keep the descenders of "design" and "people" -- and
        that 0.14em lands outside the reveal's clip and gets cut. The
        reveal has to open while the hook is running.
        """
        css = self.css()
        self.assertIn(".hook-on .claim__reveal { clip-path: none; }", css,
                      "the reveal still clips during the hook, so the "
                      "descenders it just made room for are sliced off "
                      "by the element above")
        self.assertIn(".hook-on .claim__line:not(.claim__line--built) {", css,
                      "the hook does not make room for descenders")

    def test_the_build_sweep_staggers_by_the_wrapper(self):
        """:nth-child on the line itself always matches 1.

        Every .claim__line is an only child of its own .claim__reveal,
        so `.claim__line:nth-child(2)` -- which is how this arrived --
        names nothing and all four lines fill at once. The counting has
        to happen on the wrapper.
        """
        css = self.css()
        delays = re.findall(
            r"\.hook-on\.hook-build ([^{]*?) \{ animation-delay", css)
        self.assertTrue(delays, "the build sweep has no stagger at all")
        for sel in delays:
            with self.subTest(sel=sel):
                self.assertIn(".claim__reveal:nth-child(", sel,
                              "the stagger counts lines, not wrappers, so "
                              "it matches one element and staggers nothing")
        home = self.html("index.html")
        lines = home.count('class="claim__reveal"')
        self.assertGreaterEqual(
            len(delays), lines,
            "%d authored lines and only %d build delays: the last line "
            "fills with the first" % (lines, len(delays)))

    def test_the_load_cascade_stands_down_for_the_hook(self):
        """Two entrances for the same elements, in the wrong order.

        The hero's own load animation arrives on page load; the hook
        does not reach those elements until the claim is built, about
        1.5s later. Unguarded, both run -- the supporting content
        arrives first, under a headline that is still a row of outlines
        waiting to be filled. .hook-done keeps them off afterwards, so
        clearing .hook-on does not replay the whole cascade.
        """
        css = self.css()
        for keyframe in ("hero-step-in", "maskUp"):
            with self.subTest(keyframe=keyframe):
                i = css.index("animation: %s" % keyframe)
                rule = css[css.rindex("}", 0, i):i]
                self.assertIn("html:not(.hook-on):not(.hook-done)", rule,
                              "%s plays underneath the hook" % keyframe)

    def test_everything_the_signal_measures_is_on_the_page(self):
        """A selector that matches nothing routes the trace into a wall.

        measure() returns null and the circuit silently never appears --
        no error, no drawing, nothing to notice. Every class it reaches
        for is checked against the markup it reaches into.
        """
        src = self.js("signal.js")
        wanted = set()
        for m in re.finditer(r"querySelector(?:All)?\('([^']+)'\)", src):
            wanted.update(re.findall(r"\.([a-z][a-z0-9_-]*)", m.group(1)))
        self.assertTrue(wanted, "the signal selects nothing")
        home = set()
        for m in re.finditer(r'class="([^"]*)"', self.html("index.html")):
            home.update(m.group(1).split())
        missing = sorted(w for w in wanted if w not in home)
        self.assertEqual(missing, [],
                         "the signal measures classes the homepage does "
                         "not have: %s" % missing)

    def test_the_signal_stays_off_paper_and_out_of_forced_colours(self):
        """It is decoration drawn in the margin.

        Printed it is a stray line down the page; in a forced-colours
        theme it is flattened to the one stroke colour and stops being
        faint, which puts a hard black rule through the gutter.
        """
        css = self.css()
        self.assertIn("@media print { .signal { display: none; } }", css)
        self.assertIn("@media (forced-colors: active) { .signal { display: none; } }", css)

    def test_the_header_ask_waits_and_comes_back(self):
        """One Book a call on the first screen was two, 300px apart.

        It collapses rather than fading: an invisible button still holds
        its width, leaving a hole in the header, and still takes a tab
        stop. And it hides again at the top, so arriving back at the
        hero does not leave it showing.
        """
        css = self.css()
        i = css.index(".js .site-head nav a.site-nav__cta {")
        rule = css[i:css.index("}", i)]
        for prop in ("max-width: 0", "visibility: hidden", "padding-inline: 0"):
            self.assertIn(prop, rule, "the collapsed button still %s" % prop)
        self.assertNotIn("display: none", rule,
                         "display: none cannot transition, so the button "
                         "would appear rather than arrive")
        src = (ROOT / "assets" / "enhance.js").read_text(encoding="utf-8")
        self.assertIn("en.boundingClientRect.top < 0", src,
                      "the button shows whenever the hero's ask is out of "
                      "view, including below it")
        self.assertIn("if (!ask || !io) { cta.classList.add('is-shown'); return; }",
                      src,
                      "a page with no hero loses its only ask")

    def test_the_page_asks_twice(self):
        """Six asks, four of them the same four words, was the note.

        Header, hero, under the Ways cards, and the closing band's pair.
        What is left is the header's -- which waits -- and the closing
        band's, which is the one place the page is allowed to be loud.
        """
        home = self.html("index.html")
        self.assertEqual(home.count(">Book a call"), 2,
                         "the homepage says Book a call a number of times "
                         "other than twice")
        self.assertNotIn("ways__ask", home)

    def test_the_counts_on_the_bars_are_counted(self):
        """A typed count starts lying the first time the list changes."""
        home = self.html("index.html")
        counts = re.findall(r'<p class="band__count">([^<]*)</p>', home)
        self.assertEqual(len(counts), 2,
                         "the homepage does not have exactly two bars")
        rows = home.count('<li class="index__row">')
        ways = home.count('<li class="way">')
        self.assertTrue(counts[0].startswith("%02d" % rows),
                        "the work bar says %r for %d rows" % (counts[0], rows))
        self.assertEqual(counts[1], "%02d" % ways,
                         "the ways bar says %r for %d cards" % (counts[1], ways))
        # ...and the span is derived, not typed.
        sys.path.insert(0, str(ROOT))
        import build
        self.assertIn(build.work_span(
            [p for p in build.load_projects()
             if p["slug"] in [i["slug"] for i
                              in build.SITE["sections"]["selected"]["items"]]]),
            counts[0])


class TestTheOutlinedHeadline(BuildCase):
    """For about a second and a half the h1 IS the outline.

    It is also what is left on screen if hook.js never arrives and the
    failsafe has not fired yet, and what a visitor sees for the whole
    sequence. So the outline colour has to be readable against the
    canvas in both themes, not merely visible -- a hairline at 2:1 on a
    136px letterform is a headline nobody can read.
    """

    FLOOR = 4.5

    @staticmethod
    def _rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    @classmethod
    def _ratio(cls, a, b):
        def lum(rgb):
            c = [v / 255 for v in rgb]
            c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
                 for x in c]
            return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
        x, y = lum(cls._rgb(a)), lum(cls._rgb(b))
        if x < y:
            x, y = y, x
        return (x + 0.05) / (y + 0.05)

    def test_the_outline_is_readable_in_both_themes(self):
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        m = re.search(r"\.hook-on \.claim__line \{[^}]*?"
                      r"-webkit-text-stroke: 1px var\((--[a-z-]+)\)", css, re.S)
        self.assertIsNotNone(m, "the outline does not come from a token")
        token = m.group(1)[2:]
        key = re.sub(r"-(\w)", lambda k: k.group(1).upper(), token)
        key = key[len("color"):]
        key = key[0].lower() + key[1:]
        tokens = json.loads((ROOT / "tokens.json").read_text(encoding="utf-8"))
        for group, label in (("color", "dark"), ("colorLight", "light")):
            with self.subTest(theme=label):
                ink = tokens[group][key]
                bg = tokens[group]["bg"]
                r = self._ratio(ink, bg)
                self.assertGreaterEqual(
                    round(r, 2), self.FLOOR,
                    "the outlined headline reads %.2f:1 against the %s "
                    "canvas, under AA -- for a second and a half that is "
                    "the h1" % (r, label))


class TestNothingNeedsJavaScript(BuildCase):
    """Every rule the hook and the signal add hides or moves something.

    Each one is scoped to a class that only a script sets, so with
    JavaScript off none of them apply and the page is the page. The
    failure here is silent and total: one unscoped `color: transparent`
    and the headline is simply gone for anyone without JS.
    """

    #: Properties that can remove content from a page.
    HIDING = ("color: transparent", "opacity: 0;", "display: none",
              "visibility: hidden", "clip-path: none")
    #: Classes nothing can see until a script puts them on <html>.
    GATES = (".hook-on", ".hook-done", ".signal-on", ".signal", ".js ",
             ".hook-cursor", ".signal__", ".is-")

    @staticmethod
    def _rules(css):
        """(selector, declarations) for every rule, at-rules flattened.

        Written out rather than regexed: a declaration can hold braces,
        percentages and parentheses, and the first attempt at this
        matched "100%" out of the middle of a linear-gradient and
        reported it as an unguarded selector.
        """
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        out, buf, stack = [], "", []
        i = 0
        while i < len(css):
            c = css[i]
            if c == "{":
                stack.append(buf.strip())
                buf = ""
            elif c == "}":
                sel = stack.pop() if stack else ""
                # Keyframe steps are "0%" and "to", not selectors, and
                # every one of them sets opacity. Skip the whole at-rule.
                inside_frames = any(f.lstrip().startswith("@keyframes")
                                    for f in stack)
                if not sel.startswith("@") and not inside_frames:
                    out.append((sel, buf))
                buf = ""
            else:
                buf += c
            i += 1
        return out

    def test_every_hiding_rule_in_the_new_work_is_behind_a_script(self):
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        start = css.index("/* \u2500\u2500 Signal: a forward pass")
        bad = []
        for sel, body in self._rules(css[start:]):
            if not sel or not any(h in body for h in self.HIDING):
                continue
            if not any(g in sel for g in self.GATES):
                bad.append(" ".join(sel.split())[:70])
        self.assertEqual(
            bad, [],
            "these rules hide page content with no script-set class in "
            "front of them, so they apply with JavaScript off: %s" % bad)

    def test_the_markup_itself_carries_none_of_it(self):
        """Nothing is pre-hidden in the HTML either."""
        home = self.html("index.html")
        self.assertNotIn("hook-cursor", home,
                         "the cursor is in the markup; it is decoration "
                         "and hook.js builds and removes it")
        self.assertNotIn("<svg class=\"signal\"", home,
                         "the circuit is in the markup; signal.js builds "
                         "it from measurements that do not exist yet")
        self.assertNotIn('class="hook-on"', home)
        self.assertIn('class="claim__line">I design AI products</span>', home,
                      "the claim is not plain text in the source")


class TestTheTwoPagesLookLikeOneSite(BuildCase):
    """/about read as a different product from the homepage.

    Its headline was 88px at weight 400 in the accent pink; the
    homepage's is 136px at weight 700 in the page's own ink. Its
    sections had bare labels where the homepage has a counted bar. Its
    four jobs were set at body size while the homepage's four projects
    carry the row at 34px. Its closing band stacked down the left edge
    while the homepage's is a row. Four separate drifts, each one small,
    and together they made two sites.
    """

    def css(self):
        return (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")

    def rule(self, selector):
        """Every declaration this exact selector sets, anywhere in the file.

        All of them joined, not the last one: these properties are split
        across a base rule and a desktop override, and reading only one
        of the two reported a missing line-height on a heading that has
        one.
        """
        hits = [m.group(1) for m in re.finditer(
            r"(?:^|\})\s*" + re.escape(selector) + r"\s*\{([^}]*)\}",
            self.css(), re.M)]
        self.assertTrue(hits, "no rule for %s" % selector)
        return "\n".join(hits)

    def test_neither_headline_is_set_in_the_accent(self):
        """A pink h1 on one page and a white one on the other is two brands."""
        body = self.rule(".about .about__statement")
        self.assertIn("color: var(--color-text)", body,
                      "the about headline is not the page's ink")
        self.assertNotIn("accent", body,
                         "the about headline is back in the accent, which "
                         "nothing else on either page is set in")

    def test_both_headlines_share_a_desktop_treatment(self):
        """Same weight, same tracking, same leading, above 1100px.

        The sizes differ on purpose -- the about sentence is six words
        longer -- but everything that makes the two read as the same
        typeface decision is asserted to match.
        """
        for sel in (".opening__claim", ".about .about__statement"):
            with self.subTest(sel=sel):
                body = self.rule(sel)
                self.assertIn("line-height: 0.96", body)
                self.assertIn("letter-spacing: -0.05em", body)
                self.assertIn("font-weight: var(--font-weight-bold)", body)

    def test_the_about_headline_outranks_the_legacy_h1_rules(self):
        """Three `.about h1` rules sit at (0,1,1) in this file.

        A bare `.about__statement` is (0,1,0) and loses to all three
        silently: the rule is in the stylesheet, the heading renders at
        the old size, and nothing anywhere says why. Measured once by
        hand already, so it gets a check.
        """
        css = self.css()
        self.assertTrue(re.search(r"(?:^|\})\s*\.about h1\s*\{", css, re.M),
                        "the legacy rules are gone, so this guard can go "
                        "too -- delete the test with them")
        for m in re.finditer(r"([.\w\s-]*\babout__statement)\s*\{", css):
            sel = m.group(1).strip()
            with self.subTest(sel=sel):
                self.assertIn(".about ", sel + " ",
                              "%s is outranked by `.about h1` and will not "
                              "apply" % sel)

    def test_both_pages_count_their_lists(self):
        """Every section bar on either page is the same component."""
        for page in ("index.html", "about.html"):
            with self.subTest(page=page):
                html = self.html(page)
                # The closing band is exempt: its h2 is the ask itself,
                # not the title of a list, and there is nothing to count
                # opposite a question.
                loose = re.findall(
                    r'<section class="band([^"]*)"[^>]*>\s*<h2', html)
                self.assertEqual(
                    [c for c in loose if "band--close" not in c], [],
                    "%s has a list section whose heading is not a band "
                    "bar" % page)
                self.assertIn('class="band__bar"', html)
        about = self.html("about.html")
        jobs = about.count('<li class="job">')
        counts = re.findall(r'<p class="band__count">([^<]*)</p>', about)
        self.assertTrue(counts, "/about counts nothing")
        self.assertTrue(counts[0].startswith("%02d" % jobs),
                        "the experience bar says %r for %d jobs"
                        % (counts[0], jobs))

    def test_both_lists_are_carried_by_their_names(self):
        """One size for the four projects and the four companies."""
        size = "clamp(1.5rem, 2.4vw, 2.125rem)"
        for sel in (".index__name", ".job__company"):
            with self.subTest(sel=sel):
                self.assertIn("font-size: %s" % size, self.rule(sel),
                              "%s is not set at the shared index size" % sel)

    def test_both_closing_bands_are_rows(self):
        for page in ("index.html", "about.html"):
            with self.subTest(page=page):
                self.assertIn('class="close__row"', self.html(page),
                              "%s still stacks its closing band down the "
                              "left edge" % page)


class TestTheWordmark(BuildCase):
    """The mark in front of the first name.

    It was a 2px rectangle -- a rule -- in an identity whose other half
    is the hand-drawn stroke the share card puts under "trust.". The two
    did not read as one hand, so the bar became that stroke, and it
    moved from the surname to the given name.
    """

    PAGES = ("index.html", "about.html", "404.html",
             "projects/instadeep.html")

    def css(self):
        return (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")

    def test_the_mark_is_drawn_on_every_page_that_has_a_header(self):
        for page in self.PAGES:
            with self.subTest(page=page):
                html = self.html(page)
                self.assertIn('class="wordmark__mark"', html,
                              "%s has a header with no mark in it" % page)

    def test_the_mark_sits_in_front_of_the_first_name(self):
        """Not the surname, which is where the ruled bar used to sit.

        Asserted off the rendered name rather than off the class, so
        swapping which line carries the indent without moving the mark
        fails here.
        """
        sys.path.insert(0, str(ROOT))
        from build import SITE
        first, rest = SITE["name"].split(" ", 1)
        html = self.html("index.html")
        m = re.search(r'<span class="wordmark__line wordmark__line--in">'
                      r'(.*?)</span>\s*<span class="wordmark__line">(.*?)</span>',
                      html, re.S)
        self.assertIsNotNone(
            m, "the wordmark is no longer an indented line followed by a "
               "flush one")
        self.assertIn("wordmark__mark", m.group(1),
                      "the indented line has no mark in it")
        self.assertIn(first, m.group(1),
                      "the mark is not on the given name")
        self.assertEqual(m.group(2).strip(), rest,
                         "the second line is not the surname on its own")
        self.assertNotIn("wordmark__line--in::before", self.css(),
                         "the ruled bar is still drawn as well as the "
                         "stroke, so the mark renders twice")

    def test_the_mark_is_decoration_and_says_so(self):
        """It is the logo's ornament; the link already carries the name."""
        html = self.html("index.html")
        svg = re.search(r'<svg class="wordmark__mark"[^>]*>', html).group(0)
        self.assertIn('aria-hidden="true"', svg)
        self.assertIn('focusable="false"', svg,
                      "an SVG without this takes a tab stop in some "
                      "browsers, which would put a focus ring on an "
                      "ornament inside a link")
        link = re.search(r'<a class="site-head__name"[^>]*>', html).group(0)
        self.assertIn('aria-label=', link,
                      "the logo's accessible name came from its text, and "
                      "its text now starts with a drawing")

    def test_the_mark_takes_its_colour_from_a_token(self):
        """Inline SVG and not a background image, for exactly this.

        A data URI would have to spell the colour out, and every colour
        in this stylesheet comes from tokens so that both themes repaint
        from one place. A hardcoded crimson mark would stay crimson on
        paper and in the light theme, where the accent is a different
        red.
        """
        css = self.css()
        i = css.index(".wordmark__mark {")
        rule = css[i:css.index("}", i)]
        self.assertIn("stroke: var(--color-accent)", rule)
        self.assertNotIn("fill: var", rule)
        self.assertIn("fill: none", rule,
                      "a filled path would render the curve as a blob")
        self.assertNotIn("data:image/svg", rule,
                         "the mark is back as a background image, which "
                         "cannot follow the theme")
        # The one data URI in this file is a colourless noise filter, and
        # it is why the check above is scoped to the rule: a blanket ban
        # would have failed on something that is already correct.
        self.assertEqual(css.count("data:image/svg"), 1,
                         "a second inline SVG has appeared in the "
                         "stylesheet; check it carries no colour")


class TestTheFontsAreFetchedOnce(BuildCase):
    """A preload only helps if it names the URL @font-face will ask for.

    They did not match. The preload carried a ?v= hash and the
    @font-face url did not, so they were two cache entries and BOTH
    FACES WERE DOWNLOADED TWICE -- the preload landing at 784ms and the
    request the page actually waits on finishing at 1524ms, measured on
    the live site.

    What that looks like to a visitor is the bug that found it: first
    paint in the fallback face at ~976ms, the display face swapping in
    around 1.5s, and the hook -- which waits on document.fonts.ready --
    unable to start until then. A reflowing headline in the wrong face
    with the rest of the hero still hidden, for about 600ms, and then
    everything moving at once.

    A mismatch here is invisible in every other way: both files are
    correct on their own, nothing 404s, nothing warns.
    """

    def head_of(self, page="index.html"):
        html = self.html(page)
        return html[:html.index("</head>")]

    def test_the_preload_and_the_font_face_ask_for_the_same_url(self):
        css_path = ROOT / "assets" / "fonts.css"
        css = css_path.read_text(encoding="utf-8")
        faces = re.findall(r"url\('([^']+)'\)", css)
        self.assertTrue(faces, "fonts.css loads no font files")
        head = self.head_of()
        preloads = re.findall(
            r'<link rel="preload" href="([^"]+)"[^>]*as="font"', head)
        self.assertEqual(
            len(preloads), len(faces),
            "%d faces and %d preloads: a face with no preload is a "
            "layout shift, a preload with no face is a wasted request"
            % (len(faces), len(preloads)))
        # Both resolve against their own file's directory, so compare
        # what the browser would: the path from the site root.
        want = {("assets/" + u).replace("assets/fonts/", "assets/fonts/")
                for u in faces}
        self.assertEqual(
            set(preloads), want,
            "the preload and the @font-face ask for different URLs, so "
            "the browser treats them as different files and fetches "
            "each face twice:\n  preload   %s\n  font-face %s"
            % (sorted(preloads), sorted(want)))

    def test_every_preloaded_font_is_cors_and_typed(self):
        """Fonts are always fetched in CORS mode.

        A preload without `crossorigin` is a separate cache entry from
        the one @font-face goes on to request -- the same double-fetch
        by a different route.
        """
        for link in re.findall(r'<link rel="preload"[^>]*as="font"[^>]*>',
                               self.head_of()):
            with self.subTest(link=link[:70]):
                self.assertIn("crossorigin", link,
                              "a font preload without crossorigin is "
                              "fetched twice")
                self.assertIn('type="font/woff2"', link)

    def test_the_font_url_is_busted_where_it_is_requested(self):
        """The hash has to be on the URL @font-face asks for.

        It used to be on the preload only -- a URL nothing else
        requested -- so the file the page actually loaded had no
        cache-buster at all and a replaced face would have been served
        stale indefinitely.
        """
        sys.path.insert(0, str(ROOT))
        from build import asset_v
        css = (ROOT / "assets" / "fonts.css").read_text(encoding="utf-8")
        for url in re.findall(r"url\('([^']+)'\)", css):
            with self.subTest(url=url):
                path, _, query = url.partition("?")
                self.assertTrue(
                    (ROOT / "assets" / path).is_file(),
                    "fonts.css loads %s, which is not on disk" % path)
                self.assertEqual(
                    "?" + query, asset_v("assets/" + path),
                    "%s carries a hash that is not a hash of its own "
                    "bytes" % path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
