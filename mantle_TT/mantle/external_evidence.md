# External Evidence (Canonical Tracker)

This file is the single source of truth for **public, verifier-facing evidence**.
Only mark an item complete when a real URL or hash is available. Do not treat plans or placeholders as done.

## Verified (submitter-provided, public)

| Item | Status | Link |
| --- | --- | --- |
| GitHub repository | Done | https://github.com/lokii-D/lirix |
| Mantle harness branch | Done | https://github.com/lokii-D/lirix/tree/mantle-turing-2026-harness |
| Pin commit (this packet) | Done | https://github.com/lokii-D/lirix/commit/6a87c0fadbbdc4b9f2cb1508b618dfc7d008ef2b |

## Pending (mandatory for final DoraHacks score — submitter must supply)

| Item | Status | Notes |
| --- | --- | --- |
| Hugging Face Spaces / public demo URL | Pending | Add URL when deployed and reachable without login |
| On-chain proof (tx hash) | Pending | Add Mantle explorer link + one-line description of what was called |
| Contract verification (optional) | Pending | Only if claiming deployment award |

## In-package reproducibility (not a substitute for rows above)

```bash
bash mantle_TT/scripts/validate_bundle.sh    # expect: bundle-ok
bash mantle_TT/scripts/validate_harness.sh   # bundle + pytest + ruff + black
bash mantle_TT/scripts/run_mantle_demo.sh    # malicious → repair → safe
bash mantle_TT/scripts/pack_bundle.sh        # dist/mantle_TT_submission_bundle.tar.gz
```
