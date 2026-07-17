import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple


REQUIRED_TOP_LEVEL_KEYS = (
    "metadata",
    "labels",
    "label_sets",
    "alias_to_canonical",
    "hierarchy",
    "transitions",
    "severity_lexicon",
    "question_types",
    "question_routing",
    "claim_schema",
    "parser_patterns",
    "evaluation_profiles",
    "matching_policy",
)


@dataclass
class LongitudinalEvalConfig:
    path: str
    raw: Dict
    validation_warnings: List[str]

    @property
    def version(self) -> str:
        return str(self.raw.get("metadata", {}).get("version", "unknown"))

    @property
    def labels(self) -> Dict:
        return self.raw["labels"]

    @property
    def label_sets(self) -> Dict:
        return self.raw["label_sets"]

    @property
    def alias_to_canonical(self) -> Dict[str, str]:
        return self.raw["alias_to_canonical"]

    @property
    def hierarchy(self) -> Dict:
        return self.raw["hierarchy"]

    @property
    def transitions(self) -> Dict:
        return self.raw["transitions"]

    @property
    def severity_lexicon(self) -> Dict:
        return self.raw["severity_lexicon"]

    @property
    def question_types(self) -> Dict:
        return self.raw["question_types"]

    @property
    def question_routing(self) -> Dict:
        return self.raw["question_routing"]

    @property
    def parser_patterns(self) -> Dict:
        return self.raw["parser_patterns"]

    @property
    def evaluation_profiles(self) -> Dict:
        return self.raw["evaluation_profiles"]

    @property
    def matching_policy(self) -> Dict:
        return self.raw["matching_policy"]

    @property
    def all_label_ids(self) -> Set[str]:
        return set(self.labels.keys())

    @property
    def abstract_hierarchy_nodes(self) -> Set[str]:
        parents = set((self.hierarchy.get("parent_child") or {}).keys())
        return parents - self.all_label_ids

    def labels_for_view(self, view: str) -> Set[str]:
        if view == "all_31":
            return set(self.label_sets.get("all_31", self.labels.keys()))
        if view == "cxr_primary":
            return set(self.label_sets.get("primary_cxr", []))
        if view == "chexpert_projected":
            exact = set(self.label_sets.get("chexpert_compatible_exact", []))
            partial = set(self.label_sets.get("chexpert_compatible_partial", []))
            return {
                label
                for label in (exact | partial)
                if self.labels.get(label, {}).get("chexpert_projection") is not None
            }
        raise ValueError(f"unknown longitudinal ontology view: {view}")

    def chexpert_projection_for(self, label: str) -> Optional[str]:
        value = self.labels.get(label, {}).get("chexpert_projection")
        if value is None:
            return None
        return str(value)

    def label_group(self, label: str) -> Optional[str]:
        value = self.labels.get(label, {}).get("group")
        return None if value is None else str(value)


def _load_json(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_alias(alias: str) -> str:
    return " ".join(str(alias).lower().strip().split())


def _collect_aliases(raw: Dict) -> Tuple[Dict[str, str], List[str]]:
    labels = raw.get("labels", {})
    configured_alias_map = {
        _normalize_alias(alias): str(canonical)
        for alias, canonical in (raw.get("alias_to_canonical") or {}).items()
        if _normalize_alias(alias)
    }

    alias_map: Dict[str, str] = {}
    collisions: List[str] = []
    for canonical, info in labels.items():
        aliases = set(info.get("aliases") or [])
        aliases.add(canonical.replace("_", " "))
        display = info.get("display_name")
        if display:
            aliases.add(display)
        for alias in aliases:
            key = _normalize_alias(alias)
            if not key:
                continue
            if key in alias_map and alias_map[key] != canonical:
                collisions.append(
                    f"alias collision: {key!r} -> {alias_map[key]!r} and {canonical!r}"
                )
            alias_map[key] = str(canonical)

    for alias, canonical in configured_alias_map.items():
        if canonical not in labels:
            collisions.append(
                f"alias_to_canonical maps {alias!r} to unknown label {canonical!r}"
            )
            continue
        if alias in alias_map and alias_map[alias] != canonical:
            collisions.append(
                f"alias_to_canonical overrides {alias!r}: {alias_map[alias]!r} -> {canonical!r}"
            )
        alias_map[alias] = canonical

    return alias_map, collisions


def _validate_config(raw: Dict) -> List[str]:
    missing = [k for k in REQUIRED_TOP_LEVEL_KEYS if k not in raw]
    if missing:
        raise ValueError(f"longitudinal eval config missing top-level keys: {missing}")

    warnings: List[str] = []
    labels = raw["labels"]
    if not isinstance(labels, dict) or len(labels) == 0:
        raise ValueError("longitudinal eval config requires a non-empty labels object")

    for label, info in labels.items():
        if not isinstance(info, dict):
            raise ValueError(f"label definition must be an object: {label}")
        if "aliases" not in info or not isinstance(info["aliases"], list):
            raise ValueError(f"label requires aliases list: {label}")
        if "eval_tier" not in info:
            raise ValueError(f"label requires eval_tier: {label}")
        if "cxr_verifiability" not in info:
            raise ValueError(f"label requires cxr_verifiability: {label}")

    label_ids = set(labels.keys())
    label_sets = raw["label_sets"]
    non_disease_optional = set(label_sets.get("not_disease_but_trackable_optional", []))
    for set_name, members in label_sets.items():
        if not isinstance(members, list):
            raise ValueError(f"label_sets.{set_name} must be a list")
        for member in members:
            if member not in label_ids and member not in non_disease_optional:
                raise ValueError(f"label_sets.{set_name} references unknown label: {member}")

    alias_map, alias_warnings = _collect_aliases(raw)
    warnings.extend(alias_warnings)
    raw["alias_to_canonical"] = alias_map

    transitions = raw["transitions"]
    for key in ("presence_transition", "severity_transition"):
        if key not in transitions or not isinstance(transitions[key], dict):
            raise ValueError(f"transitions.{key} is required")

    question_types = raw["question_types"]
    for qtype, info in question_types.items():
        if "patterns" not in info or "primary_profile" not in info:
            raise ValueError(f"question type requires patterns and primary_profile: {qtype}")
        profile = info["primary_profile"]
        if (
            profile not in raw["evaluation_profiles"]
            and info.get("implemented") is not False
        ):
            warnings.append(
                f"question type {qtype!r} references unsupported profile {profile!r}; "
                "it will be reported as not_implemented unless code support is added"
            )

    routing = raw["question_routing"]
    precedence = routing.get("precedence") or []
    if not isinstance(precedence, list) or not precedence:
        raise ValueError("question_routing.precedence must be a non-empty list")
    for qtype in precedence:
        if qtype not in question_types:
            raise ValueError(
                f"question_routing.precedence references unknown question type: {qtype}"
            )
    location_override = routing.get("location_conditioned_difference") or {}
    override_target = location_override.get("result_question_type")
    if override_target not in question_types:
        raise ValueError(
            "question_routing.location_conditioned_difference.result_question_type "
            f"references unknown question type: {override_target}"
        )
    for key in ("broad_difference_patterns", "location_cues"):
        values = location_override.get(key)
        if not isinstance(values, list) or not values:
            raise ValueError(
                f"question_routing.location_conditioned_difference.{key} "
                "must be a non-empty list"
            )

    hierarchy = raw["hierarchy"]
    parent_child = hierarchy.get("parent_child") or {}
    for parent, children in parent_child.items():
        if not isinstance(children, list):
            raise ValueError(f"hierarchy parent must map to a list: {parent}")
        for child in children:
            if child not in label_ids:
                raise ValueError(f"hierarchy child references unknown label: {parent} -> {child}")

    weights = hierarchy.get("partial_match_weights") or {}
    for required in (
        "exact_or_synonym",
        "chexpert_projection_equivalent",
        "parent_child_same_transition",
        "same_group_same_transition",
        "unrelated",
    ):
        if required not in weights:
            raise ValueError(f"hierarchy.partial_match_weights missing: {required}")
    if float(weights["exact_or_synonym"]) != 1.0:
        raise ValueError("hierarchy.partial_match_weights.exact_or_synonym must equal 1.0")
    for name, value in weights.items():
        numeric = float(value)
        if numeric < 0.0 or numeric > 1.0:
            raise ValueError(
                f"hierarchy.partial_match_weights.{name} must be between 0 and 1"
            )
    if hierarchy.get("one_to_one_matching_required") is not True:
        raise ValueError("hierarchy.one_to_one_matching_required must be true")

    profiles = raw["evaluation_profiles"]
    change_profile = profiles.get("change_presence_f1") or {}
    change_values = set(change_profile.get("scored_values") or [])
    if not change_values:
        raise ValueError("evaluation_profiles.change_presence_f1.scored_values is required")
    for source, target in (change_profile.get("projection") or {}).items():
        if target not in change_values:
            raise ValueError(
                "evaluation_profiles.change_presence_f1.projection maps "
                f"{source!r} to unsupported scored value {target!r}"
            )
    level_values = set(
        (profiles.get("level_direction_f1") or {}).get("scored_values") or []
    )
    if not level_values:
        raise ValueError(
            "evaluation_profiles.level_direction_f1.scored_values is required"
        )

    hard_contradictions = (
        raw["matching_policy"].get("hard_contradictions") or {}
    )
    transition_ids = {
        "presence": set(transitions["presence_transition"]),
        "severity": set(transitions["severity_transition"]),
    }
    for axis, valid_values in transition_ids.items():
        pairs = hard_contradictions.get(axis)
        if not isinstance(pairs, list):
            raise ValueError(
                f"matching_policy.hard_contradictions.{axis} must be a list"
            )
        for pair in pairs:
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError(
                    f"matching_policy.hard_contradictions.{axis} requires pairs"
                )
            unknown = set(map(str, pair)) - valid_values
            if unknown:
                raise ValueError(
                    f"matching_policy.hard_contradictions.{axis} references "
                    f"unknown transitions: {sorted(unknown)}"
                )

    global_policy = hard_contradictions.get("global")
    if not isinstance(global_policy, dict):
        raise ValueError(
            "matching_policy.hard_contradictions.global must be an object"
        )
    if global_policy.get("denominator") != "gold_global_or_nonempty_primary":
        raise ValueError(
            "matching_policy.hard_contradictions.global.denominator is unsupported"
        )
    for key in (
        "gold_global_vs_pred_nonempty",
        "gold_nonempty_vs_pred_global",
    ):
        if not isinstance(global_policy.get(key), bool):
            raise ValueError(
                f"matching_policy.hard_contradictions.global.{key} must be boolean"
            )

    wide = raw.get("chexpert_wide_encoding", {})
    wide_columns = set(wide.get("columns") or [])
    for label, info in labels.items():
        projection = info.get("chexpert_projection")
        if projection is None:
            continue
        projection = str(projection)
        if projection not in wide_columns and "_or_" not in projection:
            warnings.append(
                f"label {label!r} has CheXpert projection {projection!r} outside chexpert_wide_encoding.columns"
            )

    return warnings


def load_longitudinal_eval_config(path: str) -> LongitudinalEvalConfig:
    if path in (None, "", "None"):
        raise ValueError("--longitudinal_config_path is required for longitudinal evaluation")
    if not os.path.exists(path):
        raise FileNotFoundError(f"longitudinal eval config not found: {path}")
    raw = _load_json(path)
    warnings = _validate_config(raw)
    return LongitudinalEvalConfig(path=path, raw=raw, validation_warnings=warnings)
