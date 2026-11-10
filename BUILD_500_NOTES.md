# Build 500 – Internal Release Candidate

Source branch: `release/build500-internal-rc1`, based on the verified
PersonOSINT/EagleEye integration branch through Build 499.

## Integration
- 497: explicit, once-only provider-plan execution through
  `ProviderCollection120Service`; live mode requires an independently
  approved case search intent and approved query.
- 498: fixed-loopback local Ollama plan proposals; typed JSON schema and
  separate human acceptance; zero direct AI network, graph or Evidence writes.
- 499: recoverable, idempotent human-reviewed PersonOSINT candidate transfer
  to the existing graph. A stored case document is mandatory; new node remains
  unverified and no graph relationship is added.
- 500: unified current factory, package and bootstrap installer versions,
  secure source/data separation, complete Windows offline wheelhouse,
  dual SHA-256 inventories and real loopback startup/restart acceptance.
- Do not silently merge the separate PersonOSINT application database.

## Release gates
Automated GitHub Actions check installable Windows artifacts and focused
test paths of current Build 497–500 (not all historical accepted builds).
The internal release must stay **HOLD** until actual operator confirmation:
- Windows clean installation, startup and restart on target machine
- all source provenance and data access policies reviewed
- independent backup/restore drill including original WARC, graph and case DB
- no regressions in user-visible operations and login flows
- source/permission and GDPR/DSGVO checks for actual work
- acceptable field/agent workflow and manual four-eyes case review

## Known constraints
- Historical internal modules and long-lived abstractions remain. There has
  been no full deletion/migration sweep of all legacy paths.
- Local model quality depends on installed Ollama model, not guaranteed.
- No proof of autonomous field operations or unrestricted multi-source search.
- Real external provider availability and authorized production performance
  are not proven by deterministic CI tests.
- Some advanced subsystems require their own settings/licences and explicit
  operator approval.

This is a **source + bootstrap/Wheel Windows candidate**, not a formally
certified professional forensic product.
