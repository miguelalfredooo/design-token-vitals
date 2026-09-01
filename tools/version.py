#!/usr/bin/env python3
"""The skill's own version, for stamping into every report.

    python3 tools/version.py          # e.g. 0.2.0+6f41570
    python3 tools/version.py --json   # {"version": ..., "commit": ..., "tag": ...}

Every report records provenance.skill_version so two runs can be told
apart by which skill produced them, and so trend.py can refuse to compare
across versions that measured differently. The schema required the field
from the start; nothing supplied it until now.

The version is the nearest tag plus the short commit, read from the
skill's own checkout. With no tag yet it is 0.0.0 plus the commit. Outside
a git checkout it is "unknown", and the report says so rather than
guessing.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*args):
    try:
        out = subprocess.run(["git", "-C", ROOT] + list(args),
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return None


def describe():
    commit = git("rev-parse", "--short", "HEAD")
    if not commit:
        return {"version": "unknown", "commit": None, "tag": None, "dirty": None}
    tag = git("describe", "--tags", "--abbrev=0")
    dirty = bool(git("status", "--porcelain"))
    base = tag.lstrip("v") if tag else "0.0.0"
    version = "%s+%s%s" % (base, commit, ".dirty" if dirty else "")
    return {"version": version, "commit": commit, "tag": tag, "dirty": dirty}


def main(argv):
    info = describe()
    if "--json" in argv:
        print(json.dumps(info, sort_keys=True))
    else:
        print(info["version"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
