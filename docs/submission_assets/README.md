# Submission screenshots (judge-facing)

Captured from `mantle_TT/app.py` Streamlit presentation — **verified, in-repo**.

## Gallery index

| File | Captures |
| --- | --- |
| [`01_hero_banner.png`](01_hero_banner.png) | Hero banner · Mantle Sepolia verified badge · fail-closed / L1–L5 / SHA-256 keywords · story selector |
| [`02_malicious_blocked.png`](02_malicious_blocked.png) | Merchant Moe route poisoning → **BLOCKED** · fail-closed protection activated |
| [`03_safe_swap_passed.png`](03_safe_swap_passed.png) | Clean V2 swap → L1–L5 **PASSED** · pipeline DAG visualization |
| [`04_lirix_2.0.4_core_strengths.png`](04_lirix_2.0.4_core_strengths.png) | Lirix 2.0.4 core strengths · frozen config · linear DAG · SHA-256 evidence |
| [`05_final_decision_safe_blocked.png`](05_final_decision_safe_blocked.png) | Final decision banners — **SAFE TO EXECUTE ON MANTLE** vs **BLOCKED** |

## On-chain proof (Mantle Sepolia) — public external evidence

| Field | Value |
| --- | --- |
| **tx hash** | `0xa23bb06ad14518ea7418082caef761cf864548a6705e8a2682b08c6cd69b055a` |
| **Explorer** | https://sepolia.mantlescan.xyz/tx/0xa23bb06ad14518ea7418082caef761cf864548a6705e8a2682b08c6cd69b055a |
| **Contract** | [`0x844cd69eADcc097F759FBf76C2d9735A55A9635c`](https://sepolia.mantlescan.xyz/address/0x844cd69eADcc097F759FBf76C2d9735A55A9635c) |

Evidence layering: public URLs → [`mantle_TT/external_evidence.md`](../../mantle_TT/external_evidence.md) §1; these PNGs → §2.

## Embed in submission docs

```markdown
![Hero banner](docs/submission_assets/01_hero_banner.png)
```

From `mantle_TT/README_submission.md` use `docs/submission_assets/` (copied into the package).
