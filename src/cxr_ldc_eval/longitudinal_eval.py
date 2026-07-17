import csv
import hashlib
import json
import os
from typing import Dict, List, Optional

from cxr_ldc_eval.longitudinal_claims import LongitudinalClaimExtractor
from cxr_ldc_eval.longitudinal_config import load_longitudinal_eval_config
from cxr_ldc_eval.longitudinal_metrics import compute_all_view_metrics
from cxr_ldc_eval.longitudinal_projection import detect_question_type, project_all_views


LONGITUDINAL_EVAL_VERSION = "cxr_longitudinal_eval_v0_1_1"
LONGITUDINAL_OUTPUT_TAG = "v0_1_1"


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _dump_json(data, path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _sha256_file(path: Optional[str]) -> Optional[str]:
    if path in (None, "", "None"):
        return None
    if not os.path.isfile(str(path)):
        raise FileNotFoundError(f"provenance file not found: {path}")
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reported_path(path: Optional[str]) -> Optional[str]:
    if path in (None, "", "None"):
        return None
    return "<provided>"


def _load_generation_manifest(path: Optional[str]) -> Optional[Dict]:
    if path in (None, "", "None"):
        return None
    if not os.path.isfile(path):
        raise FileNotFoundError(f"generation manifest not found: {path}")
    manifest = _load_json(path)
    if not isinstance(manifest, dict):
        raise ValueError("generation manifest must contain a JSON object")
    return manifest


def _load_questions_by_row_index(query_file: Optional[str]) -> Dict[int, str]:
    if query_file in (None, "", "None"):
        return {}
    if not os.path.isfile(str(query_file)):
        raise FileNotFoundError(f"query file not found: {query_file}")
    questions = {}
    with open(query_file, "r", encoding="utf-8", newline="") as f:
        first_line = f.readline()
        f.seek(0)
        if "," in first_line and first_line.startswith("row_index,"):
            reader = csv.DictReader(f)
            raw_rows = []
            for fallback_idx, row in enumerate(reader, start=1):
                question = str(row.get("question", "")).strip()
                if not question:
                    continue
                try:
                    raw_idx = int(row.get("row_index", fallback_idx))
                except Exception:
                    raw_idx = fallback_idx
                raw_rows.append((raw_idx, question))

            # Path CSV files store 0-based source row indices, while merged
            # generation artifacts and prompt caches use the existing TSV
            # convention: row_index starts at 1.
            offset = 1 if raw_rows and min(idx for idx, _ in raw_rows) == 0 else 0
            for raw_idx, question in raw_rows:
                row_index = int(raw_idx) + offset
                if row_index in questions:
                    raise ValueError(
                        f"duplicate query row_index after normalization: {row_index}"
                    )
                questions[row_index] = question
            return questions

        reader = csv.reader(f, delimiter="\t")
        for row_idx, row in enumerate(reader, start=1):
            if len(row) > 3:
                questions[row_idx] = row[3].strip()
    return questions


def _merged_gt_by_image_id(merged_gt_path: str) -> Dict[int, Dict]:
    gt = _load_json(merged_gt_path)
    if not isinstance(gt, dict):
        raise ValueError("merged GT must contain a COCO-style JSON object")

    images_by_id = {}
    for image in gt.get("images", []):
        if "id" not in image:
            continue
        image_id = int(image["id"])
        if image_id in images_by_id:
            raise ValueError(f"duplicate merged GT image id: {image_id}")
        images_by_id[image_id] = image

    out = {}
    for ann in gt.get("annotations", []):
        image_id = int(ann["image_id"])
        if image_id in out:
            raise ValueError(f"duplicate merged GT annotation image_id: {image_id}")
        row_index = ann.get("row_index")
        if row_index is None and image_id in images_by_id:
            row_index = images_by_id[image_id].get("row_index")
        out[image_id] = {
            "caption": ann.get("caption", ""),
            "row_index": None if row_index is None else int(row_index),
        }
    return out


def _preds_by_image_id(pred_path: str) -> Dict[int, Dict]:
    preds = _load_json(pred_path)
    if isinstance(preds, dict) and "results" in preds:
        preds = preds["results"]
    if not isinstance(preds, list):
        raise ValueError(f"prediction file must contain a list or results list: {pred_path}")
    out = {}
    for rec in preds:
        image_id = int(rec["image_id"])
        if image_id in out:
            raise ValueError(f"duplicate prediction image_id: {image_id}")
        out[image_id] = rec
    return out


def evaluate_longitudinal_from_paths(
    pred_path: str,
    merged_gt_path: str,
    config_path: str,
    output_prefix: str,
    output_dir: str = "./eval_results",
    generation_manifest_path: str = None,
    require_questions: bool = True,
    rules_path: str = None,
    mapping_guideline_path: str = None,
    protocol_amendment_path: str = None,
    write_claims: bool = False,
    overwrite: bool = False,
) -> Dict:
    if not os.path.exists(pred_path):
        raise FileNotFoundError(f"prediction file not found: {pred_path}")
    if not output_prefix or os.path.basename(output_prefix) != output_prefix:
        raise ValueError("output_prefix must be a non-empty file-name component")
    if not os.path.exists(merged_gt_path):
        raise FileNotFoundError(f"merged GT file not found: {merged_gt_path}")

    config = load_longitudinal_eval_config(config_path)
    extractor = LongitudinalClaimExtractor(config)
    manifest = _load_generation_manifest(generation_manifest_path)
    query_file = None if manifest is None else manifest.get("query_file")
    if (
        query_file not in (None, "", "None")
        and generation_manifest_path not in (None, "", "None")
        and not os.path.isabs(str(query_file))
    ):
        query_file = os.path.join(
            os.path.dirname(os.path.abspath(generation_manifest_path)),
            str(query_file),
        )
    questions_by_row_index = _load_questions_by_row_index(query_file)

    preds = _preds_by_image_id(pred_path)
    gts = _merged_gt_by_image_id(merged_gt_path)
    extra_predictions = sorted(set(preds) - set(gts))
    missing_predictions = sorted(set(gts) - set(preds))
    if extra_predictions or missing_predictions:
        raise ValueError(
            "prediction and merged GT image_id sets must match exactly: "
            f"extra_predictions={len(extra_predictions)}, "
            f"missing_predictions={len(missing_predictions)}, "
            f"first_extra={extra_predictions[:5]}, "
            f"first_missing={missing_predictions[:5]}"
        )

    records: List[Dict] = []
    claim_dump: List[Dict] = []
    for image_id in sorted(preds):
        pred_caption = str(preds[image_id].get("caption", ""))
        gt_caption = str(gts[image_id].get("caption", ""))
        pred_row_index = preds[image_id].get("row_index")
        gt_row_index = gts[image_id].get("row_index")
        if (
            pred_row_index is not None
            and gt_row_index is not None
            and int(pred_row_index) != int(gt_row_index)
        ):
            raise ValueError(
                f"row_index mismatch for image_id={image_id}: "
                f"prediction={pred_row_index}, merged_gt={gt_row_index}"
            )
        row_index = pred_row_index if pred_row_index is not None else gt_row_index
        row_index = None if row_index is None else int(row_index)
        question = questions_by_row_index.get(row_index, "")
        question_type = detect_question_type(question, config)

        pred_parsed = extractor.extract(pred_caption, question_text=question)
        gold_parsed = extractor.extract(gt_caption, question_text=question)
        pred_projections = project_all_views(pred_parsed, config, question_text=question, question_type=question_type)
        gold_projections = project_all_views(gold_parsed, config, question_text=question, question_type=question_type)

        record = {
            "image_id": image_id,
            "row_index": row_index,
            "question": question,
            "question_type": question_type,
            "pred_answer": pred_caption,
            "gold_answer": gt_caption,
            "pred_parsed": pred_parsed,
            "gold_parsed": gold_parsed,
            "pred_projections": pred_projections,
            "gold_projections": gold_projections,
        }
        records.append(record)
        claim_dump.append(record)

    metrics = compute_all_view_metrics(records, config)
    query_coverage = sum(1 for r in records if r.get("question"))
    if require_questions and query_coverage != len(records):
        raise ValueError(
            "longitudinal paper evaluation requires question text for every sample: "
            f"samples={len(records)}, questions_loaded={query_coverage}, "
            f"questions_missing={len(records) - query_coverage}, query_file={query_file}"
        )
    summary = {
        "versions": {
            "longitudinal_eval": LONGITUDINAL_EVAL_VERSION,
            "config_version": config.version,
            "paper_rules": "difference_vqa_evaluation_rules_20260526",
            "paper_mapping_guideline": "difference_vqa_evaluation_mapping_guideline_v2_20260526",
            "protocol_amendment": "location_conditioned_change_to_level_v0_1_1",
            "extractor": "longitudinal_rule_v0_1_1",
        },
        "paths": {
            "pred_path": _reported_path(pred_path),
            "merged_gt_path": _reported_path(merged_gt_path),
            "config_path": _reported_path(config_path),
            "rules_path": _reported_path(rules_path),
            "mapping_guideline_path": _reported_path(mapping_guideline_path),
            "protocol_amendment_path": _reported_path(protocol_amendment_path),
            "generation_manifest_path": _reported_path(generation_manifest_path),
            "query_file": _reported_path(query_file),
        },
        "digests": {
            "pred_sha256": _sha256_file(pred_path),
            "merged_gt_sha256": _sha256_file(merged_gt_path),
            "config_sha256": _sha256_file(config_path),
            "rules_sha256": _sha256_file(rules_path),
            "mapping_guideline_sha256": _sha256_file(mapping_guideline_path),
            "protocol_amendment_sha256": _sha256_file(protocol_amendment_path),
            "generation_manifest_sha256": _sha256_file(generation_manifest_path),
            "query_file_sha256": _sha256_file(query_file),
        },
        "protocol": {
            "gold_source": "ground_truth_answer_text_from_merged_gt",
            "prediction_source": "generated_answer_text_from_merged_predictions",
            "question_source": "generation_manifest.query_file row_index lookup; missing questions are rejected by default",
            "require_questions": bool(require_questions),
            "primary_metric": "Exact LDC-F1",
            "primary_matching": "exact disease + query-aware primary transition",
            "broad_difference_policy": "severity transitions project to PRESENT_BOTH in primary tuples",
            "level_question_policy": "explicit and configured location-conditioned change questions use severity_transition",
            "chexpert_role": "secondary_projection_metric",
            "external_llm_extraction": False,
        },
        "config_validation_warnings": config.validation_warnings,
        "counts": {
            "samples": len(records),
            "questions_loaded": query_coverage,
            "questions_missing": len(records) - query_coverage,
            "predictions": len(preds),
            "merged_gt_annotations": len(gts),
        },
        "metrics": metrics,
    }

    summary_path = os.path.join(
        output_dir,
        f"{output_prefix}_longitudinal_eval_{LONGITUDINAL_OUTPUT_TAG}.json",
    )
    claims_path = os.path.join(
        output_dir,
        f"{output_prefix}_longitudinal_claims_{LONGITUDINAL_OUTPUT_TAG}.json",
    )
    report_path = os.path.join(
        output_dir,
        f"{output_prefix}_longitudinal_eval_{LONGITUDINAL_OUTPUT_TAG}.md",
    )
    output_paths = [summary_path, report_path]
    if write_claims:
        output_paths.append(claims_path)
    elif os.path.exists(claims_path):
        raise FileExistsError(
            "a stale claims artifact exists for this prefix; remove it explicitly "
            f"before a no-claims run: {claims_path}"
        )
    existing = [path for path in output_paths if os.path.exists(path)]
    if existing and not overwrite:
        raise FileExistsError(
            "refusing to overwrite existing evaluation artifacts: "
            + ", ".join(existing)
        )

    artifacts = {
        "summary_json": os.path.basename(summary_path),
        "summary_md": os.path.basename(report_path),
    }
    if write_claims:
        artifacts["claims_json"] = os.path.basename(claims_path)
    summary["artifacts"] = artifacts
    _dump_json(summary, summary_path)
    if write_claims:
        _dump_json(claim_dump, claims_path)
    _write_markdown_report(summary, report_path)
    return summary


def _write_markdown_report(summary: Dict, path: str):
    lines = [
        f"# CXR Longitudinal Eval Summary ({summary['versions']['longitudinal_eval']})",
        "",
        "## Core Metrics",
    ]
    for view_name, view_metrics in summary["metrics"].items():
        lines.append(f"### {view_name}")
        for key in (
            "Exact LDC-F1",
            "Ontology Entity F1",
            "Direction Accuracy",
            "Change-Presence F1",
            "Level-Direction F1",
            "Hierarchical LDC-F1",
            "Hallucinated Disease-Change Rate",
            "Omission Rate",
            "Presence Contradiction Rate",
            "Explicit Severity Contradiction Rate",
            "Global No-Change Contradiction Rate",
            "NoChange-Acc",
        ):
            lines.append(f"- {key}: {_format_metric_for_report(view_metrics, key)}")
        diagnostics = view_metrics.get("diagnostics", {})
        if diagnostics:
            lines.append("- broad_difference_queries: {}".format(diagnostics.get("broad_difference_queries", 0)))
            lines.append("- level_queries: {}".format(diagnostics.get("level_queries", 0)))
            lines.append("- explicit_level_queries: {}".format(diagnostics.get("explicit_level_queries", 0)))
            lines.append(
                "- location_conditioned_difference_queries: {}".format(
                    diagnostics.get("location_conditioned_difference_queries", 0)
                )
            )
            lines.append(
                "- location_conditioned_level_queries: {}".format(
                    diagnostics.get("location_conditioned_level_queries", 0)
                )
            )
            lines.append("- primary_pred_claims: {}".format(diagnostics.get("primary_pred_claims", 0)))
            lines.append("- primary_gold_claims: {}".format(diagnostics.get("primary_gold_claims", 0)))
            lines.append("- gold_presence_claims: {}".format(diagnostics.get("gold_presence_claims", 0)))
            lines.append("- gold_level_claims: {}".format(diagnostics.get("gold_level_claims", 0)))
            lines.append("- gold_severity_tuples: {}".format(diagnostics.get("gold_severity_tuples", 0)))
            lines.append("- pred_severity_tuples: {}".format(diagnostics.get("pred_severity_tuples", 0)))
            lines.append(
                "- presence_contradiction_denominator: {}".format(
                    diagnostics.get("presence_contradiction_denominator", 0)
                )
            )
            lines.append(
                "- severity_contradiction_denominator: {}".format(
                    diagnostics.get("severity_contradiction_denominator", 0)
                )
            )
            lines.append(
                "- global_contradiction_denominator: {}".format(
                    diagnostics.get("global_contradiction_denominator", 0)
                )
            )
            lines.append("- no_change_total: {}".format(diagnostics.get("no_change_total", 0)))
        lines.append("")

    lines.append("## Protocol")
    for key, value in summary["protocol"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Paths")
    for key, value in summary["paths"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## SHA-256")
    for key, value in summary.get("digests", {}).items():
        lines.append(f"- {key}: {value}")

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _metric_denominator(metrics: Dict, key: str) -> Optional[float]:
    diagnostics = metrics.get("diagnostics", {})
    if key in ("Exact LDC-F1", "Hallucinated Disease-Change Rate", "Omission Rate"):
        counts = metrics.get("exact_counts", {})
        if key == "Hallucinated Disease-Change Rate":
            return counts.get("pred_count", 0)
        if key == "Omission Rate":
            return counts.get("gold_count", 0)
        return float(counts.get("pred_count", 0)) + float(counts.get("gold_count", 0))
    if key == "Hierarchical LDC-F1":
        counts = metrics.get("hierarchical_counts", {})
        return float(counts.get("pred_count", 0)) + float(counts.get("gold_count", 0))
    if key == "Ontology Entity F1":
        counts = metrics.get("entity_counts", {})
        return float(counts.get("pred_count", 0)) + float(counts.get("gold_count", 0))
    if key == "Change-Presence F1":
        counts = metrics.get("change_presence_counts", {})
        return float(counts.get("pred_count", 0)) + float(counts.get("gold_count", 0))
    if key == "Level-Direction F1":
        counts = metrics.get("level_direction_counts", {})
        return float(counts.get("pred_count", 0)) + float(counts.get("gold_count", 0))
    if key == "Direction Accuracy":
        return diagnostics.get("direction_total", 0)
    if key == "Presence Contradiction Rate":
        return diagnostics.get("presence_contradiction_denominator", 0)
    if key == "Explicit Severity Contradiction Rate":
        return diagnostics.get("severity_contradiction_denominator", 0)
    if key == "Global No-Change Contradiction Rate":
        return diagnostics.get("global_contradiction_denominator", 0)
    if key == "NoChange-Acc":
        return diagnostics.get("no_change_total", 0)
    return 1


def _format_metric_for_report(metrics: Dict, key: str) -> str:
    denom = _metric_denominator(metrics, key)
    if denom is not None and float(denom) <= 0:
        return "N/A"
    value = metrics.get(key)
    if isinstance(value, (int, float)):
        return f"{float(value):.4f}"
    return "N/A"


def print_longitudinal_summary(summary: Dict):
    print("=========================================")
    print("[cxr longitudinal ontology eval]")
    print("view\tExact-LDC\tHier-LDC\tEntity\tChangePresence\tLevelDirection\tDA")
    for view_name, metrics in summary["metrics"].items():
        print(
            "\t".join(
                [
                    view_name,
                    _format_metric_for_report(metrics, "Exact LDC-F1"),
                    _format_metric_for_report(metrics, "Hierarchical LDC-F1"),
                    _format_metric_for_report(metrics, "Ontology Entity F1"),
                    _format_metric_for_report(metrics, "Change-Presence F1"),
                    _format_metric_for_report(metrics, "Level-Direction F1"),
                    _format_metric_for_report(metrics, "Direction Accuracy"),
                ]
            )
        )
    print("Artifacts:")
    for key, value in summary.get("artifacts", {}).items():
        print(f"  - {key}: {value}")
