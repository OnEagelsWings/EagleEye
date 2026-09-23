# Build 432 — fallspezifischer Selbsttest

Build 432 kann direkt in einem von dir gewählten Fall getestet werden. Verwende möglichst einen eigenen Testfall, weil der Selbsttest einen klar markierten synthetischen Datensatz im Fall hinterlässt.

## 1. EagleEye starten

Starte Build 432 normal und melde dich im Browser an.

## 2. Fall-ID einsetzen

Öffne im angemeldeten EagleEye-Fenster die Browser-Entwicklerkonsole und ersetze in den Beispielen `CASE_ID` durch die konkrete Fall-ID.

## 3. Ein-Schritt-Selbsttest

```javascript
await fetch('/api/build432/cases/CASE_ID/social/selftest', {
  method: 'POST',
  credentials: 'same-origin'
}).then(async r => ({status:r.status, body:await r.json()}))
```

Erwartet:
- HTTP 200
- `result: "PASS"`
- `case_bound: true`
- `event_bound: true`
- `content_bound: true`
- `fixture_visible_in_case: true`
- `integrity_valid: true`
- `network_authority_absent: true`

Der Test erzeugt automatisch eine synthetische Social-Quelle, sofern sie noch nicht existiert. Dafür benötigt der angemeldete Benutzer `source.manage`.

## 4. Fallbericht prüfen

```javascript
await fetch('/api/build432/cases/CASE_ID/social/report', {
  credentials: 'same-origin'
}).then(r => r.json())
```

Der Bericht zeigt nur Build-432-Daten dieses Falls: Anzahl der Beobachtungen, Plattformen, Adapter, Objekttypen, Quellen und Anzahl synthetischer Fixtures.

## 5. Einzelne Beobachtungen prüfen

```javascript
await fetch('/api/build432/cases/CASE_ID/social?include_fixtures=true', {
  credentials: 'same-origin'
}).then(r => r.json())
```

Ein Build-432-Testdatensatz muss `test_fixture: true` tragen und exakt die angegebene `case_id` enthalten.

## 6. Fallisolation testen

Führe den Selbsttest in zwei verschiedenen Testfällen aus und rufe anschließend jeweils `/social/report` auf. Die jeweiligen Beobachtungen dürfen nur im zugehörigen Fall erscheinen.

## Was dieser Test ausdrücklich nicht testet

Build 432 führt selbst keine Social-Media-Netzwerkabfragen durch. Der Selbsttest prüft den fallbezogenen Datenpfad, Provenienzbindung, Normalisierung, Integrität, Isolation und Adaptervertrag. Live-Connectoren und breitere Datenversorgung werden in den nachfolgenden Builds weiter ausgebaut.
