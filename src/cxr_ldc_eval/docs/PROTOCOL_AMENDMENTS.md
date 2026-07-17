# Protocol Amendments for v0.1.1

Date: 2026-07-17  
Applies to: CXR LDC Eval 0.1.1 and config 0.1.1

This document supersedes only the conflicting statements identified below. All unaffected ontology and metric definitions in the 2026-05-26 rules and mapping guideline remain historical protocol context.

## A1. Location-conditioned “what has changed” is Level

Runtime rule:

```text
what has changed compared to the reference image?  -> difference
what has changed in the left/right/... area?       -> level
```

An anatomic scope attached to the `what has changed` family selects the Level profile. Its primary tuple is `(entity, severity_transition)`.

This supersedes:

- examples in Sections 2 and 3.1 of `difference_vqa_evaluation_rules_20260526.md` that grouped a right-lung-area question with broad Difference;
- Section 8.1 and related diagnostic wording in `difference_vqa_evaluation_mapping_guideline_v2_20260526.md` that grouped right/left/bibasilar-area questions with broad Difference.

The JSON `question_routing.location_conditioned_difference` object is the runtime source of truth.

### Evidence supporting the project decision

In the inspected valid and test evaluation splits:

- 362 of 32,761 questions were location-conditioned `what has changed` variants;
- all 362 reference answers were Level-only under the configured grammar;
- each contained one mapped entity;
- directions were 175 WORSENED, 165 IMPROVED, 22 SAME_LEVEL, and 0 direction-unspecified.

Only aggregate/template evidence is recorded. No source row or identifier is distributed.

## A2. Zero denominators

A paper-facing metric with denominator zero is undefined. JSON serializes it as `null`; Markdown and CLI render `N/A`. It must not be interpreted as zero performance.

## A3. No-change eligibility

`NoChange-Acc` uses references with an explicit global no-change statement. Empty primary tuples caused only by ontology-view filtering or extraction failure do not enter its denominator.

A separate config-driven Global No-Change Contradiction Rate detects:

- explicit reference global no-change versus nonempty predicted primary claims;
- nonempty reference primary claims versus explicit predicted global no-change.

## A4. Reproducibility effect

These amendments can change question counts, axis-specific denominators, and reported scores relative to the historical v0.1.0 implementation. Paper-facing results must record evaluator/config version 0.1.1 and rerun all compared systems under the same release.
