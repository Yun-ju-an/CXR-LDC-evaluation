import argparse
from pathlib import Path
from typing import Optional, Sequence

from cxr_ldc_eval.longitudinal_config import load_longitudinal_eval_config
from cxr_ldc_eval.longitudinal_eval import (
    evaluate_longitudinal_from_paths,
    print_longitudinal_summary,
)
from cxr_ldc_eval.records import evaluate_records_from_path
from cxr_ldc_eval.resources import (
    default_config_path,
    default_mapping_guideline_path,
    default_protocol_amendment_path,
    default_rules_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ldc-eval",
        description="Config-driven CXR longitudinal disease-change evaluation.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.1")
    subparsers = parser.add_subparsers(dest="command", required=True)

    records = subparsers.add_parser(
        "records",
        help="Evaluate the public JSON/JSONL record format.",
    )
    records.add_argument("--input", required=True, help="JSON or JSONL record file.")
    records.add_argument("--output-dir", default="./eval_results")
    records.add_argument("--output-prefix", default=None)
    records.add_argument("--config-path", default=str(default_config_path()))
    records.add_argument(
        "--allow-missing-questions",
        action="store_true",
        help="Allow missing question text and fall back to the broad difference profile.",
    )
    records.add_argument(
        "--write-claims",
        action="store_true",
        help="Persist per-record source text and extracted claims; review before sharing.",
    )
    records.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace output files with the same names.",
    )

    legacy = subparsers.add_parser(
        "legacy",
        help="Evaluate merged LLaVA/COCO-style prediction and GT artifacts.",
    )
    legacy.add_argument("--pred-path", required=True)
    legacy.add_argument("--merged-gt-path", required=True)
    legacy.add_argument("--output-prefix", required=True)
    legacy.add_argument("--output-dir", default="./eval_results")
    legacy.add_argument("--generation-manifest-path", default=None)
    legacy.add_argument("--config-path", default=str(default_config_path()))
    legacy.add_argument("--allow-missing-questions", action="store_true")
    legacy.add_argument(
        "--write-claims",
        action="store_true",
        help="Persist per-record source text and extracted claims; review before sharing.",
    )
    legacy.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace output files with the same names.",
    )

    validate = subparsers.add_parser(
        "validate-config",
        help="Validate a longitudinal ontology config and print its scope.",
    )
    validate.add_argument("--config-path", default=str(default_config_path()))
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate-config":
        config = load_longitudinal_eval_config(args.config_path)
        print(f"config_version={config.version}")
        print(f"labels={len(config.labels)}")
        for view in ("cxr_primary", "all_31", "chexpert_projected"):
            print(f"{view}_labels={len(config.labels_for_view(view))}")
        print(f"validation_warnings={len(config.validation_warnings)}")
        for warning in config.validation_warnings:
            print(f"warning={warning}")
        return 0

    if args.command == "records":
        output_prefix = args.output_prefix or Path(args.input).stem
        summary = evaluate_records_from_path(
            input_path=args.input,
            config_path=args.config_path,
            output_prefix=output_prefix,
            output_dir=args.output_dir,
            require_questions=not args.allow_missing_questions,
            rules_path=str(default_rules_path()),
            mapping_guideline_path=str(default_mapping_guideline_path()),
            protocol_amendment_path=str(default_protocol_amendment_path()),
            write_claims=args.write_claims,
            overwrite=args.overwrite,
        )
        print_longitudinal_summary(summary)
        return 0

    summary = evaluate_longitudinal_from_paths(
        pred_path=args.pred_path,
        merged_gt_path=args.merged_gt_path,
        config_path=args.config_path,
        output_prefix=args.output_prefix,
        output_dir=args.output_dir,
        generation_manifest_path=args.generation_manifest_path,
        require_questions=not args.allow_missing_questions,
        rules_path=str(default_rules_path()),
        mapping_guideline_path=str(default_mapping_guideline_path()),
        protocol_amendment_path=str(default_protocol_amendment_path()),
        write_claims=args.write_claims,
        overwrite=args.overwrite,
    )
    print_longitudinal_summary(summary)
    return 0
