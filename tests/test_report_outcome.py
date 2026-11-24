import unittest
from backend.services.report_outcome import outcome_report


class Outcomes(unittest.TestCase):
    def test_limited_corroboration_preserves_direction(self):
        for relation, expected in (
            ("Supports", "LIKELY TRUE"),
            ("Contradicts", "LIKELY FALSE"),
        ):
            report = dict(
                analysis={"kind": "factual"},
                verdict="UNVERIFIABLE",
                findings=[{"assertion": 0, "relation": relation}],
                subclaims=[{"assertion": "Example", "verdict": "UNVERIFIABLE"}],
                summary={},
                validation_failures=[],
            )
            self.assertEqual(outcome_report(report)["verdict"], expected)
            self.assertEqual(report["subclaims"][0]["verdict"], expected)
            self.assertEqual(outcome_report(report)["verdict"], expected)
