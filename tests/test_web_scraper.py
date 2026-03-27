import unittest

from sales_prospector_mcp.utils.web_scraper import detect_regions


class DetectRegionsTests(unittest.TestCase):
    def test_state_abbreviation_matching_is_case_insensitive(self):
        text = "Portfolio updates in ny and Sc with no uppercase abbreviations"
        regions = detect_regions(text)
        states = {entry["state"] for entry in regions}

        self.assertIn("NY", states)
        self.assertIn("SC", states)

    def test_charleston_disambiguation_supports_both_states(self):
        text = "Pipeline projects in Charleston, WV and Charleston, SC this quarter"
        regions = detect_regions(text)
        states = {entry["state"] for entry in regions}

        self.assertIn("WV", states)
        self.assertIn("SC", states)


if __name__ == "__main__":
    unittest.main()
