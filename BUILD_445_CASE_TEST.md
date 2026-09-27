# Build 445 case-specific qualification

Use a dedicated synthetic/demo case with a system-administrator identity.

## Run the checkpoint

```
POST /api/build445/cases/{case_id}/qualification/run
```

The deterministic portion opens no external sockets.

It runs the current Surface, hardening, News and Public-Social self-tests and checks the resulting provenance chain.

## Expected result in CI or a fresh installation

Before real external validation, the expected state is:

- engineering result: `pass`
- external result: `hold`
- overall result: `hold`
- data acquisition gate pass: `false`

That is the correct outcome. CI replay must never satisfy the external-validation requirement.

## How external evidence becomes eligible

Only non-fixture sources count.

- Surface: explicit Build-442 external validation using `VALIDATE442_EXTERNAL`
- News: explicit live Build-443 execution using `NEWS443_LIVE`
- Public Social: explicit live Build-444 execution using `SOCIAL444_LIVE`

After each path has at least one successful non-fixture external run, rerun Build 445.

A gate pass is evidence for the current bounded acquisition scope only. It is not a production certification.
