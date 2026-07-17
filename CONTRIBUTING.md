# Contributing

Open an issue before changing the paper-facing protocol.

Keep changes small and config-driven. Disease labels, aliases, hierarchy, transitions, question routing, projection mappings, and contradiction pairs belong in the JSON config, with matching regression tests.

A contribution should state:

- the intended protocol effect;
- whether reported numbers can change;
- the config and code files touched;
- a synthetic regression case;
- commands run and validation status.

Do not submit dataset rows, clinical text, patient/study identifiers, model weights, checkpoints, predictions, or claim dumps. Use invented examples only.

Before contributing, confirm that the repository has completed its license review. Until then, this release candidate grants no redistribution permission.
