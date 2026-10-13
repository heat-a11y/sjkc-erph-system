# Working Rules

Every time we build, follow the SDD → DDD → TDD cycle for any feature or fix
in this workspace:

1. **SDD (Spec-Driven)** — identify/read the spec first (e.g. `docs/SPEC.md`,
   official papers/docs); it is the contract. If behaviour changes, update the
   spec in the same change.
2. **DDD (Domain-Driven)** — change the domain model first (models, data pools,
   generation rules); keep every renderer/consumer in sync afterwards.
3. **TDD (Test-Driven)** — write the failing test BEFORE the feature code.
   Cover new behaviour, regression paths, and hermetic/offline behaviour. Then
   implement, then run the full suite.

## Mandatory verification before finishing ANY task

1. Run the project's test suite — ALL green.
2. Run end-to-end smoke tests / CLI invocations to confirm real-world output.
3. Confirm any errors from earlier are fixed (no regressions).