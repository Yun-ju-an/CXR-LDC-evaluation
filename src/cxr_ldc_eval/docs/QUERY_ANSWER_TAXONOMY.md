# Observed Query and Answer Taxonomy

This document summarizes the actual Query/Answer forms observed while preparing CXR LDC Eval. It publishes only normalized templates and aggregate counts. It does not contain a dataset row, identifier, image path, or patient-specific clinical answer.

## Audit scope

| Split | Rows | Missing question |
|---|---:|---:|
| Valid | 16,372 | 0 |
| Test | 16,389 | 0 |
| Combined | 32,761 | 0 |

The CheXpert14-oriented and 31-label-oriented evaluation exports had identical `(row_index, question, answer)` hashes within each split, so they were counted once rather than double-counted.

Counts below describe these two evaluation splits only. They are not claims about training data or another corpus version.

## Actual Query templates

Question text was lowercased and whitespace-trimmed for grouping; punctuation shown below is the observed template punctuation.

| Observed question | Valid | Test | Combined | LDC route |
|---|---:|---:|---:|---|
| `what has changed compared to the reference image?` | 16,186 | 16,213 | 32,399 | Difference |
| `what has changed in the bibasilar area?` | 3 | 4 | 7 | Level |
| `what has changed in the left apical area?` | 2 | 2 | 4 | Level |
| `what has changed in the left lung area?` | 87 | 74 | 161 | Level |
| `what has changed in the left lung lower area?` | 1 | 0 | 1 | Level |
| `what has changed in the left retrocardiac area?` | 2 | 0 | 2 | Level |
| `what has changed in the retrocardiac area?` | 1 | 1 | 2 | Level |
| `what has changed in the right left area?` | 1 | 5 | 6 | Level |
| `what has changed in the right lung area?` | 87 | 86 | 173 | Level |
| `what has changed in the right rib area?` | 2 | 0 | 2 | Level |
| `what has changed in the apical area?` | 0 | 2 | 2 | Level |
| `what has changed in the right apical area?` | 0 | 2 | 2 | Level |
| **Total** | **16,372** | **16,389** | **32,761** | — |

The `right left area` string is recorded verbatim as an observed anomalous template; the evaluator does not silently rewrite it.

There were 32,399 generic Difference questions and 362 location-conditioned questions. No separate generic explicit-Level query template was observed. Nevertheless, every location-conditioned reference answer was Level-only, which is why this project intentionally keeps those questions on the Level profile.

## Observed Answer grammar

All inspected answers fit combinations of four placeholder forms:

```text
NO_CHANGE
  nothing has changed

NEW({ENTITY_LIST})
  the main image has an additional finding of {ENTITY_LIST} than the reference image
  the main image has additional findings of {ENTITY_LIST} than the reference image

RESOLVED({ENTITY_LIST})
  the main image is missing the finding of {ENTITY_LIST} than the reference image
  the main image is missing the findings of {ENTITY_LIST} than the reference image

LEVEL({ENTITY}, {REFERENCE_LEVEL}, {CURRENT_LEVEL})
  the level of {ENTITY} has changed from {REFERENCE_LEVEL} to {CURRENT_LEVEL}
```

These are grammar templates, not copied clinical rows. `ENTITY` values are resolved through the released ontology config.

### Clause counts

| Clause type | Combined clauses |
|---|---:|
| NEW | 20,316 |
| RESOLVED | 19,921 |
| LEVEL | 1,759 |
| NO_CHANGE | 4,544 |

### Row-level combinations

| Answer composition | Rows |
|---|---:|
| NO_CHANGE | 4,544 |
| NEW only | 7,515 |
| RESOLVED only | 7,105 |
| NEW + RESOLVED | 11,902 |
| LEVEL only | 489 |
| NEW + LEVEL | 292 |
| RESOLVED + LEVEL | 307 |
| NEW + RESOLVED + LEVEL | 607 |
| **Total** | **32,761** |

A clause count is not a row count: one row may contain several clauses and several entities.

### Location-conditioned Level subset

| Direction | Valid | Test | Combined |
|---|---:|---:|---:|
| WORSENED | 94 | 81 | 175 |
| IMPROVED | 87 | 78 | 165 |
| SAME_LEVEL | 5 | 17 | 22 |
| LEVEL_CHANGED_UNSPECIFIED | 0 | 0 | 0 |
| **Total** | **186** | **176** | **362** |

All 362 scoped answers contained exactly one mapped entity. This is empirical support for the Level routing decision, not a guarantee for future data.

## Structural distribution

| Sentences per answer | Rows |
|---:|---:|
| 1 | 19,645 |
| 2 | 12,474 |
| 3 | 621 |
| 4 | 21 |

Mapped entity-claim count per answer had median 2, 95th percentile 5, and maximum 10.

## How researchers should use this taxonomy

- Use the templates to build synthetic parser and metric tests.
- Use the counts to understand current coverage, not as a universal language model.
- Validate new free-form answers, uncertainty, negation, and synonyms separately.
- Keep the location-conditioned routing regression test.
- Do not copy source rows into issues, tests, documentation, or public artifacts.

## Publication caution

Some template cells contain only one or two samples. Before publishing this table, confirm that the governing dataset agreement and institutional policy permit aggregate/template disclosure and small-cell counts. If not, collapse rare location templates into an `other location` row while keeping the Level routing behavior unchanged.
