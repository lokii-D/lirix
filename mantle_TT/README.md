# Lirix 2.0.4 — Mantle Submission Package

<div align="center">

**Mantle AI Agent Security Guardian**

fail-closed · L1–L5 linear DAG · SHA-256 evidence chain · **Mantle Sepolia verified**

[![HF Spaces Demo](https://img.shields.io/badge/Demo-Hugging%20Face-yellow?style=flat-square)](https://huggingface.co/spaces/lokiii07/lirix-mantle-harness)
[![Contract](https://img.shields.io/badge/Contract-Mantle%20Sepolia-blue?style=flat-square)](https://sepolia.mantlescan.xyz/address/0x844cd69eADcc097F759FBf76C2d9735A55A9635c)

</div>

## 30-second story

Lirix 2.0.4 is a **fail-closed** orchestration layer between untrusted AI agent payloads and Mantle execution. Every intent traverses a **L1–L5 linear DAG** — intent gate, schema validation, DeFi calldata parsing, RPC quorum, and shadow simulation — with a **SHA-256 evidence chain** at each stage. Unsafe payloads earn **BLOCKED (fail-closed protection activated)**; safe payloads earn **SAFE TO EXECUTE ON MANTLE**.

**Judges:** [`README_submission.md`](README_submission.md) → `streamlit run mantle_TT/app.py` → [`external_evidence.md`](external_evidence.md).

## Quick start

```bash
# From repository root
python -m pip install -e .
python -m pip install streamlit pytest

# Interactive presentation (recommended for judges)
streamlit run mantle_TT/app.py

# Validate this package
bash mantle_TT/scripts/validate_harness.sh
```

**Docker:**

```bash
docker compose -f mantle_TT/docker-compose.yml up --build
```

## What to open first

| Order | File | Why |
| --- | --- | --- |
| 1 | [`README_submission.md`](README_submission.md) | Submit-ready one-pager |
| 2 | [`app.py`](app.py) | Streamlit L1–L5 interactive demo |
| 3 | [`external_evidence.md`](external_evidence.md) | Verifiable links & three-layer evidence tracker |
| 4 | [`mantle/submission_one_pager.md`](mantle/submission_one_pager.md) | Technical depth summary |
| 5 | [`examples/mantle_defi_demo.py`](examples/mantle_defi_demo.py) | CLI malicious → safe path |

## Package layout

- `app.py` — judge-facing Streamlit UI (stories, pipeline DAG, final decision)
- `contracts/LirixShield.sol` — on-chain shield contract source
- `mantle/` — canonical judge packet (architecture, checklist, evidence)
- `scripts/` — validate, demo, pack
- `tests/` — Mantle bundle verification tests

## Evidence policy

- No fabricated transaction hashes or explorer links
- No placeholder URLs marked as verified
- Pending items use explicit `TODO` markers — see [`external_evidence.md`](external_evidence.md)

## Links

| Resource | URL |
| --- | --- |
| GitHub | https://github.com/lokii-D/lirix |
| Harness branch | https://github.com/lokii-D/lirix/tree/mantle-turing-2026-harness |
| HF Spaces demo | https://huggingface.co/spaces/lokiii07/lirix-mantle-harness |
| LirixShield (Sepolia) | https://sepolia.mantlescan.xyz/address/0x844cd69eADcc097F759FBf76C2d9735A55A9635c |
| On-chain proof tx | https://sepolia.mantlescan.xyz/tx/0xa23bb06ad14518ea7418082caef761cf864548a6705e8a2682b08c6cd69b055a |
| Screenshots | [`../docs/submission_assets/`](../docs/submission_assets/) |
| Demo video | https://youtu.be/16Oa0ur-NFk |
