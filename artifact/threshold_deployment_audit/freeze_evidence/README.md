# Frozen-plan commit evidence

The audit cohort and policy were committed before result generation as
`bd58e0ec733c43d215110349f91cc31ec303b0ab`. This directory preserves two
independent representations:

- `frozen_plan_bd58e0e.bundle`: a complete Git bundle whose advertised head is
  the frozen-plan commit;
- `commit.bd58e0e.raw`: the exact raw Git commit object.

The paper driver runs `../verify_freeze_evidence.mjs`, which recomputes the Git
object SHA-1, checks the frozen tree identifier, and confirms that the bundle
header advertises the same commit. If Git is installed, the bundle can also be
inspected directly:

```text
git bundle verify frozen_plan_bd58e0e.bundle
git clone -b artifact-freeze-plan-v46 frozen_plan_bd58e0e.bundle frozen-plan
git -C frozen-plan show --stat bd58e0ec733c43d215110349f91cc31ec303b0ab
```

The commit proves only an author-controlled same-day freeze. It is not an
independent preregistration timestamp and does not remove the selection-bias
limitations recorded in `../cohort.v1.json`.
