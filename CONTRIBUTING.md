# Contributing to EagleEye

Thank you for helping test or improve EagleEye.

## Current status

Build 400 is a public testing/evaluation baseline. It is not presented as production-ready software. Please use only synthetic, demo, or clearly public information when testing.

## The fastest useful contribution

A valuable contribution can be as small as:

1. Clone or download the repository.
2. Start EagleEye on a clean machine.
3. Create a demo case.
4. Restart the application.
5. Report what worked, what failed, and the exact error message.

See `TESTING.md` for the full test procedure.

## Bug reports

For reproducible defects, please open a GitHub issue and include:

- operating system and version
- CPU and RAM
- Python version
- install method (clone or ZIP)
- exact steps to reproduce
- expected behavior
- actual behavior
- exact error message or traceback

Remove API keys, tokens, cookies, private usernames, identifying local paths, case material, and other sensitive information before posting logs or screenshots.

## Pull requests

Pull requests are welcome for clear, reviewable fixes. Please:

- keep the change focused
- explain the defect or improvement
- include regression tests where practical
- preserve the local-first and human-governed security model
- do not silently broaden network access, autonomous execution authority, credential handling, or access-control permissions
- run the relevant test suite before submitting

For Build 400 the canonical integration test is:

```bash
pytest -q tests/test_build400_integrated.py
```

## Security-sensitive findings

Do not publish real credentials, secrets, private investigation data, or personal data in an issue. Describe the problem with synthetic examples wherever possible.

## Community feedback

Critical feedback is useful. Installation friction, confusing UX, misleading status indicators, resource problems, crawler/research errors, and AI/investigator workflow problems are all in scope for the public beta.
