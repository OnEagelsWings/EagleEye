# Build 433 — fallspezifischer Test

Build 433 lässt sich direkt in einem von dir gewählten EagleEye-Fall testen. Verwende möglichst einen eigenen Testfall; der Selbsttest legt klar markierte synthetische Organisationsdaten im Fall an.

## Ein-Schritt-Selbsttest

Starte Build 433, melde dich an und öffne die Browser-Entwicklerkonsole. Ersetze `CASE_ID`:

```javascript
await fetch('/api/build433/cases/CASE_ID/organizations/selftest', {
  method: 'POST',
  credentials: 'same-origin'
}).then(async r => ({status:r.status, body:await r.json()}))
```

Erwartet wird HTTP 200 und `result: "PASS"`.

Der Test prüft:
- beide Organisationssubjekte sind exakt an den gewählten Fall gebunden;
- Observation und Relationsclaim sind an denselben Acquisition Event und Content Object gebunden;
- ein synthetischer Registrierungs-Identifier bleibt erhalten;
- die Organisationsbeziehung bleibt ausdrücklich ein `source_claim`;
- keine automatische Entity Resolution findet statt;
- Integritätsprüfung ist grün;
- Build 433 besitzt keine Netzwerkautorität.

## Fallübersicht

```javascript
await fetch('/api/build433/cases/CASE_ID/organizations/report', {
  credentials: 'same-origin'
}).then(r => r.json())
```

## Organisationen des Falls

```javascript
await fetch('/api/build433/cases/CASE_ID/organizations', {
  credentials: 'same-origin'
}).then(r => r.json())
```

Für die Detailansicht eines Subjekts:

```javascript
await fetch('/api/build433/cases/CASE_ID/organizations/SUBJECT_ID', {
  credentials: 'same-origin'
}).then(r => r.json())
```

Die Detailansicht zeigt alle source-bound Observations, Identifier- und Personenclaims, Relationship Claims sowie widersprüchliche Attributwerte. Widersprüche werden nicht automatisch aufgelöst.

## Was Build 433 noch nicht tut

Build 433 führt keine Live-Recherche selbst aus, entscheidet keine wirtschaftliche oder rechtliche Kontrolle, führt keine automatische cross-source Entity Resolution durch und stuft Quellenbehauptungen nicht automatisch als Tatsachen ein. Die Registerintegration folgt planmäßig in Build 434; Cross-source Entity Resolution folgt später in Build 437.
