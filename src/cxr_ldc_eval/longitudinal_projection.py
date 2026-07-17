from typing import Dict, List, Optional, Set, Tuple

from cxr_ldc_eval.longitudinal_claims import normalize_text
from cxr_ldc_eval.longitudinal_config import LongitudinalEvalConfig




def detect_question_type(question_text: str, config: LongitudinalEvalConfig) -> str:
    question = normalize_text(question_text)
    if not question:
        return "difference"

    location_override = config.question_routing["location_conditioned_difference"]
    if (
        location_override.get("enabled", False)
        and is_location_conditioned_difference_question(question, config)
    ):
        return str(location_override["result_question_type"])

    for qtype in config.question_routing["precedence"]:
        if _matches_question_patterns(question, config, qtype):
            return qtype
    return "difference"


def is_location_conditioned_difference_question(
    question_text: str,
    config: LongitudinalEvalConfig,
) -> bool:
    question = normalize_text(question_text)
    if not question:
        return False
    routing = config.question_routing["location_conditioned_difference"]
    broad_difference = any(
        normalize_text(cue) in question
        for cue in routing["broad_difference_patterns"]
    )
    return broad_difference and any(
        normalize_text(cue) in question for cue in routing["location_cues"]
    )


def _matches_question_patterns(question: str, config: LongitudinalEvalConfig, qtype: str) -> bool:
    info = config.question_types.get(qtype, {})
    for pattern in info.get("patterns") or []:
        if normalize_text(pattern) in question:
            return True
    return False


def _entity_for_view(entity: Optional[str], view: str, config: LongitudinalEvalConfig) -> Optional[str]:
    if entity is None:
        return None
    labels = config.labels_for_view(view)
    if entity not in labels:
        return None
    if view == "chexpert_projected":
        return config.chexpert_projection_for(entity)
    return entity


def _project_change_presence(
    claim: Dict,
    config: LongitudinalEvalConfig,
) -> Optional[str]:
    projection = config.evaluation_profiles["change_presence_f1"]["projection"]
    presence = claim.get("presence_transition")
    severity = claim.get("severity_transition")
    if presence in projection:
        return projection[presence]
    if severity in projection:
        return projection[severity]
    return None


def _make_tuple(entity: str, value: str, axis: str, claim: Dict) -> Dict:
    out = {
        "entity": entity,
        "axis": axis,
        "value": value,
        "presence_transition": claim.get("presence_transition"),
        "severity_transition": claim.get("severity_transition"),
        "source_sentence": claim.get("source_sentence"),
        "claim_id": claim.get("claim_id"),
    }
    if axis == "location":
        location = claim.get("location") or {}
        out["side"] = location.get("side")
        out["region"] = location.get("region")
        out["value"] = f"{location.get('side') or 'unknown'}:{location.get('region') or 'unknown'}"
    return out


def project_claims_for_question(
    parsed: Dict,
    config: LongitudinalEvalConfig,
    question_text: str = "",
    view: str = "all_31",
    question_type: Optional[str] = None,
) -> Dict:
    qtype = question_type or detect_question_type(question_text, config)
    qinfo = config.question_types.get(qtype, {})
    primary_profile = qinfo.get("primary_profile")
    disease_eval = bool(qinfo.get("disease_eval", True))
    labels_in_view = config.labels_for_view(view)

    primary_tuples: List[Dict] = []
    entity_tuples: List[Dict] = []
    severity_tuples: List[Dict] = []
    global_no_change = bool(parsed.get("explicit_global_no_change", False))
    skipped = {
        "outside_view": 0,
        "unsupported_question_type": 0,
        "unprojectable_claim": 0,
    }

    if not disease_eval:
        return {
            "question_type": qtype,
            "view": view,
            "disease_eval": False,
            "primary_axis": "view",
            "primary_tuples": [],
            "entity_tuples": [],
            "severity_tuples": [],
            "global_no_change": global_no_change,
            "not_implemented": False,
            "skipped": skipped,
        }

    if qtype == "type":
        skipped["unsupported_question_type"] = len(parsed.get("claims") or [])
        return {
            "question_type": qtype,
            "view": view,
            "disease_eval": True,
            "primary_axis": "attribute_type",
            "primary_tuples": [],
            "entity_tuples": [],
            "severity_tuples": [],
            "global_no_change": global_no_change,
            "not_implemented": True,
            "skipped": skipped,
        }

    for claim in parsed.get("claims") or []:
        entity = claim.get("entity")
        if entity is None:
            continue
        if entity not in labels_in_view:
            skipped["outside_view"] += 1
            continue
        projected_entity = _entity_for_view(entity, view, config)
        if projected_entity is None:
            skipped["outside_view"] += 1
            continue

        entity_tuples.append(_make_tuple(projected_entity, "ENTITY", "entity", claim))
        severity = claim.get("severity_transition")
        level_values = set(
            config.evaluation_profiles["level_direction_f1"]["scored_values"]
        )
        if severity in level_values:
            severity_tuples.append(_make_tuple(projected_entity, severity, "severity_transition", claim))

        if primary_profile == "change_presence_f1":
            value = _project_change_presence(claim, config)
            if value is None:
                skipped["unprojectable_claim"] += 1
                continue
            primary_tuples.append(_make_tuple(projected_entity, value, "presence_transition", claim))
        elif primary_profile == "level_direction_f1":
            if severity not in level_values:
                skipped["unprojectable_claim"] += 1
                continue
            primary_tuples.append(_make_tuple(projected_entity, severity, "severity_transition", claim))
        elif primary_profile == "current_presence_accuracy":
            current_presence = claim.get("current_presence")
            if current_presence in ("PRESENT", "ABSENT", "UNCERTAIN"):
                primary_tuples.append(_make_tuple(projected_entity, current_presence, "current_presence", claim))
            else:
                skipped["unprojectable_claim"] += 1
        elif primary_profile == "location_f1":
            location = claim.get("location") or {}
            if location.get("side") is None and location.get("region") is None:
                skipped["unprojectable_claim"] += 1
                continue
            primary_tuples.append(_make_tuple(projected_entity, "", "location", claim))
        elif primary_profile == "entity_f1":
            primary_tuples.append(_make_tuple(projected_entity, "ENTITY", "entity", claim))
        else:
            skipped["unsupported_question_type"] += 1

    return {
        "question_type": qtype,
        "view": view,
        "disease_eval": True,
        "primary_axis": _primary_axis(primary_profile, config, qtype),
        "primary_tuples": _dedupe_tuples(primary_tuples),
        "entity_tuples": _dedupe_tuples(entity_tuples),
        "severity_tuples": _dedupe_tuples(severity_tuples),
        "global_no_change": global_no_change,
        "not_implemented": False,
        "skipped": skipped,
    }


def project_all_views(
    parsed: Dict,
    config: LongitudinalEvalConfig,
    question_text: str = "",
    question_type: Optional[str] = None,
) -> Dict:
    return {
        view: project_claims_for_question(
            parsed,
            config=config,
            question_text=question_text,
            view=view,
            question_type=question_type,
        )
        for view in ("cxr_primary", "all_31", "chexpert_projected")
    }


def _primary_axis(
    primary_profile: Optional[str],
    config: LongitudinalEvalConfig,
    question_type: str,
) -> str:
    primary_tuple = (
        config.evaluation_profiles.get(primary_profile or "", {}).get("primary_tuple")
        or []
    )
    if "presence_transition" in primary_tuple:
        return "presence_transition"
    if "severity_transition" in primary_tuple:
        return "severity_transition"
    if "current_presence" in primary_tuple:
        return "current_presence"
    if any(str(field).startswith("location.") for field in primary_tuple):
        return "location"
    if primary_tuple == ["entity"]:
        return "entity"
    if question_type == "view":
        return "view"
    if question_type == "type":
        return "attribute_type"
    return "unknown"


def tuple_key(item: Dict, include_axis: bool = True) -> Tuple:
    axis = item.get("axis")
    if axis == "location":
        key = (item.get("entity"), item.get("side"), item.get("region"))
    elif axis == "entity":
        key = (item.get("entity"),)
    else:
        key = (item.get("entity"), item.get("value"))
    if include_axis:
        return (axis,) + key
    return key


def _dedupe_tuples(items: List[Dict]) -> List[Dict]:
    seen: Set[Tuple] = set()
    out: List[Dict] = []
    for item in items:
        key = tuple_key(item, include_axis=True)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
