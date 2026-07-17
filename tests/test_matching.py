import unittest

from _support import load_config, transition_tuple

from cxr_ldc_eval.longitudinal_matching import (
    _max_weight_one_to_one,
    compute_matching_stats,
)


class HungarianMatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()

    def test_global_optimum_beats_row_greedy_assignment(self):
        weights = [
            [10.0, 9.0],
            [9.0, 0.0],
        ]

        pairs = _max_weight_one_to_one(weights)
        score = sum(weights[row][column] for row, column in pairs)

        self.assertEqual(score, 18.0)
        self.assertEqual(set(pairs), {(0, 1), (1, 0)})

    def test_rectangular_matrices_have_unique_one_to_one_assignments(self):
        matrices = (
            [[10.0, 9.0, 0.0], [9.0, 0.0, 7.0]],
            [[10.0, 9.0], [9.0, 0.0], [0.0, 8.0]],
        )

        for weights in matrices:
            with self.subTest(shape=(len(weights), len(weights[0]))):
                pairs = _max_weight_one_to_one(weights)
                self.assertEqual(len({row for row, _ in pairs}), len(pairs))
                self.assertEqual(len({column for _, column in pairs}), len(pairs))
                self.assertEqual(
                    sum(weights[row][column] for row, column in pairs), 18.0
                )

    def test_ragged_matrix_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "rectangular"):
            _max_weight_one_to_one([[1.0, 0.0], [1.0]])

    def test_hierarchical_matching_remains_one_to_one(self):
        predictions = [
            transition_tuple("lung_opacity", "NEW", "presence_transition"),
            transition_tuple("pneumonia", "NEW", "presence_transition"),
        ]
        references = [
            transition_tuple("pneumonia", "NEW", "presence_transition"),
            transition_tuple("consolidation", "NEW", "presence_transition"),
        ]

        stats = compute_matching_stats(
            predictions,
            references,
            self.config,
            hierarchical=True,
        )

        self.assertEqual(len(stats["matched_pairs"]), 2)
        self.assertEqual(
            len({pair["pred_index"] for pair in stats["matched_pairs"]}), 2
        )
        self.assertEqual(
            len({pair["gold_index"] for pair in stats["matched_pairs"]}), 2
        )
        self.assertGreater(stats["score"], 1.0)


if __name__ == "__main__":
    unittest.main()
