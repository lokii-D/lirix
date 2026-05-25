# L3 Mantle Fork Notes

## Current behavior
- Mantle parser requires explicit router configuration for non-mainnet chain ids.
- Mantle preset now provides router configuration through `LirixConfig.for_mantle()`.

## Expected validation path
- router swap selector accepted
- amountOutMin=0 rejected
- recipient poisoning rejected via address checks
- multicall recursion supported

## Reviewer note
If stricter fork-level proof is required, run the demo/tests against an Anvil fork that exposes Mantle router/token addresses already present in the project allowlist.
