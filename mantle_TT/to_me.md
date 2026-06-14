# To Mantle Turing Test Judges

**Project:** Lirix 2.0.4 — Mantle AI Agent Security Guardian
**Track:** AI DevTools / Agentic Economy
**Harness branch:** https://github.com/lokii-D/lirix/tree/mantle-turing-2026-harness

---

## 30-second pitch

Lirix is the **fail-closed execution airlock** between untrusted AI agent payloads and Mantle. Every intent traverses **L1–L5** (intent, schema, DeFi calldata, RPC quorum, simulation) before any signer handoff. Unsafe payloads earn **BLOCKED**; safe payloads earn **SAFE TO EXECUTE ON MANTLE** — with a **SHA-256 evidence chain** and on-chain **LirixShield** anchor.

---

## Where to start (recommended order)

| Step | Time | Action |
| --- | --- | --- |
| 1 | 30 sec | Read [`README_submission.md`](README_submission.md) |
| 2 | 30 sec | Open [HF Spaces demo](https://huggingface.co/spaces/lokiii07/lirix-mantle-harness) → **Malicious** → **Run L1–L5** |
| 3 | 2 min | Verify [LirixShield on Mantlescan](https://sepolia.mantlescan.xyz/address/0x844cd69eADcc097F759FBf76C2d9735A55A9635c) + [proof tx](https://sepolia.mantlescan.xyz/tx/0xa23bb06ad14518ea7418082caef761cf864548a6705e8a2682b08c6cd69b055a) |
| 4 | 3 min | From repo root: `./scripts/full_dry_run.sh` |

---

## Public proof (click to verify)

| Artifact | Link |
| --- | --- |
| Live demo | https://huggingface.co/spaces/lokiii07/lirix-mantle-harness |
| Contract (Mantlescan) | https://sepolia.mantlescan.xyz/address/0x844cd69eADcc097F759FBf76C2d9735A55A9635c |
| Demo video | https://youtu.be/16Oa0ur-NFk |
| Evidence SSOT | [`external_evidence.md`](external_evidence.md) |

---

## Package map

- **Judge UI:** `app.py` (Streamlit L1–L5 presentation)
- **Judge packet:** `mantle/` (architecture, checklist, one-pager)
- **Screenshots:** repo-root `docs/submission_assets/` (5 PNG — canonical SSOT)
- **Contract source:** `contracts/LirixShield.sol`
- **Type-1 requirements:** `type1/type1.md` (symlinked via `type1/to_me.md` → this file)

---

## Reproduce locally

```bash
git clone -b mantle-turing-2026-harness https://github.com/lokii-D/lirix.git
cd lirix
python3 -m venv .venv && source .venv/bin/activate
pip install -e . && pip install -r requirements_submission.txt
./scripts/full_dry_run.sh
streamlit run mantle_TT/app.py
```

Built for Mantle Turing Test Hackathon 2026.
