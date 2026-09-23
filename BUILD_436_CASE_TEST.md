# Build 436 — fallspezifischer Test

Build 436 kann vollständig ohne externe Netzwerkverbindungen in einem Testfall geprüft werden.

## Ein-Schritt-Selbsttest

```javascript
await fetch('/api/build436/cases/CASE_ID/surface-onion/selftest', {
  method: 'POST',
  credentials: 'same-origin'
}).then(async r => ({status:r.status, body:await r.json()}))
```

Erwartet: HTTP 200 und `result: "PASS"`.

Der Test führt zunächst den sicheren Build-435-Replaytest aus, erzeugt anschließend einen synthetischen Clearnet-Datensatz mit identischem Testinhalt und prüft, dass Build 436 daraus genau einen provenance-bound `exact_sha256`-Kandidaten bilden kann.

Geprüft werden:
- Fallisolation;
- nur bereits menschlich reviewtes Onion-Material;
- exakte Content-Korrelation;
- `candidate_only: true`;
- keine automatische Identitätsfeststellung;
- OPSEC-Vertrag ohne Blocker;
- keine Netzwerkaktivität und kein Cross-Surface-Kontakt;
- Integrität.

## Analyse und Bericht

```javascript
await fetch('/api/build436/cases/CASE_ID/surface-onion/analyze', {
  method: 'POST',
  credentials: 'same-origin',
  headers: {'Content-Type':'application/json'},
  body: JSON.stringify({min_jaccard: 0.75})
}).then(r => r.json())
```

```javascript
await fetch('/api/build436/cases/CASE_ID/surface-onion/report', {
  credentials: 'same-origin'
}).then(r => r.json())
```

Ein Kandidat bedeutet nur, dass gespeicherte Inhalte/Provenienz relevante Überschneidungen zeigen. Die Frage, ob zwei Quellen, Accounts oder Organisationen tatsächlich dieselbe Entität darstellen, wird in Build 436 ausdrücklich **nicht** entschieden.
