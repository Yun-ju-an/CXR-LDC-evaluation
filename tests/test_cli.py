import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from _support import load_config, write_json

from cxr_ldc_eval.cli import build_parser, main
from cxr_ldc_eval.longitudinal_eval import LONGITUDINAL_OUTPUT_TAG


QUESTION = "What has changed compared to the reference image?"
ANSWER = (
    "The main image has an additional finding of pleural effusion "
    "than the reference image."
)


class CliIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config_path = load_config().path

    def _run_main(self, argv):
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(argv)
        self.assertEqual(result, 0)
        return output.getvalue()

    def _record_input(self, root):
        return write_json(
            Path(root) / "records.json",
            [
                {
                    "id": "synthetic-cli-1",
                    "question": QUESTION,
                    "prediction": ANSWER,
                    "reference": ANSWER,
                }
            ],
        )

    def test_records_cli_does_not_write_claims_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = self._record_input(root)
            output_dir = root / "outputs"

            stdout = self._run_main(
                [
                    "records",
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(output_dir),
                    "--output-prefix",
                    "default",
                    "--config-path",
                    self.config_path,
                ]
            )

            self.assertIn("[cxr longitudinal ontology eval]", stdout)
            self.assertTrue(
                (
                    output_dir
                    / f"default_longitudinal_eval_{LONGITUDINAL_OUTPUT_TAG}.json"
                ).is_file()
            )
            self.assertFalse(
                (
                    output_dir
                    / f"default_longitudinal_claims_{LONGITUDINAL_OUTPUT_TAG}.json"
                ).exists()
            )

    def test_records_cli_write_claims_is_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = self._record_input(root)
            output_dir = root / "outputs"

            self._run_main(
                [
                    "records",
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(output_dir),
                    "--output-prefix",
                    "opt_in",
                    "--config-path",
                    self.config_path,
                    "--write-claims",
                ]
            )

            self.assertTrue(
                (
                    output_dir
                    / f"opt_in_longitudinal_claims_{LONGITUDINAL_OUTPUT_TAG}.json"
                ).is_file()
            )

    def test_legacy_cli_requires_questions_unless_explicitly_allowed(self):
        parser = build_parser()
        required_args = [
            "legacy",
            "--pred-path",
            "predictions.json",
            "--merged-gt-path",
            "ground_truth.json",
            "--output-prefix",
            "legacy",
        ]
        self.assertFalse(parser.parse_args(required_args).allow_missing_questions)
        self.assertTrue(
            parser.parse_args(required_args + ["--allow-missing-questions"])
            .allow_missing_questions
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pred_path = write_json(
                root / "predictions.json",
                [{"image_id": 1, "row_index": 1, "caption": ANSWER}],
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
                            "caption": ANSWER,
                        }
                    ],
                },
            )
            output_dir = root / "outputs"
            command = [
                "legacy",
                "--pred-path",
                str(pred_path),
                "--merged-gt-path",
                str(gt_path),
                "--output-prefix",
                "legacy",
                "--output-dir",
                str(output_dir),
                "--config-path",
                self.config_path,
            ]

            with self.assertRaisesRegex(ValueError, "requires question text"):
                main(command)

            self._run_main(command + ["--allow-missing-questions"])
            summary_path = (
                output_dir
                / f"legacy_longitudinal_eval_{LONGITUDINAL_OUTPUT_TAG}.json"
            )
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["counts"]["questions_missing"], 1)
            self.assertFalse(
                (
                    output_dir
                    / f"legacy_longitudinal_claims_{LONGITUDINAL_OUTPUT_TAG}.json"
                ).exists()
            )

    def test_version_exits_successfully(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as raised:
                main(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(stdout.getvalue().strip(), "ldc-eval 0.1.1")

    def test_validate_config_cli(self):
        stdout = self._run_main(
            ["validate-config", "--config-path", self.config_path]
        )

        self.assertIn("config_version=0.1.1", stdout)
        self.assertIn("labels=31", stdout)
        self.assertIn("all_31_labels=31", stdout)


if __name__ == "__main__":
    unittest.main()
