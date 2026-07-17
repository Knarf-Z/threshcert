# Independent extended experiments

This directory contains only the three requested additions:

1. scalability and certificate-computation cost;
2. threshold, resistance-distribution, and initial-exposure sensitivity;
3. simple baseline comparisons.

It is intentionally separate from the original artifact. Running this
directory does not rerun or overwrite the original certificate, Möbius, Dune,
deployment, or Chiado experiments.

From the artifact root, run:

```bash
python extended_experiments/reproduce_extended.py
```

The final line is:

```text
extended_experiments=PASS
```

## Inputs

- `inputs/solver_scaling_repeats_summary.csv` is a frozen copy of the summary
  computed from the ten previously recorded laptop benchmark runs. The extended
  runner reads this copy; it does not repeat the expensive exact solver runs.
- `inputs/scaling_environment.json` records the machine and Python environment
  associated with those measurements.
- Resistance profiles and sensitivity parameters are declared directly in
  `scripts/run_extended_certificate_experiments.py`.

## Outputs

- `results/scalability_analysis.csv`: measured `n=8` through `n=18` scaling,
  including median runtime, inclusive IQR, range-derived inputs, memory, and
  state-normalized costs.
- `results/certificate_cost_models.csv`: sorting versus generic subset-state
  operation growth for committee sizes through `n=448`.
- `results/parameter_sensitivity.csv`: 48 controlled combinations of four
  thresholds, four equal-mean resistance shapes, and three initial-exposure
  levels.
- `results/baseline_comparison.csv`: public-only, minimum-member-floor, exact
  lower-tail, and mean-resistance heuristic comparisons.

## Interpretation boundary

The resistance profiles are controlled inputs, not observed production Keyper
resistance. The mean-resistance heuristic is explicitly marked uncertified.
The runtime values belong to the recorded laptop implementation; the larger
committee-size table is a complexity-model comparison rather than a measured
runtime claim.
