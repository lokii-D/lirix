# Mantle Judge Packet (Canonical Review Entry)

This folder is the official, judge-facing packet for the Mantle submission.

## Recommended review order

1. `submission_one_pager.md`
2. `architecture.md`
3. `video_script.md`
4. `delivery_checklist.md`
5. `bundle_manifest.md`
6. `final_bundle_index.md`
7. `test_mantle_config.py`

## What to verify first

- The project demonstrates layered, fail-closed security on Mantle.
- Mantle presets and allowlists are present and test-backed.
- The package is reproducible without hidden dependencies.

## Minimal command path (from repository root)

Bundle integrity:

```bash
bash mantle_TT/scripts/validate_bundle.sh
```

Primary demo:

```bash
python mantle_TT/examples/mantle_defi_demo.py
```

Canonical demo source is `mantle_TT/examples/mantle_defi_demo.py`.
The `mantle_TT/demo/` directory is supplementary and not the judge default path.

Core regression suite:

```bash
./.venv/bin/python -m pytest -q
```

## Evidence policy

This packet does not fabricate deployment, explorer, or verification evidence.
Any public links (GitHub, Spaces, on-chain proof) must be real and submitter-provided.
