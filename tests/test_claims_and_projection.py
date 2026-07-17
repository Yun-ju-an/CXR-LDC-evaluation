import unittest

from _support import clone_config, load_config

from cxr_ldc_eval.longitudinal_claims import LongitudinalClaimExtractor
from cxr_ldc_eval.longitudinal_projection import (
    detect_question_type,
    is_location_conditioned_difference_question,
    project_claims_for_question,
)


class ClaimExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        cls.extractor = LongitudinalClaimExtractor(cls.config)

    def test_new_negation_does_not_emit_new(self):
        parsed = self.extractor.extract("No new pleural effusion is identified.")

        self.assertTrue(parsed["claims"])
        self.assertFalse(
            any(claim["presence_transition"] == "NEW" for claim in parsed["claims"])
        )

    def test_partially_resolved_is_improved_not_resolved(self):
        parsed = self.extractor.extract("The pleural effusion is partially resolved.")

        self.assertEqual(len(parsed["claims"]), 1)
        claim = parsed["claims"][0]
        self.assertEqual(claim["entity"], "pleural_effusion")
        self.assertEqual(claim["presence_transition"], "PRESENT_BOTH")
        self.assertEqual(claim["severity_transition"], "IMPROVED")


class QuestionRoutingAndProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        cls.extractor = LongitudinalClaimExtractor(cls.config)

    def test_location_conditioned_what_has_changed_remains_level(self):
        questions = (
            "What has changed in the left lung area?",
            "What has changed in the right lung area?",
            "What has changed in the bibasilar area?",
        )

        for question in questions:
            with self.subTest(question=question):
                self.assertTrue(
                    is_location_conditioned_difference_question(question, self.config)
                )
                self.assertEqual(detect_question_type(question, self.config), "level")

    def test_broad_difference_projects_severity_to_present_both(self):
        question = "What has changed compared to the reference image?"
        parsed = self.extractor.extract(
            "The level of pleural effusion has changed from mild to moderate."
        )

        self.assertEqual(detect_question_type(question, self.config), "difference")
        projected = project_claims_for_question(
            parsed,
            config=self.config,
            question_text=question,
            view="all_31",
        )
        self.assertEqual(projected["primary_axis"], "presence_transition")
        self.assertEqual(
            [(item["entity"], item["value"]) for item in projected["primary_tuples"]],
            [("pleural_effusion", "PRESENT_BOTH")],
        )
        self.assertEqual(projected["severity_tuples"][0]["value"], "WORSENED")

    def test_location_conditioned_question_scores_level_direction(self):
        question = "What has changed in the left lung area?"
        parsed = self.extractor.extract(
            "The level of pleural effusion has changed from mild to moderate."
        )

        projected = project_claims_for_question(
            parsed,
            config=self.config,
            question_text=question,
            view="all_31",
        )
        self.assertEqual(projected["question_type"], "level")
        self.assertEqual(projected["primary_axis"], "severity_transition")
        self.assertEqual(projected["primary_tuples"][0]["value"], "WORSENED")

    def test_change_projection_is_config_driven(self):
        question = "What has changed compared to the reference image?"
        parsed = self.extractor.extract(
            "The level of pleural effusion has changed from mild to moderate."
        )
        modified = clone_config(self.config)
        modified.raw["evaluation_profiles"]["change_presence_f1"]["projection"][
            "PRESENT_BOTH"
        ] = "NEW"

        projected = project_claims_for_question(
            parsed,
            config=modified,
            question_text=question,
            view="all_31",
        )
        self.assertEqual(projected["primary_tuples"][0]["value"], "NEW")


if __name__ == "__main__":
    unittest.main()
