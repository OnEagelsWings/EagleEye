# AI Investigation Policy – Build 382

- The AI investigator may create and persist case-scoped research plans against the persistent Source Registry.
- Every plan remains `requires_go=true`, `execution_authority=false`, and `scope_expansion_authority=false`.
- Persisting a plan or approving a source for case scope never executes a connector, crawler, query, or network request.
- Coverage and gap metrics are planning/research-completeness indicators, never truth probabilities.
- `no_result_observed` is bounded evidence about a specific attempt and never establishes non-existence.
- OPSEC or Operations hold prevents new research-plan persistence.
