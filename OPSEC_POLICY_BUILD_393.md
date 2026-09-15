# OPSEC Policy – Build 393.0

The Build-393 dialogue/challenge engine is local and network-silent. It has no direct HTTP/client imports and no execution authority.

A dialogue turn cannot issue or consume GO grants, confirm LIVE execution, enqueue crawler jobs, alter firewall/Tor/credential/ACL state, or promote evidence. Kernel admission is a notebook-only bridge requiring the exact `ADMIT CHALLENGE TO KERNEL` confirmation.

All external research authority remains governed by the existing Phase-17 GO/LIVE/OPSEC/Operations chain from Builds 385-388.
