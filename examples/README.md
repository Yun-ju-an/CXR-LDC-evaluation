# Synthetic Examples

`synthetic_records.jsonl` is invented test data. It contains no dataset row or clinical identifier.

Run:

```bash
ldc-eval records \
  --input examples/synthetic_records.jsonl \
  --output-dir /tmp/cxr_ldc_demo \
  --output-prefix synthetic
```

Claim text is not written by default. Add `--write-claims` only when you intend to inspect the per-record extraction locally.
