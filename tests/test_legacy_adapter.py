import tempfile
import unittest
from pathlib import Path

from _support import load_config, write_json

from cxr_ldc_eval.longitudinal_eval import evaluate_longitudinal_from_paths


ANSWER = (
    "The main image has an additional finding of pleural effusion "
    "than the reference image."
)


def prediction(image_id, row_index):
    return {"image_id": image_id, "row_index": row_index, "caption": ANSWER}


def merged_gt(items):
    return {
        "images": [
            {"id": image_id, "row_index": row_index}
            for image_id, row_index in items
        ],
        "annotations": [
            {
                "id": annotation_id,
                "image_id": image_id,
                "row_index": row_index,
                "caption": ANSWER,
            }
            for annotation_id, (image_id, row_index) in enumerate(items, start=1)
        ],
    }


class LegacyAdapterAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        cls.config_path = cls.config.path

    def _evaluate(self, root, predictions, ground_truth):
        root = Path(root)
        pred_path = write_json(root / "predictions.json", predictions)
        gt_path = write_json(root / "ground_truth.json", ground_truth)
        return evaluate_longitudinal_from_paths(
            pred_path=str(pred_path),
            merged_gt_path=str(gt_path),
            config_path=self.config_path,
            output_prefix="legacy",
            output_dir=str(root / "outputs"),
        )

    def test_prediction_and_ground_truth_id_sets_must_match_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "image_id sets must match exactly"):
                self._evaluate(
                    tmp,
                    [prediction(1, 1)],
                    merged_gt([(1, 1), (2, 2)]),
                )

    def test_extra_prediction_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "image_id sets must match exactly"):
                self._evaluate(
                    tmp,
                    [prediction(1, 1), prediction(2, 2)],
                    merged_gt([(1, 1)]),
                )

    def test_row_index_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "row_index mismatch"):
                self._evaluate(
                    tmp,
                    [prediction(1, 2)],
                    merged_gt([(1, 1)]),
                )

    def test_duplicate_prediction_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "duplicate prediction image_id"):
                self._evaluate(
                    tmp,
                    [prediction(1, 1), prediction(1, 1)],
                    merged_gt([(1, 1)]),
                )


if __name__ == "__main__":
    unittest.main()
