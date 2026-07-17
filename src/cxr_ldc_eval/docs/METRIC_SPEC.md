# CXR Longitudinal Disease-Change Metric Specification

Version: 0.1.1  
Primary metric: Exact LDC-F1  
Runtime source of truth: `config/cxr_longitudinal_eval_config_v0_1.json`

## Evaluation unit

The evaluator applies the same deterministic extractor to prediction and reference text. Each mapped statement becomes a normalized claim with a canonical entity, presence transition, severity transition, and provenance fields.

The paper-facing primary tuple depends on the question profile.

| Profile | Primary tuple | Scored values |
|---|---|---|
| Difference/Change | `(entity, presence_transition)` | `NEW`, `RESOLVED`, `PRESENT_BOTH` |
| Level | `(entity, severity_transition)` | `WORSENED`, `IMPROVED`, `SAME_LEVEL`, `LEVEL_CHANGED_UNSPECIFIED` |

For broad Difference/Change questions, severity claims project to `PRESENT_BOTH`. An explicit opposite direction remains available to the severity contradiction analysis.

A location-conditioned `what has changed` question is a Level question in this protocol. See [PROTOCOL_AMENDMENTS.md](PROTOCOL_AMENDMENTS.md).

## Exact LDC-F1

For all eligible records in one ontology view, let (P) and (G) be the accumulated predicted and reference primary claims. Exact matching requires the same canonical entity, axis, and transition value.

```text
precision = TP / |P|
recall    = TP / |G|
Exact LDC-F1 = 2 TP / (|P| + |G|)
```

Claims are deduplicated within an answer. Matching is one-to-one. If (|P| + |G| = 0), the paper-facing F1 is undefined: JSON uses `null`, while Markdown and CLI use `N/A`.

`Ontology Change F1` is retained as a backward-compatible alias of Exact LDC-F1.

## Ontology views

Every run reports three independent views:

- `cxr_primary`: the main CXR-oriented ontology subset;
- `all_31_auxiliary`: all 31 configured labels, interpreted as answer-text consistency;
- `chexpert_projected`: an auxiliary projection for prior-work comparison.

Do not merge CXR-primary and All-31 results or present the CheXpert projection as the primary LDC metric.

## Hierarchical LDC-F1

The auxiliary hierarchical score uses config weights for exact/synonym, CheXpert-projection equivalent, parent-child, same-group, and unrelated pairs. It solves an exact maximum-weight one-to-one bipartite assignment in cubic time. A prediction cannot match multiple reference claims.

## Diagnostic metrics

- `Ontology Entity F1`: exact entity agreement without transition.
- `Change-Presence F1`: Exact LDC aggregation restricted to presence-primary questions.
- `Level-Direction F1`: Exact LDC aggregation restricted to severity-primary questions.
- `Direction Accuracy`: transition agreement among entities present on both sides of the primary tuple set.
- `Hallucinated Disease-Change Rate`: unmatched predicted claims divided by predicted claims.
- `Omission Rate`: unmatched reference claims divided by reference claims.
- `Presence Contradiction Rate`: configured opposite presence transitions among shared entities on presence-primary questions.
- `Explicit Severity Contradiction Rate`: configured opposite severity directions among shared explicit severity entities.
- `Global No-Change Contradiction Rate`: configured global/no-change conflict over samples whose reference is explicit global no-change or has a nonempty primary claim set.
- `NoChange-Acc`: among explicit global-no-change references, the fraction with no predicted primary change claim.

Each diagnostic with a zero denominator is `null`/`N/A`.

## Extraction order

For each sentence, the rule extractor checks:

1. explicit global no-change;
2. structured level-change grammar;
3. structured NEW/RESOLVED grammar;
4. entity aliases plus configured transition phrases.

Entity aliases use longest non-overlapping matching and map to canonical labels from config. Negated NEW phrases and `partially resolved` are handled so they do not become false NEW/RESOLVED claims. The latter maps to `PRESENT_BOTH + IMPROVED`.

## Question routing

Routing order and the location override are config-defined. The primary axis is derived from the selected evaluation profile's declared primary tuple, not independently hard-coded from a question name.

The paper-facing supported scope is Difference/Change and Level. Presence, location, and abnormality profiles have partial projection scaffolding; free-form yes/no, location extraction, entity inheritance, Type, and View are not claimed as validated paper-facing metrics in this release.

## Alignment and provenance

Generic records require unique IDs. The legacy adapter requires exact prediction/reference ID-set equality and rejects duplicate IDs, duplicate query CSV row indices, and row-index disagreement when both sides provide an index.

Summaries include evaluator/config versions, protocol policy, counts, artifact names, and SHA-256 digests of supplied inputs/config/documents. Source path strings are not emitted.

## Limitations

LDC is an answer-text agreement metric. It does not establish that an answer is grounded in the images, that the image pair is temporally correct, or that a clinical statement is medically true.

The extractor is strongest on the answer grammar documented in [QUERY_ANSWER_TAXONOMY.md](QUERY_ANSWER_TAXONOMY.md). New free-form corpora require coverage and error analysis before paper-facing use.
