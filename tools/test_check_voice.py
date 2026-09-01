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


class TestFencedCodeBlocks(unittest.TestCase):
    def test_banned_word_inside_fence_not_flagged(self):
        findings = check_text("```\nSimply swap the token.\n```")
        self.assertEqual(findings, [])

    def test_british_spelling_inside_fence_not_flagged(self):
        findings = check_text("```\nThe colour token is missing.\n```")
        self.assertEqual(findings, [])

    def test_prose_after_closed_fence_is_still_flagged(self):
        findings = check_text("```\nSimply swap the token.\n```\nThe colour is wrong.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "us-english")
        self.assertEqual(findings[0].line, 4)


class TestUnbalancedFence(unittest.TestCase):
    def test_prose_after_unclosed_fence_is_still_flagged(self):
        findings = check_text("```\nsome code\nThe colour is wrong.")
        us_findings = [f for f in findings if f.rule == "us-english"]
        self.assertEqual(len(us_findings), 1)
        self.assertEqual(us_findings[0].line, 3)

    def test_unclosed_fence_reports_unbalanced_fence_error(self):
        from check_voice import has_errors
        findings = check_text("```\nsome code\nThe colour is wrong.")
        fence_findings = [f for f in findings if f.rule == "unbalanced-fence"]
        self.assertEqual(len(fence_findings), 1)
        self.assertEqual(fence_findings[0].level, "error")
        self.assertEqual(fence_findings[0].line, 1)
        self.assertTrue(has_errors(findings))


class TestInlineCode(unittest.TestCase):
    """An inline code span holds code, and the lint leaves code alone."""

    def test_british_spelling_in_inline_code_is_allowed(self):
        text = "Look for `colour` as a name some codebases use."
        self.assertEqual(check_text(text), [])

    def test_british_spelling_in_prose_still_errors(self):
        text = "Look for the colour tokens."
        self.assertTrue(any(f.rule == "us-english" for f in check_text(text)))

    def test_banned_word_in_inline_code_is_allowed(self):
        text = "The `simply` key is a real config name here."
        self.assertEqual(check_text(text), [])

    def test_banned_word_in_prose_still_errors(self):
        text = "You can simply run it."
        self.assertTrue(any(f.rule == "banned-phrase" for f in check_text(text)))

    def test_prose_after_a_code_span_is_still_checked(self):
        text = "The `--colour-bg` token is not a robust choice."
        rules = {f.rule for f in check_text(text)}
        self.assertIn("banned-phrase", rules)

    def test_line_numbers_survive_stripping(self):
        text = "fine line\nanother fine line\nyou can simply do it"
        findings = check_text(text)
        self.assertEqual([f.line for f in findings], [3])


if __name__ == "__main__":
    unittest.main()
