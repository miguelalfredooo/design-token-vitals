"""The template, held to PRINCIPLES.md.

Principle 3: a chapter says what was found before it shows anything. That is
a number, a name and one line: the line states a finding or a figure, and
how the thing was measured is kept for the Method chapter. A chapter that
opens on a paragraph about itself makes the reader wait for the point.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_discovery  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "assets", "report-template.html")

CHAPTER = re.compile(
    r'<div class="chapter[^"]*" id="([^"]+)" data-chapter="(\d\d)">(.*?)'
    r'(?=\n  <div class="chapter|\n  <footer>)', re.S)
HEAD = re.compile(r'<header class="chapter-head">(.*?)</header>', re.S)
SUB = re.compile(r'<p class="chapter-sub">(.*?)</p>', re.S)


def body():
    with open(TEMPLATE, encoding="utf-8") as fh:
        html = fh.read()
    return html[html.rindex("</style>"):]


def chapters():
    return CHAPTER.findall(body())


def text(fragment):
    return re.sub(r"\s+", " ", re.sub(r"<!--.*?-->|<[^>]+>", " ", fragment,
                                      flags=re.S)).strip()


class TestEveryChapterSaysWhatWasFound(unittest.TestCase):
    def setUp(self):
        self.chapters = chapters()

    def test_the_fourteen_chapters_are_there_in_order(self):
        self.assertEqual(
            [(number, chapter_id) for chapter_id, number, _body in self.chapters],
            [(number, chapter_id)
             for number, chapter_id, _name in render_discovery.CHAPTERS])

    def test_a_chapter_opens_with_its_number_and_its_name(self):
        names = {chapter_id: name
                 for _number, chapter_id, name in render_discovery.CHAPTERS}
        for chapter_id, number, inner in self.chapters:
            with self.subTest(chapter=chapter_id):
                head = HEAD.search(inner)
                self.assertIsNotNone(head, "no chapter head")
                self.assertIn('<span class="chapter-n">%s</span>' % number,
                              head.group(1))
                self.assertIn("<h2>%s</h2>" % names[chapter_id], head.group(1))
                self.assertLess(inner.index("<header"), inner.index("<section"))

    def test_every_chapter_but_the_verdict_has_one_line_under_its_name(self):
        """The verdict's line is its sentence. Every other chapter states a
        figure or a finding in one line, in a region the run fills."""
        for chapter_id, _number, inner in self.chapters:
            if chapter_id == "verdict":
                continue
            with self.subTest(chapter=chapter_id):
                sub = SUB.search(HEAD.search(inner).group(1))
                self.assertIsNotNone(sub, "no one-line subtitle")
                self.assertRegex(sub.group(1), r"<!-- SLOT:sub-[a-z-]+ -->")
                line = text(sub.group(1))
                self.assertTrue(line, "the subtitle is empty")
                self.assertLessEqual(len(line.split()), 16, line)
                self.assertNotIn(". ", line, "one line, not a paragraph: %s" % line)

    def test_no_chapter_carries_an_eyebrow_or_a_lede(self):
        """Both were the old pattern: a label over the heading and a paragraph
        about the section under it, before any evidence."""
        html = body()
        self.assertNotIn('class="eyebrow"', html)
        self.assertNotIn('class="lede"', html)

    def test_sections_are_siblings_and_never_nested(self):
        """The tools find a section from its opening tag to the first closing
        tag, so one section inside another would be cut short."""
        depth = 0
        for tag in re.findall(r"<(/?)section\b", body()):
            depth += -1 if tag else 1
            self.assertIn(depth, (0, 1), "a section is nested inside another")

    def test_every_id_an_older_report_linked_to_still_resolves(self):
        html = body()
        for anchor in render_discovery.ANCHOR_IDS:
            with self.subTest(anchor=anchor):
                self.assertEqual(html.count('id="%s"' % anchor), 1)

    def test_there_is_one_contents_list_and_it_names_every_chapter(self):
        html = body()
        navs = re.findall(r'<nav class="contents"[^>]*>(.*?)</nav>', html, re.S)
        self.assertEqual(len(navs), 1)
        self.assertEqual(
            re.findall(r'href="#([^"]+)"', navs[0]),
            [chapter_id for _number, chapter_id, _name in render_discovery.CHAPTERS])
        for retired in ("report-view-switcher", "contents-more", "All sections",
                        "data-report-view"):
            self.assertNotIn(retired, html)

    def test_the_inventory_and_the_lineage_open_folded(self):
        html = body()
        for section_id in ("inventory", "lineage"):
            with self.subTest(section=section_id):
                section = re.search(
                    r'<section id="%s"[^>]*>(.*?)</section>' % section_id,
                    html, re.S).group(1)
                first = re.search(r"<details\b[^>]*>", section)
                self.assertIsNotNone(first)
                self.assertNotRegex(first.group(0), r"\sopen\b")


if __name__ == "__main__":
    unittest.main()
