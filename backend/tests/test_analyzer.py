import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from analyzer.main import ComicAnalyzer

class TestComicAnalyzer(unittest.TestCase):

    def setUp(self):
        # We don't need a real database manager for this test
        self.analyzer = ComicAnalyzer(db_manager=None)

    def test_filter_copyright_text(self):
        
        test_cases = [
            {
                "input": "Some text with copyright 2023 Mike Krahulik & Jerry Holkins.",
                "expected": "Some text with ."
            },
            {
                "input": "© 2024 Mike Krahulik & Jerry Holkins",
                "expected": ""
            },
            {
                "input": "© 2024 Mike Krahulik and Jerry Holkins",
                "expected": ""
            },
            {
                "input": "Text with www.penny-arcade.com URL.",
                "expected": "Text with URL."
            },
            {
                "input": "A mix of © 2025 Mike Krahulik & Jerry Holkins and www.penny-arcade.com",
                "expected": "A mix of and"
            },
            {
                "input": "copyright  2023   Mike    Krahulik  &  Jerry   Holkins",
                "expected": ""
            },
            {
                "input": "No copyright here.",
                "expected": "No copyright here."
            },
            {
                "input": "",
                "expected": ""
            }
        ]
        
        for case in test_cases:
            with self.subTest(input=case["input"]):
                cleaned_text = self.analyzer.filter_copyright_text(case["input"])
                self.assertEqual(cleaned_text, case["expected"])

if __name__ == '__main__':
    unittest.main()
