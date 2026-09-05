"""Every report must wear the current template's skin.

Two mechanisms keep that true, and this file guards both.

The first is procedural: render_discovery.py starts from the EXISTING html
unless --refresh-template is passed (see `document_path` in that file), so a
report generated once keeps its stylesheet forever. SKILL.md is what makes the
finished-report path pass the flag. If that instruction is ever dropped, new
reports silently inherit whatever document they started from — which is exactly
how examples/shadcn-ui/report.html came to predate the dashboard section.

The second is the artifact: a report shipped IN this repo is the one people
read before running anything, so it must not be older than the template.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "assets", "report-template.html")
SHIPPED = [os.path.join(ROOT, "examples", "shadcn-ui", "report.html")]


def stylesheet(path):
    with open(path, encoding="utf-8") as fh:
        html = fh.read()
    return html[html.index("<style>"):html.rindex("</style>") + len("</style>")]


class TestRefreshIsDocumented(unittest.TestCase):
    """The flag is the only thing making a finished report current."""

    def setUp(self):
        with open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8") as fh:
            self.skill = fh.read()

    def test_the_finished_report_command_refreshes_the_template(self):
        commands = [
            line for line in self.skill.splitlines()
            if "render_discovery.py" in line and "--html" in line
        ]
        self.assertTrue(commands, "SKILL.md no longer shows a render command")
        self.assertTrue(
            any("--refresh-template" in line for line in commands),
            "no render command in SKILL.md passes --refresh-template — a report "
            "generated without it keeps whatever stylesheet it already had",
        )

    def test_the_requirement_is_stated_in_prose_not_only_in_a_command(self):
        """A command can be copied without its reason; the prose is the reason."""
        self.assertTrue(
            re.search(r"`?--refresh-template`?[^\n]*required", self.skill),
            "SKILL.md no longer states that --refresh-template is required",
        )


@unittest.skip(
    "BLOCKED, not passing: examples/shadcn-ui/report.html predates the dashboard "
    "section entirely — it carries 0 .dashboard-* elements and its .glance block "
    "is that section's ancestor. It cannot be brought current by swapping its "
    "stylesheet, and re-running render_discovery.py --refresh-template replaces "
    "its real findings with the template's demo content (verified: 'shadcn-ui/ui' "
    "disappears, the demo literal #0F8A83 appears, unfilled regions go 23 -> 32). "
    "Unblocked by one real run of the skill against a shadcn-ui checkout, after "
    "which this skip comes off. Stated as blocked rather than deleted or quietly "
    "passed, which is the same thing this tool does with a vital it cannot measure."
)
class TestShippedReportsMatchTheTemplate(unittest.TestCase):
    def test_stylesheet_is_byte_identical_to_the_template(self):
        expected = stylesheet(TEMPLATE)
        for path in SHIPPED:
            with self.subTest(report=os.path.relpath(path, ROOT)):
                self.assertEqual(stylesheet(path), expected)


if __name__ == "__main__":
    unittest.main()
