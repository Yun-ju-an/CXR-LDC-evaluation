import re
from typing import Dict, List, Optional, Sequence, Tuple

from cxr_ldc_eval.longitudinal_config import LongitudinalEvalConfig


PRESENCE_TRANSITIONS = (
    "NEW",
    "RESOLVED",
    "PRESENT_BOTH",
    "ABSENT_BOTH",
    "GLOBAL_NO_CHANGE",
    "UNKNOWN",
    "NOT_APPLICABLE",
)
SEVERITY_TRANSITIONS = (
    "WORSENED",
    "IMPROVED",
    "SAME_LEVEL",
    "LEVEL_CHANGED_UNSPECIFIED",
    "NOT_APPLICABLE",
    "UNKNOWN",
)


def normalize_text(text: str) -> str:
    text = "" if text is None else str(text)
    text = text.lower().replace("\u2019", "'")
    text = re.sub(r"[^a-z0-9\s\.,;:/_-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def _contains_pattern(text: str, pattern: str) -> bool:
    normalized = normalize_text(pattern)
    if not normalized:
        return False
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text) is not None



def _compile_alias_pattern(alias: str) -> re.Pattern:
    escaped = re.escape(normalize_text(alias)).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", flags=re.IGNORECASE)


def _split_sentences(text: str) -> List[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    parts = re.split(r"(?<=[\.;])\s+|\n+", normalized)
    return [p.strip(" .;") for p in parts if p.strip(" .;")]


class LongitudinalClaimExtractor:
    def __init__(self, config: LongitudinalEvalConfig):
        self.config = config
        alias_items = sorted(
            config.alias_to_canonical.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )
        self.alias_patterns = [
            (alias, canonical, _compile_alias_pattern(alias))
            for alias, canonical in alias_items
        ]
        patterns = config.parser_patterns
        self.new_clause_re = re.compile(patterns["new_clause_regex"], flags=re.IGNORECASE)
        self.resolved_clause_re = re.compile(patterns["resolved_clause_regex"], flags=re.IGNORECASE)
        self.level_clause_re = re.compile(patterns["level_clause_regex"], flags=re.IGNORECASE)
        self.global_no_change_re = re.compile(patterns["global_no_change_regex"], flags=re.IGNORECASE)
        self.entity_split_re = re.compile(patterns["entity_list_split_regex"], flags=re.IGNORECASE)

        severity = config.severity_lexicon
        self.severity_replacements = {
            normalize_text(k): normalize_text(v)
            for k, v in (severity.get("normalization_replacements") or {}).items()
        }
        self.ordinal_scale = {
            normalize_text(k): float(v)
            for k, v in (severity.get("ordinal_scale") or {}).items()
        }
        self.direction_keywords = {
            normalize_text(k): str(v)
            for k, v in (severity.get("direction_keywords") or {}).items()
        }

    def extract(self, answer_text: str, question_text: str = "") -> Dict:
        sentences = _split_sentences(answer_text)
        claims: List[Dict] = []
        invalid_reasons: List[str] = []
        global_no_change = False

        for sentence in sentences:
            sentence_claims = self._extract_from_sentence(sentence)
            if len(sentence_claims) == 0 and self._looks_like_change_statement(sentence):
                invalid_reasons.append("no_mappable_claim")
            for claim in sentence_claims:
                if claim["presence_transition"] == "GLOBAL_NO_CHANGE":
                    global_no_change = True
                claims.append(claim)

        claims = self._deduplicate_claims(claims)
        for idx, claim in enumerate(claims):
            claim["claim_id"] = f"c{idx}"

        entity_to_directions: Dict[str, set] = {}
        for claim in claims:
            entity = claim.get("entity")
            if not entity:
                continue
            key = (entity, claim.get("presence_transition"))
            entity_to_directions.setdefault(key, set()).add(claim.get("severity_transition"))
        for (entity, _), directions in entity_to_directions.items():
            explicit = {d for d in directions if d in ("WORSENED", "IMPROVED", "SAME_LEVEL")}
            if len(explicit) > 1:
                invalid_reasons.append(f"self_conflicting_severity:{entity}")

        return {
            "answer_text": "" if answer_text is None else str(answer_text),
            "question_text": "" if question_text is None else str(question_text),
            "normalized_text": normalize_text(answer_text),
            "claims": claims,
            "explicit_global_no_change": global_no_change,
            "invalid": len(invalid_reasons) > 0,
            "invalid_reasons": sorted(set(invalid_reasons)),
            "extractor": "rule_based",
            "extractor_version": "longitudinal_rule_v0_1_1",
        }

    def _extract_from_sentence(self, sentence: str) -> List[Dict]:
        sentence = sentence.strip(" .;")
        if not sentence:
            return []
        if self.global_no_change_re.search(sentence):
            return [self._make_claim(
                entity=None,
                entity_raw=None,
                source_sentence=sentence,
                presence_transition="GLOBAL_NO_CHANGE",
                severity_transition="NOT_APPLICABLE",
                assertion_type="global_change",
                direction_source="explicit_phrase",
            )]

        level_match = self.level_clause_re.search(sentence)
        if level_match:
            entity_matches = self._extract_entities(level_match.group("entity"))
            ref_level = self._normalize_level(level_match.group("reference_level"))
            cur_level = self._normalize_level(level_match.group("current_level"))
            severity_transition, direction_source = self._severity_from_levels(ref_level, cur_level, sentence)
            if not entity_matches:
                return []
            return [
                self._make_claim(
                    entity=match["entity"],
                    entity_raw=match["raw"],
                    source_sentence=sentence,
                    presence_transition="PRESENT_BOTH",
                    severity_transition=severity_transition,
                    assertion_type="comparative_transition",
                    direction_source=direction_source,
                    level={
                        "reference_raw": level_match.group("reference_level").strip(),
                        "current_raw": level_match.group("current_level").strip(),
                        "reference_normalized": ref_level["normalized"],
                        "current_normalized": cur_level["normalized"],
                        "reference_ordinal": ref_level["ordinal"],
                        "current_ordinal": cur_level["ordinal"],
                    },
                )
                for match in entity_matches
            ]

        for regex, transition in (
            (self.new_clause_re, "NEW"),
            (self.resolved_clause_re, "RESOLVED"),
        ):
            m = regex.search(sentence)
            if m:
                entities = self._extract_entity_list(m.group("entities"))
                return [
                    self._make_claim(
                        entity=match["entity"],
                        entity_raw=match["raw"],
                        source_sentence=sentence,
                        presence_transition=transition,
                        severity_transition="NOT_APPLICABLE",
                        assertion_type="comparative_transition",
                        direction_source="explicit_phrase",
                    )
                    for match in entities
                ]

        entities = self._extract_entities(sentence)
        if not entities:
            return []

        presence_transition = self._detect_presence_transition(sentence)
        severity_transition, severity_source = self._detect_severity_transition(sentence)
        direction_source = "explicit_phrase"

        if severity_transition in ("WORSENED", "IMPROVED", "SAME_LEVEL", "LEVEL_CHANGED_UNSPECIFIED"):
            if presence_transition in (None, "UNKNOWN"):
                presence_transition = "PRESENT_BOTH"
            direction_source = severity_source

        if presence_transition is None:
            presence_transition = "UNKNOWN"

        return [
            self._make_claim(
                entity=match["entity"],
                entity_raw=match["raw"],
                source_sentence=sentence,
                presence_transition=presence_transition,
                severity_transition=severity_transition,
                assertion_type="comparative_transition" if presence_transition != "UNKNOWN" else "current_state",
                direction_source=direction_source if presence_transition != "UNKNOWN" else "unknown",
            )
            for match in entities
        ]

    def _extract_entity_list(self, text: str) -> List[Dict]:
        matches: List[Dict] = []
        for part in self.entity_split_re.split(text):
            part_matches = self._extract_entities(part)
            matches.extend(part_matches)
        if not matches:
            matches = self._extract_entities(text)
        return self._dedupe_entity_matches(matches)

    def _extract_entities(self, text: str) -> List[Dict]:
        text_norm = normalize_text(text)
        raw_matches: List[Tuple[int, int, str, str]] = []
        for alias, canonical, pattern in self.alias_patterns:
            for match in pattern.finditer(text_norm):
                raw_matches.append((match.start(), match.end(), canonical, match.group(0)))

        raw_matches.sort(key=lambda item: (item[1] - item[0], -item[0]), reverse=True)
        occupied: List[Tuple[int, int]] = []
        out: List[Dict] = []
        for start, end, canonical, raw in raw_matches:
            if any(not (end <= os_ or start >= oe_) for os_, oe_ in occupied):
                continue
            occupied.append((start, end))
            out.append({"entity": canonical, "raw": raw, "start": start, "end": end})
        out.sort(key=lambda item: item["start"])
        return self._dedupe_entity_matches(out)

    def _dedupe_entity_matches(self, matches: Sequence[Dict]) -> List[Dict]:
        seen = set()
        out = []
        for match in matches:
            entity = match["entity"]
            if entity in seen:
                continue
            seen.add(entity)
            out.append(match)
        return out

    def _detect_presence_transition(self, sentence: str) -> Optional[str]:
        sentence = normalize_text(sentence)
        transitions = self.config.transitions.get("presence_transition", {})
        for name, info in transitions.items():
            if name in ("GLOBAL_NO_CHANGE", "UNKNOWN"):
                continue
            patterns = info.get("positive_patterns") or []
            negative_patterns = info.get("negative_patterns") or []
            if (
                any(_contains_pattern(sentence, pattern) for pattern in patterns)
                and not any(
                    _contains_pattern(sentence, pattern) for pattern in negative_patterns
                )
            ):
                return name
        return None

    def _detect_severity_transition(self, sentence: str) -> Tuple[str, str]:
        sentence_norm = normalize_text(sentence)
        detected = []
        transitions = self.config.transitions.get("severity_transition", {})
        for name, info in transitions.items():
            if name in ("NOT_APPLICABLE", "UNKNOWN"):
                continue
            patterns = info.get("positive_patterns") or []
            if any(_contains_pattern(sentence_norm, pattern) for pattern in patterns):
                detected.append(name)
        for keyword, direction in self.direction_keywords.items():
            if _contains_pattern(sentence_norm, keyword):
                detected.append(direction)
        detected = sorted(set(detected))
        if len(detected) == 1:
            return detected[0], "level_keyword" if detected[0] in ("WORSENED", "IMPROVED") else "explicit_phrase"
        if len(detected) > 1:
            return "UNKNOWN", "unknown"
        return "NOT_APPLICABLE", "unknown"

    def _normalize_level(self, raw_level: str) -> Dict:
        normalized = normalize_text(raw_level)
        for src, dst in sorted(self.severity_replacements.items(), key=lambda item: len(item[0]), reverse=True):
            normalized = normalized.replace(src, dst)
        normalized = normalize_text(normalized).replace(" ", "_")
        ordinal = self.ordinal_scale.get(normalized)
        if ordinal is None:
            values = []
            for key, value in self.ordinal_scale.items():
                pattern = re.compile(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])")
                if pattern.search(normalized):
                    values.append(value)
            ordinal = max(values) if values else None
        return {"normalized": normalized or None, "ordinal": ordinal}

    def _severity_from_levels(self, ref_level: Dict, cur_level: Dict, sentence: str) -> Tuple[str, str]:
        ref = ref_level.get("ordinal")
        cur = cur_level.get("ordinal")
        if ref is not None and cur is not None:
            if cur > ref:
                return "WORSENED", "level_ordinal"
            if cur < ref:
                return "IMPROVED", "level_ordinal"
            return "SAME_LEVEL", "level_ordinal"

        keyword_direction, source = self._detect_severity_transition(sentence)
        if keyword_direction in ("WORSENED", "IMPROVED", "SAME_LEVEL"):
            return keyword_direction, source
        return "LEVEL_CHANGED_UNSPECIFIED", "unknown"

    def _make_claim(
        self,
        entity: Optional[str],
        entity_raw: Optional[str],
        source_sentence: str,
        presence_transition: str,
        severity_transition: str,
        assertion_type: str,
        direction_source: str,
        level: Optional[Dict] = None,
    ) -> Dict:
        if level is None:
            level = {
                "reference_raw": None,
                "current_raw": None,
                "reference_normalized": None,
                "current_normalized": None,
                "reference_ordinal": None,
                "current_ordinal": None,
            }

        current_presence, reference_presence = self._presence_states(presence_transition)
        label_info = self.config.labels.get(entity, {}) if entity is not None else {}
        return {
            "claim_id": "",
            "entity": entity,
            "entity_raw": entity_raw,
            "entity_source": "answer" if entity is not None else None,
            "eval_tier": label_info.get("eval_tier"),
            "presence_transition": presence_transition if presence_transition in PRESENCE_TRANSITIONS else "UNKNOWN",
            "severity_transition": severity_transition if severity_transition in SEVERITY_TRANSITIONS else "UNKNOWN",
            "current_presence": current_presence,
            "reference_presence": reference_presence,
            "level": level,
            "location": self._extract_location(source_sentence),
            "certainty": self._extract_certainty(source_sentence),
            "assertion_type": assertion_type,
            "source_sentence": source_sentence,
            "direction_source": direction_source,
            "extractor": "rule_based",
            "extractor_confidence": 1.0 if entity is not None or presence_transition == "GLOBAL_NO_CHANGE" else 0.0,
            "flags": [],
        }

    def _presence_states(self, transition: str) -> Tuple[str, str]:
        if transition == "NEW":
            return "PRESENT", "ABSENT"
        if transition == "RESOLVED":
            return "ABSENT", "PRESENT"
        if transition == "PRESENT_BOTH":
            return "PRESENT", "PRESENT"
        if transition == "ABSENT_BOTH":
            return "ABSENT", "ABSENT"
        return "UNKNOWN", "UNKNOWN"

    def _extract_certainty(self, sentence: str) -> str:
        text = normalize_text(sentence)
        if any(token in text for token in ("no evidence of", "without", "absent", "not seen")):
            return "negated"
        if any(token in text for token in ("possible", "possibly", "questionable", "may represent")):
            return "possible"
        if any(token in text for token in ("probable", "likely")):
            return "probable"
        return "definite"

    def _extract_location(self, sentence: str) -> Dict:
        text = normalize_text(sentence)
        side = None
        if "bilateral" in text or "both" in text:
            side = "bilateral"
        elif "left" in text:
            side = "left"
        elif "right" in text:
            side = "right"
        region = None
        for candidate in ("upper", "mid", "middle", "lower", "base", "basilar", "apical", "apex", "hilar"):
            if candidate in text:
                region = candidate
                break
        return {
            "raw": None if side is None and region is None else sentence,
            "side": side,
            "region": region,
            "source": None if side is None and region is None else "answer",
        }

    def _deduplicate_claims(self, claims: Sequence[Dict]) -> List[Dict]:
        seen = set()
        out = []
        for claim in claims:
            key = (
                claim.get("entity"),
                claim.get("presence_transition"),
                claim.get("severity_transition"),
                claim.get("source_sentence"),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(claim)
        return out

    def _looks_like_change_statement(self, sentence: str) -> bool:
        text = normalize_text(sentence)
        cues = (
            "changed",
            "change",
            "additional",
            "missing",
            "resolved",
            "new",
            "worse",
            "worsened",
            "improved",
            "increase",
            "decrease",
            "persistent",
            "stable",
        )
        return any(cue in text for cue in cues)


def extract_claims_from_answer(
    answer_text: str,
    config: LongitudinalEvalConfig,
    question_text: str = "",
) -> Dict:
    return LongitudinalClaimExtractor(config).extract(answer_text, question_text=question_text)
