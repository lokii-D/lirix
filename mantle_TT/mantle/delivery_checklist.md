# Delivery Checklist

## Code and runtime readiness

- [x] Mantle mainnet/testnet presets configured
- [x] Mantle-oriented router/token allowlists included
- [x] L3 calldata safety checks implemented
- [x] L4 RPC quorum checks implemented
- [x] L5 shadow policy enforcement available
- [x] Streamlit demo entrypoint available
- [x] Docker and compose entrypoints available

## Validation and quality gates

- [x] Bundle validation script available (`mantle_TT/scripts/validate_bundle.sh`; judge dry-run: `./scripts/validate_harness.sh`)
- [x] Automated Mantle bundle tests included
- [x] Repository-wide tests available
- [x] Ruff/Black/MyPy strict quality gates available
- [x] Coverage workflow available (target 100% fail-under in project config)

## Reviewer-facing packet completeness

- [x] One-pager (`submission_one_pager.md`)
- [x] Architecture summary (`architecture.md`)
- [x] Demo script (`video_script.md`)
- [x] Bundle manifest (`bundle_manifest.md`)
- [x] Final index (`final_bundle_index.md`)
- [x] Judge packet grouped under `mantle_TT/mantle/`

## External evidence to be supplied by submitter

- [x] Public GitHub URL
- [x] Public demo/hosting URL (HF Spaces)
- [x] Deployed contract on Mantle Sepolia (explorer link)
- [x] Demo video (2–3 min) — https://youtu.be/16Oa0ur-NFk
- [x] Public on-chain proof (deploy / tx hash) — tx `0xa23bb06a…b055a` · [Mantlescan](https://sepolia.mantlescan.xyz/tx/0xa23bb06ad14518ea7418082caef761cf864548a6705e8a2682b08c6cd69b055a)
- [x] Contract verification (Mantlescan Exact Match) — [LirixShield verified](https://sepolia.mantlescan.xyz/address/0x844cd69eADcc097F759FBf76C2d9735A55A9635c#code)
- [x] Screenshots under repo-root `docs/submission_assets/` (5 PNG) — [`../../docs/submission_assets/`](../../docs/submission_assets/)
