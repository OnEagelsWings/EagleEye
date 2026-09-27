# Build 446 case-specific qualification

Use a dedicated synthetic/demo case.

## Deterministic qualification

```
POST /api/build446/cases/{case_id}/selftest
```

The deterministic qualification opens no external sockets.

It:

1. registers one synthetic Surface source, one News source and one Public-Social source;
2. creates a Build-439 investigation loop with exactly those source IDs;
3. verifies dispatch preparation is blocked before the Build-439 human GO;
4. authorizes the loop;
5. prepares three specialized dispatch tickets;
6. verifies the retained Surface/News/Social confirmation contracts;
7. replays each specialized path through its real adapter logic without external network;
8. verifies Build-437/438/418/419 analytical refresh;
9. verifies no auto-execution, scope expansion or truth determination;
10. verifies Build-446 integrity.

## Optional live flow

Prepare dispatches:

```
POST /api/build446/loops/{loop_id}/dispatches/prepare
```

Then execute one reviewed ticket using the confirmation shown on that ticket.

The confirmation applies to that path-specific dispatch only. Build 446 does not provide an "execute everything" confirmation.
