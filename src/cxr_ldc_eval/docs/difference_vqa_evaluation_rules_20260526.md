# Difference VQA Evaluation Rules and Metric Selection

> **v0.1.1 supersession notice (2026-07-17):** this is a historical rules document. Location-conditioned `what has changed ... area?` questions now route to the **Level** profile, not Broad Difference. The released JSON config is the runtime source of truth. See [PROTOCOL_AMENDMENTS.md](PROTOCOL_AMENDMENTS.md).

Date: 2026-05-26
Scope: Medical-Diff-VQA Difference subset evaluation
Purpose: Codex-ready specification for aligning the evaluator with the intended paper claim.

---

## 1. Final Evaluation Claim

This evaluation targets the Difference subset of Medical-Diff-VQA. The goal is to evaluate whether a generated answer preserves disease-level longitudinal change semantics described in the ground-truth answer.

The primary unit of evaluation is a disease-change claim:

```text
(clinical_finding, longitudinal_transition)
```

The evaluator should compare generated answer text against ground-truth answer text after applying the same rule-based claim extraction pipeline to both.

The main contribution metric is:

```text
Exact LDC-F1
```

Exact LDC-F1 gives credit only when both the clinical finding and the selected longitudinal transition are identical.

---

## 2. Key Design Principle

The Difference subset contains broad longitudinal change questions, such as:

```text
what has changed compared to the reference image?
what has changed in the right lung area?
```

In these broad change questions, report-derived answers often describe:

```text
additional finding of X
missing finding of Y
level of Z changed from A to B
nothing has changed
```

However, broad change questions do not always require reliable fine-grained severity ordering from the model. Report language can be noisy or incomparable, and models may reasonably state that a finding persists rather than explicitly outputting worsened or improved.

Therefore, the evaluator should separate two cases:

1. Broad Difference query
   - Primary transition axis: presence transition
   - Use `NEW`, `RESOLVED`, `PRESENT_BOTH`
   - If a severity clause is present in the answer, map it to `PRESENT_BOTH` in the primary score
   - Keep explicit severity information only for contradiction analysis

2. Explicit level-comparison query
   - Primary transition axis: severity transition
   - Use `WORSENED`, `IMPROVED`, `SAME_LEVEL`, `LEVEL_CHANGED_UNSPECIFIED`
   - This is the only case where worsened and improved should directly affect the primary F1 score

This preserves `PRESENT_BOTH` as a clinically meaningful relaxed state for broad change answers, while still evaluating `WORSENED` and `IMPROVED` when the question explicitly asks for level comparison.

---

## 3. Query-Aware Primary Transition Policy

### 3.1 Broad Difference Queries

Examples:

```text
what has changed compared to the reference image?
what has changed in the right lung area?
what has changed in the left lung area?
```

Primary transitions:

```text
NEW
RESOLVED
PRESENT_BOTH
```

Mapping rules:

| Extracted information | Primary transition |
|---|---|
| additional finding of X | NEW |
| new finding of X | NEW |
| missing finding of X | RESOLVED |
| resolved X | RESOLVED |
| X is persistent/stable/again seen | PRESENT_BOTH |
| level of X changed from A to B | PRESENT_BOTH |
| worsened X | PRESENT_BOTH |
| improved X | PRESENT_BOTH |

Severity information from broad difference answers should still be retained in `severity_tuples` for contradiction analysis, but it should not replace the primary transition.

### 3.2 Explicit Level-Comparison Queries

Examples:

```text
has the level of atelectasis changed?
has the severity of pleural effusion changed?
has edema worsened or improved?
```

Primary transitions:

```text
WORSENED
IMPROVED
SAME_LEVEL
LEVEL_CHANGED_UNSPECIFIED
```

Mapping rules:

| Extracted information | Primary transition |
|---|---|
| level changed from lower severity to higher severity | WORSENED |
| level changed from higher severity to lower severity | IMPROVED |
| unchanged severity or same level | SAME_LEVEL |
| level changed but direction cannot be determined | LEVEL_CHANGED_UNSPECIFIED |

---

## 4. Final Metric Set

### 4.1 Main Metric

#### Exact LDC-F1

Use as the primary metric.

Definition:

```text
Exact LDC-F1 = F1 over query-aware primary disease-change claims
```

A claim matches only if:

```text
predicted clinical finding == ground-truth clinical finding
and
predicted primary transition == ground-truth primary transition
```

This metric should be used for main model comparison and main conclusions.

---

### 4.2 Supporting Metrics for Main Table

#### Ontology Entity F1

Purpose:

```text
Measures whether the model mentions the correct clinical findings, ignoring transition direction.
```

Use it to show whether a model knows the disease entity but fails at longitudinal direction.

Interpretation:

```text
High Entity F1 + Low Exact LDC-F1 = disease names are often correct, but change directions are wrong or incomplete.
```

#### Direction Accuracy

Purpose:

```text
Among clinical findings shared by generated and ground-truth answers, measures whether the transition is correct.
```

It does not measure omission or hallucination. It is a conditional direction correctness metric.

---

### 4.3 Axis-Specific Breakdown Metrics

These are not primary contribution metrics. They explain Exact LDC-F1 by transition type.

#### Change-Presence F1

Use for broad Difference queries only.

Transitions:

```text
NEW
RESOLVED
PRESENT_BOTH
```

Purpose:

```text
Measures additional, missing, and co-present finding consistency.
```

#### Level-Direction F1

Use for explicit level-comparison queries only.

Transitions:

```text
WORSENED
IMPROVED
SAME_LEVEL
LEVEL_CHANGED_UNSPECIFIED
```

Purpose:

```text
Measures whether the model correctly answers explicit level-change questions.
```

If the evaluation split contains zero explicit level-comparison questions, do not report Level-Direction F1 in the main table. Report it as N/A or omit it.

---

### 4.4 Diagnostic Error Metrics

These metrics should be used for error analysis, not as main comparison metrics.

#### Hallucinated Disease-Change Rate

Definition:

```text
unmatched generated disease-change claims / generated disease-change claims
```

Purpose:

```text
Measures unsupported disease-change claims.
```

#### Omission Rate

Definition:

```text
unmatched ground-truth disease-change claims / ground-truth disease-change claims
```

Purpose:

```text
Measures missed disease-change claims.
```

#### Presence Contradiction Rate

Contradiction pairs:

```text
NEW vs RESOLVED
RESOLVED vs NEW
```

Purpose:

```text
Measures direct additional/missing reversal for the same disease.
```

#### Explicit Severity Contradiction Rate

Recommended contradiction pairs:

```text
WORSENED vs IMPROVED
IMPROVED vs WORSENED
```

Purpose:

```text
Measures direct severity-direction reversal when both answers explicitly mention severity direction.
```

Do not treat absence of an explicit severity statement as a contradiction in broad Difference questions.

#### NoChange-Acc

Definition:

```text
Among no-change or no-primary-claim ground-truth samples, accuracy of generating no primary claim.
```

Purpose:

```text
Measures whether the model avoids hallucinating disease-change claims when the answer says nothing has changed.
```

Use as a no-change subset analysis. Do not use it as the main metric.

---

### 4.5 Supplementary Metric

#### Hierarchical LDC-F1

Use only as supplementary analysis.

Reason:

```text
It uses fixed partial matching weights for semantically related labels, such as projection-equivalent or parent-child findings.
```

Do not base main conclusions on Hierarchical LDC-F1 because partial weights are configuration-defined and may be considered arbitrary if not validated.

Main conclusions should be based on Exact LDC-F1.

---

## 5. Metrics to Remove or De-emphasize

Do not use the following as main paper metrics:

```text
FC-F1_micro
FC-F1_macro
Finding-Only F1
FOF1
Ontology Change F1
```

Reasons:

- These are legacy or redundant names.
- `Ontology Entity F1` replaces Finding-Only F1 / FOF1.
- `Exact LDC-F1` replaces FC-F1_micro / Ontology Change F1 for current answer-level evaluation.
- Macro F1 is not currently part of the main longitudinal evaluator and should not be introduced unless class-wise support is sufficient and implementation is explicit.

---

## 6. Required Code Behavior

### 6.1 Query Text Must Be Available

The evaluator must load query text from the query file or manifest.

If query text is unavailable, the evaluator may default all samples to broad Difference mode, but this is unsafe for paper-level evaluation because explicit level-comparison queries would not be evaluated correctly.

Recommended behavior for paper experiments:

```text
require_questions = True
```

If question text is missing for any sample, raise an error or report the sample count and exclude those samples from level-specific analysis.

### 6.2 Keep Current Broad Difference Relaxation

For broad Difference queries:

```text
WORSENED / IMPROVED / SAME_LEVEL / LEVEL_CHANGED_UNSPECIFIED
→ PRESENT_BOTH in primary tuples
```

This is intentional.

Do not change broad Difference primary scoring to directly use WORSENED / IMPROVED unless the paper claim changes.

### 6.3 Use Level Direction Only for Explicit Level Queries

For explicit level-comparison queries:

```text
primary_axis = severity_transition
```

and primary tuples should directly use:

```text
WORSENED
IMPROVED
SAME_LEVEL
LEVEL_CHANGED_UNSPECIFIED
```

### 6.4 Use Exact Matching as Primary

For the main score:

```text
hierarchical = False
```

### 6.5 Hierarchical Matching Is Optional

If used:

- Report only in supplementary analysis
- State that weights are fixed before evaluation
- Do not tune weights based on model outputs
- Consider sensitivity analysis if included in the paper

---

## 7. Recommended Paper Tables

### Table A: Main Results

Recommended columns:

```text
Model
BLEU-4
ROUGE-L
CIDEr
Ontology Entity F1
Exact LDC-F1
Direction Accuracy
```

### Table B: Transition-Axis Breakdown

Recommended columns:

```text
Model
Change-Presence F1
# Presence claims
Level-Direction F1
# Level claims
```

If there are no explicit level-comparison queries in a split, omit Level-Direction F1 or mark as N/A.

### Table C: Error Analysis

Recommended columns:

```text
Model
Hallucinated Disease-Change Rate
Omission Rate
Presence Contradiction Rate
Explicit Severity Contradiction Rate
NoChange-Acc
```

### Appendix Table

Recommended columns:

```text
Model
Hierarchical LDC-F1
configured partial matching weights
sensitivity result if available
```

---

## 8. Codex Implementation Request Template

Use the following request when asking Codex to update the evaluator:

```text
Please update the longitudinal evaluation code according to these rules:

1. Keep Medical-Diff-VQA Difference subset as the target evaluation scope.
2. Preserve query-aware primary axis selection:
   - broad Difference query -> presence transition primary axis
   - explicit level-comparison query -> severity transition primary axis
3. For broad Difference queries, keep severity transitions mapped to PRESENT_BOTH in primary tuples.
4. For explicit level-comparison queries, evaluate WORSENED, IMPROVED, SAME_LEVEL, LEVEL_CHANGED_UNSPECIFIED directly as primary tuples.
5. Use Exact LDC-F1 as the primary metric based on exact matching only.
6. Keep Hierarchical LDC-F1 as supplementary only.
7. Rename or organize output metrics as:
   - Exact LDC-F1
   - Ontology Entity F1
   - Direction Accuracy
   - Change-Presence F1
   - Level-Direction F1
   - Hallucinated Disease-Change Rate
   - Omission Rate
   - Presence Contradiction Rate
   - Explicit Severity Contradiction Rate
   - NoChange-Acc
8. Remove or de-emphasize legacy names:
   - FC-F1_micro
   - FC-F1_macro
   - FOF1
   - Finding-Only F1
   - Ontology Change F1
9. Add strict query availability checking for paper evaluation.
10. Add diagnostics for number of broad Difference queries, explicit level-comparison queries, presence claims, severity claims, and no-change samples.

Do not change broad Difference scoring to directly penalize WORSENED/IMPROVED omissions. Severity direction should directly affect primary score only for explicit level-comparison questions.
```

---

## 9. One-Sentence Paper Claim

Recommended claim:

```text
We evaluate Medical-Diff-VQA Difference answers by converting generated and ground-truth answers into disease-level longitudinal claims and measuring exact disease-transition agreement, while separately analyzing presence-change, explicit level-change, contradiction, hallucination, omission, and no-change behavior.
```
