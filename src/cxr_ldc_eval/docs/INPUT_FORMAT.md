# Input Format

The recommended public interface is a JSON or JSONL collection of aligned question, prediction, and reference text. It has no dataset or model dependency.

## Record schema

| Field | Required | Type | Meaning |
|---|---:|---|---|
| `id` | no | string or number | Stable opaque sample key; defaults to one-based input position |
| `question` | yes by default | string | Routes the sample to its primary evaluation profile |
| `prediction` | yes | string | Generated answer text |
| `reference` | yes | string | Ground-truth/reference answer text |
| `row_index` | no | string or number | Optional provenance carried into an opt-in claim dump |

IDs must be unique after string conversion. Use opaque IDs; never place patient or study identifiers in a shareable input.

## JSONL

One object per line:

```json
{"id":"s1","question":"what has changed compared to the reference image?","prediction":"nothing has changed","reference":"nothing has changed"}
```

Blank lines are ignored. Every nonblank line must be a JSON object.

## JSON

Either a top-level list:

```json
[
  {
    "id": "s1",
    "question": "what has changed in the left lung area?",
    "prediction": "the level of pleural effusion has changed from small to large",
    "reference": "the level of pleural effusion has changed from small to large"
  }
]
```

or an object containing a `records` list:

```json
{"records": [{"id": "s1", "question": "...", "prediction": "...", "reference": "..."}]}
```

## Question requirement

Question text is required by default. This is protocol-sensitive:

- a broad `what has changed compared to the reference image?` question uses the Difference profile;
- a location-conditioned `what has changed ... area?` question uses the Level profile.

`--allow-missing-questions` explicitly enables a broad-Difference fallback. Results produced with that fallback are not comparable to paper-facing results that require complete question routing.

## Outputs

The command writes aggregate JSON and Markdown summaries. Per-record source text and extracted claims are not written by default. `--write-claims` is an explicit opt-in and may create a sensitive artifact.

Input filenames are not copied into the summary; a `<provided>` marker and SHA-256 digest are recorded instead. Existing outputs are protected. If a claims file already exists for a prefix, a no-claims run refuses to proceed rather than silently leaving that stale sensitive file.

## Legacy format

The `legacy` adapter accepts:

- a prediction list, or an object with a `results` list, containing `image_id`, `caption`, and optional `row_index`;
- a COCO-style ground-truth object with `images` and `annotations`;
- an optional generation manifest whose `query_file` points to a TSV or `row_index,question` CSV.

Prediction and ground-truth ID sets must match exactly. Duplicate IDs, duplicate query CSV row indices, and prediction/ground-truth row-index mismatches are rejected. Question coverage is required by default. `image_id` is the alignment key; the adapter does not require `row_index` values to be globally unique across different IDs, so protocols needing that invariant must validate it upstream.
