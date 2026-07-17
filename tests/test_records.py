import json
import tempfile
import unittest
from pathlib import Path

from _support import load_config, write_json

from cxr_ldc_eval.longitudinal_eval import LONGITUDINAL_OUTPUT_TAG
from cxr_ldc_eval.records import evaluate_records, evaluate_records_from_path


BROAD_QUESTION = "What has changed compared to the reference image?"
LOCATION_QUESTION = "What has changed in the left lung area?"
NEW_ANSWER = (
    "The main image has an additional finding of pleural effusion "
    "than the reference image."
)
LEVEL_ANSWER = "The level of pleural effusion has changed from mild to moderate."


def synthetic_records():
    return [
        {
            "id": "broad-1",
            "question": BROAD_QUESTION,
            "prediction": NEW_ANSWER,
            "reference": NEW_ANSWER,
        },
        {
            "id": "level-1",
            "question": LOCATION_QUESTION,
            "prediction": LEVEL_ANSWER,
            "reference": LEVEL_ANSWER,
        },
    ]


class GenericRecordEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        cls.config_path = cls.config.path

    def test_records_end_to_end_writes_reproducible_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = write_json(tmp_path / "synthetic.json", synthetic_records())
            output_dir = tmp_path / "outputs"

            summary = evaluate_records_from_path(
                input_path=str(input_path),
                config_path=self.config_path,
                output_prefix="synthetic",
                output_dir=str(output_dir),
            )

            self.assertEqual(summary["counts"]["samples"], 2)
            all_31 = summary["metrics"]["all_31_auxiliary"]
            self.assertEqual(all_31["Exact LDC-F1"], 1.0)
            self.assertEqual(
                all_31["diagnostics"]["query_type_counts"],
                {"difference": 1, "level": 1},
            )
            self.assertEqual(
                all_31["diagnostics"]["location_conditioned_level_queries"], 1
            )

            expected = {
                f"synthetic_longitudinal_eval_{LONGITUDINAL_OUTPUT_TAG}.json",
                f"synthetic_longitudinal_eval_{LONGITUDINAL_OUTPUT_TAG}.md",
            }
            self.assertEqual({path.name for path in output_dir.iterdir()}, expected)
            self.assertNotIn("claims_json", summary["artifacts"])

            persisted = json.loads(
                (output_dir / summary["artifacts"]["summary_json"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(persisted["artifacts"], summary["artifacts"])
            self.assertEqual(persisted["digests"]["input_sha256"], summary["digests"]["input_sha256"])

    def test_claim_output_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = write_json(tmp_path / "synthetic.json", synthetic_records())
            output_dir = tmp_path / "outputs"

            summary = evaluate_records_from_path(
                input_path=str(input_path),
                config_path=self.config_path,
                output_prefix="with_claims",
                output_dir=str(output_dir),
                write_claims=True,
            )

            claims_name = (
                f"with_claims_longitudinal_claims_{LONGITUDINAL_OUTPUT_TAG}.json"
            )
            self.assertEqual(summary["artifacts"]["claims_json"], claims_name)
            self.assertTrue((output_dir / claims_name).is_file())

    def test_duplicate_record_ids_are_rejected(self):
        records = synthetic_records()
        records[1]["id"] = records[0]["id"]

        with self.assertRaisesRegex(ValueError, "duplicate record id"):
            evaluate_records(records, self.config_path)

    def test_missing_question_is_rejected_by_default(self):
        record = {
            "id": "missing-question",
            "prediction": NEW_ANSWER,
            "reference": NEW_ANSWER,
        }

        with self.assertRaisesRegex(ValueError, "has no question"):
            evaluate_records([record], self.config_path)

    def test_existing_outputs_require_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = write_json(tmp_path / "synthetic.json", synthetic_records())
            output_dir = tmp_path / "outputs"
            kwargs = {
                "input_path": str(input_path),
                "config_path": self.config_path,
                "output_prefix": "collision",
                "output_dir": str(output_dir),
            }
            evaluate_records_from_path(**kwargs)

            with self.assertRaisesRegex(FileExistsError, "refusing to overwrite"):
                evaluate_records_from_path(**kwargs)

            overwritten = evaluate_records_from_path(**kwargs, overwrite=True)
            self.assertEqual(overwritten["counts"]["samples"], 2)


if __name__ == "__main__":
    unittest.main()
