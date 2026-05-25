# 2-3 Minute Demo Video Script

## Scene 1 - Problem framing

Show the Mantle ecosystem and explain that DeFi execution often routes through routers, proxies, and batched calls. Emphasize that unsafe calldata can still look legitimate at a glance.

## Scene 2 - Lirix inspection

Open the Lirix demo and load the Mantle configuration. Highlight that the bundle uses real Mantle RPC and real router/token addresses.

## Scene 3 - Malicious payload

Paste a hostile swap payload that uses a valid Mantle router but unsafe execution parameters such as missing slippage protection.

## Scene 4 - Layered rejection

Show the validation pipeline rejecting the payload at L3 or earlier. Explain why the route is unsafe and how the system identified it.

## Scene 5 - Safety recap

Summarize the result: the bundle demonstrates practical Mantle support, real-address coverage, and a reproducible defense path suitable for a security-first AI DevTools submission.
