# Contributing to Lirix

Lirix welcomes contributions from people who respect deterministic systems, security boundaries, and production-grade engineering discipline. We are friendly, but we are exacting: if a change weakens the trust model, slips on quality, or introduces ambiguity, it will not be merged.

## The 1000% Standard

Every pull request must satisfy all of the following before review can proceed:

- `pytest` must pass at 100% for the touched surface, with no regression in overall coverage.
- `mypy` must pass in strict mode.
- `black` must pass with no formatting drift.
- `ruff` must pass with zero lint violations.
- Changes must preserve the Zero-Key, Zero-Telemetry, Zero-Trust boundary.
- Any behavior change must be accompanied by tests that prove the new behavior and protect the old one.
- Pull requests that break CLI idempotency are auto-rejected, including any change that causes `lirix init` to corrupt, overwrite, or leak `.env` files.
- Pull requests that weaken L4 BFT concurrency guarantees are auto-rejected, including any change that fails strict async-mocking coverage for HTTP 429 handling, timeouts, and retry-safe failure paths.
- Release-facing documentation must stay synchronized with the published version, including v1.6.0 terminology, examples, and user-facing wording.

If a PR misses any of these requirements, it is auto-rejected until corrected.

## PR Lifecycle

The expected workflow is intentionally simple:

1. **Fork** the repository.
2. **Create a feature branch** with a narrow, reviewable scope.
3. **Implement and test** the change locally.
4. **Run the full validation suite** before opening the PR.
5. **Request review** only after the branch is clean and reproducible.

Suggested validation commands:

```bash
black .
ruff check .
mypy .
pytest
pytest tests/test_v15_cli_ignition.py tests/test_v15_intelligence.py tests/test_quorum_bft.py tests/test_v15_vivisection_e2e.py
anvil
```

If your change affects the L5 path, run the relevant Foundry / Anvil-backed integration tests as well.

## Quality Expectations

We review for more than correctness. We also look for:

- Clear, deterministic behavior
- Strong typing and explicit failure modes
- Security-aware edge cases
- Minimal, readable diffs
- Documentation updates when user-facing behavior changes

We prefer a smaller change that is correct over a larger change that is clever.

## What We Do Not Merge

Do not submit code that:

- Handles private keys inside the library
- Adds hidden telemetry or analytics
- Introduces non-deterministic safety checks
- Weakens validation to make tests pass faster
- Bypasses strict typing or formatting rules
- Relaxes security boundaries without a compelling, reviewed design
- Breaks `lirix init` path confinement, environment isolation, or `.env` hygiene
- Reduces the resilience of L4 quorum selection under concurrent retries, 429 responses, or timeout conditions

## Recommended Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

curl -L https://foundry.paradigm.xyz | bash
foundryup
anvil

pytest
pytest tests/test_v15_cli_ignition.py tests/test_v15_intelligence.py tests/test_quorum_bft.py tests/test_v15_vivisection_e2e.py
```

If you are touching documentation, preserve the project’s bilingual clarity and keep the technical tone sharp, precise, and consistent.
