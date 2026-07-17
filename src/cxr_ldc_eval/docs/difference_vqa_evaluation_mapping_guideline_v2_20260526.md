# Difference VQA Evaluation Mapping Guideline v2

> **v0.1.1 supersession notice (2026-07-17):** this is a historical v2 guideline. Section 8.1's location-conditioned `what has changed ... area?` examples now route to the **Level** profile. The released JSON config is the runtime source of truth. See [PROTOCOL_AMENDMENTS.md](PROTOCOL_AMENDMENTS.md).

Date: 2026-05-26  
Scope: Medical-Diff-VQA Difference subset evaluation  
Primary implementation context: `eval_formula_context_20260520.tar.gz`  
Primary data check file: `report_disease31_wide_encoded_paths_test.csv`

---

## 0. Executive Summary

이 문서는 Medical-Diff-VQA의 **Difference subset**을 대상으로, generated answer와 ground-truth answer를 disease-level longitudinal claim으로 변환해 평가하기 위한 최종 metric 및 mapping 규칙을 정리한다.

최종적으로 논문에서 주장할 핵심은 다음이다.

```text
We evaluate Medical-Diff-VQA Difference answers by converting generated and ground-truth answers into disease-level longitudinal claims and measuring exact disease-transition agreement, while separately analyzing presence-change, explicit level-change, contradiction, hallucination, omission, and no-change behavior.
```

한국어로는 다음과 같다.

```text
본 연구는 Medical-Diff-VQA Difference answer를 disease-level longitudinal claim으로 구조화하고, generated answer가 ground-truth answer의 disease-transition semantics를 얼마나 정확히 재현하는지 Exact LDC-F1로 평가한다. Presence change, explicit level change, contradiction, hallucination, omission, no-change 성능은 보조 분석으로 분리해 보고한다.
```

---

## 1. Final Metric Positioning

### 1.1 Main Metric

| Metric | Position | Reason |
|---|---|---|
| **Exact LDC-F1** | Main contribution metric | disease와 longitudinal transition이 모두 동일해야 match. partial weight 없음. 기존 NLG metric 및 disease mention metric과 명확히 차별화됨. |

### 1.2 Supporting Metrics for Main Table

| Metric | Position | Purpose |
|---|---|---|
| **Ontology Entity F1** | Supporting | transition을 제거하고 disease entity만 평가. disease mention 성능 확인용. |
| **Direction Accuracy** | Supporting | generated와 ground-truth가 동일 disease를 공유할 때 transition이 일치하는지 평가. disease mention 조건부 direction consistency. |
| **Hierarchical LDC-F1** | Supporting or Supplementary | label granularity mismatch 완화용. 단, partial matching weight를 사용하므로 main conclusion의 근거로 쓰지 않음. |

### 1.3 Axis-Specific Breakdown Metrics

| Metric | Position | Purpose |
|---|---|---|
| **Change-Presence F1** | Breakdown | broad Difference query에서 NEW, RESOLVED, PRESENT_BOTH 성능 분석. |
| **Level-Direction F1** | Breakdown or N/A | explicit level-comparison query에서 WORSENED, IMPROVED, SAME_LEVEL, LEVEL_CHANGED_UNSPECIFIED 성능 분석. 현재 test CSV에는 explicit level-comparison query가 없으므로 main table에서는 N/A 가능. |

### 1.4 Error Analysis Metrics

| Metric | Position | Purpose |
|---|---|---|
| **Hallucinated Disease-Change Rate** | Error analysis | generated claim 중 ground-truth와 match되지 않은 unsupported disease-change 비율. |
| **Omission Rate** | Error analysis | ground-truth claim 중 generated answer가 놓친 disease-change 비율. |
| **Presence Contradiction Rate** | Error analysis | 동일 disease에 대해 NEW와 RESOLVED가 반대로 기술된 경우. |
| **Explicit Severity Contradiction Rate** | Error analysis | 동일 disease에 대해 WORSENED와 IMPROVED가 반대로 기술된 경우. |
| **NoChange-Acc** | Error analysis | no-change sample에서 generated answer도 disease-change claim을 생성하지 않았는지 평가. |

### 1.5 Remove or De-emphasize

| Old or Redundant Metric | Recommendation | Reason |
|---|---|---|
| `FC-F1_micro` | Remove from current paper terminology | legacy TSV-gold evaluator term. Exact LDC-F1로 대체. |
| `FC-F1_macro` | Remove unless explicitly implemented | current longitudinal evaluator main flow에는 macro class F1이 명확히 정의되어 있지 않음. |
| `Finding-Only F1` / `FOF1` | Replace with Ontology Entity F1 | current evaluator terminology와 일치시키기 위함. |
| `Ontology Change F1` | Remove or alias to Exact LDC-F1 only in code | 현재 code에서 Exact LDC-F1과 동일 값을 반환. 중복. |
| `Change-Presence F1` as main | Do not use as main | Exact LDC-F1의 axis-specific decomposition으로만 사용. |
| `Level-Direction F1` as main | Do not use as main | explicit level-comparison query subset이 있을 때만 의미 있음. |

---

## 2. Data Evidence from Provided Test CSV

File: `report_disease31_wide_encoded_paths_test.csv`

### 2.1 Basic Statistics

| Item | Count |
|---|---:|
| Total test rows | 16,389 |
| Unique question texts | 9 |
| `what has changed compared to the reference image?` | 16,213 |
| Location-conditioned change questions | 176 |
| Explicit level-comparison questions in this test CSV | 0 observed |

### 2.2 Answer Pattern Statistics

| Answer pattern | Count |
|---|---:|
| Contains `additional finding` | 10,217 rows |
| Contains `missing` | 9,942 rows |
| Contains level-change clause | 892 rows |
| Contains `nothing has changed` | 2,319 rows |

### 2.3 Encoded Label Value Distribution

The wide label columns use the following apparent code distribution:

| Encoded value | Interpreted class | Aggregate count |
|---:|---|---:|
| 0 | no active label | 456,112 |
| 1 | NEW | 20,420 |
| 2 | RESOLVED | 19,090 |
| 3 | WORSENED | 401 |
| 4 | IMPROVED | 377 |
| 5 | UNCHANGED or auxiliary co-present/stable | 11,659 |

### 2.4 Interpretation

The test CSV supports the following design choice.

1. Most queries are broad Difference queries.
2. Broad Difference answers frequently contain additional and missing findings.
3. Some broad Difference answers include level-change clauses.
4. However, broad Difference query wording does not explicitly force the model to answer with severity direction.
5. Therefore, broad Difference scoring should not over-penalize the absence of explicit WORSENED/IMPROVED when the answer only supports that the finding is present in both images.
6. `PRESENT_BOTH` is clinically meaningful as a relaxed transition for broad Difference answers.
7. WORSENED/IMPROVED should directly affect the primary score only when the query explicitly asks for level/severity comparison.

---

## 3. Core Terminology

Use the following terms consistently in the paper and code comments.

| Concept | Recommended term | Avoid |
|---|---|---|
| 정답 답변 | `ground-truth answer` | `reference answer`, because `reference image` already exists |
| 생성 답변 | `generated answer` | `candidate answer`, unless discussing GREEN-style report evaluation |
| 정답 claim 집합 | `ground-truth claim set` | `gold claim set`, unless code variable uses gold internally |
| 생성 claim 집합 | `generated claim set` | `predicted claim set`, optional but less aligned with generated answers |
| 질병 표준 label 공간 | `canonical clinical finding label space` | newly invented ontology name not present in code |
| 질병 표현 정규화 | `alias normalization` | unsupported entity linking claim |
| 변화 상태 | `longitudinal transition` | overly broad `progression state` when formalizing formulas |
| 발생/소실/양시점 존재 | `presence transition` | `change-presence state` |
| 악화/호전/동일 수준 | `severity transition` | `level direction` except metric name |
| 평가 tuple | `disease-change claim` | `disease-progression pair` if code uses claim terminology |
| 엄격 일치 | `exact matching` | `strict score` |
| hierarchy 기반 부분 일치 | `hierarchical matching` | `soft score`, to avoid suggesting learned softness |
| 부분 점수 weight | `partial matching weight` | `credit score`, except explanatory text |
| 답변 수준 평가 | `answer-level evaluation` | `visual reasoning proof` |

---

## 4. Evaluation Scope

### 4.1 Dataset Scope

The target evaluation scope is:

```text
Medical-Diff-VQA Difference subset
```

This means that the evaluated questions are longitudinal comparison questions over a main image and a reference image.

### 4.2 What Is Compared

The evaluator compares:

```text
generated answer text vs. ground-truth answer text
```

The evaluator does **not** directly compare model output to original MIMIC-CXR reports in the primary current setup.

### 4.3 Evaluation-Only Setting

During evaluation:

- Ground-truth answers are not used as model input.
- Ontology-derived labels are not used as model input.
- No external LLM should be required for claim extraction.
- The same deterministic rule-based parser is applied to both generated and ground-truth answers.

---

## 5. Claim Extraction Overview

Each answer is converted into a set of disease-change claims.

Formal notation:

```latex
\mathcal{C}_i = \phi(A_i), \quad \hat{\mathcal{C}}_i = \phi(\hat{A}_i)
```

where:

- \(A_i\): ground-truth answer
- \(\hat{A}_i\): generated answer
- \(\phi\): rule-based longitudinal claim extractor
- \(\mathcal{C}_i\): ground-truth claim set
- \(\hat{\mathcal{C}}_i\): generated claim set

Each claim is:

```text
(clinical_finding, longitudinal_transition)
```

Formal notation:

```latex
c = (d, s)
```

where:

- \(d \in \mathcal{D}\): canonical clinical finding label
- \(s\): longitudinal transition

---

## 6. Canonical Finding Mapping

### 6.1 Alias Normalization

Natural language disease expressions are mapped to canonical labels using alias normalization.

Example mappings:

```text
pleural fluid        -> pleural_effusion
cardiac enlargement  -> cardiomegaly or enlargement_of_the_cardiac_silhouette depending on config
opacity              -> lung_opacity
```

### 6.2 Longest Alias First

Longer aliases should be matched before shorter aliases to prevent duplicate or fragmented extraction.

Example:

```text
left pleural effusion
```

should not be decomposed into unrelated shorter mentions if a longer alias is configured.

### 6.3 Duplicate Removal

If the same canonical finding and transition are extracted multiple times from one answer, duplicates should be removed before matching.

---

## 7. Transition Classes and Mapping Policy

### 7.1 Presence Transitions

Presence transitions describe whether a finding newly appears, disappears, or is present in both time points.

| Transition | Meaning | Typical answer expression |
|---|---|---|
| `NEW` | finding is present in main image but absent in reference image | `additional finding of X`, `new X` |
| `RESOLVED` | finding was present in reference image but is absent in main image | `missing finding of X`, `resolved X` |
| `PRESENT_BOTH` | finding is present in both images, but no reliable severity direction is used in broad Difference scoring | `persistent X`, `again seen X`, severity change clause under broad Difference query |
| `GLOBAL_NO_CHANGE` | answer states no overall change | `nothing has changed` |
| `UNKNOWN` | transition cannot be determined | parser fallback |

### 7.2 Severity Transitions

Severity transitions describe explicit severity or level direction.

| Transition | Meaning | Typical answer expression |
|---|---|---|
| `WORSENED` | current severity is greater than reference severity | `changed from minimal to mild`, `worsened X` |
| `IMPROVED` | current severity is lower than reference severity | `changed from moderate to small`, `improved X` |
| `SAME_LEVEL` | severity is explicitly unchanged | `same level`, `unchanged severity` |
| `LEVEL_CHANGED_UNSPECIFIED` | level changed but direction cannot be inferred | `level has changed` without ordinal direction |

---

## 8. Query-Aware Primary Transition Policy

This is the most important mapping rule.

### 8.1 Broad Difference Queries

Examples observed in the provided test CSV:

```text
what has changed compared to the reference image?
what has changed in the right lung area?
what has changed in the left lung area?
what has changed in the bibasilar area?
```

Primary transitions:

```text
NEW
RESOLVED
PRESENT_BOTH
```

Mapping rules:

| Extracted answer content | Primary transition under broad Difference query | Keep severity tuple? |
|---|---|---|
| `additional finding of X` | `NEW` | no |
| `new X` | `NEW` | no |
| `missing finding of X` | `RESOLVED` | no |
| `resolved X` | `RESOLVED` | no |
| `persistent X` | `PRESENT_BOTH` | no |
| `stable X` | `PRESENT_BOTH` or auxiliary stable depending on parser | optional |
| `level of X changed from A to B` | `PRESENT_BOTH` | yes |
| `worsened X` | `PRESENT_BOTH` | yes |
| `improved X` | `PRESENT_BOTH` | yes |

Rationale:

Broad Difference answers are often derived from reports and may include severity-related language, but the query does not necessarily require the model to output exact severity ordering. Therefore, severity change is relaxed to `PRESENT_BOTH` for the primary claim. Explicit severity information is retained for contradiction analysis only.

### 8.2 Explicit Level-Comparison Queries

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

| Extracted answer content | Primary transition under explicit level query |
|---|---|
| lower severity -> higher severity | `WORSENED` |
| higher severity -> lower severity | `IMPROVED` |
| same severity | `SAME_LEVEL` |
| changed but direction unknown | `LEVEL_CHANGED_UNSPECIFIED` |

Rationale:

When the query explicitly asks about level or severity change, the severity direction is the core answer. In this case, WORSENED and IMPROVED must directly affect the primary score.

### 8.3 Current Test CSV Caveat

The provided test CSV does not show explicit level-comparison queries. Therefore:

- `Change-Presence F1` is expected to be meaningful for this test set.
- `Level-Direction F1` may be undefined or N/A for this test set.
- Broad Difference answers may still contain level-change clauses, but those are mapped to `PRESENT_BOTH` in primary scoring.
- Explicit severity contradiction can still be computed if both generated and ground-truth answers explicitly contain severity direction for the same disease.

---

## 9. Exact Matching Rule

The main metric uses exact matching.

Generated claim:

```latex
\hat{c} = (\hat{d}, \hat{s})
```

Ground-truth claim:

```latex
c = (d, s)
```

Exact matching:

```latex
m_{\text{exact}}(\hat{c}, c)=
\begin{cases}
1, & \hat{d}=d \text{ and } \hat{s}=s,\\
0, & \text{otherwise}.
\end{cases}
```

Examples:

| Ground-truth | Generated | Exact match |
|---|---|---:|
| `(pneumothorax, NEW)` | `(pneumothorax, NEW)` | 1 |
| `(pneumothorax, NEW)` | `(pneumothorax, RESOLVED)` | 0 |
| `(pleural_effusion, RESOLVED)` | `(pleural_effusion, PRESENT_BOTH)` | 0 |
| `(atelectasis, WORSENED)` under explicit level query | `(atelectasis, WORSENED)` | 1 |
| `(atelectasis, WORSENED)` under explicit level query | `(atelectasis, IMPROVED)` | 0 |
| `(pneumonia, NEW)` | `(lung_opacity, NEW)` | 0 under exact matching |

---

## 10. Exact LDC-F1

### 10.1 Definition

Exact Longitudinal Disease-Change F1 is the primary metric.

Let:

- \(TP\): number of exactly matched disease-change claims
- \(FP\): generated claims that do not match any ground-truth claim
- \(FN\): ground-truth claims that are not matched by generated claims

Precision:

```latex
P = \frac{TP}{TP+FP}
```

Recall:

```latex
R = \frac{TP}{TP+FN}
```

Exact LDC-F1:

```latex
\text{Exact LDC-F1} = \frac{2PR}{P+R}
```

Equivalent count form:

```latex
\text{Exact LDC-F1} = \frac{2TP}{|\hat{\mathcal{C}}| + |\mathcal{C}|}
```

### 10.2 What It Measures

Exact LDC-F1 measures whether the generated answer reproduces the disease-level longitudinal change claims in the ground-truth answer.

It evaluates:

```text
disease identity + transition direction
```

rather than:

```text
surface text overlap only
```

### 10.3 Difference from Existing Metrics

| Metric | What it measures | Limitation for Difference VQA | Exact LDC-F1 difference |
|---|---|---|---|
| BLEU / ROUGE / CIDEr | lexical or n-gram similarity | can be high despite reversed change direction | evaluates disease-transition claims |
| CheXpert / CheXbert F1 | disease mention overlap | ignores additional vs missing or severity direction | includes longitudinal transition |
| RadGraph-F1 | entity/relation overlap | not designed for disease-specific longitudinal direction binding | explicitly binds disease with transition |
| GREEN | report-level factual error categories | not specifically a deterministic disease-transition metric for Difference VQA | specialized for Difference answer claims |
| Libra F1temp | temporal expression overlap in RRG | does not necessarily bind temporal word to each disease | evaluates disease-conditioned transition |

---

## 11. Ontology Entity F1

### 11.1 Definition

Projection:

```text
(disease, transition) -> disease
```

Entity-level matching ignores transition value.

### 11.2 Purpose

Ontology Entity F1 measures whether the model mentions the correct diseases or findings, regardless of whether it gets the longitudinal transition correct.

### 11.3 Interpretation

| Entity F1 | Exact LDC-F1 | Interpretation |
|---:|---:|---|
| high | high | disease and transition both good |
| high | low | disease mentions correct, transitions wrong or incomplete |
| low | low | disease mention itself is poor |
| low | high | unlikely, check parser or denominator |

### 11.4 Role

Supporting metric in main result table.

---

## 12. Direction Accuracy

### 12.1 Definition

Direction Accuracy evaluates transition correctness only for diseases shared by generated and ground-truth answers.

```latex
\text{Direction Accuracy}
=
\frac{
|\{d: d \in \hat{\mathcal{D}} \cap \mathcal{D}, \hat{S}_d \cap S_d \neq \emptyset\}|
}{
|\hat{\mathcal{D}} \cap \mathcal{D}|
}
```

where:

- \(\mathcal{D}\): disease set from ground-truth claims
- \(\hat{\mathcal{D}}\): disease set from generated claims
- \(S_d\): transition set for disease \(d\) in ground-truth answer
- \(\hat{S}_d\): transition set for disease \(d\) in generated answer

### 12.2 Purpose

Direction Accuracy answers:

```text
When the model mentions the same disease as ground truth, does it assign the correct transition?
```

### 12.3 Limitation

Direction Accuracy does not penalize:

- omitted diseases not generated by the model
- hallucinated diseases not in ground truth

Therefore it should not replace Exact LDC-F1.

### 12.4 Role

Supporting metric in main result table.

---

## 13. Change-Presence F1

### 13.1 Definition

Change-Presence F1 is an axis-specific breakdown over broad Difference primary transitions.

Target transitions:

```text
NEW
RESOLVED
PRESENT_BOTH
```

### 13.2 Purpose

This metric evaluates additional, missing, and co-present finding consistency.

Examples:

| Ground-truth | Generated | Change-Presence match |
|---|---|---:|
| `(pneumothorax, NEW)` | `(pneumothorax, NEW)` | 1 |
| `(pleural_effusion, RESOLVED)` | `(pleural_effusion, NEW)` | 0 |
| `(edema, PRESENT_BOTH)` | `(edema, PRESENT_BOTH)` | 1 |

### 13.3 Role

Breakdown metric, not main metric.

For the provided test CSV, this is expected to be the most relevant axis-specific breakdown because most queries are broad Difference queries.

---

## 14. Level-Direction F1

### 14.1 Definition

Level-Direction F1 is an axis-specific breakdown for explicit level-comparison queries.

Target transitions:

```text
WORSENED
IMPROVED
SAME_LEVEL
LEVEL_CHANGED_UNSPECIFIED
```

### 14.2 Purpose

It evaluates whether the model correctly answers questions explicitly asking about severity or level change.

Examples:

| Query | Ground-truth | Generated | Level-Direction match |
|---|---|---|---:|
| `Has the level of atelectasis changed?` | `(atelectasis, WORSENED)` | `(atelectasis, WORSENED)` | 1 |
| same | `(atelectasis, WORSENED)` | `(atelectasis, IMPROVED)` | 0 |
| same | `(atelectasis, IMPROVED)` | `(atelectasis, PRESENT_BOTH)` | 0 or unprojectable depending on parser |

### 14.3 Role

Breakdown metric, not main metric.

If a split contains no explicit level-comparison query, report:

```text
Level-Direction F1 = N/A
```

rather than interpreting 0.0 as poor model performance.

---

## 15. Error Analysis Metrics

### 15.1 Hallucinated Disease-Change Rate

Definition:

```latex
\text{Hallucinated Rate} = \frac{FP}{TP+FP}
```

Meaning:

```text
Among generated disease-change claims, how many are unsupported by the ground-truth answer?
```

Use:

- false longitudinal change generation
- unsupported additional or missing findings

---

### 15.2 Omission Rate

Definition:

```latex
\text{Omission Rate} = \frac{FN}{TP+FN}
```

Meaning:

```text
Among ground-truth disease-change claims, how many did the model miss?
```

Use:

- missed additional findings
- missed missing findings
- missed explicit level answers when level query exists

---

### 15.3 Presence Contradiction Rate

Contradiction pairs:

```text
NEW vs RESOLVED
RESOLVED vs NEW
```

Definition:

```text
Among shared diseases, count cases where generated and ground-truth presence transitions are direct opposites.
```

Example:

```text
Ground-truth: (pleural_effusion, NEW)
Generated:    (pleural_effusion, RESOLVED)
```

Interpretation:

This is the direct `additional`/`missing` reversal error.

---

### 15.4 Explicit Severity Contradiction Rate

Recommended contradiction pairs:

```text
WORSENED vs IMPROVED
IMPROVED vs WORSENED
```

Current code also includes SAME_LEVEL-related contradictions:

```text
WORSENED vs SAME_LEVEL
SAME_LEVEL vs WORSENED
IMPROVED vs SAME_LEVEL
SAME_LEVEL vs IMPROVED
```

Recommended paper stance:

- For main paper explanation, emphasize WORSENED vs IMPROVED reversal.
- If code includes SAME_LEVEL contradictions, report the exact denominator and define it explicitly.
- Do not count absent explicit severity statement as contradiction in broad Difference query.

Example:

```text
Ground-truth: (edema, WORSENED)
Generated:    (edema, IMPROVED)
```

---

### 15.5 NoChange Accuracy

Definition:

```text
Among samples whose ground-truth primary claim set is empty or expresses global no-change, measure whether generated primary claim set is also empty.
```

Example:

| Ground-truth | Generated | NoChange-Acc |
|---|---|---:|
| `nothing has changed` | `nothing has changed` | 1 |
| `nothing has changed` | `additional pneumothorax` | 0 |

Caveat:

Parser failures can artificially increase no-primary-claim cases. Always report diagnostic counts or validate parser behavior.

---

## 16. Hierarchical LDC-F1

### 16.1 Position

Hierarchical LDC-F1 can be used as a **supporting** metric or supplementary robustness analysis, but it should not be the main contribution metric.

### 16.2 Motivation

Exact matching is strict. It gives zero score when labels differ in granularity:

```text
Ground-truth: pneumonia NEW
Generated: lung_opacity NEW
```

Even though pneumonia can be expressed radiographically as an opacity, exact matching treats them as different labels. Hierarchical LDC-F1 provides partial matching to account for this granularity mismatch.

### 16.3 Required Safety Rule

Partial match is allowed only when the transition is the same.

Examples:

| Ground-truth | Generated | Hierarchical match allowed? |
|---|---|---:|
| `(pneumonia, NEW)` | `(lung_opacity, NEW)` | yes, if hierarchy/projection relation exists |
| `(pneumonia, NEW)` | `(lung_opacity, RESOLVED)` | no |
| `(edema, RESOLVED)` | `(lung_opacity, RESOLVED)` | yes, if hierarchy/projection relation exists |
| `(edema, RESOLVED)` | `(lung_opacity, NEW)` | no |

### 16.4 Relation Types

The current code supports these relation types:

| Relation type | Code key | Fallback weight in code | Recommended paper use |
|---|---|---:|---|
| exact or synonym | `exact_or_synonym` | 1.0 | use |
| same CheXpert projection | `chexpert_projection_equivalent` | 0.8 | use carefully |
| parent-child relation | `parent_child_same_transition` | 0.5 | use as support |
| same group | `same_group_same_transition` | 0.25 | risky, consider 0 or appendix only |
| unrelated | `unrelated` | 0.0 | use |

### 16.5 Weight Risk

The partial matching weights are not learned. They are predefined in configuration.

Risk:

```text
Changing parent-child weight from 0.5 to 0.7 can change Hierarchical LDC-F1.
```

Therefore:

- Do not use Hierarchical LDC-F1 as primary metric.
- State weights are fixed before evaluation.
- Do not tune weights based on model outputs.
- Prefer Exact LDC-F1 for all main conclusions.
- If Hierarchical LDC-F1 is included in the paper, provide sensitivity analysis or appendix table.

### 16.6 Literature Grounding for Hierarchical Matching

Hierarchical matching can be justified as a label-granularity support metric if based on established radiology terminology resources.

Potential grounding:

1. PadChest-style hierarchical taxonomy  
   Chest X-ray labels can be organized as radiographic findings, diagnoses, and anatomical locations in hierarchical or standardized terminology structures.

2. RadLex / UMLS controlled terminology  
   Radiology terminology resources support synonym normalization and concept-level mapping.

3. Chest ImaGenome-style CXR ontology  
   CXR-specific ontology and image-grounded scene graph resources provide precedents for structured radiographic finding representation and longitudinal comparison relations.

Recommended paper wording:

```text
Hierarchical LDC-F1 is reported as a supportive metric to account for label granularity mismatch among radiographic findings. Partial matching is allowed only when the longitudinal transition is identical and the finding labels are related by pre-defined synonym, projection-equivalent, or parent-child relations. Because the partial weights are pre-defined rather than learned, all main conclusions are based on Exact LDC-F1.
```

---

## 17. Current Code Behavior Checklist

Based on the provided code package:

### 17.1 Projection Behavior

File:

```text
src/cxr_ldc_eval/longitudinal_projection.py
```

Current relevant constants:

```python
DIFFERENCE_PRESENCE_CLASSES = ("NEW", "RESOLVED", "PRESENT_BOTH")
LEVEL_DIRECTION_CLASSES = ("WORSENED", "IMPROVED", "SAME_LEVEL", "LEVEL_CHANGED_UNSPECIFIED")
SEVERITY_PRESENT_BOTH_SOURCES = (
    "WORSENED",
    "IMPROVED",
    "SAME_LEVEL",
    "LEVEL_CHANGED_UNSPECIFIED",
)
```

Current behavior:

```text
qtype == "difference":
    presence NEW/RESOLVED/PRESENT_BOTH -> primary tuple
    severity WORSENED/IMPROVED/SAME_LEVEL/LEVEL_CHANGED_UNSPECIFIED -> PRESENT_BOTH

qtype == "level":
    severity WORSENED/IMPROVED/SAME_LEVEL/LEVEL_CHANGED_UNSPECIFIED -> primary tuple
```

This behavior matches the final intended design.

### 17.2 Metrics Behavior

File:

```text
src/cxr_ldc_eval/longitudinal_metrics.py
```

Current exact metrics:

- `Exact LDC-F1`: exact matching over primary tuples.
- `Ontology Change F1`: currently duplicate of Exact LDC-F1. Should be removed or ignored in paper.
- `Change-Presence F1`: accumulated when `primary_axis == presence_transition`.
- `Level-Direction F1`: accumulated when `primary_axis == severity_transition`.

### 17.3 Matching Behavior

File:

```text
src/cxr_ldc_eval/longitudinal_matching.py
```

Current matching behavior:

- exact matching requires same axis, same entity, same value.
- hierarchical matching requires same axis and same value before partial entity relation is considered.
- one-to-one maximum weight matching is used to prevent duplicate credit.

This behavior is good and should be retained.

---

## 18. Recommended Code Adjustments

These are recommended but not all are mandatory.

### 18.1 Must Have for Paper Evaluation

#### A. Strict Query Availability Check

Problem:

If question text is unavailable, current code defaults to `difference`. This can incorrectly evaluate explicit level-comparison queries as broad Difference queries.

Recommendation:

```text
For paper experiments, require question text to be loaded.
```

Implementation request:

```text
Add require_questions=True option. If query text is missing for any evaluated sample, either raise an error or explicitly report and exclude those samples from axis-specific analysis.
```

Diagnostics to report:

```text
questions_loaded
questions_missing
broad_difference_query_count
explicit_level_query_count
location_conditioned_difference_query_count
```

#### B. Report Denominators

Always report counts for:

```text
primary generated claim count
primary ground-truth claim count
presence claim count
level claim count
severity tuple count
no-change sample count
presence contradiction denominator
severity contradiction denominator
```

### 18.2 Should Have

#### A. Rename or Hide Redundant Metric

Current code returns:

```text
Ontology Change F1 = Exact LDC-F1
```

Recommendation:

```text
Remove Ontology Change F1 from paper-facing output or keep only as alias in logs.
```

#### B. N/A Handling for Empty Denominator

Current `safe_div` returns 0.0 when denominator is 0.

For paper-facing tables:

```text
If denominator == 0, report N/A instead of 0.0.
```

This is especially important for Level-Direction F1 if no explicit level-comparison query exists.

### 18.3 Optional

#### A. Hierarchical Sensitivity Analysis

If Hierarchical LDC-F1 is included:

```text
Run sensitivity with same_group weight = 0.
Optionally run parent_child weight in {0.25, 0.5, 0.75}.
Confirm model ranking is not primarily driven by hierarchical weights.
```

#### B. Simplify Severity Contradiction

Current code includes SAME_LEVEL-related contradictions. If the paper wants a narrower definition, use only:

```text
WORSENED <-> IMPROVED
```

This is cleaner but changes current metric. If code is not changed, define the broader contradiction set explicitly.

---

## 19. Recommended Paper Structure for Metrics

### 19.1 Method Section

Recommended subsections:

```text
3.1 Task Definition
3.2 Longitudinal Claim Extraction
3.3 Exact Disease-Change Matching
3.4 Evaluation Metrics
```

Optional:

```text
3.5 Hierarchical Matching for Supportive Analysis
```

Do not create a long standalone Evaluation Protocol section unless needed. A pipeline figure plus a short paragraph is enough.

### 19.2 Pipeline Figure

Recommended figure flow:

```text
Ground-truth answer ─┐
                     ├─ Text normalization
Generated answer ────┘
        ↓
Alias normalization
        ↓
Longitudinal claim extraction
        ↓
Query-aware primary transition mapping
        ├─ broad Difference: NEW / RESOLVED / PRESENT_BOTH
        └─ explicit level query: WORSENED / IMPROVED / SAME_LEVEL / LEVEL_CHANGED_UNSPECIFIED
        ↓
Exact disease-change matching
        ↓
Exact LDC-F1
        ↓
Supporting and error analysis metrics
```

### 19.3 Main Result Table

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

### 19.4 Breakdown Table

Recommended columns:

```text
Model
Change-Presence F1
# presence GT claims
Level-Direction F1
# level GT claims
```

If no explicit level query exists:

```text
Level-Direction F1 = N/A
```

### 19.5 Error Analysis Table

Recommended columns:

```text
Model
Hallucinated Disease-Change Rate
Omission Rate
Presence Contradiction Rate
Explicit Severity Contradiction Rate
NoChange-Acc
```

### 19.6 Supplementary Table

Recommended columns:

```text
Model
Hierarchical LDC-F1
partial matching weight setting
sensitivity setting if available
```

---

## 20. Codex Implementation Request Template

Use this when asking Codex to adjust the evaluator.

```text
Please update the longitudinal Difference VQA evaluator according to the following paper-facing metric policy.

Scope:
- Evaluate Medical-Diff-VQA Difference subset only.
- Compare generated answer text with ground-truth answer text.
- Apply the same rule-based claim extractor to both.

Primary metric:
- Use Exact LDC-F1 as the main metric.
- Exact match requires same canonical clinical finding and same query-aware primary transition.

Query-aware primary transition policy:
- Broad Difference queries use presence-transition primary axis:
  NEW, RESOLVED, PRESENT_BOTH.
- In broad Difference queries, explicit severity transitions WORSENED, IMPROVED, SAME_LEVEL, LEVEL_CHANGED_UNSPECIFIED should map to PRESENT_BOTH for primary scoring.
- Explicit level-comparison queries use severity-transition primary axis:
  WORSENED, IMPROVED, SAME_LEVEL, LEVEL_CHANGED_UNSPECIFIED.
- Severity information from broad Difference queries should still be retained in severity_tuples for explicit severity contradiction analysis.

Paper-facing metric outputs:
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
- Hierarchical LDC-F1 as support/supplementary only

Remove or hide redundant/legacy names from paper-facing output:
- FC-F1_micro
- FC-F1_macro
- Finding-Only F1
- FOF1
- Ontology Change F1

Strict query handling:
- Add require_questions=True for paper evaluation.
- If query text is missing, raise an error or report missing count and mark level-specific analysis invalid.
- Report diagnostics: broad Difference query count, explicit level query count, location-conditioned Difference query count, presence GT claim count, level GT claim count, no-change sample count.

N/A handling:
- If a metric denominator is zero, return N/A in paper-facing summaries rather than 0.0.

Hierarchical LDC-F1:
- Keep exact matching as primary.
- Use hierarchical matching only as support/supplementary.
- Do not tune partial matching weights on model outputs.
- Prefer sensitivity analysis if hierarchical scores are reported.

Do not change broad Difference scoring to directly penalize WORSENED/IMPROVED omissions. Severity direction directly affects the primary score only for explicit level-comparison queries.
```

---

## 21. Method Wording Draft

### 21.1 Exact LDC-F1 Claim

```text
We use Exact LDC-F1 as the primary metric. Each generated and ground-truth answer is converted into a set of disease-change claims, where each claim consists of a canonical clinical finding and a query-aware longitudinal transition. A generated claim is counted as correct only when both the finding and transition match the ground-truth claim exactly.
```

### 21.2 PRESENT_BOTH Rationale

```text
For broad Difference queries, severity expressions such as worsened or improved are projected to PRESENT_BOTH in the primary presence-transition space. This design reflects the fact that broad change questions primarily require identifying findings that are newly present, resolved, or present in both time points, while report-derived severity comparisons are not always consistently available or explicitly required. Explicit severity directions are therefore evaluated directly only when the query asks for level comparison, and otherwise retained for contradiction analysis.
```

### 21.3 Hierarchical LDC-F1 Wording

```text
In addition to Exact LDC-F1, we report Hierarchical LDC-F1 as a supportive metric to account for label granularity mismatch. Hierarchical matching allows partial credit only when the longitudinal transition is identical and the clinical finding labels are related by pre-defined synonym, projection-equivalent, or parent-child relations. Because partial weights are pre-defined rather than learned, all main conclusions are based on Exact LDC-F1.
```

### 21.4 Supporting Metrics Wording

```text
Entity-level F1 and Direction Accuracy are reported to separate disease mention performance from transition consistency. Change-Presence F1 and Level-Direction F1 provide axis-specific breakdowns for broad change and explicit level-comparison queries, respectively. Hallucinated Disease-Change Rate, Omission Rate, Presence Contradiction Rate, Explicit Severity Contradiction Rate, and NoChange Accuracy are used for failure mode analysis.
```

---

## 22. Final Recommended Metric Set

### Main

```text
Exact LDC-F1
```

### Supporting

```text
Ontology Entity F1
Direction Accuracy
Hierarchical LDC-F1
```

### Breakdown

```text
Change-Presence F1
Level-Direction F1
```

### Error Analysis

```text
Hallucinated Disease-Change Rate
Omission Rate
Presence Contradiction Rate
Explicit Severity Contradiction Rate
NoChange-Acc
```

### Remove or Do Not Report in Main Paper

```text
FC-F1_micro
FC-F1_macro
Finding-Only F1
FOF1
Ontology Change F1
```

---

## 23. Final Sanity Checklist Before Running Experiments

Before generating final tables, verify:

- [ ] Query text is loaded for all samples.
- [ ] `questions_missing == 0` or missing samples are explicitly handled.
- [ ] Broad Difference query count is reported.
- [ ] Explicit level-comparison query count is reported.
- [ ] Presence-transition claim count is reported.
- [ ] Level-direction claim count is reported.
- [ ] No-change sample count is reported.
- [ ] Exact LDC-F1 is used for primary comparison.
- [ ] Hierarchical LDC-F1 is not used as the main conclusion.
- [ ] `Ontology Change F1` duplicate output is not included in paper tables.
- [ ] Metrics with zero denominator are shown as N/A, not 0.0.
- [ ] Parser validation or manual spot-check is performed for a sample of generated/ground-truth answer pairs.

