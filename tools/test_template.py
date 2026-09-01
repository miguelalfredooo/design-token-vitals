"""The template, held to PRINCIPLES.md.

Principle 3: every section opens by answering what you are looking at,
why it matters, and what to do with it — an eyebrow, a heading, a lede —
before it shows any data. A section that skips that hands the reader a
table with no way in.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "assets", "report-template.html")

SECTION = re.compile(r"<section\b[^>]*>(.*?)</section>", re.S)
EYEBROW = re.compile(r'<div class="eyebrow">([^<]+)</div>')
HEADING = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
LEDE = re.compile(r'<p class="lede"[^>]*>(.*?)</p>', re.S)


def sections():
    with open(TEMPLATE, encoding="utf-8") as fh:
        html = fh.read()
    body = html[html.rindex("</style>"):]
    return SECTION.findall(body)


class TestEverySectionOrients(unittest.TestCase):
    def setUp(self):
        self.sections = sections()
        self.assertGreater(len(self.sections), 10, "the template should have many sections")

    def test_every_section_says_what_you_are_looking_at(self):
        missing = [i for i, s in enumerate(self.sections) if not EYEBROW.search(s)]
        self.assertEqual(missing, [], "sections with no eyebrow (by index)")

    def test_every_section_says_why_it_matters(self):
        missing = [EYEBROW.search(s).group(1) for s in self.sections
                   if EYEBROW.search(s) and not HEADING.search(s)]
        self.assertEqual(missing, [], "sections with no heading")

    def test_every_section_opens_with_a_lede_before_its_data(self):
        """The lede comes before the first table, grid or list in the section."""
        problems = []
        for s in self.sections:
            name = EYEBROW.search(s).group(1) if EYEBROW.search(s) else "?"
            lede = LEDE.search(s)
            if not lede:
                problems.append("%s: no lede" % name)
                continue
            first_data = min([m.start() for m in re.finditer(r"<(table|div class=\"(swatches|ramps|typescale|bars|gleaks|lin|exec|cov|chips)\b|ol|ul)\b", s)] or [len(s)])
            if lede.start() > first_data:
                problems.append("%s: data appears before the lede" % name)
        self.assertEqual(problems, [])

    def test_a_lede_is_a_sentence_and_not_a_label(self):
        """Orientation takes a sentence. A four-word lede is a caption."""
        short = []
        for s in self.sections:
            name = EYEBROW.search(s).group(1) if EYEBROW.search(s) else "?"
            for m in LEDE.finditer(s):
                words = len(re.sub(r"<[^>]+>", "", m.group(1)).split())
                if words < 12:
                    short.append("%s: %d words" % (name, words))
                break
        self.assertEqual(short, [])


if __name__ == "__main__":
    unittest.main()
