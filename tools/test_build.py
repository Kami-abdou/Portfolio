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

    def test_highlights_band_holds_exactly_three_slugs(self):
        self.assertEqual(
            self.site["sections"]["highlights"]["slugs"],
            ["steer", "konnect", "instadeep"])

    def test_selected_work_band_holds_the_other_six(self):
        self.assertEqual(
            self.site["sections"]["selectedWork"]["slugs"],
            ["fixerloop", "fissa3", "groupado", "pharmadrive", "undrive", "smarthub"])

    def test_old_section_keys_are_gone(self):
        for stale in ("caseStudies", "otherProjects"):
            self.assertNotIn(stale, self.site["sections"])

    def test_both_grids_are_three_across(self):
        """3 cards at 2-up orphans one; 6 at 4-up orphans two."""
        index = self.html("index.html")
        self.assertEqual(index.count("--cols: 3"), 2,
                         "expected both bands to declare --cols: 3")

    def test_headline_cards_are_large_and_the_rest_are_not(self):
        index = self.html("index.html")
        self.assertEqual(index.count('class="card card--lg"'), 3)
        self.assertEqual(index.count('class="card"'), 6)

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

    def test_component_browser_still_auto_populates(self):
        """assets/components/ is globbed by autoImages, not listed in JSON.

        If the folder failed to move, auto_images() returns [] and the viewer
        section silently vanishes -- the exact failure this guards.
        """
        page = self.html("projects/instadeep.html")
        self.assertIn('class="viewer"', page)
        self.assertIn("assets/components/", page)

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

    def test_nine_project_pages_and_eleven_sitemap_urls(self):
        self.assertIn("11 URLs", self.stdout)
        self.assertIn("9 pages", self.stdout)


class TestHighlightsFormat(BuildCase):

    TIER2 = [("06-fixerloop", "fixerloop"), ("03-fissa3", "fissa3"),
             ("04-groupado", "groupado"), ("05-pharmadrive", "pharmadrive"),
             ("07-undrive", "undrive"), ("08-smarthub", "smarthub")]

    def test_all_six_are_flagged(self):
        for folder, _ in self.TIER2:
            self.assertEqual(self.content(folder).get("format"), "highlights",
                             "%s is not flagged" % folder)

    def test_tier_one_is_not_flagged(self):
        for folder in ("01-steer", "02-konnect", "10-instadeep"):
            self.assertIsNone(self.content(folder).get("format"),
                              "%s should stay a full case study" % folder)

    def test_prose_is_not_deleted_only_unrendered(self):
        """The whole point of the flag: reversible by removing one field."""
        fixerloop = self.content("06-fixerloop")
        bodies = [s.get("body") for s in fixerloop["sections"] if s.get("body")]
        self.assertGreater(len(bodies), 5,
                           "Fixerloop's narrative was deleted, not just hidden")

    def test_highlights_pages_render_images_but_not_body_prose(self):
        page = self.html("projects/fixerloop.html")
        self.assertIn('class="shots', page)
        body = [s["body"] for s in self.content("06-fixerloop")["sections"]
                if s.get("body") and not s["body"].startswith("TODO")][0]
        first_sentence = body.split(".")[0]
        self.assertNotIn(first_sentence, page,
                         "highlights page still renders section prose")

    def test_eyebrow_follows_tier_not_category(self):
        """Fissa3 and Groupado are category:case-study but Tier 2."""
        for slug in ("fissa3", "groupado", "fixerloop"):
            self.assertIn(">Project<", self.html("projects/%s.html" % slug),
                          "%s does not read as a Tier-2 page" % slug)
        for slug in ("steer", "konnect", "instadeep"):
            self.assertIn(">Case study<", self.html("projects/%s.html" % slug),
                          "%s does not read as a case study" % slug)

    def test_highlights_pages_have_no_table_of_contents(self):
        """A TOC over image blocks with no prose is navigation to nothing."""
        self.assertNotIn('class="toc"', self.html("projects/undrive.html"))

    def test_a_lone_section_is_not_numbered(self):
        """A leading "01" claims a position in a sequence that does not exist.

        Trimming prose leaves PharmaDrive and UnDrive with a single live
        section, and theirs happens to be titled "The outcome" -- so "01 The
        outcome" invited "the outcome of what?" exactly where the setup used
        to be. Pages that do have a sequence keep their numbers.
        """
        for slug in ("pharmadrive", "undrive"):
            page = self.html("projects/%s.html" % slug)
            self.assertEqual(page.count("project__section"), 1,
                             "%s is no longer a single-section page" % slug)
            self.assertNotIn("project__num", page,
                             "%s numbers its only section" % slug)
        for slug in ("fixerloop", "steer"):
            page = self.html("projects/%s.html" % slug)
            self.assertEqual(page.count("project__section"),
                             page.count("project__num"),
                             "%s lost its section numbering" % slug)


if __name__ == "__main__":
    unittest.main(verbosity=2)
