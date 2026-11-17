"""One vocabulary, real plurals, and counts that reconcile."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vocab  # noqa: E402


def report(**grades):
    vitals = {name: {"grade": "healthy"} for name in vocab.CHECK_ORDER}
    for name, grade in grades.items():
        vitals[name.replace("_", "-")] = {"grade": grade}
    return {"vitals": vitals}


class TestFiveStates(unittest.TestCase):
    def test_there_are_five_labels_and_no_second_set(self):
        self.assertEqual(
            [vocab.label(grade) for grade in vocab.GRADES],
            ["Healthy", "Watch", "Fix", "Blocked", "Not needed"])

    def test_blocked_is_about_what_we_saw_and_never_about_the_code(self):
        meaning = vocab.GRADE_MEANING["not-visible"]
        self.assertIn("couldn't see", meaning)
        self.assertIn("doesn't mean your code is wrong", meaning)

    def test_an_unknown_grade_reads_as_blocked(self):
        """The conservative direction: we never call something fine by accident."""
        self.assertEqual(vocab.label("mystery"), "Blocked")

    def test_every_check_has_a_name_a_phrase_a_question_and_its_lines(self):
        for table in (vocab.CHECK_NAME, vocab.CHECK_PHRASE, vocab.CHECK_ASKS,
                      vocab.CHECK_LINE):
            self.assertEqual(set(table), set(vocab.CHECK_ORDER))

    def test_no_reader_facing_name_says_vital_mode_or_orphan(self):
        shown = " ".join(list(vocab.CHECK_NAME.values()) +
                         list(vocab.CHECK_PHRASE.values()) +
                         list(vocab.CHECK_ASKS.values())).lower()
        for word in ("vital", "mode", "orphan", "lineage"):
            self.assertNotIn(word, shown)


class TestCountsReconcile(unittest.TestCase):
    def test_the_breakdown_always_sums_to_the_checks(self):
        for doc in (report(), report(leakage="not-visible", orphans="watch"),
                    report(leakage="needs-work", coverage="not-needed"),
                    {"vitals": {}}, report(leakage="something-new")):
            counts = vocab.grade_counts(doc)
            self.assertEqual(sum(counts.values()), len(vocab.CHECK_ORDER))

    def test_a_missing_or_unknown_grade_is_counted_as_blocked(self):
        self.assertEqual(vocab.grade_counts({"vitals": {}})["not-visible"], 8)
        self.assertEqual(
            vocab.grade_counts(report(leakage="something-new"))["not-visible"], 1)

    def test_measured_is_every_check_that_returned_a_reading(self):
        counts = vocab.grade_counts(report(
            leakage="not-visible", orphans="watch", single_source="needs-work"))
        self.assertEqual(vocab.measured(counts), 7)

    def test_the_breakdown_reads_in_the_fixed_order(self):
        counts = vocab.grade_counts(report(
            leakage="not-visible", orphans="watch", single_source="needs-work"))
        self.assertEqual(vocab.breakdown(counts),
                         "5 Healthy · 1 Watch · 1 Fix · 1 Blocked")


class TestNumbersAreSentences(unittest.TestCase):
    def test_a_count_of_one_never_gets_an_s(self):
        self.assertEqual(vocab.plural(1, "check"), "1 check")
        self.assertEqual(vocab.plural(3, "check"), "3 checks")
        self.assertEqual(vocab.plural(0, "check"), "0 checks")
        self.assertEqual(vocab.plural(2, "family", "families"), "2 families")

    def test_thousands_get_a_separator(self):
        self.assertEqual(vocab.plural(1216, "token"), "1,216 tokens")

    def test_a_count_carries_its_denominator_and_its_share(self):
        self.assertEqual(vocab.of(1088, 1216), "1,088 of 1,216 (89%)")
        self.assertEqual(vocab.of(74, 729, "custom properties"),
                         "74 of 729 custom properties (10%)")

    def test_no_share_is_invented_without_a_whole(self):
        self.assertEqual(vocab.of(3, 0), "3 of 0")
        self.assertEqual(vocab.pct(3, 0), "")

    def test_lists_read_as_a_sentence(self):
        self.assertEqual(vocab.join_and(["a"]), "a")
        self.assertEqual(vocab.join_and(["a", "b"]), "a and b")
        self.assertEqual(vocab.join_and(["a", "b", "c"]), "a, b and c")


class TestPlainWords(unittest.TestCase):
    """The net under an audit's own notes, which the renderer did not write."""

    def test_raw_grade_names_become_the_readers_words(self):
        self.assertEqual(vocab.plain("leakage: not-visible"), "leakage: blocked")
        self.assertEqual(vocab.plain("which is needs-work"), "which is fix")

    def test_the_retired_words_do_not_survive(self):
        text = vocab.plain("3 unmeasured vital(s); 2 check(s); blast radius; 4 root(s)")
        for word in ("unmeasured", "vital(s)", "check(s)", "blast radius", "(s)"):
            self.assertNotIn(word, text)

    def test_a_path_is_shown_from_the_top_of_the_repository(self):
        self.assertEqual(
            vocab.plain("see /home/a/app/src/x.css:4", "/home/a/app"),
            "see src/x.css:4")
        self.assertEqual(
            vocab.plain("python3 t.py /home/a/app --json o", "/home/a/app/"),
            "python3 t.py . --json o")

    def test_ordinary_prose_is_left_alone(self):
        text = "Five checks read tokens on every pull request."
        self.assertEqual(vocab.plain(text), text)


if __name__ == "__main__":
    unittest.main()
