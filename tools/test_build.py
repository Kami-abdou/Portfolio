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


class TestHomepageTiers(BuildCase):

    def test_highlights_band_holds_four_case_studies(self):
        """Three, then two, now four.

        A three-lens review (CEO / recruiter / design director) independently
        led with the same finding: 2,439 words of written prose sat in the
        content files and reached no visitor, because seven of nine projects
        carried format:highlights. Fixerloop -- the best commercially framed
        piece in the set -- and InstaDeep -- the current role, and the
        thinnest page on the site at 165 words -- were promoted back.

        The running order is the owner's call. InstaDeep leads because it is
        the current role; Steer follows as the largest scope. The array and
        each project's `order` have to be changed together -- see
        test_each_band_reads_in_order below, which is the guard this
        docstring used to only warn about."""
        self.assertEqual(
            self.site["sections"]["highlights"]["slugs"],
            ["instadeep", "steer", "fixerloop", "konnect"])

    def test_each_band_reads_in_order(self):
        """`order` must ascend down each band, or the numbering jumps.

        It is rendered as the visible %02d card number and it drives the
        prev/next pager, while the band's slug array decides what sits
        where on the homepage. They are two separate files saying the same
        thing, so they can disagree: reorder the array alone and the band
        counts 03, 01, 04, 02 down the page while Next walks a different
        route entirely.

        Nothing checked this before -- the class docstring warned about it
        in prose and no assertion backed it up, which is how a warning
        survives a reorder.
        """
        orders = {}
        for folder in sorted((ROOT / "projects").iterdir()):
            f = folder / "content.json"
            if f.is_file():
                d = json.loads(f.read_text(encoding="utf-8"))
                orders[d["slug"]] = d["order"]

        for band, spec in self.site["sections"].items():
            got = [orders[s] for s in spec["slugs"]]
            self.assertEqual(
                got, sorted(got),
                "%s is displayed as %s but their order values are %s -- the "
                "card numbers and the pager would disagree with the page"
                % (band, spec["slugs"], got))

    def test_the_two_bands_do_not_interleave(self):
        """Every case study outranks every gallery piece.

        The bands render one after the other, so if their order values
        interleave the page counts 01, 03, 02, 04 across the boundary even
        though each band is internally sorted.
        """
        orders = {}
        for folder in sorted((ROOT / "projects").iterdir()):
            f = folder / "content.json"
            if f.is_file():
                d = json.loads(f.read_text(encoding="utf-8"))
                orders[d["slug"]] = d["order"]
        top = [orders[s] for s in self.site["sections"]["highlights"]["slugs"]]
        rest = [orders[s] for s in self.site["sections"]["selectedWork"]["slugs"]]
        self.assertLess(
            max(top), min(rest),
            "the bands interleave: case studies are %s, gallery is %s" % (top, rest))

    def test_gallery_band_holds_the_remaining_four(self):
        """Was six, then five, now six again.

        UnDrive was removed at the owner's request -- its three images came
        from a Notion export rather than the portfolio Figma file, so it was
        the one Tier-2 entry with no route to better screens. Its originals
        are archived outside the repo, not in git.

        `portfolio` then took the sixth slot: this site, entered as its own
        project. It is the only evidence on the site for the build half of
        the positioning, and unlike every other entry a stranger can verify
        it by viewing source."""
        self.assertEqual(
            self.site["sections"]["selectedWork"]["slugs"],
            ["fissa3", "groupado", "smarthub", "portfolio"])

    def test_pharmadrive_is_gone_everywhere(self):
        """Removed on the design director's recommendation: lorem ipsum, a
        logo reading "PharmasDrive", "ordonnoce" misspelled, a cart totalling
        300 EUR for two 12 EUR items, and TND currency inside a euro product.
        Its six _src originals were checksum-verified into
        ../_archive/pharmadrive/ before deletion. The T+ informatique
        employment row stays -- that job happened; only the project chip went,
        because build.py exits on an unknown slug."""
        for band in ("highlights", "selectedWork"):
            self.assertNotIn("pharmadrive", self.site["sections"][band]["slugs"])
        self.assertFalse((ROOT / "projects" / "05-pharmadrive").exists())
        self.assertFalse((ROOT / "projects" / "pharmadrive.html").exists())
        self.assertNotIn("pharmadrive", (ROOT / "sitemap.xml").read_text(encoding="utf-8"))
        for page in ("index.html", "about.html"):
            self.assertNotIn("pharmadrive", self.html(page).lower())

    def test_undrive_is_gone_everywhere(self):
        """One assertion per surface it could survive on: the band, the
        filesystem, the sitemap, and any card or link in the built HTML."""
        self.assertNotIn("undrive", self.site["sections"]["selectedWork"]["slugs"])
        self.assertFalse((ROOT / "projects" / "07-undrive").exists())
        self.assertFalse((ROOT / "projects" / "undrive.html").exists())
        self.assertNotIn("undrive", (ROOT / "sitemap.xml").read_text(encoding="utf-8"))
        for page in ("index.html", "about.html"):
            self.assertNotIn("undrive", self.html(page).lower())

    def test_old_section_keys_are_gone(self):
        for stale in ("caseStudies", "otherProjects"):
            self.assertNotIn(stale, self.site["sections"])

    def test_the_two_bands_declare_different_column_counts(self):
        """The column counts are what make the headline cards bigger.

        Both bands ran at --cols: 3 briefly, to avoid the short last row that
        6 cards at 4-up leaves -- and that inverted the hierarchy. grid--lg
        carries a 48px gap against grid--sm's 32px, so at equal column counts
        the "large" cards rendered NARROWER (352px vs 363px) and shorter (a
        3/2 media against 4/3 gave 235px against 272px). Only the title was
        bigger, so Tier 2 visually outweighed Tier 1 -- the exact opposite of
        the point of the restructure.

        Measured after the fix at a 1280px viewport: 352px vs 264px wide,
        media area 83k vs 52k px^2. Equalising these is a regression, not a
        tidy-up.

        Asserted as an inequality rather than two literals. The headline band
        is min(3, len(slugs)) so that it never declares more columns than it
        has cards -- at three case studies that was 3, and when InstaDeep left
        for the gallery band it became 2 rather than leaving a 352px hole in
        the most important row on the site. Pinning the literal 3 would have
        failed here for a change that is correct.
        """
        import re
        index = self.html("index.html")
        cols = [int(m) for m in re.findall(r'style="--cols: (\d)"', index)]
        self.assertEqual(len(cols), 2, "expected exactly two card grids")
        large, small = cols
        self.assertLess(large, small,
                        "the headline band declares %d columns against the "
                        "gallery band's %d -- equal or more means Tier 1 "
                        "cards are no longer wider" % (large, small))

    def test_headline_cards_are_large_and_the_rest_are_not(self):
        index = self.html("index.html")
        self.assertEqual(index.count('class="card card--lg"'), 4)
        self.assertEqual(index.count('class="card"'), 4)

    def test_instadeep_is_the_first_card(self):
        """The owner's call, replacing an earlier review recommendation.

        This test used to assert the opposite -- Steer first, on the
        reasoning that leading with the non-AI role showed breadth rather
        than letting the site read as AI-only. That was a reviewer's
        recommendation, not a fact, and the owner has since put InstaDeep
        first: it is the current role, at an AI company acquired by
        BioNTech, and the about bio now leads on the same footing.

        The breadth concern it was protecting has its own test --
        test_hero_statement_names_more_than_one_domain -- which checks the
        copy rather than the running order, so nothing is lost by changing
        this.
        """
        index = self.html("index.html")
        self.assertLess(index.index('href="projects/instadeep"'),
                        index.index('href="projects/steer"'))

    def test_work_anchor_survives_the_rename(self):
        self.assertIn('id="work"', self.html("index.html"))


class TestHeroPositioning(BuildCase):
    """The hero must not claim AI is the whole practice.

    Asserted as a rendered-output property, not a string match on site.json:
    what matters is what the visitor reads. heroStatement is checked for the
    breadth signal rather than exact wording, so the owner can rewrite the
    copy without breaking the test.
    """

    def test_hero_statement_names_more_than_one_domain(self):
        statement = self.site["heroStatement"].lower()
        domains = ["fintech", "automotive", "delivery", "retail"]
        hits = [d for d in domains if d in statement]
        self.assertTrue(
            hits, "heroStatement names no non-AI domain: %r" % self.site["heroStatement"])

    def test_hero_statement_is_rendered_on_the_homepage(self):
        """Compared against the ESCAPED form, which is what build.py writes.

        build.py runs every string through html.escape(..., quote=True) (its
        e() helper). Asserting the raw site.json value appears verbatim would
        pass only for copy that happens to contain no apostrophe, ampersand
        or quote -- so it would fail spuriously the moment the owner exercised
        the rewrite freedom this class's docstring promises them.
        """
        rendered = html.escape(self.site["heroStatement"], quote=True)
        self.assertIn(rendered, self.html("index.html"))


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
    """

    def test_statement_wrapper_carries_shell(self):
        self.assertIn('<div class="hero__statement shell">', self.html("index.html"))

    def test_measure_lives_on_the_inner_element(self):
        self.assertIn('class="hero__statement__text"', self.html("index.html"))

    def test_statement_does_not_reintroduce_margin_or_max_width(self):
        """The regression is specifically these two properties coming back."""
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        block = css.split(".hero__statement {", 1)[1].split("}", 1)[0]
        for prop in ("margin", "max-width"):
            self.assertNotIn(prop, block,
                             ".hero__statement declares %s again, which "
                             "overrides .shell and breaks alignment" % prop)

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


class TestFavicon(BuildCase):
    """The AY mark, regenerated from the site's own Anton webfont.

    The owner supplied it as one 32x32 PNG -- a white disc with a black AY.
    Fine for a tab, useless for anything bigger: upscaled to 180 for the
    iOS home screen it is visibly mush. The mark is Anton, which ships in
    this repo and is the same face as the wordmark, so tools/make-favicon.py
    re-sets it at 512 and scales DOWN instead.

    The size was measured, not guessed: rendering at a candidate size,
    downscaling to 32 and diffing ink pixels against the supplied file gave
    a clear minimum at 344px -- 21 differing pixels of 1024, against 43-53
    either side. What remains is antialiasing, not a shape difference.
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
        for page in ("index.html", "about.html", "contact.html",
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
                         ("contact.html", ""), ("projects/steer.html", "../")):
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
        self.assertIn("anton-400.woff2", src,
                      "the generator no longer uses the site's own typeface")
        self.assertIn("FONT_SIZE = 344", src,
                      "the measured font size changed without the comparison "
                      "against the supplied file being redone")


class TestLinkIcons(BuildCase):
    """LinkedIn, GitHub, Email and the CV carry their marks.

    Same contract as the toolkit chips, deliberately: the icon appears only
    if the file was supplied, and whether it needs a light plate behind it
    is MEASURED rather than decided by eye, because that failure is silent.

    Measured against this page's #0A0A0B: cv 13.29:1, email 12.41:1,
    github 8.78:1, linkedin 8.36:1 -- so none takes a plate today. GitHub
    is worth understanding rather than just accepting: its black disc does
    vanish into the page, and what survives is the white Octocat, which is
    still the mark. Averaging over opaque pixels gives the right answer
    there for a counter-intuitive reason, so it was checked on screen at
    3x as well as computed.
    """

    SLUGS = ("linkedin", "github", "email", "cv")

    def test_every_mark_is_on_disk(self):
        for slug in self.SLUGS:
            self.assertTrue((ROOT / "assets" / "links" / ("%s.png" % slug)).is_file(),
                            "assets/links/%s.png is missing, so that button "
                            "silently loses its mark" % slug)

    def test_the_contact_buttons_all_carry_one(self):
        """Homepage band and /contact are the same block, so both or neither."""
        for page in ("index.html", "contact.html"):
            row = self.html(page).split('class="btn-row"', 1)[1].split("</div>", 1)[0]
            for slug in self.SLUGS:
                self.assertIn("assets/links/%s.png" % slug, row,
                              "%s: the %s button has no mark" % (page, slug))

    def test_the_about_page_carries_them_too(self):
        about = self.html("about.html")
        for slug in ("linkedin", "github", "email"):
            self.assertIn("assets/links/%s.png" % slug, about,
                          "about page: the %s button has no mark" % slug)

    def test_the_label_match_does_not_overreach(self):
        """"Source on GitHub" is GitHub. "Groupado today" is not anything.

        The match is a keyword inside an owner-authored label, so the risk
        is a false positive putting a brand mark on an unrelated link.
        """
        portfolio = self.html("projects/portfolio.html")
        self.assertIn("assets/links/github.png", portfolio,
                      '"Source on GitHub" lost its mark')
        for slug in ("steer", "groupado", "konnect", "fixerloop"):
            page = self.html("projects/%s.html" % slug)
            row = re.search(r'<div class="btn-row">(.*?)</div>', page, re.S)
            if not row:
                continue
            self.assertNotIn("assets/links/", row.group(1),
                             "%s has a product link wearing a brand mark it "
                             "should not have matched" % slug)

    def test_the_marks_are_decorative(self):
        """Every button says what it is in words, so alt must be empty.

        A filled alt would make a screen reader announce the brand twice.
        """
        for page in ("index.html", "contact.html", "about.html"):
            for img in re.findall(r'<img class="btn__icon[^>]*>', self.html(page)):
                self.assertIn('alt=""', img,
                              "%s has a non-decorative button mark: %s" % (page, img))

    def test_dimensions_come_from_the_file(self):
        """The CV mark is a portrait sheet, not a square.

        Hardcoding 36x36 would squash it and reserve the wrong box, so the
        row would shift as it loaded. This asserts the non-square case
        specifically, because the three square marks would pass either way.
        """
        img = re.search(r'<img class="btn__icon"[^>]*links/cv\.png[^>]*>',
                        self.html("contact.html"))
        self.assertIsNotNone(img, "the CV button lost its mark")
        w = re.search(r'width="(\d+)"', img.group(0))
        h = re.search(r'height="(\d+)"', img.group(0))
        self.assertIsNotNone(w, "the CV mark declares no width")
        self.assertNotEqual(w.group(1), h.group(1),
                            "the CV mark is declared square; it is a portrait "
                            "sheet and would be squashed")

    def test_the_plate_is_measured_not_hardcoded(self):
        """The one rule that keeps a future dark mark from disappearing."""
        src = (ROOT / "build.py").read_text(encoding="utf-8")
        fn = src.split("def link_icon(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("icon_needs_plate", fn,
                      "link_icon stopped measuring contrast, so a dark mark "
                      "dropped in later would silently vanish")
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".btn__icon--plate", css,
                      "the plate class has no styling, so measuring for it "
                      "would do nothing")

    def test_buttons_align_the_mark_with_the_label(self):
        """inline-block would drop the mark onto the text baseline."""
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        block = css.split("\n.btn {", 1)[1].split("}", 1)[0]
        self.assertIn("inline-flex", block,
                      "the buttons are not flex, so the mark sits on the "
                      "baseline with a descender gap under it")
        self.assertIn("align-items: center", block)


class TestCleanUrls(BuildCase):
    """/work, /about and /contact, not index.html#contact.

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

    PAGES = ("index.html", "work.html", "about.html", "contact.html")

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
        """A project page is one level down, so every href needs ../."""
        for slug in ("steer", "instadeep"):
            head = self.html("projects/%s.html" % slug).split("</header>", 1)[0]
            for target in ("work", "about", "contact"):
                self.assertIn('href="../%s"' % target, head,
                              "projects/%s.html cannot reach /%s" % (slug, target))

    def test_contact_is_a_page_and_the_band_is_still_on_the_homepage(self):
        """Both, deliberately: the nav gets a page, the scroller gets a band."""
        contact = self.html("contact.html")
        self.assertIn('id="contact"', contact)
        self.assertIn("mailto:%s" % self.site["email"], contact)
        self.assertIn('id="contact"', self.html("index.html"),
                      "the homepage lost its contact band")

    def test_the_contact_band_has_one_source(self):
        """It carries the email, the CV and every link.

        Copied, it would have two places to fall out of date on the one
        block where being wrong costs an actual opportunity. So the band is
        asserted identical on both pages.
        """
        def band(page):
            return self.html(page).split('class="band band--contact', 1)[1] \
                                  .split("</section>", 1)[0]
        self.assertEqual(band("index.html"), band("contact.html"),
                         "the contact band differs between the homepage and "
                         "/contact, so one of them is stale")

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
        for target in ("work", "about", "contact"):
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


class TestHeroScrim(BuildCase):
    """The scrim that fades the hero's foot must stay in two named parts.

    It exists because the wall and the statement are both --color-text: on a
    short window the poster type slides in behind the paragraph and contrast
    goes to nothing. The fix is a band of solid --color-bg under the text
    with a ramp above it.

    The bug was that the WHOLE thing was sized off the hero --
    clamp(380px, 55%, 500px) -- so the ramp was only ever the remainder. It
    ran 124px on a short window and 244px on a 1080p one, and at 1920x1080
    the scrim reached 500px and rubbed out the entire third row of the wall
    plus the foot of the accent row. The solid band is the part with a real
    requirement; the ramp wants to be constant. So they are now two tokens
    and the height is their sum.

    Measured by hiding every hero child except .wall and reading the
    rendered pixels at 1440x900/700, 1920x1080, 1024x768, 390x844 and
    320x568: the solid band is flat --color-bg in all six.
    """

    REM = 16.0
    #: Highest the statement's top line reaches above the hero's foot, over
    #: every viewport measured. 320x568 is the worst case -- narrowest
    #: measure, so the paragraph wraps to four lines.
    STATEMENT_TOP_PX = 185

    def scrim_lengths(self):
        """Resolve --scrim-solid and --scrim-fade to pixels.

        The tokens they are built from live in tokens.css, which build.py
        generates, so this resolves against the built file rather than
        hardcoding 2rem/4rem -- change a space step and the test follows.
        """
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        tokens = (ROOT / "assets" / "tokens.css").read_text(encoding="utf-8")

        def px(expr):
            for name, value in re.findall(r"(--[\w-]+):\s*([^;]+);", tokens):
                expr = expr.replace("var(%s)" % name, value.strip())
            expr = re.sub(r"\bcalc\b", "", expr)
            total = 0.0
            for number, unit in re.findall(r"([\d.]+)(rem|px)", expr):
                total += float(number) * (self.REM if unit == "rem" else 1)
            self.assertNotIn("var(", expr, "unresolved token in %r" % expr)
            return total

        # Six separate rules in this stylesheet open with `.hero {`, so
        # splitting on the first one reads a block that never mentioned the
        # scrim and the test passes for the wrong reason -- the exact way an
        # earlier nav test went green while asserting nothing. Take every
        # .hero block and require that exactly one declares the tokens.
        blocks = [chunk.split("}", 1)[0] for chunk in css.split(".hero {")[1:]]
        owners = [b for b in blocks if "--scrim-" in b]
        self.assertEqual(len(owners), 1,
                         "expected exactly one .hero rule to declare the "
                         "scrim tokens, found %d" % len(owners))
        found = dict(re.findall(r"(--scrim-\w+):\s*([^;]+);", owners[0]))
        self.assertEqual(set(found), {"--scrim-solid", "--scrim-fade"},
                         "the scrim's parts are no longer declared on .hero")
        return px(found["--scrim-solid"]), px(found["--scrim-fade"])

    def test_height_is_the_sum_of_the_two_parts(self):
        """A literal or a percentage here is the regression, whatever it says."""
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        block = css.split(".hero::after {", 1)[1].split("}", 1)[0]
        height = re.search(r"height:\s*([^;]+);", block).group(1)
        self.assertIn("var(--scrim-solid)", height,
                      "the scrim height stopped tracking its solid band: %r" % height)
        self.assertIn("var(--scrim-fade)", height,
                      "the scrim height stopped tracking its ramp: %r" % height)
        self.assertNotIn("%", height,
                         "the scrim is sizing itself off the hero again, which "
                         "is what made the ramp balloon to 244px: %r" % height)

    def test_gradient_stops_at_the_same_token_as_the_height(self):
        """If the stop and the height drift apart the ramp silently changes."""
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        block = css.split(".hero::after {", 1)[1].split("}", 1)[0]
        gradient = block.split("background:", 1)[1]
        self.assertIn("var(--color-bg) var(--scrim-solid)", gradient,
                      "the opaque stop no longer uses --scrim-solid, so the "
                      "solid band and the declared height can disagree")

    def test_solid_band_clears_the_statement(self):
        """The whole point: every line of the paragraph on flat colour."""
        solid, _ = self.scrim_lengths()
        self.assertGreaterEqual(
            solid, self.STATEMENT_TOP_PX,
            "--scrim-solid is %.0fpx but the paragraph's top line reaches "
            "%dpx above the hero's foot at 320px wide, so the top line would "
            "sit on wall letters" % (solid, self.STATEMENT_TOP_PX))

    def test_ramp_stays_long_enough_not_to_band(self):
        """A short ramp on a 151px letterform reads as a hard edge.

        124px was the shortest ramp the old clamp ever produced, and it
        shipped without banding, so it is the evidence-backed ceiling on how
        far this can be cut -- not a number picked for feel.
        """
        _, fade = self.scrim_lengths()
        self.assertGreater(fade, 0, "the scrim lost its ramp and is now a hard edge")
        self.assertLessEqual(
            fade, 124,
            "--scrim-fade is %.0fpx, longer than the 124px the old clamp's "
            "floor produced -- the ramp is growing back into the wall" % fade)


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
        silently vanishes -- the exact failure this guards. Asserts the count
        as well as the path, because a partial glob is the quieter bug.

        This used to assert `class="viewer"`. InstaDeep became a gallery, and
        highlights pages drop the tabbed browser: it shows one board at a time,
        which earns its keep only when prose is walking the reader through
        them. What matters either way is that every board reaches the page.
        """
        page = self.html("projects/instadeep.html")
        self.assertIn("assets/components/", page)
        folder = ROOT / "projects" / "10-instadeep" / "assets" / "components"
        boards = sorted(p.name for p in folder.glob("*.png"))
        self.assertEqual(len(boards), 7, "component board count changed")
        for name in boards:
            self.assertIn("components/%s" % name, page,
                          "%s never made it onto the page" % name)

    def test_gallery_pages_do_not_render_the_tabbed_browser(self):
        """A tablist with no prose hides six of seven boards behind controls
        the visitor has no reason to click."""
        self.assertNotIn('class="viewer"', self.html("projects/instadeep.html"))
        self.assertNotIn('role="tab"', self.html("projects/instadeep.html"))

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

        The sitemap total is the eight project pages plus /work, /about and
        /contact. index.html is deliberately not listed: it is the same
        bytes as /work, which is the canonical of the pair, so listing both
        would ask a crawler to decide what the canonical already decided.
        """
        self.assertIn("11 URLs", self.stdout)
        self.assertIn("8 pages", self.stdout)


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
        for slug in ("fissa3", "groupado", "smarthub", "portfolio"):
            self.assertIn(">Project<", self.html("projects/%s.html" % slug),
                          "%s does not read as a Tier-2 page" % slug)
        for slug in ("steer", "konnect", "fixerloop", "instadeep"):
            self.assertIn(">Case study<", self.html("projects/%s.html" % slug),
                          "%s does not read as a case study" % slug)

    def test_highlights_pages_have_no_table_of_contents(self):
        """A TOC over image blocks with no prose is navigation to nothing."""
        self.assertNotIn('class="toc"', self.html("projects/fissa3.html"))

    def test_a_lone_section_is_not_numbered(self):
        """A leading "01" claims a position in a sequence that does not exist.

        Trimming prose used to leave UnDrive and PharmaDrive with one live
        section each, both titled "The outcome" -- so "01 The outcome" invited
        "the outcome of what?" exactly where the setup used to be.

        Both projects have since been removed, so NO page has a lone section
        today and this passes vacuously on the first loop. That is deliberate:
        asserted as a property over every page rather than against a named
        slug, so it starts failing again the moment a one-section page
        reappears, instead of erroring on a file that no longer exists -- which
        is how this test broke when PharmaDrive went.
        """
        import glob
        lone = multi = 0
        for path in sorted(glob.glob(str(ROOT / "projects" / "*.html"))):
            name = "projects/" + pathlib.Path(path).name
            page = self.html(name)
            sections = page.count('class="project__section"')
            if sections == 1:
                lone += 1
                self.assertNotIn("project__num", page,
                                 "%s numbers its only section" % name)
            elif sections > 1:
                multi += 1
                self.assertEqual(sections, page.count("project__num"),
                                 "%s lost its section numbering" % name)
        self.assertGreater(multi, 0, "no multi-section page left to check")


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
        hero = re.search(r'<figure class="hero__portrait">.*?</figure>',
                         index, re.S)
        self.assertIsNotNone(hero, "hero portrait figure is gone from the page")
        self.assertNotIn(".avif", hero.group(0),
                         "an AVIF source is back in the hero -- verify its "
                         "PIXELS in a browser, not its bytes, before shipping")

    def test_hero_image_exists_and_is_a_real_jpeg(self):
        import re, struct
        index = self.html("index.html")
        src = re.search(r'<figure class="hero__portrait">.*?<img src="([^"?]+)',
                        index, re.S).group(1)
        path = ROOT / src
        self.assertTrue(path.is_file(), "hero portrait missing: %s" % src)
        head = path.read_bytes()[:2]
        self.assertEqual(head, b"\xff\xd8", "%s is not a JPEG" % src)
        # A black or empty encode compresses to almost nothing. The real file
        # is ~265 KB; anything under 20 KB at these dimensions is a red flag.
        self.assertGreater(path.stat().st_size, 20_000,
                           "%s is suspiciously small -- is it blank?" % src)

    def test_hero_portrait_is_cropped_to_include_the_subject(self):
        """object-position must stay biased down.

        portrait.jpg is 0.56 aspect going into a 3/4 frame, so `cover` throws
        away height. At the default 50% the crop centres on the buildings and
        cuts the subject off at the frame edge -- the one thing the portrait
        exists to show.
        """
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        block = css.split(".hero .hero__portrait img {", 1)[1].split("}", 1)[0]
        self.assertIn("object-position", block,
                      "the hero portrait lost its downward crop bias")


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
        """
        self.assertIn('href="work" aria-current="page"',
                      self.html("index.html"))
        self.assertIn('href="about" aria-current="page"',
                      self.html("about.html"))
        self.assertIn('href="contact" aria-current="page"',
                      self.html("contact.html"))

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
            nav = page.split('<nav aria-label="Primary">', 1)[1].split("</nav>", 1)[0]
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
        for slug in ("steer", "konnect", "instadeep", "fixerloop"):
            page = self.html("projects/%s.html" % slug)
            nav = page.split('<nav aria-label="Primary">', 1)[1].split("</nav>", 1)[0]
            self.assertNotIn("aria-current", nav,
                             "%s marks a nav item as the current page" % slug)

    def test_contact_navigates_rather_than_firing_a_mail_client(self):
        """Contact was a mailto: sitting between two page links.

        In a nav that is a surprise -- it opens a mail client, or on a
        machine with none configured it appears to do nothing at all. It
        then became index.html#contact, and is now its own page at
        /contact, which is what the other two nav items are. The homepage
        keeps its band, so anyone who reads to the end still finds a way
        to get in touch. The mailto lives inside both, where a visitor
        expects one.

        Depth is taken from the path, not the filename: an earlier version
        of this checked `"/" in name` against a bare basename, which is
        never true, so every project page was silently tested against the
        root-relative href and the assertion failed for the wrong reason.
        """
        import re, glob, pathlib as pl
        roots = glob.glob(str(ROOT / "*.html"))
        nested = glob.glob(str(ROOT / "projects" / "*.html"))
        for path in roots + nested:
            rel = pl.Path(path).relative_to(ROOT)
            up = "../" * (len(rel.parts) - 1)
            page = pl.Path(path).read_text(encoding="utf-8")
            nav = re.search(r'<nav aria-label="Primary">(.*?)</nav>', page, re.S)
            self.assertIsNotNone(nav, "%s lost its primary nav" % rel)
            self.assertNotIn("mailto:", nav.group(1),
                             "%s still fires a mail client from the nav" % rel)
            self.assertIn('href="%scontact"' % up, nav.group(1),
                          "%s has no route to the contact page" % rel)
        self.assertTrue((ROOT / "contact.html").is_file(),
                        "the nav points at /contact but the page is gone")
        self.assertIn('id="contact"', self.html("index.html"),
                      "the homepage lost its contact band")
        self.assertIn("mailto:", self.html("contact.html"),
                      "the contact page has no address on it")

    def test_nav_links_have_a_real_hit_area(self):
        """They had zero padding, so the target was the text box: 24px tall,
        the bare WCAG 2.5.8 minimum and well under the 44px platform norm.
        Measured after the fix: 48px tall, header height unchanged at 76px
        because the padding is offset by a negative margin."""
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        block = css.split(".site-head nav a {", 1)[1].split("}", 1)[0]
        self.assertIn("padding", block, "nav links lost their hit area")

    def test_contact_band_still_holds_the_address_and_cv(self):
        """The nav now sends people here, so this is load-bearing."""
        index = self.html("index.html")
        band = index.split('id="contact"', 1)[1].split("</section>", 1)[0]
        self.assertIn("contact__addr", band, "the visible email address is gone")
        self.assertIn("mailto:", band)
        self.assertIn(".pdf", band.lower(), "the CV is no longer at the point of intent")


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

    def test_supplied_marks_render_as_images(self):
        """Every supplied mark, on the page that actually uses it.

        An earlier version of this asserted only against portfolio.html,
        which lists Figma and Claude Code. Framer appears on instadeep.html
        only -- so deleting framer.png left the whole suite green. Assert
        each mark where it is used, or the test is decoration.
        """
        expected = {
            "projects/portfolio.html": {"Figma": "figma.png",
                                        "Claude Code": "claude-code.png"},
            "projects/instadeep.html": {"Figma": "figma.png",
                                        "Framer": "framer.png"},
        }
        for page, want in expected.items():
            chips = dict(self._chips(page))
            for name, filename in want.items():
                self.assertEqual(chips.get(name), filename,
                                 "%s on %s" % (name, page))

    def test_tools_without_a_file_fall_back_to_a_monogram(self):
        """Python is the last tool with no mark on disk.

        Git was in this list until its supplied file was usable. The file
        was always RGBA -- it just had the transparency checkerboard painted
        into opaque pixels, so it looked like a grey checked square. A
        border flood-fill cleared the background and left the mark, including
        the white branch glyph INSIDE the red diamond, which a plain colour
        key would have punched straight through.
        """
        chips = dict(self._chips("projects/portfolio.html"))
        self.assertIsNone(chips.get("Python"),
                          "Python has no icon file but rendered an <img>")
        self.assertEqual(chips.get("Git"), "git.png")

    def test_the_about_page_toolkit_uses_chips_too(self):
        """It was the one place the toolkit rendered as "A · B · C" text.

        tool_chips() had always been wired to project pages only, so the
        page where someone actually goes looking for the stack was the page
        showing it as a plain string. Depth matters here: about.html is at
        the root, so its icon paths carry no ../ prefix.
        """
        about = self.html("about.html")
        self.assertIn('<ul class="tools">', about,
                      "the about toolkit went back to plain text")
        self.assertIn('src="assets/tools/figma.png', about)
        self.assertNotIn('src="../assets/tools/', about,
                         "about.html is at the root; ../ would 404")

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
        """Dark marks get a plate, light marks must not.

        The plate was briefly applied to every icon. That fixed Framer
        (1.06:1 against the page) and broke the opposite case: MCP measures
        14.91:1 on the page and 1.20:1 on a white plate. Both directions are
        invisible, and neither announces itself.

        build.py decides per icon by averaging the luminance of the opaque
        pixels, so swapping a file re-decides automatically. These assert the
        outcome on the rendered page rather than the mechanism.
        """
        import re
        about = self.html("about.html")
        chips = {}
        for m in re.findall(r'<li class="tool">(.*?)</li>', about, re.S):
            name = re.search(r'tool__name">([^<]+)', m).group(1)
            if "tool__icon" in m:
                chips[name] = "tool__icon--plate" in m
        # dark marks: would vanish on #0A0A0B without it
        for name in ("Figma", "Framer", "VWO"):
            self.assertTrue(chips.get(name), "%s lost its plate" % name)
        # light marks: the plate would erase them instead
        for name in ("Creative Cloud", "Miro", "Notion", "Jira", "Claude Code"):
            self.assertFalse(chips.get(name, True),
                             "%s got a plate it does not need" % name)

    def test_the_plate_class_still_carries_a_background(self):
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        block = css.split(".tool__icon--plate {", 1)[1].split("}", 1)[0]
        self.assertIn("background", block)


class TestCardMeta(BuildCase):

    def test_every_project_has_a_short_meta_line(self):
        import glob
        for path in glob.glob(str(ROOT / "projects" / "*" / "content.json")):
            project = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
            meta = project.get("meta")
            self.assertTrue(meta, "%s has no meta line" % project["slug"])
            self.assertLessEqual(
                len(meta), 44,
                "%s meta is %d chars, too long for a card" % (project["slug"], len(meta)))

    def test_meta_renders_on_every_card(self):
        self.assertEqual(self.html("index.html").count('class="card__meta"'), 8)

    def test_todo_meta_is_suppressed_not_printed(self):
        """usable() must gate this like every other field -- BUILD.md rule."""
        sys.path.insert(0, str(ROOT))
        from build import usable
        self.assertFalse(usable("TODO — year"))
        self.assertNotIn("TODO", self.html("index.html"))


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
