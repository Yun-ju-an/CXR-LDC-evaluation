# Changelog

## 0.1.1 — 2026-07-17

Initial extracted release candidate.

- Added a dataset- and model-independent JSON/JSONL evaluator and CLI.
- Kept location-conditioned `what has changed` questions on the Level profile.
- Moved question routing, scored transition values, projections, and contradiction pairs into validated config.
- Added strict legacy ID/row alignment and duplicate checks.
- Added SHA-256 provenance, filename-redacted path markers, overwrite protection, and privacy-first claim-output opt-in.
- Added config-driven Global No-Change Contradiction Rate.
- Rendered zero-denominator paper metrics as `null`/`N/A`.
- Replaced exponential assignment with exact cubic-time one-to-one matching.
- Added aggregate-only Query/Answer taxonomy documentation and synthetic tests.
