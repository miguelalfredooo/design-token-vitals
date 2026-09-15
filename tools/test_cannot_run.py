"""Exit 2 means COULD NOT RUN, and examining nothing is a 2.

Every one of these cases was DRIVEN before it was fixed, and every one returned
the wrong code:

    check_voice.py                  ->  "voice: clean (0 file(s))", exit 0
    check_voice.py /nope/missing.md ->  traceback, exit 1
    palette.py <no colour pairs>    ->  "clears 4.5:1 in every theme", exit 0
    palette.py /nope/x.html         ->  traceback, exit 1

The two zeros are the dangerous pair: a clean verdict over a file nobody read.
The two ones are the quieter defect — an uncaught raise exits 1, which is the
same code as "found problems", so a missing file reads as a finding.

0 clean . 1 findings . 2 could not run.
"""

import os
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)


def run(tool, *args):
    proc = subprocess.run(
        [sys.executable, os.path.join(TOOLS, tool), *args],
        capture_output=True, text=True, cwd=ROOT,
    )
    return proc.returncode, proc.stdout + proc.stderr


class CannotRunIsTwo(unittest.TestCase):
    def test_check_voice_with_no_files_does_not_report_clean(self):
        code, out = run("check_voice.py")
        self.assertEqual(code, 2, out)
        # The old bug printed a verdict. A cannot-run must not.
        self.assertNotIn("clean", out)

    def test_check_voice_with_a_missing_file(self):
        code, out = run("check_voice.py", "/nope/missing.md")
        self.assertEqual(code, 2, out)
        self.assertIn("could not run", out)

    def test_palette_with_a_missing_file(self):
        code, out = run("palette.py", "/nope/x.html")
        self.assertEqual(code, 2, out)
        self.assertIn("could not run", out)

    def test_palette_on_a_document_with_no_pairs(self):
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as fh:
            fh.write("<p>no colours here</p>\n")
            path = fh.name
        try:
            code, out = run("palette.py", path)
            self.assertEqual(code, 2, out)
            # The old bug claimed every theme cleared AA on this file.
            self.assertNotIn("clears", out)
        finally:
            os.unlink(path)


class TheHappyPathStillPasses(unittest.TestCase):
    """A gate that fires on correct input is the same defect facing the other
    way, so the real inputs are asserted beside the broken ones."""

    def test_check_voice_on_real_files(self):
        code, out = run("check_voice.py", "SKILL.md", "README.md")
        self.assertEqual(code, 0, out)

    def test_palette_on_its_own_template(self):
        code, out = run("palette.py")
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
