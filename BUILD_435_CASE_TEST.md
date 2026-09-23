# Build 435 — fallspezifischer Test

Build 435 kann ohne Tor-Netzwerkzugriff vollständig an einem ausgewählten Testfall geprüft werden.

## Sicherer Ein-Schritt-Selbsttest

Starte Build 435, melde dich an und ersetze `CASE_ID`:

```javascript
await fetch('/api/build435/cases/CASE_ID/tor/selftest', {
  method: 'POST',
  credentials: 'same-origin'
}).then(async r => ({status:r.status, body:await r.json()}))
```

Erwartet werden HTTP 200 und `result: "PASS"`. Der Test verwendet eine synthetische v3-Onion-Adresse und einen deterministischen Replay-Transport; **es werden keine externen Netzwerkverbindungen geöffnet**.

Geprüft werden unter anderem:
- exakte Fallbindung;
- `tor_onion` + `tor_public` Quellvertrag;
- Build-422-Event mit Status `quarantined`;
- Build-423-Content-Bindung;
- Replay ohne Netzwerk;
- obligatorische Human-Review;
- Integrität;
- alle 435-Checkpoint-Sicherheitsgrenzen.

## Tasks und Bericht

```javascript
await fetch('/api/build435/cases/CASE_ID/tor/tasks', {credentials:'same-origin'}).then(r => r.json())
```

```javascript
await fetch('/api/build435/cases/CASE_ID/tor/report', {credentials:'same-origin'}).then(r => r.json())
```

Der Selbsttest hinterlässt einen klar synthetischen, bereits reviewten Task im Testfall.

## Hard-Checkpoint-Status

```javascript
await fetch('/api/build435/checkpoint', {credentials:'same-origin'}).then(r => r.json())
```

`checkpoint_ready: true` bedeutet, dass die lokalen Integritäts- und Sicherheitsgrenzen des Checkpoints erfüllt sind. Es bedeutet **nicht**, dass ein externer Onion-Service erfolgreich kontaktiert wurde.

## Live-Tor-Nutzung

Live-Ausführung ist absichtlich nicht Teil des Selbsttests. Sie setzt voraus:
1. einen vom Administrator ausdrücklich aktivierten, loopback-only Build-370-Tor-SOCKS-Gateway;
2. eine registrierte, überprüfte v3-Onion-Quelle;
3. einen fallspezifischen Task mit `approval_ref`;
4. erneute Eingabe desselben `approval_ref`;
5. exakte Bestätigung `TOR435_LIVE`.

Keine Authentifizierung an Zielseiten, keine Formulare/Uploads, keine Zahlungen, kein Zugangsschutz-Bypass und keine autonome Scope-Erweiterung.
