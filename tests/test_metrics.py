import unittest

from _support import (
    clone_config,
    load_config,
    metric_record,
    projection,
    transition_tuple,
)

from cxr_ldc_eval.longitudinal_eval import _format_metric_for_report
from cxr_ldc_eval.longitudinal_metrics import compute_longitudinal_metrics


class MetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()

    def test_zero_denominators_are_none_and_reported_as_na(self):
        metrics = compute_longitudinal_metrics([], self.config, "all_31")

        for key in (
            "Exact LDC-F1",
            "Ontology Entity F1",
            "Change-Presence F1",
            "Level-Direction F1",
            "Direction Accuracy",
            "Hallucinated Disease-Change Rate",
            "Omission Rate",
            "Presence Contradiction Rate",
            "Explicit Severity Contradiction Rate",
            "NoChange-Acc",
        ):
            with self.subTest(metric=key):
                self.assertIsNone(metrics[key])
                self.assertEqual(_format_metric_for_report(metrics, key), "N/A")

        self.assertIsNone(metrics["exact_counts"]["precision"])
        self.assertIsNone(metrics["exact_counts"]["recall"])
        self.assertIsNone(metrics["exact_counts"]["f1"])

    def test_presence_contradictions_are_config_driven(self):
        pred_tuple = transition_tuple("pleural_effusion", "NEW", "presence_transition")
        gold_tuple = transition_tuple(
            "pleural_effusion", "PRESENT_BOTH", "presence_transition"
        )
        record = metric_record(
            projection("difference", "presence_transition", [pred_tuple]),
            projection("difference", "presence_transition", [gold_tuple]),
        )

        configured = clone_config(self.config)
        configured.raw["matching_policy"]["hard_contradictions"]["presence"] = [
            ["NEW", "PRESENT_BOTH"]
        ]
        configured_metrics = compute_longitudinal_metrics(
            [record], configured, "all_31"
        )
        self.assertEqual(configured_metrics["Presence Contradiction Rate"], 1.0)

        disabled = clone_config(configured)
        disabled.raw["matching_policy"]["hard_contradictions"]["presence"] = []
        disabled_metrics = compute_longitudinal_metrics([record], disabled, "all_31")
        self.assertEqual(disabled_metrics["Presence Contradiction Rate"], 0.0)

    def test_severity_contradictions_are_config_driven(self):
        primary = transition_tuple(
            "pleural_effusion", "PRESENT_BOTH", "presence_transition"
        )
        pred_severity = transition_tuple(
            "pleural_effusion", "WORSENED", "severity_transition"
        )
        gold_severity = transition_tuple(
            "pleural_effusion", "SAME_LEVEL", "severity_transition"
        )
        record = metric_record(
            projection(
                "difference",
                "presence_transition",
                [primary],
                severity_tuples=[pred_severity],
            ),
            projection(
                "difference",
                "presence_transition",
                [primary],
                severity_tuples=[gold_severity],
            ),
        )

        configured = clone_config(self.config)
        configured.raw["matching_policy"]["hard_contradictions"]["severity"] = [
            ["WORSENED", "SAME_LEVEL"]
        ]
        configured_metrics = compute_longitudinal_metrics(
            [record], configured, "all_31"
        )
        self.assertEqual(
            configured_metrics["Explicit Severity Contradiction Rate"], 1.0
        )

        disabled = clone_config(configured)
        disabled.raw["matching_policy"]["hard_contradictions"]["severity"] = []
        disabled_metrics = compute_longitudinal_metrics([record], disabled, "all_31")
        self.assertEqual(
            disabled_metrics["Explicit Severity Contradiction Rate"], 0.0
        )

    def test_level_questions_do_not_enter_presence_contradiction_denominator(self):
        pred = transition_tuple("pleural_effusion", "WORSENED", "severity_transition")
        gold = transition_tuple("pleural_effusion", "IMPROVED", "severity_transition")
        record = metric_record(
            projection("level", "severity_transition", [pred], severity_tuples=[pred]),
            projection("level", "severity_transition", [gold], severity_tuples=[gold]),
            question="What has changed in the left lung area?",
        )

        metrics = compute_longitudinal_metrics([record], self.config, "all_31")
        self.assertEqual(
            metrics["diagnostics"]["presence_contradiction_denominator"], 0
        )
        self.assertIsNone(metrics["Presence Contradiction Rate"])


if __name__ == "__main__":
    unittest.main()
