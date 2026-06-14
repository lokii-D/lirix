# Final Bundle Index

## Root bundle
- `mantle_TT/README.md`
- `mantle_TT/to_me.md`
- `mantle_TT/app.py`
- `mantle_TT/Dockerfile`
- `mantle_TT/docker-compose.yml`

## Judge packet
- `mantle_TT/mantle/README.md`
- `mantle_TT/mantle/submission_one_pager.md`
- `mantle_TT/mantle/architecture.md`
- `mantle_TT/mantle/video_script.md`
- `mantle_TT/mantle/delivery_checklist.md`
- `mantle_TT/mantle/bundle_manifest.md`
- `mantle_TT/mantle/final_bundle_index.md`
- `mantle_TT/mantle/test_mantle_config.py`

## Demo and support files
- `mantle_TT/examples/mantle_defi_demo.py`
- `mantle_TT/demo/mantle_defi_demo.py`
- `mantle_TT/docs/submission_one_pager.md`
- `mantle_TT/docs/submission_notes.md`
- `mantle_TT/docs/video_script.md`
- `mantle_TT/docs/delivery_checklist.md`
- `mantle_TT/assets/architecture.md`
- `mantle_TT/assets/pitch_outline.md`
- `mantle_TT/assets/demo_payload.json`
- `mantle_TT/assets/cover.md`
- `mantle_TT/scripts/run_mantle_demo.sh`
- `mantle_TT/scripts/pack_bundle.sh`
- `mantle_TT/scripts/validate_bundle.sh`
- `mantle_TT/tests/README.md`
- `mantle_TT/tests/mantle/test_mantle_bundle.py`

## Recommended command sequence (judges)
1. Read `mantle_TT/README_submission.md`
2. `./scripts/full_dry_run.sh` (repo root — canonical judge path)
3. `bash mantle_TT/scripts/validate_bundle.sh` (mantle_TT package file check only)
4. `python mantle_TT/examples/mantle_defi_demo.py`
