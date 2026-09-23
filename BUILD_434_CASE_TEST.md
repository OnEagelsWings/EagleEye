# Build 434 — fallspezifischer Test

Build 434 kann in einem ausgewählten EagleEye-Testfall geprüft werden.

## Ein-Schritt-Selbsttest

Starte Build 434, melde dich an und ersetze `CASE_ID`:

```javascript
await fetch('/api/build434/cases/CASE_ID/registry-organizations/selftest', {
  method: 'POST',
  credentials: 'same-origin'
}).then(async r => ({status:r.status, body:await r.json()}))
```

Erwartet: HTTP 200 und `result: "PASS"`.

Der Test erzeugt eine klar markierte synthetische Registerquelle und einen synthetischen Registerdatensatz. Geprüft werden Fallbindung, Acquisition-Event- und Content-Provenienz, Organisationsanlage, Identifier-Erhalt, Identifier-Candidate-Lookup, Integrität sowie die Sperre gegen automatisches Merge/Entity Resolution.

## Importierte Registerdatensätze

```javascript
await fetch('/api/build434/cases/CASE_ID/registry-organizations', {
  credentials: 'same-origin'
}).then(r => r.json())
```

## Fallbericht

```javascript
await fetch('/api/build434/cases/CASE_ID/registry-organizations/report', {
  credentials: 'same-origin'
}).then(r => r.json())
```

## Identifier-Kandidaten prüfen

Nach dem Selbsttest steht im Ergebnis ein synthetischer `registry_number`. Er kann so gesucht werden:

```javascript
await fetch('/api/build434/cases/CASE_ID/registry-organizations/identifier-candidates?identifier_type=registry_number&value=DEIN_WERT', {
  credentials: 'same-origin'
}).then(r => r.json())
```

Ein Treffer trägt `candidate_only: true`; `automatic_merge` und `automatic_entity_resolution` bleiben `false`.

## Abgrenzung

Build 434 führt keine eigenständigen Live-Abfragen bei Handels-, Vereins-, Charity- oder LEI-Registern aus. Er integriert bereits rechtmäßig/public erfasste Registerdaten in den fallbezogenen Provenienzpfad. Live-Datenversorgung und Cross-source Entity Resolution werden in späteren Builds weiter ausgebaut.
