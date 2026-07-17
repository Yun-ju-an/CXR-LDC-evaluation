import tempfile
import unittest
from pathlib import Path

from _support import (
    clone_config,
    load_config,
    metric_record,
    projection,
    transition_tuple,
    write_json,
)

from cxr_ldc_eval.longitudinal_claims import LongitudinalClaimExtractor
from cxr_ldc_eval.longitudinal_eval import (
    LONGITUDINAL_OUTPUT_TAG,
    _format_metric_for_report,
    evaluate_longitudinal_from_paths,
)
from cxr_ldc_eval.longitudinal_metrics import compute_longitudinal_metrics
from cxr_ldc_eval.longitudinal_projection import project_claims_for_question
from cxr_ldc_eval.records import evaluate_records_from_path


QUESTION = "What has changed compared to the reference image?"
NEW_ANSWER = (
    "The main image has an additional finding of pleural effusion "
    "than the reference image."
)
LEVEL_ANSWER = "The level of pleural effusion has changed from mild to moderate."


class ConfigDrivenPrimaryAxisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        cls.extractor = LongitudinalClaimExtractor(cls.config)

    def test_primary_axis_follows_configured_primary_profile(self):
        modified = clone_config(self.config)
        modified.raw["question_types"]["difference"][
            "primary_profile"
        ] = "level_direction_f1"
        parsed = self.extractor.extract(LEVEL_ANSWER, question_text=QUESTION)

        projected = project_claims_for_question(
            parsed,
            config=modified,
            question_text=QUESTION,
            view="all_31",
            question_type="difference",
        )

        self.assertEqual(projected["question_type"], "difference")
        self.assertEqual(projected["primary_axis"], "severity_transition")
        self.assertEqual(projected["primary_tuples"][0]["value"], "WORSENED")


class GlobalNoChangeContradictionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()

    def _projection(self, primary_tuples, global_no_change=False):
        value = projection("difference", "presence_transition", primary_tuples)
        value["global_no_change"] = global_no_change
        return value

    def test_gold_nonempty_predicted_global_no_change_is_contradiction(self):
        gold_tuple = transition_tuple(
            "pleural_effusion", "NEW", "presence_transition"
        )
        record = metric_record(
            self._projection([], global_no_change=True),
            self._projection([gold_tuple]),
        )

        metrics = compute_longitudinal_metrics([record], self.config, "all_31")

        self.assertEqual(metrics["Global No-Change Contradiction Rate"], 1.0)
        self.assertEqual(metrics["diagnostics"]["global_contradictions"], 1)
        self.assertEqual(
            metrics["diagnostics"]["global_contradiction_denominator"], 1
        )

    def test_gold_global_no_change_predicted_nonempty_is_contradiction(self):
        pred_tuple = transition_tuple(
            "pleural_effusion", "NEW", "presence_transition"
        )
        record = metric_record(
            self._projection([pred_tuple]),
            self._projection([], global_no_change=True),
        )

        metrics = compute_longitudinal_metrics([record], self.config, "all_31")

        self.assertEqual(metrics["Global No-Change Contradiction Rate"], 1.0)
        self.assertEqual(metrics["diagnostics"]["global_contradictions"], 1)
        self.assertEqual(
            metrics["diagnostics"]["global_contradiction_denominator"], 1
        )

    def test_zero_global_contradiction_denominator_is_null_and_na(self):
        metrics = compute_longitudinal_metrics([], self.config, "all_31")

        self.assertIsNone(metrics["Global No-Change Contradiction Rate"])
        self.assertEqual(
            _format_metric_for_report(
                metrics,
                "Global No-Change Contradiction Rate",
            ),
            "N/A",
        )


class StaleClaimsArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config_path = load_config().path

    def test_records_no_claims_overwrite_rejects_stale_claims_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = write_json(
                root / "records.json",
                [
                    {
                        "id": "synthetic-record",
                        "question": QUESTION,
                        "prediction": NEW_ANSWER,
                        "reference": NEW_ANSWER,
                    }
                ],
            )
            output_dir = root / "outputs"
            output_dir.mkdir()
            claims_path = (
                output_dir
                / f"stale_longitudinal_claims_{LONGITUDINAL_OUTPUT_TAG}.json"
            )
            claims_path.write_text("synthetic-sensitive-content", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "stale claims artifact"):
                evaluate_records_from_path(
                    input_path=str(input_path),
                    config_path=self.config_path,
                    output_prefix="stale",
                    output_dir=str(output_dir),
                    write_claims=False,
                    overwrite=True,
                )

            self.assertEqual(
                claims_path.read_text(encoding="utf-8"),
                "synthetic-sensitive-content",
            )
            self.assertEqual(list(output_dir.iterdir()), [claims_path])

    def test_legacy_no_claims_overwrite_rejects_stale_claims_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pred_path = write_json(
                root / "predictions.json",
                [{"image_id": 1, "row_index": 1, "caption": NEW_ANSWER}],
            )
            gt_path = write_json(
                root / "ground_truth.json",
                {
                    "images": [{"id": 1, "row_index": 1}],
                    "annotations": [
                        {
                            "id": 1,
                            "image_id": 1,
                            "row_index": 1,
                            "caption": NEW_ANSWER,
                        }
                    ],
                },
            )
            output_dir = root / "outputs"
            output_dir.mkdir()
            claims_path = (
                output_dir
                / f"stale_longitudinal_claims_{LONGITUDINAL_OUTPUT_TAG}.json"
            )
            claims_path.write_text("synthetic-sensitive-content", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "stale claims artifact"):
                evaluate_longitudinal_from_paths(
                    pred_path=str(pred_path),
                    merged_gt_path=str(gt_path),
                    config_path=self.config_path,
                    output_prefix="stale",
                    output_dir=str(output_dir),
                    require_questions=False,
                    write_claims=False,
                    overwrite=True,
                )

            self.assertEqual(
                claims_path.read_text(encoding="utf-8"),
                "synthetic-sensitive-content",
            )
            self.assertEqual(list(output_dir.iterdir()), [claims_path])


if __name__ == "__main__":
    unittest.main()
