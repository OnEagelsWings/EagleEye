# Defensive OPSEC Policy – Build 372

- Evaluation labels and source-quality scores cannot activate network access or alter crawler transport policy.
- Source-quality scores cannot authorize identity confirmation, automatic merging or review bypass.
- Entity-link jobs whose payload/result claims automatic merge or identity confirmation are treated as boundary violations.
- Queued/running violating entity-link jobs may be cancelled only within the affected case.
- No firewall, OS, Tor, credential, account or ACL mutation authority is introduced.
- Synthetic holdout and replay data remain explicitly separated from external validation claims.
