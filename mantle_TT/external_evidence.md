# External Evidence — Lirix 2.0.4 Mantle Submission

Single source of truth for judge-facing evidence.
**Three layers** — do not mix public URLs with in-repo paths in the same table.

---

## 1. Public external evidence

Verifier clicks these **without cloning the repo**. Every row must be a real public URL or on-chain hash.

| Item | Value |
| --- | --- |
| GitHub repository | https://github.com/lokii-D/lirix |
| Mantle harness branch | https://github.com/lokii-D/lirix/tree/mantle-turing-2026-harness |
| Hugging Face Spaces demo | https://huggingface.co/spaces/lokiii07/lirix-mantle-harness |
| LirixShield contract (Mantlescan) | https://sepolia.mantlescan.xyz/address/0x844cd69eADcc097F759FBf76C2d9735A55A9635c |
| LirixShield contract (alias) | https://explorer.sepolia.mantle.xyz/address/0x844cd69eADcc097F759FBf76C2d9735A55A9635c → Mantlescan |
| LirixShield address | `0x844cd69eADcc097F759FBf76C2d9735A55A9635c` |
| On-chain proof tx (Mantlescan) | https://sepolia.mantlescan.xyz/tx/0xa23bb06ad14518ea7418082caef761cf864548a6705e8a2682b08c6cd69b055a |
| On-chain proof tx hash | `0xa23bb06ad14518ea7418082caef761cf864548a6705e8a2682b08c6cd69b055a` |
| Mantle Sepolia RPC | `https://rpc.sepolia.mantle.xyz` |
| Mantle Sepolia explorer (canonical) | `https://sepolia.mantlescan.xyz` |
| Mantle Sepolia explorer (alias) | `https://explorer.sepolia.mantle.xyz` (redirects) |
| **Demo video (2–3 min)** | https://youtu.be/16Oa0ur-NFk |

---

## 2. In-repo reproducibility evidence

Verifier **clones the repo** and reproduces these locally. Paths and commands — not public URLs.

| Item | How to verify |
| --- | --- |
| Submission screenshots (5 PNG) | [`../docs/submission_assets/`](../docs/submission_assets/) (repo root — canonical) |
| Streamlit judge UI | `streamlit run mantle_TT/app.py` (or root `app.py`) |
| CLI demo path | `python mantle_TT/examples/mantle_defi_demo.py` |
| Full harness dry-run | `./scripts/full_dry_run.sh` from repository root |
| Mantle_TT package validation | `bash mantle_TT/scripts/validate_harness.sh` |
| Mantle test slice | `python -m pytest tests/mantle -q -o addopts=` (root `validate_harness.sh` uses this) |
| Lint / format gate | `ruff check` + `black --check` (run inside `validate_harness.sh`) |
| Submission tarball | `./scripts/full_dry_run.sh` → `dist/mantle-turing-2026-harness.tar.gz` |
| Dependency pin list | `requirements_submission.txt` |
| Env template (public addresses) | `.env.example` (`LIRIX_SHIELD_CONTRACT`, `ON_CHAIN_PROOF_TX`) |

---

## 3. Pending artifacts

None at this time — all submission artifacts are published.

---

## Evidence policy

- Layer 1 rows are **only** public URLs / on-chain hashes
- Layer 2 rows are **only** in-repo paths and reproduction commands
- Layer 3 rows stay **TODO** until real artifacts ship
- Presentation mode in `app.py` does not claim on-chain execution unless a real `tx_hash` is in the payload JSON

## Related docs

- Mantle packet mirror: [`mantle/external_evidence.md`](mantle/external_evidence.md)
- Root landing page: [`../README_submission.md`](../README_submission.md)
- Screenshot index: [`../docs/submission_assets/README.md`](../docs/submission_assets/README.md)
