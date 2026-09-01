import unittest
from check_voice import check_text


class TestBritishSpelling(unittest.TestCase):
    def test_flags_colour(self):
        findings = check_text("The colour token is missing.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].level, "error")
        self.assertEqual(findings[0].rule, "us-english")
        self.assertIn("color", findings[0].message)

    def test_flags_capitalized_colour(self):
        findings = check_text("Colour matters most.")
        self.assertEqual(len(findings), 1)
        self.assertIn("Color", findings[0].message)

    def test_flags_tokenised(self):
        findings = check_text("7 of 11 categories are tokenised.")
        self.assertEqual(len(findings), 1)
        self.assertIn("tokenized", findings[0].message)

    def test_does_not_flag_css_color_property(self):
        findings = check_text("  color: var(--ink);")
        self.assertEqual(findings, [])

    def test_reports_line_number(self):
        findings = check_text("fine\nfine\nthe colour is wrong")
        self.assertEqual(findings[0].line, 3)


class TestBannedPhrases(unittest.TestCase):
    def test_flags_simply(self):
        findings = check_text("Simply swap the token.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "banned-phrase")

    def test_flags_utilize(self):
        findings = check_text("Utilize the semantic layer.")
        self.assertEqual(findings[0].rule, "banned-phrase")

    def test_does_not_flag_just_as_adjective_context(self):
        findings = check_text("This is the just-in-time path.")
        self.assertEqual(findings, [])


class TestNegativeParallelism(unittest.TestCase):
    def test_warns_on_is_not_a(self):
        findings = check_text("A list of hex codes is not a review.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].level, "warning")
        self.assertEqual(findings[0].rule, "negative-parallelism")

    def test_warning_does_not_fail_the_run(self):
        from check_voice import has_errors
        self.assertFalse(has_errors(check_text("This is not a problem.")))


class TestClean(unittest.TestCase):
    def test_clean_text_returns_nothing(self):
        findings = check_text(
            "Each row is a hardcoded value that one of your tokens already holds."
        )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
