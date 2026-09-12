#!/usr/bin/env python3
"""How far the working tree has moved since the run measured it.

    python3 tools/freshness.py <root> --ref <the ref discovery recorded>

A report with no date on its evidence is trusted for as long as somebody
leaves the tab open, and a token audit goes out of date the next time
anyone touches a stylesheet. Naming the commit the run measured, and the
distance from it, is what turns "these were the numbers" into "these are
the numbers, as of here" — and what makes a reader re-run rather than
believe a month-old figure.

Nothing is claimed where nothing can be checked: outside a checkout, or
for a ref this repository does not have, the state is `unknown` rather
than a guess in either direction.
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import EXIT_OK, add_json_flag, emit_json  # noqa: E402


def git(root, *args):
    try:
        result = subprocess.run(["git", "-C", root] + list(args),
                                check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def measure(root, ref):
    root = os.path.abspath(root)
    if git(root, "rev-parse", "--git-dir") is None:
        return {"ref": ref, "state": "unknown", "commits_since": None,
                "dirty": None,
                "note": "The audited root is not a git checkout, so evidence "
                        "age cannot be established."}
    dirty = bool(git(root, "status", "--porcelain"))
    if not ref:
        return {"ref": None, "state": "unknown", "commits_since": None,
                "dirty": dirty,
                "note": "The run recorded no commit, so its evidence cannot "
                        "be placed in history."}
    if git(root, "rev-parse", "--verify", "--quiet", "%s^{commit}" % ref) is None:
        return {"ref": ref, "state": "unknown", "commits_since": None,
                "dirty": dirty,
                "note": "Commit %s is not in this repository, so the two "
                        "cannot be compared." % ref}
    count = git(root, "rev-list", "--count", "%s..HEAD" % ref)
    behind = int(count) if count and count.isdigit() else 0
    # A dirty tree is never fresh. The edit in it is exactly the change the
    # audit did not see, and it is the likeliest one to matter.
    if behind == 0 and not dirty:
        return {"ref": ref, "state": "fresh", "commits_since": 0,
                "dirty": False,
                "note": "Evidence is fresh against %s." % ref}
    reasons = []
    if behind:
        reasons.append("%d commit(s) since %s" % (behind, ref))
    if dirty:
        reasons.append("uncommitted changes in the working tree")
    return {"ref": ref, "state": "stale", "commits_since": behind,
            "dirty": dirty,
            "note": "Evidence is behind the tree: %s." % " and ".join(reasons)}


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root")
    parser.add_argument("--ref")
    add_json_flag(parser)
    args = parser.parse_args(argv)
    result = measure(args.root, args.ref)
    emit_json(args.json_out, result)
    print("%s — %s" % (result["state"], result["note"]))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
