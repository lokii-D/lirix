# `scripts/` — Mantle harness tooling

## SSOT sync (no manual copy)

Harness entrypoints are **edited only in `mantle_TT/`**:

| SSOT (edit here) | Root mirror (auto-synced) |
| --- | --- |
| `mantle_TT/README_submission.md` | `README_submission.md` |
| `mantle_TT/app.py` | `app.py` |

`validate_harness.sh` and `full_dry_run.sh` call `sync_submission_entrypoints.sh` first.
Root copies are gitignored duplicates for pack/lint — do not edit them by hand.

```bash
bash scripts/sync_submission_entrypoints.sh   # manual sync if needed
```

## Judge priority path (start here)

| Step | Time | Command / link |
| --- | --- | --- |
| 1. **Understand** | 30 sec | Read [`mantle_TT/README_submission.md`](../mantle_TT/README_submission.md) — award landing page |
| 2. **See it live** | 30 sec | https://huggingface.co/spaces/lokiii07/lirix-mantle-harness |
| 3. **Verify on-chain** | 2 min | [Proof tx](https://sepolia.mantlescan.xyz/tx/0xa23bb06ad14518ea7418082caef761cf864548a6705e8a2682b08c6cd69b055a) |
| 4. **Reproduce locally** | 3 min | `./scripts/full_dry_run.sh` |

Evidence layers (public / in-repo / pending): [`mantle_TT/external_evidence.md`](../mantle_TT/external_evidence.md)

## Scripts

| Script | Purpose |
| --- | --- |
| `sync_submission_entrypoints.sh` | Mirror `mantle_TT/` → root (`README_submission.md`, `app.py`) |
| `full_dry_run.sh` | One-shot validate + pack — **judge reproducibility entry** |
| `validate_harness.sh` | Bundle checks → **Mantle-only** pytest (`tests/mantle`, addopts overridden) → ruff → black |
| `pack_bundle.sh` | Build `dist/mantle-turing-2026-harness.tar.gz` |

## Local setup (before dry-run)

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -U pip wheel
python -m pip install -e .
python -m pip install -r requirements_submission.txt
```

## Submission package

Self-contained bundle: [`mantle_TT/`](../mantle_TT/README_submission.md)

```bash
streamlit run mantle_TT/app.py
bash mantle_TT/scripts/validate_harness.sh
```

## If something fails

| Failure | Likely fix |
| --- | --- |
| `Missing bundle inputs` | Run from repo root; ensure harness branch is checked out |
| `pytest` errors | `pip install -r requirements_submission.txt` |
| `ruff` / `black` errors | `pip install -r requirements_submission.txt` then re-run |
| `No module named pytest` | Activate venv; install submission requirements |
