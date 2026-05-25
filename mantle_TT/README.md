# Mantle DoraHacks Submission Bundle

This directory is the final, reviewer-ready package for the Mantle track submission.

## What this bundle demonstrates

Lirix is a layered security pipeline for AI-generated DeFi intents on Mantle:

- **L1** intent and payload gate
- **L2** schema and semantic validation
- **L3** DeFi calldata parsing (swap selectors, route checks, proxy-aware paths)
- **L4** RPC quorum consistency checks
- **L5** shadow policy arbitration (fail-closed)

The goal is to block unsafe payloads before execution and provide an explainable decision path.

## Quick reviewer path

Open these files in order:

1. `mantle/README.md`
2. `mantle/submission_one_pager.md`
3. `mantle/architecture.md`
4. `mantle/video_script.md`
5. `mantle/delivery_checklist.md`
6. `examples/mantle_defi_demo.py` (canonical demo entry)

## Package structure

- `app.py` - Streamlit interface for interactive L1-L5 inspection
- `Dockerfile`, `docker-compose.yml` - containerized execution
- `examples/` - canonical demo entrypoint for judges
- `demo/` - legacy/demo-support materials (non-canonical)
- `docs/` - supporting notes and checklists
- `assets/` - architecture and pitch support content
- `mantle/` - judge-facing canonical packet
- `scripts/` - validation, demo launch, packaging
- `tests/` - Mantle bundle verification tests

## Local setup

From repository root:

```bash
python -m pip install -e .
python -m pip install streamlit pytest
```

## Run and validate

Bundle integrity:

```bash
bash mantle_TT/scripts/validate_bundle.sh
```

Primary demo (canonical):

```bash
python mantle_TT/examples/mantle_defi_demo.py
```

Interactive demo:

```bash
streamlit run mantle_TT/app.py
```

Full test suite:

```bash
./.venv/bin/python -m pytest -q
```

Coverage (target: 100% fail-under):

```bash
./.venv/bin/python -m coverage erase
./.venv/bin/python -m coverage run -m pytest -q
./.venv/bin/python -m coverage report
```

## Docker

```bash
docker compose up --build
```

## Evidence policy (important)

- No fabricated transaction hashes
- No fabricated explorer links
- No fabricated deployment or verification claims
- External links (GitHub, Spaces, on-chain proof) must be real and provided by submitter
