# DoraHacks Delivery Checklist

## Must include

- [x] Mantle mainnet/testnet configuration
- [x] Multi-RPC preset
- [x] Router and token whitelist coverage
- [x] Demo script for a real Mantle DeFi scenario
- [x] Mantle-specific tests
- [x] Submission notes
- [x] Judge packet under `mantle_TT/mantle/`

## Recommended attachments for submission

- [x] Architecture diagram — see mermaid in root `README.md` § Architecture & security trace
- [x] Demo screenshots — 5 PNG in repo-root `docs/submission_assets/`
- [x] 2-3 minute demo video — https://youtu.be/16Oa0ur-NFk
- [ ] Pitch deck PDF — not required for AI DevTools track (outline: `mantle_TT/assets/pitch_outline.md`)
- [x] Live deployment URL / Hugging Face Space — https://huggingface.co/spaces/lokiii07/lirix-mantle-harness
- [x] Public on-chain proof — tx `0xa23bb06a…b055a` · contract verified on Mantlescan

## Final verification steps

1. `streamlit run mantle_TT/app.py` (or root `app.py` after sync)
2. `./scripts/full_dry_run.sh` from repository root
3. `bash mantle_TT/scripts/validate_harness.sh` (CI-equivalent mantle slice)
4. Confirm `dist/mantle-turing-2026-harness.tar.gz` contains 5 screenshots
