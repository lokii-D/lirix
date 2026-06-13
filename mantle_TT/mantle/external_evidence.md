# External Evidence (Canonical Tracker)

This file is the single source of truth for **public, verifier-facing evidence**.
Only mark an item complete when a real URL or hash is available. Do not treat plans or placeholders as done.

## Verified (submitter-provided, public)

| Item | Status | Link |
| --- | --- | --- |
| GitHub repository | Done | https://github.com/lokii-D/lirix |
| Mantle harness branch | Done | https://github.com/lokii-D/lirix/tree/mantle-turing-2026-harness |
| Hugging Face Spaces demo | Done | https://huggingface.co/spaces/lokiii07/lirix-mantle-harness |
| Deployed contract (Mantle Sepolia) | Done | https://explorer.sepolia.mantle.xyz/address/0x844cd69eADcc097F759FBf76C2d9735A55A9635c |
| Mantle Sepolia RPC | Done | https://rpc.sepolia.mantle.xyz |

## Phase 0 — evidence collection (complete before packaging)

| Item | Status | Notes |
| --- | --- | --- |
| Demo video (2–3 min) | Pending | URL will be added after recording — do not use placeholder links |
| On-chain proof (tx hash) | Pending | Add deploy or `validateAndExecute` tx hash when available |
| Submission screenshots | Pending | Add PNGs under `docs/submission_assets/` (see README there) |

## Phase 1 — optional hardening / verifier extras

| Item | Status | Notes |
| --- | --- | --- |
| Contract verification | Pending | Only if claiming deployment award |
| Additional public artifacts | Pending | Add any extra verifier-facing URLs or hashes here if they are real and public |

## In-package reproducibility (not a substitute for rows above)

```bash
./scripts/full_dry_run.sh                         # validate + pack (root SSOT)
bash mantle_TT/scripts/validate_harness.sh        # mantle_TT bundle + pytest + lint
bash mantle_TT/scripts/run_mantle_demo.sh         # malicious → repair → safe
bash mantle_TT/scripts/pack_bundle.sh             # dist/mantle_TT_submission_bundle.tar.gz
```
