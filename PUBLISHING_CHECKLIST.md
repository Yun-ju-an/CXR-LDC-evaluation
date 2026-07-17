# Publishing Checklist

## Rights and attribution

- [ ] Confirm authorship/provenance for every file in the release manifest.
- [ ] Obtain authorization to distribute all code, config, and protocol text.
- [ ] Select and add an approved `LICENSE`.
- [ ] Add license metadata to `pyproject.toml`.
- [ ] Replace placeholders in `CITATION.cff.template`, rename it to `CITATION.cff`, and validate it.
- [ ] Add third-party notices if required.

## Scope and privacy

- [ ] Confirm there are no dataset rows, images, identifiers, clinical narratives, model artifacts, or absolute workstation paths.
- [ ] Confirm only aggregate/template Query/Answer evidence is documented.
- [ ] Confirm the dataset agreement and institutional policy permit template aggregates and small-cell counts; collapse rare cells if required.
- [ ] Remove `*.orig`, `*.rej`, caches, build products, and local outputs.
- [ ] Inspect `git diff --cached` and the final archive contents.
- [ ] Run a secret scanner approved by the institution.

## Protocol

- [ ] Confirm location-conditioned `what has changed` still routes to `level`.
- [ ] Confirm the JSON config is the released source of truth.
- [ ] Confirm Exact LDC-F1, hierarchy matching, contradiction rules, and zero-denominator handling match the paper.
- [ ] Record the config and protocol-document SHA-256 values used for reported results.
- [ ] Report CXR-primary and All-31 auxiliary views separately.

## Validation

- [ ] Install in a clean Python 3.9+ environment.
- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Run `python -m py_compile src/cxr_ldc_eval/*.py`.
- [ ] Run `ldc-eval validate-config`.
- [ ] Run the synthetic records example and inspect all outputs.
- [ ] Verify overwrite protection, default no-claims behavior, `--write-claims` opt-in, and stale-claims refusal.
- [ ] Confirm GitHub Actions passes.
