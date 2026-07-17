from importlib import resources
from pathlib import Path


CONFIG_NAME = "cxr_longitudinal_eval_config_v0_1.json"
RULES_NAME = "difference_vqa_evaluation_rules_20260526.md"
MAPPING_GUIDELINE_NAME = "difference_vqa_evaluation_mapping_guideline_v2_20260526.md"
PROTOCOL_AMENDMENT_NAME = "PROTOCOL_AMENDMENTS.md"


def resource_path(*parts: str) -> Path:
    """Return the installed path of a bundled package resource."""
    return Path(str(resources.files("cxr_ldc_eval").joinpath(*parts)))


def default_config_path() -> Path:
    return resource_path("config", CONFIG_NAME)


def default_rules_path() -> Path:
    return resource_path("docs", RULES_NAME)


def default_mapping_guideline_path() -> Path:
    return resource_path("docs", MAPPING_GUIDELINE_NAME)


def default_protocol_amendment_path() -> Path:
    return resource_path("docs", PROTOCOL_AMENDMENT_NAME)
