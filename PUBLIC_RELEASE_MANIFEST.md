# Public Release Manifest

## Included

- `src/cxr_ldc_eval/*.py`: standard-library metric, extraction, projection, matching, CLI, and adapters
- `src/cxr_ldc_eval/config/*.json`: versioned ontology and evaluation settings
- `src/cxr_ldc_eval/docs/*.md`: bundled protocol, metric, input, amendment, and aggregate Query/Answer documentation
- `examples/synthetic_records.jsonl`: invented, non-clinical examples
- `tests/*.py`: synthetic regression tests
- `.github/workflows/tests.yml`: CPU-only CI
- root packaging, contribution, citation-template, changelog, and release-checklist files

The runtime config contains ontology and evaluation settings only. Dataset-derived aggregate counts appear only in the taxonomy and historical protocol documents; none contains a source row, image path, patient/study identifier, or clinical narrative.

## Explicitly excluded

- Images and dataset tables
- Patient, study, image, or institution identifiers
- Raw clinical questions/answers at row level
- Model code, weights, adapters, checkpoints, and prompt caches
- Prediction JSON/JSONL, merged ground truth, claim dumps, and metric outputs
- Training scripts and LLaVA runtime code
- Logs, W&B artifacts, caches, and local environment files
- Patch backups/rejects such as `*.orig` and `*.rej`

## Public interface

The recommended public interface is the generic `records` command. The `legacy` adapter is included only to reproduce existing COCO-style evaluation artifacts; it does not import LLaVA.

## Artifact sensitivity

Summary JSON and Markdown contain aggregate metrics, `<provided>` path markers, and SHA-256 digests. Claims JSON is disabled by default; opt-in `--write-claims` contains source question/reference/prediction text and is excluded from public release review.

## Release blocker

No public distribution is authorized until [LICENSE_SELECTION_REQUIRED.md](LICENSE_SELECTION_REQUIRED.md) is resolved.
