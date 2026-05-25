# 2-3 Minute Demo Video Script

## Scene 1 - Problem and threat model (20-30s)

Explain that Mantle DeFi execution frequently involves routers, proxy contracts, and multicall batches.
State the risk: payloads can look syntactically valid while still being economically or operationally unsafe.

## Scene 2 - Setup and context (20-30s)

Show the bundle entrypoint and mention:

- Mantle presets are enabled
- real protocol/token addresses are configured
- decisions are produced by a layered fail-closed pipeline (L1-L5)

## Scene 3 - Malicious payload walkthrough (35-45s)

Run a hostile payload (for example, recipient poisoning or unsafe slippage profile).
Highlight where the payload is blocked and display the reason.

## Scene 4 - Safe payload walkthrough (35-45s)

Run a safe payload variant through the same path.
Show successful validation and policy pass.

## Scene 5 - Evidence and close (20-30s)

Conclude with reproducibility artifacts:

- bundle validation script
- automated tests
- quality gates and coverage target

Final line: Lirix prevents unsafe Mantle transactions before execution and provides explicit, reviewable reasoning.
