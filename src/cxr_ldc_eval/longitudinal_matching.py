from typing import Dict, List, Sequence, Tuple

from cxr_ldc_eval.longitudinal_config import LongitudinalEvalConfig
from cxr_ldc_eval.longitudinal_projection import tuple_key


def safe_f1(precision_num: float, pred_count: float, gold_count: float) -> float:
    denom = pred_count + gold_count
    if denom <= 0:
        return 0.0
    return 2.0 * precision_num / denom


def compute_matching_stats(
    pred_tuples: Sequence[Dict],
    gold_tuples: Sequence[Dict],
    config: LongitudinalEvalConfig,
    hierarchical: bool = False,
) -> Dict:
    pred = list(pred_tuples or [])
    gold = list(gold_tuples or [])
    weights = [
        [
            _tuple_match_weight(p, g, config=config, hierarchical=hierarchical)
            for g in gold
        ]
        for p in pred
    ]
    pairs = _max_weight_one_to_one(weights)
    matched_pairs = []
    score = 0.0
    for pred_idx, gold_idx in pairs:
        weight = weights[pred_idx][gold_idx]
        if weight <= 0:
            continue
        score += weight
        matched_pairs.append(
            {
                "pred_index": pred_idx,
                "gold_index": gold_idx,
                "weight": weight,
                "pred": pred[pred_idx],
                "gold": gold[gold_idx],
            }
        )

    pred_count = float(len(pred))
    gold_count = float(len(gold))
    precision = 0.0 if pred_count == 0 else score / pred_count
    recall = 0.0 if gold_count == 0 else score / gold_count
    return {
        "score": score,
        "tp": score,
        "fp": pred_count - score,
        "fn": gold_count - score,
        "pred_count": len(pred),
        "gold_count": len(gold),
        "precision": precision,
        "recall": recall,
        "f1": safe_f1(score, pred_count, gold_count),
        "matched_pairs": matched_pairs,
    }


def _tuple_match_weight(
    pred: Dict,
    gold: Dict,
    config: LongitudinalEvalConfig,
    hierarchical: bool,
) -> float:
    if pred.get("axis") != gold.get("axis"):
        return 0.0
    if tuple_key(pred, include_axis=True) == tuple_key(gold, include_axis=True):
        return float(config.hierarchy["partial_match_weights"].get("exact_or_synonym", 1.0))
    if not hierarchical:
        return 0.0

    axis = pred.get("axis")
    if axis == "entity":
        pred_value = gold_value = "ENTITY"
    else:
        pred_value = pred.get("value")
        gold_value = gold.get("value")
    if pred_value != gold_value:
        return 0.0

    pred_entity = pred.get("entity")
    gold_entity = gold.get("entity")
    if not pred_entity or not gold_entity:
        return 0.0

    weights = config.hierarchy["partial_match_weights"]

    if _same_chexpert_projection(pred_entity, gold_entity, config):
        return float(weights.get("chexpert_projection_equivalent", 0.8))

    if _is_parent_child(pred_entity, gold_entity, config):
        return float(weights.get("parent_child_same_transition", 0.5))

    if _same_group(pred_entity, gold_entity, config):
        return float(weights.get("same_group_same_transition", 0.25))

    return float(weights.get("unrelated", 0.0))


def _same_chexpert_projection(a: str, b: str, config: LongitudinalEvalConfig) -> bool:
    proj_a = config.chexpert_projection_for(a)
    proj_b = config.chexpert_projection_for(b)
    if proj_a is None or proj_b is None:
        return False
    if proj_a == proj_b:
        return True
    return a in proj_b.split("_or_") or b in proj_a.split("_or_")


def _is_parent_child(a: str, b: str, config: LongitudinalEvalConfig) -> bool:
    parent_child = config.hierarchy.get("parent_child") or {}
    return b in parent_child.get(a, []) or a in parent_child.get(b, [])


def _same_group(a: str, b: str, config: LongitudinalEvalConfig) -> bool:
    group_a = config.label_group(a)
    group_b = config.label_group(b)
    return group_a is not None and group_a == group_b


def _max_weight_one_to_one(weights: List[List[float]]) -> List[Tuple[int, int]]:
    """Return an exact maximum-weight assignment in cubic time."""
    if not weights or not weights[0]:
        return []
    n_pred = len(weights)
    n_gold = len(weights[0])
    if any(len(row) != n_gold for row in weights):
        raise ValueError("matching weight matrix must be rectangular")

    size = max(n_pred, n_gold)
    max_weight = max(max(row) for row in weights)
    costs = [
        [
            max_weight - (weights[i][j] if i < n_pred and j < n_gold else 0.0)
            for j in range(size)
        ]
        for i in range(size)
    ]

    u = [0.0] * (size + 1)
    v = [0.0] * (size + 1)
    assignment_by_column = [0] * (size + 1)
    previous_column = [0] * (size + 1)

    for row in range(1, size + 1):
        assignment_by_column[0] = row
        minimum_slack = [float("inf")] * (size + 1)
        used = [False] * (size + 1)
        column = 0
        while True:
            used[column] = True
            assigned_row = assignment_by_column[column]
            delta = float("inf")
            next_column = 0
            for candidate in range(1, size + 1):
                if used[candidate]:
                    continue
                reduced_cost = (
                    costs[assigned_row - 1][candidate - 1]
                    - u[assigned_row]
                    - v[candidate]
                )
                if reduced_cost < minimum_slack[candidate]:
                    minimum_slack[candidate] = reduced_cost
                    previous_column[candidate] = column
                if minimum_slack[candidate] < delta:
                    delta = minimum_slack[candidate]
                    next_column = candidate
            for candidate in range(size + 1):
                if used[candidate]:
                    u[assignment_by_column[candidate]] += delta
                    v[candidate] -= delta
                else:
                    minimum_slack[candidate] -= delta
            column = next_column
            if assignment_by_column[column] == 0:
                break

        while True:
            previous = previous_column[column]
            assignment_by_column[column] = assignment_by_column[previous]
            column = previous
            if column == 0:
                break

    pairs = []
    for gold_slot in range(1, size + 1):
        pred_slot = assignment_by_column[gold_slot]
        if (
            1 <= pred_slot <= n_pred
            and gold_slot <= n_gold
            and weights[pred_slot - 1][gold_slot - 1] > 0
        ):
            pairs.append((pred_slot - 1, gold_slot - 1))
    return sorted(pairs)
