#!/usr/bin/env python3
"""Build-output tests. Run: python3 tools/test_build.py

The site ships with no dependencies and no test framework, so these use
stdlib unittest and assert against the real generated HTML.

build.py is run as a SUBPROCESS rather than imported: it reads site.json
into a module global at import time (build.py:22), so an in-process import
would test a stale copy of the very file most of these tests change.
"""
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
        self.assertIn(self.site["heroStatement"], self.html("index.html"))

    def test_no_page_claims_specialising_in_ai(self):
        for page in ("index.html", "about.html"):
            self.assertNotIn("specialising in AI", self.html(page),
                             "%s still narrows the practice to AI" % page)


if __name__ == "__main__":
    unittest.main(verbosity=2)
