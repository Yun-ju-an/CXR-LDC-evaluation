import copy
import json
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PACKAGE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def load_config():
    from cxr_ldc_eval.longitudinal_config import load_longitudinal_eval_config
    from cxr_ldc_eval.resources import default_config_path

    return load_longitudinal_eval_config(str(default_config_path()))


def clone_config(config):
    from cxr_ldc_eval.longitudinal_config import LongitudinalEvalConfig

    return LongitudinalEvalConfig(
        path="synthetic-config.json",
        raw=copy.deepcopy(config.raw),
        validation_warnings=list(config.validation_warnings),
    )


def write_json(path, value):
    path = Path(path)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def transition_tuple(entity, value, axis):
    return {
        "entity": entity,
        "axis": axis,
        "value": value,
        "presence_transition": value if axis == "presence_transition" else "PRESENT_BOTH",
        "severity_transition": value if axis == "severity_transition" else "NOT_APPLICABLE",
        "source_sentence": "synthetic",
        "claim_id": "synthetic",
    }


def projection(question_type, primary_axis, primary_tuples, severity_tuples=None):
    return {
        "question_type": question_type,
        "view": "all_31",
        "disease_eval": True,
        "primary_axis": primary_axis,
        "primary_tuples": list(primary_tuples),
        "entity_tuples": [],
        "severity_tuples": list(severity_tuples or []),
        "global_no_change": False,
        "not_implemented": False,
        "skipped": {},
    }


def metric_record(pred_projection, gold_projection, question="What has changed?"):
    return {
        "question": question,
        "pred_parsed": {"invalid": False},
        "gold_parsed": {"invalid": False},
        "pred_projections": {"all_31": pred_projection},
        "gold_projections": {"all_31": gold_projection},
    }
