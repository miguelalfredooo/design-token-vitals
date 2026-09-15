"""The changelog and the tag must not drift apart.

Every report stamps `provenance.skill_version`, which `tools/version.py` derives
from the nearest git tag. So a report can name a version the changelog has never
heard of, or the changelog can announce one that was never tagged, and nothing
notices. Both have a direction that matters:

  changelog ahead of the tags  ->  a report cites 0.1.0 while the notes claim
                                   0.2.0 shipped. The notes are a promise.
  tag ahead of the changelog   ->  a report cites 0.2.0 and there is nothing to
                                   read about what changed.

The first is always checkable and is the always-on assertion below. The second
is only decidable when HEAD is exactly at a tag, so it is asserted then and
skipped otherwise — and the skip says so rather than passing quietly.
"""

import os
import re
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEADING = re.compile(r"^## (\d+\.\d+\.\d+)", re.M)


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def changelog_versions():
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as fh:
        return HEADING.findall(fh.read())


class ChangelogAndTagsAgree(unittest.TestCase):
    def test_the_changelog_has_versions_to_check(self):
        # Guard the guard: an empty list would make every assertion below
        # vacuously true, which is the shape of a test that stopped testing.
        self.assertTrue(changelog_versions(), "no `## x.y.z` heading found in CHANGELOG.md")

    def test_every_released_changelog_version_has_a_tag(self):
        """The NEWEST entry is exempt: it is the release being prepared, and it
        cannot carry a tag until it has merged. Every entry BELOW it describes
        something that has already shipped, so a missing tag there means the
        notes are describing a release that never happened."""
        tags = set(git("tag", "-l").splitlines())
        if not tags:
            self.skipTest("no tags in this checkout — nothing to compare against")
        versions = changelog_versions()[1:]
        if not versions:
            self.skipTest("only one entry in the changelog, and it is the one in flight")
        for version in versions:
            self.assertIn(
                "v" + version, tags,
                "CHANGELOG announces %s but no tag v%s exists. Either tag it or "
                "the notes are describing a release that never shipped." % (version, version),
            )

    def test_a_tagged_head_is_the_newest_changelog_entry(self):
        exact = git("tag", "--points-at", "HEAD")
        if not exact:
            self.skipTest("HEAD is not exactly at a tag — the two legitimately differ between releases")
        newest = changelog_versions()[0]
        self.assertIn(
            "v" + newest, exact.splitlines(),
            "HEAD is tagged %s but the newest CHANGELOG entry is %s" % (exact, newest),
        )


if __name__ == "__main__":
    unittest.main()
