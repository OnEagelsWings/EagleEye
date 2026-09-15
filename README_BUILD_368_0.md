# EagleEye PersonOSINT Pro – Build 368.0

## Phase 16: Sanctions / Legal / Government / Archives

Build 368 adds a governed reference-intelligence layer without widening EagleEye's qualified read-only crawler boundary.

### Live-eligible exact sources
- Federal Register exact document number (`YYYY-NNNNN`)
- Internet Archive exact public item identifier, metadata only

### Plan-only sources
- NARA Catalog (API-key execution not introduced; current API storage/caching constraint conflicts with ordinary evidence persistence)
- GovInfo (API-key execution not introduced)
- OFAC SDN XML (signed-redirect provenance path not yet qualified)
- UN Security Council consolidated sanctions XML (signed-redirect provenance path not yet qualified)

### Safety / evidence model
- Source review + explicit `LIVE` before any real Build-368 request.
- No automatic network connection at boot.
- No generic URL execution.
- Replay cannot become externally validated.
- Sanctions fuzzy-name screening and automatic adverse-decision support are disabled.
- Archive payload download is disabled; Build 368 uses public metadata only.
- No autonomous firewall/OS/Tor/credential/account/ACL mutation.

### Release truthfulness
Build 368 is an internally qualified controlled-pilot build. `production_release_ready=false` remains mandatory until the outstanding external validation and professional-pilot gates are actually completed.
