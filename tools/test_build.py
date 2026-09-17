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

        Order matters here: `order` renders as the visible card number, so
        the array must ascend or the band reads 01, 02, 04, 03."""
        self.assertEqual(
            self.site["sections"]["highlights"]["slugs"],
            ["steer", "konnect", "instadeep", "fixerloop"])

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

    def test_steer_is_the_first_card(self):
        """Leading with a non-AI CPO role is the positioning fix."""
        index = self.html("index.html")
        self.assertLess(index.index("projects/steer.html"),
                        index.index("projects/instadeep.html"))

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
        """If .shell stops centring, every page moves, not just the hero."""
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        block = css.split(".shell {", 1)[1].split("}", 1)[0]
        self.assertIn("max-width: var(--max-width)", block)
        self.assertIn("margin-inline: auto", block)
        self.assertIn("padding-inline: var(--gutter)", block)

    def test_no_page_claims_specialising_in_ai(self):
        for page in ("index.html", "about.html"):
            self.assertNotIn("specialising in AI", self.html(page),
                             "%s still narrows the practice to AI" % page)


class TestInstaDeepEntry(BuildCase):

    def test_page_exists(self):
        self.assertTrue((ROOT / "projects" / "instadeep.html").is_file())

    def test_names_all_three_products(self):
        page = self.html("projects/instadeep.html")
        for product in ("DeepPCB", "Design system", "InstaNovo"):
            self.assertIn(product, page, "instadeep.html omits %s" % product)

    def test_instanovo_is_named_but_its_section_is_not_yet_rendered(self):
        """InstaNovo is named in the summary, so the entry is honest about the
        scope of the role -- but its section has a TODO body and no images, so
        build.py:838 drops it. The block appears when the screens land, with no
        template change. This test is what tells you the stub is wired
        correctly rather than merely absent."""
        page = self.html("projects/instadeep.html")
        self.assertIn("InstaNovo", page)
        self.assertNotIn('id="instanovo"', page)
        self.assertNotIn("TODO", page)
        stub = [s for s in self.content("10-instadeep")["sections"]
                if s.get("id") == "instanovo"]
        self.assertEqual(len(stub), 1, "the InstaNovo stub section is missing")
        self.assertNotIn("images", stub[0])

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
        self.assertIn('href="projects/instadeep.html"', self.html("about.html"))

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
        The sitemap total is pages + index + about."""
        self.assertIn("10 URLs", self.stdout)
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
