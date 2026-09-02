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
a git checkout it is a deterministic hash of the installed skill contents,
prefixed with `local-`, so changed local code cannot reuse stale provenance.
"""
import hashlib
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


def local_version():
    digest = hashlib.sha256()
    for current, dirs, files in os.walk(ROOT):
        dirs[:] = sorted(name for name in dirs if name not in (".git", "__pycache__"))
        for name in sorted(files):
            if name.endswith((".pyc", ".pyo")):
                continue
            path = os.path.join(current, name)
            relative = os.path.relpath(path, ROOT).replace(os.sep, "/")
            digest.update(relative.encode("utf-8"))
            with open(path, "rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    digest.update(chunk)
    return "local-" + digest.hexdigest()[:12]


def describe():
    commit = git("rev-parse", "--short", "HEAD")
    if not commit:
        return {"version": local_version(), "commit": None, "tag": None, "dirty": None}
    tag = git("describe", "--tags", "--abbrev=0")
    dirty = bool(git("status", "--porcelain"))
    base = tag.lstrip("v") if tag else "0.0.0"
    dirty_suffix = ".dirty.%s" % local_version().split("-", 1)[1] if dirty else ""
    version = "%s+%s%s" % (base, commit, dirty_suffix)
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
