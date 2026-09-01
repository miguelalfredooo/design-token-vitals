"""What every tool here agrees on.

Exit status means the same thing everywhere:

    0  the tool ran and found nothing to report
    1  the tool ran and found something — a failed rule, a regression,
       a grade that differs between two runs
    2  the tool refused to run — bad arguments, or two inputs that cannot
       honestly be compared

Every tool that produces a result accepts --json PATH and writes the same
result it printed, so a pipeline never has to parse terminal output.
"""
import json

EXIT_OK = 0
EXIT_FINDING = 1
EXIT_REFUSED = 2


def add_json_flag(parser):
    parser.add_argument("--json", dest="json_out", metavar="PATH",
                        help="also write the result as JSON to PATH")


def emit_json(path, payload):
    if not path:
        return
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
