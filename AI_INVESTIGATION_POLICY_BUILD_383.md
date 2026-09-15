# AI Investigation Policy – Build 383

Build 383 introduces Source Planner v1. Mission-to-source-class inference is advisory. Inferred selectors cannot change case scope unless an analyst provides the exact confirmation `CONFIRM SELECTORS`. Explicit or confirmed selectors create candidate source scope only. Every underlying research plan still requires human GO and has `execution_authority=false` and `scope_expansion_authority=false`.

The planner may rank only sources already present in the governed Source Registry and may expose registry, jurisdiction, entity-type, access-path and validation gaps. It does not invent a source when the registry lacks one, execute connectors, authenticate to data systems, crawl, merge identities, or treat missing results as proof of non-existence.
