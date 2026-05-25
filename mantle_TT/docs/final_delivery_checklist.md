# Final Delivery Checklist

## Structure

- [x] Self-contained submission packet in `mantle/`
- [x] Demo entrypoint in `demo/`
- [x] Test coverage in `tests/mantle/`
- [x] Packaging scripts in `scripts/`
- [x] Evaluation materials in `docs/` and `assets/`

## Verification

- [x] Mantle preset exists
- [x] Mantle whitelist exists
- [x] L3 guardrail coverage exists
- [x] Demo script is runnable
- [x] Packaging script produces a tarball
- [x] Lint check passes

## Final reviewer flow

1. Open `mantle/README.md`
2. Read `mantle/submission_one_pager.md`
3. Review `mantle/architecture.md`
4. Inspect `tests/mantle/test_mantle_config.py`
5. Run `scripts/run_mantle_demo.sh`
6. Package via `scripts/pack_bundle.sh`
