import json
from pathlib import Path
from typing import Dict, List, Sequence

from cxr_ldc_eval.longitudinal_claims import LongitudinalClaimExtractor
from cxr_ldc_eval.longitudinal_config import load_longitudinal_eval_config
from cxr_ldc_eval.longitudinal_eval import (
    LONGITUDINAL_EVAL_VERSION,
    LONGITUDINAL_OUTPUT_TAG,
    _dump_json,
    _reported_path,
    _sha256_file,
    _write_markdown_report,
)
from cxr_ldc_eval.longitudinal_metrics import compute_all_view_metrics
from cxr_ldc_eval.longitudinal_projection import detect_question_type, project_all_views


def load_records(path: str) -> List[Dict]:
    """Load the public record format from JSON or JSONL."""
    input_path = Path(path)
    if not input_path.is_file():
        raise FileNotFoundError(f"record file not found: {input_path}")

    if input_path.suffix.lower() == ".jsonl":
        records = []
        with input_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"invalid JSONL at {input_path}:{line_number}: {exc.msg}"
                    ) from exc
                if not isinstance(item, dict):
                    raise ValueError(
                        f"record at {input_path}:{line_number} must be a JSON object"
                    )
                records.append(item)
        return records

    with input_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        payload = payload.get("records")
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError("JSON input must be a list of objects or an object with a records list")
    return payload


def evaluate_records(
    source_records: Sequence[Dict],
    config_path: str,
    require_questions: bool = True,
) -> Dict:
    """Evaluate normalized public records without dataset- or model-specific adapters."""
    config = load_longitudinal_eval_config(config_path)
    extractor = LongitudinalClaimExtractor(config)
    records: List[Dict] = []
    seen_ids = set()

    for index, source in enumerate(source_records, start=1):
        sample_id = source.get("id", index)
        sample_key = str(sample_id)
        if sample_key in seen_ids:
            raise ValueError(f"duplicate record id: {sample_id!r}")
        seen_ids.add(sample_key)

        missing = [key for key in ("prediction", "reference") if key not in source]
        if missing:
            raise ValueError(f"record {sample_id!r} missing required fields: {missing}")

        question = str(source.get("question", "")).strip()
        if require_questions and not question:
            raise ValueError(
                f"record {sample_id!r} has no question; use allow-missing-questions only "
                "for explicitly documented broad-difference fallback evaluation"
            )
        prediction = str(source.get("prediction", ""))
        reference = str(source.get("reference", ""))
        question_type = detect_question_type(question, config)
        pred_parsed = extractor.extract(prediction, question_text=question)
        gold_parsed = extractor.extract(reference, question_text=question)

        records.append(
            {
                "sample_id": sample_id,
                "row_index": source.get("row_index"),
                "question": question,
                "question_type": question_type,
                "pred_answer": prediction,
                "gold_answer": reference,
                "pred_parsed": pred_parsed,
                "gold_parsed": gold_parsed,
                "pred_projections": project_all_views(
                    pred_parsed,
                    config,
                    question_text=question,
                    question_type=question_type,
                ),
                "gold_projections": project_all_views(
                    gold_parsed,
                    config,
                    question_text=question,
                    question_type=question_type,
                ),
            }
        )

    questions_loaded = sum(1 for record in records if record["question"])
    return {
        "versions": {
            "longitudinal_eval": LONGITUDINAL_EVAL_VERSION,
            "config_version": config.version,
            "paper_rules": "difference_vqa_evaluation_rules_20260526",
            "paper_mapping_guideline": (
                "difference_vqa_evaluation_mapping_guideline_v2_20260526"
            ),
            "protocol_amendment": "location_conditioned_change_to_level_v0_1_1",
            "extractor": "longitudinal_rule_v0_1_1",
            "package": "cxr_ldc_eval_0_1_1",
        },
        "protocol": {
            "gold_source": "reference_answer_text_from_public_records",
            "prediction_source": "prediction_answer_text_from_public_records",
            "question_source": "question field from each public record",
            "require_questions": bool(require_questions),
            "primary_metric": "Exact LDC-F1",
            "primary_matching": "exact disease + query-aware primary transition",
            "broad_difference_policy": (
                "severity transitions project to PRESENT_BOTH in primary tuples"
            ),
            "level_question_policy": (
                "explicit and configured location-conditioned change questions use severity_transition"
            ),
            "chexpert_role": "secondary_projection_metric",
            "external_llm_extraction": False,
        },
        "config_validation_warnings": config.validation_warnings,
        "counts": {
            "samples": len(records),
            "questions_loaded": questions_loaded,
            "questions_missing": len(records) - questions_loaded,
        },
        "metrics": compute_all_view_metrics(records, config),
        "records": records,
    }


def evaluate_records_from_path(
    input_path: str,
    config_path: str,
    output_prefix: str,
    output_dir: str = "./eval_results",
    require_questions: bool = True,
    rules_path: str = None,
    mapping_guideline_path: str = None,
    protocol_amendment_path: str = None,
    write_claims: bool = False,
    overwrite: bool = False,
) -> Dict:
    """Evaluate a JSON/JSONL record file and write summary artifacts."""
    if not output_prefix or Path(output_prefix).name != output_prefix:
        raise ValueError("output_prefix must be a non-empty file-name component")

    summary = evaluate_records(
        load_records(input_path),
        config_path=config_path,
        require_questions=require_questions,
    )
    records = summary.pop("records")
    summary["paths"] = {
        "input_path": _reported_path(input_path),
        "config_path": _reported_path(config_path),
        "rules_path": _reported_path(rules_path),
        "mapping_guideline_path": _reported_path(mapping_guideline_path),
        "protocol_amendment_path": _reported_path(protocol_amendment_path),
    }
    summary["digests"] = {
        "input_sha256": _sha256_file(input_path),
        "config_sha256": _sha256_file(config_path),
        "rules_sha256": _sha256_file(rules_path),
        "mapping_guideline_sha256": _sha256_file(mapping_guideline_path),
        "protocol_amendment_sha256": _sha256_file(protocol_amendment_path),
    }

    destination = Path(output_dir)
    summary_path = destination / (
        f"{output_prefix}_longitudinal_eval_{LONGITUDINAL_OUTPUT_TAG}.json"
    )
    report_path = destination / (
        f"{output_prefix}_longitudinal_eval_{LONGITUDINAL_OUTPUT_TAG}.md"
    )
    claims_path = destination / (
        f"{output_prefix}_longitudinal_claims_{LONGITUDINAL_OUTPUT_TAG}.json"
    )
    output_paths = [summary_path, report_path]
    if write_claims:
        output_paths.append(claims_path)
    elif claims_path.exists():
        raise FileExistsError(
            "a stale claims artifact exists for this prefix; remove it explicitly "
            f"before a no-claims run: {claims_path}"
        )
    existing = [str(path) for path in output_paths if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "refusing to overwrite existing evaluation artifacts: "
            + ", ".join(existing)
        )

    artifacts = {
        "summary_json": summary_path.name,
        "summary_md": report_path.name,
    }
    if write_claims:
        artifacts["claims_json"] = claims_path.name
    summary["artifacts"] = artifacts
    _dump_json(summary, str(summary_path))
    if write_claims:
        _dump_json(records, str(claims_path))
    _write_markdown_report(summary, str(report_path))
    return summary
