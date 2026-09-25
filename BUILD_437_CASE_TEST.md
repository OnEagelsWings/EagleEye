# Build 437 — fallspezifischer Test

Build 437 kann direkt in einem ausgewählten EagleEye-Testfall geprüft werden.

## Ein-Schritt-Selbsttest

```javascript
await fetch('/api/build437/cases/CASE_ID/entity-resolution/selftest', {
  method: 'POST',
  credentials: 'same-origin'
}).then(async r => ({status:r.status, body:await r.json()}))
```

Erwartet: HTTP 200 und `result: "PASS"`.

Der Test erzeugt zwei getrennte synthetische Organisationskandidaten aus zwei unabhängigen öffentlichen Quellfamilien. Beide enthalten denselben Registrierungs-Identifier und dieselbe Website. Build 437 muss daraus einen Review-Kandidaten bilden, die beiden Kandidaten aber getrennt erhalten.

Geprüft werden insbesondere:
- Provenienzbindung bis Source → Acquisition Event → Content;
- zwei getrennte Entity-Kandidaten;
- sichtbare starke Identifier-Anker;
- Review-Kandidat statt automatischer Identitätsfeststellung;
- keine automatische oder destruktive Zusammenführung;
- Score ist keine Identitätswahrscheinlichkeit;
- keine Netzwerkaktivität;
- Integrität der Build-437-Bindings.

## Review Queue

```javascript
await fetch('/api/build437/cases/CASE_ID/entity-resolution/review-queue', {credentials:'same-origin'}).then(r => r.json())
```

Jeder Review-Packet zeigt beide Kandidaten, Aliase, Anchor-Signale, Source/Event/Content-Bindings, Konflikte und – falls vorhanden – Build-436-Surface↔Onion-Kontext. Dieser Kontext ist ausdrücklich kein Identitätsbeweis.

## Fallbericht

```javascript
await fetch('/api/build437/cases/CASE_ID/entity-resolution/report', {credentials:'same-origin'}).then(r => r.json())
```

Der Bericht zeigt Bindings, Kandidaten, Vergleiche, offene Reviews, bestätigte nicht-destruktive Links und die Integrität der Resolution-Event-Chain.
