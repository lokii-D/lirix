# Optional SBOM (procurement / supply chain)


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

Lirix does **not** require an SBOM for merges. Some enterprise buyers ask for CycloneDX or SPDX SBOMs; you can generate one locally without changing library code.

## CycloneDX (Python environment)

Install a generator into the **same** environment you use to build wheels (for example your release venv):

```bash
python -m pip install cyclonedx-bom
```

Emit an SBOM for the installed `lirix` distribution (adjust output path):

```bash
cyclonedx-py environment -o lirix-sbom.json
```

Review the file and attach it to the release sign-off folder if procurement requires it.

## GitHub Actions (optional)

Repository maintainers may add a **non-required** `workflow_dispatch` workflow that runs `cyclonedx-bom` on `ubuntu-latest` and uploads `lirix-sbom.json` as an artifact. Keep it optional so default PR CI stays unchanged.

## PEP 639 / PyPI metadata

PyPI package metadata (`pyproject.toml`) remains the authoritative dependency list for `pip install lirix`; SBOMs are an additional export for buyers who require machine-readable bills of materials.
