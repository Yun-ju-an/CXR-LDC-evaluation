from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Set

from cxr_ldc_eval.longitudinal_config import LongitudinalEvalConfig
from cxr_ldc_eval.longitudinal_matching import compute_matching_stats, safe_f1
from cxr_ldc_eval.longitudinal_projection import is_location_conditioned_difference_question


def compute_longitudinal_metrics(
    records: Sequence[Dict],
    config: LongitudinalEvalConfig,
    view: str,
) -> Dict:
    exact_totals = _empty_match_totals()
    hier_totals = _empty_match_totals()
    entity_totals = _empty_match_totals()
    change_presence_totals = _empty_match_totals()
    level_direction_totals = _empty_match_totals()

    presence_pairs = _configured_contradiction_pairs(config, "presence")
    severity_pairs = _configured_contradiction_pairs(config, "severity")
    direction_total = 0
    direction_correct = 0
    presence_contradictions = 0
    presence_contradiction_denominator = 0
    severity_contradictions = 0
    severity_contradiction_denominator = 0
    global_contradictions = 0
    global_contradiction_denominator = 0
    no_change_total = 0
    no_change_correct = 0
    unsupported = 0
    invalid_pred = 0
    invalid_gold = 0
    query_type_counts = defaultdict(int)
    location_conditioned_difference_queries = 0
    location_conditioned_level_queries = 0
    pred_severity_tuple_count = 0
    gold_severity_tuple_count = 0

    per_question_type = defaultdict(lambda: _empty_match_totals())

    for record in records:
        pred_proj = record["pred_projections"][view]
        gold_proj = record["gold_projections"][view]
        if pred_proj.get("not_implemented") or gold_proj.get("not_implemented"):
            unsupported += 1
            continue

        pred_tuples = pred_proj.get("primary_tuples") or []
        gold_tuples = gold_proj.get("primary_tuples") or []
        question_type = gold_proj.get("question_type", "unknown")
        query_type_counts[question_type] += 1
        is_location_conditioned = is_location_conditioned_difference_question(
            record.get("question", ""), config
        )
        if is_location_conditioned:
            location_conditioned_difference_queries += 1
            if question_type == "level":
                location_conditioned_level_queries += 1

        pred_severity_tuple_count += len(pred_proj.get("severity_tuples") or [])
        gold_severity_tuple_count += len(gold_proj.get("severity_tuples") or [])

        exact = compute_matching_stats(pred_tuples, gold_tuples, config, hierarchical=False)
        hier = compute_matching_stats(pred_tuples, gold_tuples, config, hierarchical=True)
        entity = compute_matching_stats(
            pred_proj.get("entity_tuples") or [],
            gold_proj.get("entity_tuples") or [],
            config,
            hierarchical=False,
        )

        _add_match_totals(exact_totals, exact)
        _add_match_totals(hier_totals, hier)
        _add_match_totals(entity_totals, entity)
        _add_match_totals(per_question_type[question_type], exact)

        if gold_proj.get("primary_axis") == "presence_transition":
            _add_match_totals(change_presence_totals, exact)
        if gold_proj.get("primary_axis") == "severity_transition":
            _add_match_totals(level_direction_totals, exact)

        d_total, d_correct = _direction_counts(pred_tuples, gold_tuples)
        direction_total += d_total
        direction_correct += d_correct

        if gold_proj.get("primary_axis") == "presence_transition":
            p_num, p_den = _presence_contradiction_counts(
                pred_tuples,
                gold_tuples,
                presence_pairs,
            )
            presence_contradictions += p_num
            presence_contradiction_denominator += p_den

        s_num, s_den = _severity_contradiction_counts(
            pred_proj.get("severity_tuples") or [],
            gold_proj.get("severity_tuples") or [],
            severity_pairs,
        )
        severity_contradictions += s_num
        severity_contradiction_denominator += s_den

        g_num, g_den = _global_contradiction_counts(
            pred_tuples,
            gold_tuples,
            pred_proj.get("global_no_change", False),
            gold_proj.get("global_no_change", False),
            config,
        )
        global_contradictions += g_num
        global_contradiction_denominator += g_den

        if gold_proj.get("global_no_change", False):
            no_change_total += 1
            if len(pred_tuples) == 0:
                no_change_correct += 1

        if record.get("pred_parsed", {}).get("invalid"):
            invalid_pred += 1
        if record.get("gold_parsed", {}).get("invalid"):
            invalid_gold += 1

    exact_summary = _summarize_match_totals(exact_totals)
    hier_summary = _summarize_match_totals(hier_totals)
    entity_summary = _summarize_match_totals(entity_totals)
    change_presence = _summarize_match_totals(change_presence_totals)
    level_direction = _summarize_match_totals(level_direction_totals)

    hallucinated_rate = _safe_div(exact_totals["fp"], exact_totals["pred_count"])
    omission_rate = _safe_div(exact_totals["fn"], exact_totals["gold_count"])
    direction_accuracy = _safe_div(direction_correct, direction_total)
    no_change_acc = _safe_div(no_change_correct, no_change_total)

    return {
        "view": view,
        "samples": len(records),
        "unsupported_samples": unsupported,
        "Ontology Entity F1": entity_summary["f1"],
        "Change-Presence F1": change_presence["f1"],
        "Level-Direction F1": level_direction["f1"],
        "Exact LDC-F1": exact_summary["f1"],
        "Ontology Change F1": exact_summary["f1"],
        "Hierarchical LDC-F1": hier_summary["f1"],
        "Direction Accuracy": direction_accuracy,
        "Hallucinated Disease-Change Rate": hallucinated_rate,
        "Omission Rate": omission_rate,
        "Presence Contradiction Rate": _safe_div(
            presence_contradictions,
            presence_contradiction_denominator,
        ),
        "Explicit Severity Contradiction Rate": _safe_div(
            severity_contradictions,
            severity_contradiction_denominator,
        ),
        "Global No-Change Contradiction Rate": _safe_div(
            global_contradictions,
            global_contradiction_denominator,
        ),
        "NoChange-Acc": no_change_acc,
        "exact_counts": exact_summary,
        "hierarchical_counts": hier_summary,
        "entity_counts": entity_summary,
        "change_presence_counts": change_presence,
        "level_direction_counts": level_direction,
        "diagnostics": {
            "query_type_counts": {k: int(v) for k, v in sorted(query_type_counts.items())},
            "broad_difference_queries": int(query_type_counts.get("difference", 0)),
            "level_queries": int(query_type_counts.get("level", 0)),
            "explicit_level_queries": int(query_type_counts.get("level", 0) - location_conditioned_level_queries),
            "location_conditioned_difference_queries": int(location_conditioned_difference_queries),
            "location_conditioned_level_queries": int(location_conditioned_level_queries),
            "primary_pred_claims": int(exact_totals["pred_count"]),
            "primary_gold_claims": int(exact_totals["gold_count"]),
            "gold_presence_claims": int(change_presence_totals["gold_count"]),
            "pred_presence_claims": int(change_presence_totals["pred_count"]),
            "gold_level_claims": int(level_direction_totals["gold_count"]),
            "pred_level_claims": int(level_direction_totals["pred_count"]),
            "gold_severity_tuples": int(gold_severity_tuple_count),
            "pred_severity_tuples": int(pred_severity_tuple_count),
            "direction_total": direction_total,
            "direction_correct": direction_correct,
            "presence_contradictions": presence_contradictions,
            "presence_contradiction_denominator": presence_contradiction_denominator,
            "global_contradictions": global_contradictions,
            "global_contradiction_denominator": global_contradiction_denominator,
            "severity_contradictions": severity_contradictions,
            "severity_contradiction_denominator": severity_contradiction_denominator,
            "no_change_total": no_change_total,
            "no_change_correct": no_change_correct,
            "pred_invalid": invalid_pred,
            "gold_invalid": invalid_gold,
        },
        "per_question_type_exact": {
            qtype: _summarize_match_totals(totals)
            for qtype, totals in sorted(per_question_type.items())
        },
    }


def compute_all_view_metrics(records: Sequence[Dict], config: LongitudinalEvalConfig) -> Dict:
    return {
        "cxr_primary": compute_longitudinal_metrics(records, config, "cxr_primary"),
        "all_31_auxiliary": compute_longitudinal_metrics(records, config, "all_31"),
        "chexpert_projected": compute_longitudinal_metrics(records, config, "chexpert_projected"),
    }


def _empty_match_totals() -> Dict[str, float]:
    return {
        "tp": 0.0,
        "fp": 0.0,
        "fn": 0.0,
        "pred_count": 0.0,
        "gold_count": 0.0,
    }


def _add_match_totals(totals: Dict[str, float], stats: Dict):
    for key in ("tp", "fp", "fn", "pred_count", "gold_count"):
        totals[key] += float(stats.get(key, 0.0))


def _summarize_match_totals(totals: Dict[str, float]) -> Dict:
    pred_count = totals["pred_count"]
    gold_count = totals["gold_count"]
    tp = totals["tp"]
    return {
        "tp": tp,
        "fp": totals["fp"],
        "fn": totals["fn"],
        "pred_count": pred_count,
        "gold_count": gold_count,
        "precision": _safe_div(tp, pred_count),
        "recall": _safe_div(tp, gold_count),
        "f1": None if pred_count + gold_count == 0 else safe_f1(tp, pred_count, gold_count),
    }


def _entity_values(items: Iterable[Dict]) -> Dict[str, Set[str]]:
    out: Dict[str, Set[str]] = defaultdict(set)
    for item in items:
        entity = item.get("entity")
        value = item.get("value")
        if entity and value:
            out[entity].add(value)
    return out


def _direction_counts(pred_tuples: Sequence[Dict], gold_tuples: Sequence[Dict]) -> tuple:
    pred = _entity_values(pred_tuples)
    gold = _entity_values(gold_tuples)
    total = 0
    correct = 0
    for entity in sorted(set(pred) & set(gold)):
        total += 1
        if pred[entity] & gold[entity]:
            correct += 1
    return total, correct


def _configured_contradiction_pairs(
    config: LongitudinalEvalConfig,
    axis: str,
) -> Set[tuple]:
    raw_pairs = config.matching_policy.get("hard_contradictions", {}).get(axis, [])
    pairs: Set[tuple] = set()
    for pair in raw_pairs:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError(f"matching_policy.hard_contradictions.{axis} requires pairs")
        left, right = map(str, pair)
        pairs.add((left, right))
        pairs.add((right, left))
    return pairs


def _global_contradiction_counts(
    pred_tuples: Sequence[Dict],
    gold_tuples: Sequence[Dict],
    pred_global_no_change: bool,
    gold_global_no_change: bool,
    config: LongitudinalEvalConfig,
) -> tuple:
    policy = (
        config.matching_policy.get("hard_contradictions", {}).get("global") or {}
    )
    if not isinstance(policy, dict):
        raise ValueError("matching_policy.hard_contradictions.global must be an object")
    if policy.get("denominator") != "gold_global_or_nonempty_primary":
        raise ValueError(
            "unsupported global contradiction denominator policy: "
            f"{policy.get('denominator')!r}"
        )
    gold_nonempty = len(gold_tuples) > 0
    eligible = bool(gold_global_no_change or gold_nonempty)
    contradicted = (
        bool(policy.get("gold_global_vs_pred_nonempty"))
        and bool(gold_global_no_change)
        and len(pred_tuples) > 0
    ) or (
        bool(policy.get("gold_nonempty_vs_pred_global"))
        and gold_nonempty
        and bool(pred_global_no_change)
    )
    return int(eligible and contradicted), int(eligible)


def _presence_contradiction_counts(
    pred_tuples: Sequence[Dict],
    gold_tuples: Sequence[Dict],
    contradictions: Set[tuple],
) -> tuple:
    pred = _entity_values(pred_tuples)
    gold = _entity_values(gold_tuples)
    total = 0
    contrad = 0
    for entity in sorted(set(pred) & set(gold)):
        pairs = {(p, g) for p in pred[entity] for g in gold[entity]}
        if any(pair in contradictions for pair in pairs):
            contrad += 1
        total += 1
    return contrad, total


def _severity_contradiction_counts(
    pred_tuples: Sequence[Dict],
    gold_tuples: Sequence[Dict],
    contradictions: Set[tuple],
) -> tuple:
    pred = _entity_values(pred_tuples)
    gold = _entity_values(gold_tuples)
    total = 0
    contrad = 0
    for entity in sorted(set(pred) & set(gold)):
        pairs = {(p, g) for p in pred[entity] for g in gold[entity]}
        if any(pair in contradictions for pair in pairs):
            contrad += 1
        total += 1
    return contrad, total


def _safe_div(num: float, denom: float) -> Optional[float]:
    return None if denom == 0 else float(num) / float(denom)
