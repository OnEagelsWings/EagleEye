# EagleEye PersonOSINT – Handbuch für Analyst/innen

Schulungsdauer: ca. ½ Tag (Vorführung am Beispielfall + 2 Übungsfälle). Ein Beispielfall lässt sich auf der Startseite laden.

## 1. Anmelden und sicher arbeiten
- Anmeldung mit Passwort + 2FA-Code aus der Authenticator-App. Ein Code gilt nur einmal.
- **Schnellsperre** (Schloss-Symbol bzw. Tastenkürzel laut Hilfe): Bildschirm sofort leeren, wenn jemand mitschaut oder Sie den Platz verlassen.
- Glocke oben rechts: Benachrichtigungen (Überwachungen, Freigaben, Löschfristen).

## 2. Einen Fall anlegen (Assistent in 3 Schritten)
1. **Fallart** wählen: Investigativ, Personensuche, Vermisstenfall, Verbindungsanalyse.
2. **Auftrag**: Titel, Zweck (Pflicht), Rechtsgrundlage, OPSEC-Stufe, Netzausgang, ggf. vertraulich.
   **Auftragsprüfung** ehrlich beantworten. Zeigt sie Warnsignale, können Sie den Fall nicht selbst anlegen – Teamleitung einbinden (siehe docs/compliance/Auftragspruefung.md).
3. **Zielperson**: so viele Angaben wie bekannt (Name, Geburtsdatum, Ort, Benutzernamen, E-Mail, Telefon, Arbeitgeber).

## 3. OPSEC-Stufen in einem Satz
| Stufe | Wann | Was das System tut |
|---|---|---|
| 1 Standard | unkritisch | alle Quellen, direkter Netzausgang erlaubt |
| 2 Erhöht | Zielperson soll nichts merken | nur über Proxy/Tor, Deckname, Briefing-Bestätigung |
| 3 Streng | gefährdete Quellen / wehrhafte Ziele | nur passive Quellen, kein sichtbarer Zugriff, vertraulich, Export nur Verantwortliche/Prüfung |
Vor der ersten Suche in Stufe 2/3 das **Briefing** im Reiter 🛡 OPSEC bestätigen. Blockiert das System eine Abfrage, ist das gewollt („fail closed“) – nicht umgehen, Admin fragen.

## 4. Suchen und prüfen
- Reiter **Suche & Treffer**: Quellen auswählen (Symbole zeigen Exposition: lokal / passiv / Plattform / sichtbar). Lokale Referenzdaten (Sanktionen, Leaks) verlassen den Server nicht.
- Jeder Treffer muss **bestätigt** oder **verworfen** werden. Ansicht „Gruppen“ fasst Treffer zu Kandidaten zusammen – Geburtsjahr und Ort helfen, Namensvettern zu trennen.
- Bestätigte Personen/Unternehmen können in den Graphen übernommen werden.

## 5. Fakten & Bewertung
- Aussagen („geboren am“, „Geschäftsführer von“) mit Quelle und Bewertung (Admiralty: Zuverlässigkeit A–F, Glaubwürdigkeit 1–6).
- Widersprüche werden markiert; **Red Flags** sind Recherchehinweise, keine Urteile.

## 6. Verbindungen, Zeitleiste, Karte
- **Verbindungen**: Graph mit Pfadsuche zwischen zwei Personen, Schlüsselakteure.
- **Zeitleiste & Karte**: Ereignisse mit Ort/Datum (Vermisstenfälle: letzte Sichtung).

## 7. Belege sichern
- Webseiten im Dossier-Reiter sichern: Inhalt wird verschlüsselt gespeichert, mit SHA-256-Prüfsumme und Wayback-Kopie. Das **Beweispaket** (ZIP) enthält Manifest und Dateien.

## 8. Dossier
- Vorlage wählen (Volldossier, Kurzprofil, Due Diligence, Vermisst), Word oder PDF/A. Ungeprüfte Aussagen sind standardmäßig ausgeschlossen.
- Jeder Export erhält eine **Export-ID** und steht im Exportregister.
- Vor Auslieferung: Status „zur Prüfung“ → Prüfperson gibt frei (Vier-Augen).
- KI-Zusammenfassung (falls aktiviert) ist ein Entwurf: jeder Satz braucht einen Beleg [F…], Sie müssen ihn freigeben.

## 9. Überwachung
- In „Suche & Treffer“ eine Überwachung anlegen (Quellen + Abstand). Gemeldet werden nur neue Treffer.

## 10. Abschluss und Löschen
- Status „abgeschlossen“ setzt die **Löschfrist** (Badge im Fallkopf). Bei Erreichen erhalten Sie eine Erinnerung: Fall löschen oder Verlängerung in den Notizen begründen (Teamleitung).

## Übungen
1. Beispielfall laden, drei Treffer prüfen, ein Dossier „Kurzprofil“ erzeugen.
2. Neuen Fall OPSEC 2 anlegen, Briefing bestätigen, Suche über Proxy ausführen, Netzausgangs-Protokoll ansehen.
3. Auftragsprüfung mit Warnsignal durchspielen (beobachten, dass das System blockiert).
