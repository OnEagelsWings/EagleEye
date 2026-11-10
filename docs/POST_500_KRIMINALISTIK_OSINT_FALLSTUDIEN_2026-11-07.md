# EagleEye 501–550 – Kriminalistische Fallanalysen, OSINT und forensischer Belegfluss

**Stand:** 2026-11-07  
**Status:** Recherchegestützter, freizugebender POST-500-Erweiterungsplan – **keine Änderung des Build-490–500-Releaseumfangs**  
**Anbindung:** Bestehender Integrationsplan bis interne Version 1.0 (05.11.2026), bestehende Case-/Evidence-/Source-/AI-/Review-/Graph-/Timeline-/Dossier- und Audit-Dienste.  
**Branch-Kontext:** Aktive Draft-Kette bis PR #91. Kein neuer Architekturstrang, keine zweite Datenbank, keine weitere Hauptnavigation.

## 0. Zweck, Transparenz und Grenzen

Untersucht werden öffentlich dokumentierte Kriminalfälle, OSINT-Untersuchungen, strafrechtlich relevante Vorfälle, behördliche Operationen und Fälle gescheiterter Beweiswürdigung. **Nicht alle öffentlich zugänglichen Quellen veröffentlichen die vollständige Asservatenkette, Labor-Rohdaten oder gerichtlichen Beweisakten.** Die folgenden Ketten sind deshalb **rekonstruierte veröffentlichte Untersuchungs- und Prüfungsschritte**, keine Behauptung eines lückenlos eingesehenen Original-Beweisprotokolls.

Die Beweiskategorie bleibt explizit:
- **A**: Gerichtliche Feststellung/Urteil, soweit der konkrete Befund gerichtlich bestätigt ist;
- **B**: Primärbericht einer zuständigen Ermittlungs-/Untersuchungsbehörde oder unabhängiger Fachinstitution;
- **C**: transparent dokumentierte journalistische/NGO-OSINT-Verifikation;
- **D**: Hinweis/Behauptung, noch nicht unabhängig bestätigt.
Diese Buchstaben bewerten **Quellen- und Verfahrensstand**, nicht numerische Gewissheit oder die Identität einer Person. Unterschiedliche Aussagen innerhalb eines Falls erhalten getrennte Einstufungen.

**Kein** Übertragen von Mandanten-, Opfer- oder Verdächtigendaten in die allgemeine KI-Lernbasis. Keine automatische Schuldzuweisung, Personenidentifikation oder unbelegte „Evidenzqualität in Prozent“. Keine Übernahme behördlicher Sonderbefugnisse. Physische Spuren werden durch EagleEye **als externe Laborbefunde und dokumentierte Asservate** verwaltet, nicht durch KI als DNA-/Ballistik-Labor analysiert. Für sensible Kinderschutzfälle nur neutrale amtliche Methodenbeschreibungen und synthetisches Übungsmaterial, keine Missbrauchsbilder.

## 1. Gemeinsame Beleg- und Spurprozesskette

1. **Fallauftrag und Zulässigkeit**: Zweck, Rechtsgrundlage, Zuständigkeiten, zugelassene Quellen, Zeitraum, betroffene Rechte, Umfang und Stop-Bedingungen; Rollen und Genehmigungen festhalten.
2. **Hinweisaufnahme**: Form `Aussage / Eigenbeobachtung / Online-Hinweis / Dokument / materielles Asservat / Fremdlaborbefund` mit Erhebungsbedingungen und Trennung zwischen Bericht und behauptetem Sachverhalt.
3. **Originalsicherung**: Quelle/Urheber, URL/Exportpfad, Zeitpunkt der Veröffentlichung, Aufnahme- und Abrufzeit möglichst separat, Zeitzone, Upload-Kontext, technische Erfassungsmethode, Toolversion, unveränderte Binärdaten sowie SHA-256 und etwaige Einschränkungen.
4. **Übertragungskette**: jede Übernahme, Kopie, Transformation, Person/Zugriffsrolle, Zweck, Zeit, Hash-Prüfung und Ergebnis protokollieren. Original bleibt unveränderbar; Analyse auf Arbeitskopien.
5. **Spurentypisierte Verarbeitung**: Medien -> Metadaten, Frames, Bildmerkmale; Web -> archivierter Inhalt/kontextuelle Links; Dokumente -> Text/OCR mit Originalseitenankern; Digitalforensik -> Hashes/Logs/Provider-Bericht; DNA/Fingerabdruck/Ballistik/Chemie -> externen Fachbericht, Labor-ID, Verfahren, Unsicherheit, Kontaminationshinweise, nicht KI-eigene Fachbestätigung.
6. **Unabhängige Prüfung**: Ort, Zeit, Bild-/Videoauthentizität und Herkunft getrennt; alternative Erklärungen, negative Befunde, Widersprüche, Konfundierung und Quellenabhängigkeit ermitteln.
7. **Claims statt Automatikwahrheiten**: jede Schlussfolgerung auf konkrete Belege/Seiten/Frames/Hash und Gegenbelege zurückführbar; Confidence nur methodisch begründete abgestufte Darstellung, keine automatische Rechtswertung.
8. **Entitäten, Graph und Timeline**: getrennte Beziehungstypen `beobachtet`, `behauptet`, `technisch verknüpft`, `analytisch vermutet`, `verifiziert`; zeitliche Gültigkeit, negative Kanten und Versionen.
9. **Review und Dossier**: menschliche Fachprüfung, Zweitprüfung bei formeller Freigabe, alternative Hypothesen, Lücken, Rechts-/Lizenz-/Privatsphäregrenzen, Originalbelege und reproduzierbarer Prüfpfad.
10. **Neustart/Restore/Reproduktion**: gleiche Fallgrenzen, gleiche Beleganker, identische Original-Hashes, nachvollziehbare Version der Auswertungsmethoden.

Normative Ausgangspunkte: Berkeley Protocol (OHCHR/UC Berkeley), SWGDE Best Practices for Acquiring Online Content, SWGDE Digital Evidence Collection 2.0 (Stand 2025), SWGDE Computer Forensic Acquisition und INTERPOL Global Guidelines for Digital Forensics Laboratories.

## 2. Recherchierter Fallkatalog und nachbaubare Belegketten

Notation: **Eingang → Verarbeitung/Abgleich → Befund/Prüfgrenze**. `A/B/C` bezieht sich auf den unten verlinkten maßgeblichen veröffentlichten Teil. Nicht dokumentierte Ermittlungsakte werden ausdrücklich nicht ergänzt.

### A. OSINT, Luftfahrt, Kriegsverbrechen, visuelle Verifikation

**K01 MH17 (2014; B/C, teilweise gerichtlich bewertet):** Netzfotos und Videos eines Buk-Systems, Zeugen, Kommunikationsmaterial, Satellitenbilder und forensische Befunde → Originalkontext/Standortmerkmale vergleichen, Geolocation der Transportstationen, Schatten-/Zeitfenster, Serienmerkmale des Fahrzeugs, unabhängige Überprüfung durch JIT/Niederlande → zeitlich-räumliche Belegkette; OSINT-Fund wird nicht automatisch gerichtlich bestätigtes Faktum. **Test:** 6 Quellen, 4 Orte, widersprechende Ortsbehauptung, versionierte Timeline und prüfbarer Beleggraph. [Bellingcat](https://www.bellingcat.com/news/europe/2015/10/08/mh17-the-open-source-evidence/) · [Niederländische Staatsanwaltschaft](https://www.prosecutionservice.nl/topics/m/mh17-plane-crash/prosecution-and-trial/court-sessions-march-2020/status-of-the-investigation-and-position-on-the-progress-of-the-trial---part-1-10-3-2020)

**K02 Butscha/Bucha (2022; B/C, kein genereller Schuldnachweis für jedes Einzelbild):** Straßen-/Drohnenvideos und voneinander unabhängige Satellitenbilder → Geolokalisierung, Bildmerkmale, Metadaten, Chronolokalisierung anhand Sonnenstand und Drittaufnahmen, Gegenüberstellung von Behauptungen über Aufnahmezeit → belegt Teilbefunde zu Gegenwart und Zeitfenster von Opfern; Urheberschaft einzelner Tötungen benötigt weitere Beweise. **Test:** Bildüberlagerung und Quellunabhängigkeit; gezeigtes Objekt ≠ identifizierter Täter. [Centre for Information Resilience](https://www.info-res.org/eyes-on-russia/reports/disinformation-denial-russias-attempts-to-discredit-open-source-evidence-of-bucha/) · [Meduza](https://meduza.io/en/feature/2022/04/07/meduza-publishes-new-footage-evidencing-civilian-murders-in-bucha-during-russian-occupation) · [HRW](https://www.hrw.org/news/2022/04/21/ukraine-russian-forces-trail-death-bucha)

**K03 Douma (2018; B):** Umwelt-/biomedizinische Proben, Zeugenaussagen, Bilder, Ballistik, Meteorologie, chemische Fachanalysen → OPCW-Sicherung, unabhängige Fachlabore, Verifikationsabgleich und IIT-Gesamtschau → begründete Erkenntnisse zum Einsatz von Chlor und Verantwortlichkeit im fachbehördlichen Sinn; kein selbständiger Gerichtsentscheid. **Test:** Laborbericht als referenziertes externes Asservat inkl. Probe, Fachquelle, Aussagegrenzen und Beweiskettenstatus. [OPCW FFM](https://www.opcw.org/media-centre/news/2019/03/opcw-issues-fact-finding-mission-report-chemical-weapons-use-allegation) · [OPCW IIT](https://www.opcw.org/media-centre/news/2023/01/opcw-releases-third-report-investigation-and-identification-team)

**K04 Kramatorsk Bahnhof (2022; C):** Videobilder, Einschlagspunkte, Raketentrümmer und frühere Militärfotos → Geolokalisierung, Schadensbildvergleich, Gegenprüfung staatlicher Aussagen → einzelne Argumente widerlegt, aber öffentliches Material im untersuchten Bericht für Abschussort nicht ausreichend. **Test:** „unentscheidbar“ muss zulässiges Ergebnis sein; fehlende Beweise dürfen nicht von der KI ergänzt werden. [Bellingcat](https://www.bellingcat.com/news/2022/04/14/russias-kramatorsk-facts-versus-the-evidence/)

**K05 Flug PS752 (2020; B/C):** veröffentlichtes Telegram-Video, weitere Aufnahmen und Flugverlaufsdaten → Geolocation bei Parand, Zeitabgleich, unabhängige Journalisten-Verifikation, Abgleich mit behördlicher kanadischer Gesamtauswertung → Abschussgeschehen/Erklärungen mit ausgewiesenen offenen Punkten. **Test:** unterschiedliche Beweisträger und widersprechende offizielle Berichte quellenkritisch verbinden. [Bellingcat](https://www.bellingcat.com/news/middle-east/2020/01/09/video-apparently-showing-flight-ps572-missile-strike-geolocated-to-iranian-suburb/) · [Kanadischer Untersuchungsbericht](https://international.canada.ca/en/global-affairs/corporate/reports/flight-ps752/factual-analysis)

### B. Gewaltkriminalität, Terrorismus, Spuren und Fehlermittlungen

**K06 Boston-Marathon-Anschlag (2013; A/B):** Überwachungsvideos, Bürgeruploads, Bombenreste, Abdrücke, DNA und Zeugenaussagen → großvolumige Beweisannahme, forensische Laborbearbeitung, zeitliche Bewegungskette, fachliche Zeugenbeweise → gerichtliche Verurteilung; nicht jedes Video allein identifiziert jemanden verlässlich. **Test:** riesige heterogene Quellen, Dubletten, Original/Derivat und unabhängige Claims. [FBI](https://www.fbi.gov/history/cases-and-criminals/boston-marathon-bombing)

**K07 Golden State Killer (2018–2020; A/B + Fachpublikation):** Tatort-DNA → genealogischer Verwandtschaftshinweis und Stammbaumhypothese → direkte forensische Vergleichsprobe als Bestätigung vor Gerichtsverfahren; genetische Suche ist rechts- und datenschutzsensibel. **Test:** indirekte Verwandtschaftskante nie als individuelle Identität übernehmen. [Fachpublikation](https://pmc.ncbi.nlm.nih.gov/articles/PMC7219171/)

**K08 Unabomber/Ted Kaczynski (1990er; B):** Bomben-/Tatmuster, veröffentlichtes Manifest, private Vergleichsschriften → linguistischer Mustervergleich mit Kontextinformationen → Grundlage für weitere Durchsuchung und physische Beweise, keine Vollautomatisierung der Autorenschaft. **Test:** Textähnlichkeit als überprüfbarer Hinweis und externe Bestätigung. [FBI](https://www.fbi.gov/history/cases-and-criminals/unabomber)

**K09 Litvinenko (2006; B, öffentliche Untersuchung):** radioaktive Rückstände an Orten/Gegenständen, kontaminierte Teekanne, CCTV und Kontaktdaten → Strahlungsmessung, Unterscheidung primärer und sekundärer Kontamination, Ereignisfolge und konkurrierende Expositionspfade → dokumentierter Befund zum wahrscheinlichen Aufnahmeort; Rückstände allein zeigen nicht automatisch alle individuellen Handlungen. **Test:** materielle Spur mit Transfermodell und Alternativpfad. [Britische Untersuchung](https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/493860/The-Litvinenko-Inquiry-H-C-695-web.pdf)

**K10 Salisbury/Skripal (2018; B):** Umwelt- und Bioproben → unabhängige OPCW-Probenanalyse in vier Laboren, Vergleich mit britischer chemischer Identifikation → technische Stoffbestätigung; die OPCW bestätigte nicht selbst eine konkrete Täterschaft. **Test:** Befundgegenstand und Aussageumfang strikt separieren. [OPCW](https://www.opcw.org/media-centre/featured-topics/incident-salisbury)

**K11 Brandon Mayfield/Madrid (2004; B – *Fehlerfall*):** latenter Fingerabdruck nach Zuganschlag → fehlerhafte FBI-Zuordnung, spätere abweichende Identifizierung durch spanische Polizei, Widerruf → deutliches Beispiel für kognitive Verzerrung, falsche Bestätigung und notwendige unabhängige Prüfung. **Test:** Revision/Deaktivierung falscher Personenverknüpfung samt historischer Nachvollziehbarkeit. [DOJ Inspector General](https://oig.justice.gov/sites/default/files/archive/special/s0603/index.htm)

**K12 Richard Jewell/Olympiapark Atlanta (1996; B – *Fehlerfall*):** frühe Verdachtsannahme aus Tatortkontext → spätere Entlastung, weitere Anschlagszusammenhänge und Ermittlung Eric Rudolph → unbestätigte Verdachtsannahmen nicht als Personenbeweise veröffentlichen. **Test:** Exkulpation, Rufschadens-Risiko und ausdrückliche Sperre voreiliger Dossier-Formulierungen. [FBI Atlanta](https://www.fbi.gov/history/field-office-histories/atlanta) · [FBI Rudolph](https://www.fbi.gov/history/cases-and-criminals/eric-rudolph)

**K13 Fehlverurteilungen nach fragwürdiger Bissspur-/Haarvergleichsanalyse (Sammelfälle; B/Fachstudien):** Aussagen nicht ausreichend validierter forensischer Musterverfahren → spätere unabhängige DNA-Analysen und Entlastungen → methodische Fehlerquellen dokumentieren. **Test:** falsche „Match“-Aussagen statt Übernahme als Indiz kritisch prüfen. [NIJ](https://nij.ojp.gov/topics/articles/wrongful-convictions-and-dna-exonerations-understanding-role-forensic-science)

**K14 Station-Nightclub-Brand (2003; B – technische Brand-/Sorgfaltsanalyse):** Aufnahmen, Bau- und Materialbeschaffenheit, Brandablauf → technische Feuer-/Rauchausbreitungsanalyse, Rekonstruktion von Fluchtbedingungen → technische Kausalkette; NIST-Untersuchung ist keine vollständige strafrechtliche Beweisakte. **Test:** technische Ursache ≠ individuelle strafrechtliche Verantwortlichkeit. [NIST](https://www.nist.gov/disaster-failure-studies/station-nightclub-fire-2003)

### C. Cybercrime, Darknet, Kryptowährungen und verdeckte Plattformdaten

**K15 Silk Road (2011–2013; A/B):** öffentliche Forenbeiträge, Anzeigen-/Kontaktspuren, gerichtlich erlangte Netzwerkdaten, gesicherter Laptop → Account-Verknüpfung, Dokument-/Transaktionsanalyse, juristische Bestätigung → strafrechtlicher Fall; Privatzugriffe setzten Behördenbefugnisse voraus. **Test:** öffentlicher Hinweis versus nicht-öffentliches Durchsuchungsbeweismittel getrennt kennzeichnen. [FBI](https://www.fbi.gov/history/artifacts/ross-william-ulbrichts-laptop)

**K16 James Zhong / Silk-Road-Bitcoins (2012/2021–2022; A/B):** Transaktionsspuren, Blockchain-Analytik, aufgrund richterlicher Genehmigung gesicherte Speichermedien → Geldflussabgleich und rechtmäßige Beschlagnahme → Verurteilung und Sicherstellung; öffentliche Chain ist nicht gleich Besitzeridentität. **Test:** Wallet-Cluster mit Unsicherheit und externer Provenienz. [DOJ](https://www.justice.gov/usao-sdny/pr/us-attorney-announces-historic-336-billion-cryptocurrency-seizure-and-conviction?itid=lk_inline_enhanced-template)

**K17 Bitfinex-Hack (2016, Verfahren ab 2022; A/B):** Bitcoin-Transaktionen, Mixer-/Börsenwege und weitere Finanzdaten → Verfolgung von Transfers und korrespondierenden Nachweisen → dokumentiertes Geldwäscheverfahren. **Test:** Transfergraph, die genaue Grundlage jeder Eigentums- und Personenkante offenlegen. [DOJ Fallseite](https://www.justice.gov/usao-dc/2016-bitfinex-hack)

**K18 Colonial Pipeline / DarkSide (2021; B):** gemeldete Lösegeldzahlung und öffentliche Bitcoin-Transaktionen → Transferverfolgung bis beschlagnahmbarer Adresse, richterliche Sicherstellung → Teilbetrag gesichert; Walletkontrolle erfordert gesonderten Nachweis. **Test:** öffentlich sichtbare Transaktion und nichtöffentliche Zugriffsermächtigung auseinanderhalten. [DOJ](https://www.justice.gov/archives/opa/pr/department-justice-seizes-23-million-cryptocurrency-paid-ransomware-extortionists-darkside)

**K19 AlphaBay/Hansa (2017; B):** öffentlich dokumentierte Marktplatzinfrastruktur, behördlich gesicherte Plattformdaten und internationale Kooperation → Zuordnung/Analyse über Ermittlungsteams, Server- und Datensicherstellung → Takedown; private Ermittler dürfen diese behördlichen Maßnahmen nicht imitieren. **Test:** legaler Import veröffentlichter Exporte mit Quellen- und Berechtigungsprofil. [FBI](https://www.fbi.gov/news/stories/alphabay-takedown)

**K20 Hive-Ransomware (2022–2023; B):** durch gerichtliche Erlaubnis erlangte Serverdaten, Kommunikations- und Malware-Hashes, Entschlüsselungsinformationen → forensische Datenbankanalyse und unabhängige Opfervalidierung der Schlüssel → bestätigte Hilfsmaßnahmen; technische Details nur im defensiven Prüfkontext. **Test:** Tool-/Hashnachweis, mehrere Bestätigungsquellen und Rollentrennung. [DOJ](https://www.justice.gov/archives/opa/pr/us-department-justice-disrupts-hive-ransomware-variant)

**K21 LockBit/Operation Cronos (2024; B):** identifizierte Infrastruktur, Malware-/Kommunikationsdaten, internationale Ermittlungsbefunde → koordinierte Serverübernahme/-abschaltung und forensische Auswertung durch Behörden → operative Störung des Netzwerks; keine Gleichsetzung mit individuellen Schuldurteilen. **Test:** technische Infrastrukturentität und menschlichen Akteur getrennt modellieren. [Europol](https://www.europol.europa.eu/media-press/newsroom/news/law-enforcement-disrupt-worlds-biggest-ransomware-operation)

**K22 Genesis Market/Operation Cookie Monster (2023; B):** gestohlene Zugangsdaten und Onlinemarktplatz-Spuren → Strafverfolgungsdaten, grenzüberschreitende Identifizierung, Sicherstellung → Takedown, unterschiedliche Strafverfahren. **Test:** Quellenrisiko, Quarantäne von unrechtmäßigen Daten, keine Live-Verwendung fremder Zugangsdaten. [Eurojust](https://www.eurojust.europa.eu/news/takedown-online-market-sold-stolen-account-credentials-Operation-Cookie-Monster)

### D. Organisierte Kriminalität und internationale Vernetzung

**K23 EncroChat (2020 ff.; B):** verschlüsselte Kommunikationsdaten, rechtmäßig von Behörden erlangt → umfangreiche Gesprächs- und Netzwerkzuordnung plus Tat-/Sachbelege → viele Verfahren; juristische Zulässigkeit variiert nach Jurisdiktion und Einzelfall. **Test:** Nachricht als Aussage, nicht als unabhängig bewiesene Tat; Fall- und Rollengrenzen. [Europol](https://www.europol.europa.eu/media-press/newsroom/news/dismantling-encrypted-criminal-encrochat-communications-leads-to-over-6-500-arrests-and-close-to-eur-900-million-seized?trk=article-ssr-frontend-pulse_little-text-block)

**K24 ANOM/Operation Trojan Shield (2021; B):** durch Ermittlungsbehörden kontrollierte Nachrichtenplattform und internationale Belegauswertung → Nachrichten/Logistik-/Tatbelege korrelieren → Festnahmen/operative Erkenntnisse. **Test:** dokumentarische Methode lernen, keine verdeckte Chatplattform, keine Kommunikationsüberwachung implementieren. [FBI](https://www.fbi.gov/news/stories/fbi-global-partners-announce-results-of-operation-trojan-shield-060821)

**K25 Sky ECC (2021; B):** behördlich gewonnene Kommunikationsdaten → fallbezogene Vernetzung und Bestätigung durch externe Maßnahmen → internationale Verfahren; keine blanket Personenzuordnung. **Test:** Pseudonym ≠ bürgerliche Identität. [Europol](https://www.europol.europa.eu/media-press/newsroom/news/new-major-interventions-to-block-encrypted-communications-of-criminal-networks?trk=article-ssr-frontend-pulse_little-text-block)

**K26 Rotterdam/Operation SR13 (2021; B):** EncroChat-Erkenntnisse → zielgerichtete rechtmäßige polizeiliche Maßnahmen → Nachweis eines Labors und von Transportverstecken. **Test:** Kommunikationshinweis und materieller Bestätigungsbeleg voneinander trennen. [Europol](https://www.europol.europa.eu/media-press/newsroom/news/industrial-scale-cocaine-lab-uncovered-in-rotterdam-in-latest-encrochat-bust)

### E. Wirtschaftsdelikte, Korruption, Finanz- und Dokumentennetzwerke

**K27 FTX/Sam Bankman-Fried (2022–2024; A/B):** Kunden-/Unternehmensunterlagen, Softwareberechtigungen, Finanzströme, Kommunikation → Buchungsabgleich, Abweichungsnachweis, Zeugen- und Urkundenprüfung → Verurteilung; öffentliche Darstellungen sind nicht alle vollständigen Originaldaten. **Test:** Betrags-/Zeitpunkte/Konten/Behauptungen mit Gegenrechnung und Dokumentankern. [DOJ](https://www.justice.gov/usao-sdny/pr/samuel-bankman-fried-sentenced-25-years-prison?trk=article-ssr-frontend-pulse_little-text-block)

**K28 Theranos/Holmes (2022; A/B):** Marketing- und Investorenunterlagen, behauptete technische Leistungsfähigkeit, Labor-/Finanzdaten und Zeugenaussagen → Abgleich äußerer Zusagen gegen tatsächlich gemessene Fähigkeiten → Verurteilung hinsichtlich Investorenbetrugs, andere Anklagepunkte ausdrücklich nicht bestätigt. **Test:** Claim-Matrix: `wer behauptete was wann`, fachlicher Gegenbefund, genaues Urteil. [DOJ Fallseite](https://www.justice.gov/usao-ndca/us-v-elizabeth-holmes-et-al)

**K29 1MDB (2009 ff.; A/B für Einzelverfahren, B für Vermögensrückführung):** Banktransaktionen, Scheinfirmen, E-Mails, Reiseunterlagen, Belege für Luxusausgaben, Zeugenaussagen → internationale Zahlungsweg- und wirtschaftliche Berechtigtenprüfung → Verurteilungen einzelner Beteiligter/Vermögensrückführungen; nicht jede untersuchte Person gleich behandeln. **Test:** Firmen-/Konto-/Beneficial-Owner-Graph mit Herkunft jeder Kante. [DOJ Verurteilungsbericht](https://www.justice.gov/usao-edny/pr/former-goldman-sachs-investment-banker-convicted-massive-bribery-and-money-laundering)

**K30 Panama Papers (2016; C, journalistische Untersuchung, nicht pauschal Straffälle):** 11,5 Mio. geleakte Dateien, Firmendokumente, E-Mails, Tabellen → Indizierung, Dubletten-/Entity-Resolution, Register- und Medienabgleich, Redaktionsprüfung → publizierte Offshore-Beziehungen; Offshore-Beteiligung allein ist keine Straftat. **Test:** Dokumentenankerkette, Rechte/Lizenz, Namensähnlichkeit, alternative Firmennamen. [ICIJ](https://www.icij.org/investigations/panama-papers/about-the-investigation/)

**K31 FinCEN Files (2020; C, Verdachtsanzeigen keine Schuldbeweise):** SAR-Dokumente, Unternehmenstransfers, weitere Registerinformationen → redaktionelle Validierung/Abgleich und Quellenschutz → investigative Hinweise; SAR meldet Verdacht und ist ausdrücklich kein Beweis für Gesetzesbruch. **Test:** Warnung „Verdachtsanzeige ≠ nachgewiesene Straftat“. [ICIJ FAQ](https://www.icij.org/investigations/fincen-files/what-is-the-fincen-files-investigation/)

### F. Menschenhandel, Kinderschutz und Umweltkriminalität

**K32 Operation Global Chain (2024/2025; B – Sammeloperation):** Dokumenten-, Grenz-, Opfer- und Ermittlungsinformationen → internationale Abgleiche, sichere Opferbefragung, Schutzmaßnahmen → zahlreiche identifizierte potenzielle Opfer und Festnahmen, keine pauschalen individualisierten Schuldfeststellungen. **Test:** Opfer-/Quellenschutz, minimale Daten, strenge Rollen; nur anonymisierte Muster. [INTERPOL 2024](https://www.interpol.int/News-and-Events/News/2024/219-criminals-arrested-and-1-374-victims-identified-in-action-week-against-human-trafficking)

**K33 Operation Innocent Images (ab 1993; B – historisches Programm):** Zeugenaussagen, digitale Kommunikations- und Netzwerkbefunde → polizeiliche Ermittlungen, gerichtlich geregelte Datensicherung und Opferidentifizierung → Programme zum Kinderschutz. **Test:** ausschließlich abstrahierte öffentliche Metadaten-/Hinweisprozesse; keine realen Bilddateien mit Missbrauchsdarstellungen aufnehmen. [FBI](https://www.fbi.gov/history/cases-and-criminals/operation-innocent-images)

**K34 Operation Thunder 2024 (B – Sammeloperation):** Waren-/Transport-/Artenschutzdokumentation, Zollkontrollen, internationale Register → Art-/Herkunfts- und Routeprüfung, Sicherstellungen → Netzwerke und Einzelverfahren; Fund einer Art belegt nicht automatisch strafbare Täterschaft. **Test:** Güter-/Lieferketten-Graph, Quelle/Datum/Herkunftsrecht und Schutzgebiete. [INTERPOL](https://www.interpol.int/News-and-Events/News/2025/Nearly-20-000-live-animals-seized-365-suspects-arrested-in-largest-ever-wildlife-and-forestry-operation)

## 3. Ableitungen – bestehende EagleEye-Dienste statt neuer Plattform

| Wiederkehrende Ermittlungstechnik | Häufige Fehlerquelle | Erweiterung bestehender EagleEye-Funktion |
|---|---|---|
| Originalarchivierung und Quelle | Screenshot ohne Urheber/Originalbezug | Evidence: vollständiges Capture-Manifest, SHA-256, externe Asservat-ID |
| Video/Foto-OSINT | Umupload, falsches Datum/Ort | Analyse: getrennte Prüfungen Geo, Chrono, Authentizität und Aufnahme-/Uploadzeit |
| physische Spur / Fachlabor | KI behauptet Laborbefund | Evidence: externer Labor-/Probenbericht, Untersuchungsgrenzen und Kontaminationshinweise |
| Geldflüsse/Blockchains | Wallettransaktion als Besitzeridentität | Graph: Trennung Transaktion, Kontrollbeleg, wirtschaftlicher Berechtigter |
| Zeugenaussage | Erinnerung als eigene Wahrnehmung ausgegeben | Intake: Quelle, Aussagenart, zeitlicher Abstand, Wortlaut und spätere Korrekturen |
| Nachricht/Plattformdaten | Chatinhalte als begangene Tat behandelt | Claims: unabhängige Tatbestätigung zwingend |
| Forensischer „Match“ | Confirmation Bias | Review: negierende Quellen, unabhängige Zweitprüfung, revidierbare Verknüpfung |
| Netzwerkvisualisierung | Hypothesenkante wird visuell zur Tatsache | Graph: Kantenstatus, Quellenanker, Unsicherheit, Verlauf und Revoke |
| KI-Lernbasis | nicht bewiesene Fälle werden „Wissen“ | Nur freigegebene Methoden/Fehlerlehren, nie Täter- oder Mandantenbehauptungen |
| Dossier | Aussage und Urteil vermischt | geprüfte Beweis-Matrix samt konkreten gerichtlichen Feststellungen und Grenzen |

## 4. Post-500-Roadmap – Umsetzung nur nach Version 1.0

**Build 500:** bleibt unveränderter interner RC- und Praxisfreigabe-Meilenstein. Aus diesem Dokument entstehen **keine neuen Build-500-Gates**. Der Post-500-Plan darf vorab gelesen und bewertet werden; Umsetzung erst nach stabiler 1.0.

| Builds | Benutzbare Erweiterung im bestehenden System | Reproduzierbare Abnahme |
|---|---|---|
| **501–505** | 34 kuratierte öffentliche Fall-/Methodenkarten, belastbare Primärlinks, Status der strafrechtlichen Würdigung und Quellenlücken; importierbare anonymisierte Übungsfälle in vorhandener Fallverwaltung | drei Fälle ohne Identitätsdaten reproduziert; jeder Fall enthält Primärquelle und Datenrechte |
| **506–510** | durchgängiger Spur-/Beleglebenszyklus: Original, Derivat, Erhebung, Übergabe, Audit, externes Asservat/Laborbericht | Manipulation von Derivat/Original löst korrekte Integritätswarnung aus; Restore erhält Provenienz |
| **511–515** | OSINT-Geo-/Chronolokalisierung über existierende Bild-/Videoanalyse plus menschliche Prüfung | MH17/PS752/Bucha-Test: Quellenanker, Zeitfenster, gegensätzliche Geo-These, keine Auto-Freigabe |
| **516–520** | Medien-/Dokumentprüfung: Frame-/Seitenanker, Dubletten, EXIF-Lücken, Upload- versus Aufnahmezeit, Quellenabhängigkeit | Original und 2 Umuploads sowie künstlich veränderte Metadaten korrekt unterschieden |
| **521–525** | Finanz-/Unternehmens-/Kryptograph nur mit belegten Beziehungstypen, öffentlichen Testdaten | Bitfinex/FTX/1MDB-Simulation: indirekte Wallet-/Firmenkante nicht als Personenidentität |
| **526–530** | vorhandene Crawler-/Provider-/Logdaten fallgebunden mit defensiven Incident- und OSINT-Methoden verbinden | Hive/Genesis-Übungsdaten: Hash, Quelle, Abfragefreigabe, keine fremden Credentials genutzt |
| **531–535** | externer Laborbericht und Zeugenaussage als eigene Belegkategorien, Transfer- und Kontaminationspfade | Litvinenko/Douma-Simulation: Befund und Schlussfolgerung sauber getrennt |
| **536–540** | Gegenhypothesen-/Entlastungsprüfung und reversible Entity-Resolution stärken | Mayfield/Jewell: falscher Match sichtbar revidiert, frühere Version auditiert, kein aktueller Treffer |
| **541–545** | Montessori-Lernwerkstatt im vorhandenen UI: vorbereitete öffentliche/synthetische Fälle, abgestufte Hilfen, Selbstkontrolle, Kompetenzfeedback | Lernenden-Test: Originalbeleg finden, zwei Hypothesen bewerten, falsche Zuordnung berichtigen |
| **546–550** | Pilot-Stabilisierung: drei komplett reproduzierbare Fallstudien, Dossiers, Review, Neustart/Restore, Bedienbarkeit/Performance | 3 durchgehende Piloten mit Beleggraph, Gegenbeweisen und externem Review-Status |

**Strikte Anschlussregeln:** Jeder Build ist eigenständig benutzbar und nicht nur Test-/Planpflege; keine weitere Hauptnavigation, kein paralleler Datenspeicher, keine zusätzlichen Pflichtcloud-Dienste; vorhandene Dienste erweitern; bei regressionsrelevantem Defekt zuerst stabilisieren. Die hybride Feldsteuerung bleibt optional autorisiert und darf Datenschutz-/Rollengates nicht umgehen.

## 5. Drei vorrangige Pilotfälle

1. **P1 MH17 – Video/Satellit/Zeugenkontext:** öffentliche Originalquellen oder dokumentierte Reproduktionen → sichere Belegaufnahme → Orts-/Zeit-Anker → Widerlegung einer alternativen Standortthese → Graph/Timeline → Review → Dossier. Rechte und Lizenz der Bilddaten separat prüfen.
2. **P2 Finanzfluss (synthetischer Bitfinex-/FTX-inspirierter Datensatz):** freigegebene öffentliche/erfundene Wallet-/Unternehmens-/Buchungsdaten → Zahlungsbeziehung und kontrollierende Person logisch unterscheiden → alternative Erklärung → überprüfbares Dossier.
3. **P3 Mayfield – Fehlzuordnung:** synthetische Fingerabdruck-Fachberichte mit irreführendem Erst-Match und späterem Korrekturbefund → Claim-Revisionsgeschichte, Gegenbeleg, Identity-Edge-Revoke und Audit → Dossier ohne diffamierende falsche Gewissheit.

## 6. Qualitäts- und Erfolgsmessung

Metriken bei festen Übungsdatensätzen gegen Baseline: (a) Originalankerdeckung; (b) korrekte Quellen- und Zeitzonenangaben; (c) Zahl unberechtigt bestätigter Personen- und Claim-Verknüpfungen; (d) Anteil explizit genannter Gegenbelege; (e) Audit- und Hash-Integrität nach Restore; (f) manuelle Nacharbeit und Zeit bis zu prüffähigem Dossier; (g) Trefferqualität autorisierter KI-Methodenvorschläge. Keine versprochene monotone Lernverbesserung.

Kritische Negativtests: gelöschter Originalbeleg; doppelte Medienuploads; gefälschtes EXIF; falscher Zeitstempel; namensgleiche Personen; unzulässige Fall-/Quellenfreigabe; widerrufene Methode; voreiliger Verdacht; vermeintliche Täteridentität aus Wallet/Chat/Familienverwandtschaft; gerichtlich abweichender Befund; Korruption beim Restore.

## 7. Quellennormen und Nachweise

- [Berkeley Protocol / OHCHR und UC Berkeley, 2020](https://humanrights.berkeley.edu/publications/berkeley-protocol-on-digital-open-source-investigations/)
- [SWGDE: Acquiring Online Content](https://www.swgde.org/documents/published-complete-listing/21-f-001-best-practices-for-acquiring-online-content/)
- [SWGDE: Digital Evidence Collection 2.0](https://www.swgde.org/documents/published-complete-listing/18-f-002-2-0/)
- [SWGDE: Computer Forensic Acquisition](https://www.swgde.org/documents/published-complete-listing/17-f-002-2-1/)
- [NIST SP 800-86: Integrating Forensic Techniques into Incident Response](https://csrc.nist.gov/pubs/sp/800/86/final)
- [INTERPOL: Global Guidelines for Digital Forensics Laboratories](https://www.interpol.int/content/download/13501/file/INTERPOL_DFL_GlobalGuidelinesDigitalForensics)
- [National Institute of Justice: Wrongful Convictions and DNA Exonerations](https://nij.ojp.gov/topics/articles/wrongful-convictions-and-dna-exonerations-understanding-role-forensic-science)

**Forschungsgrenze:** Die 34 Katalogeinträge sind öffentlich quellenbasierte Fallskizzen, keine vollständig eingelesenen Gerichts-/Ermittlungsakten. Vor praktischer Umsetzung jeden Fall und Lizenzstatus einzeln erneut sichten und die veröffentlichten Originaldokumente/Beilagen erschließen. Bei fehlender Detailtiefe „nicht öffentlich dokumentiert“ eintragen, niemals einen Verfahrensschritt erfinden.

---

## 8. Ergänzung 07.11.2026: KLEINE REPRODUZIERBARE OSINT-FÄLLE UND INVESTIGATIVE RECHERCHEWEGE

**Anlass:** Der Anwender möchte ausdrücklich kleinere veröffentlichte OSINT-Recherchen, Personensuchen und investigative Reportagen, die nicht nur die Endergebnisse, sondern die **wirklich durchgeführten Suchschritte**, verworfenen Möglichkeiten, Quellen und Verifikationen offenlegen. Dieser Bestand gehört in die **Post-500-Fall- und Methodenbibliothek (501–505)**; er darf **keine neue Build-500-Freigabehürde** werden.

### 8.1 Qualitätskategorien für Übungsquellen

- **M1: Schrittweise rekonstruiert:** Suchausgangspunkt, charakteristische Merkmale, Suchorte/Abfragen, Vergleichsmaterial und konkreter Prüfpfad im Beitrag sichtbar. Häufig fehlen historische, gelöschte oder lizenzierte Originaldateien; das wird als Reproduktionslücke notiert.
- **M2: Methodenreportage:** Interviews/Reporternotizen geben nachvollziehbare Abfolge und Quellenklassen wieder, aber keine komplette Such-Session oder alle Originaldokumente.
- **M3: Ergebnisbeschreibung:** Rechercheansatz ist ersichtlich, aber viele Zwischenschritte fehlen; **nicht** als vollständig reproduzierbare Übung ausgeben.

**Zusätzliche Kennzeichnung** für jeden Fall: zulässiger Quellenzugang, Asset-Lizenz und Verfügbarkeit, personenbezogene Risiken, Stand der Tatsachen-/Gerichtsprüfung, frühester gesicherter Zeitpunkt, methodische Einschränkungen, synthetische Ersatzdaten nötig: ja/nein.

### 8.2 Kleine öffentliche Suchfälle – besonders geeignet für Einstiegsübungen

| ID | Öffentlicher Fall / Quelle | Dokumentierte Abfolge und überprüfbarer Wendepunkt | M | Übung in EagleEye |
|---|---|---|---|---|
| **S01** | [Kumbo/Kumfutu: Geolokalisierung eines Brandvideos, Bellingcat 2018](https://www.bellingcat.com/resources/case-studies/2018/11/21/geolocation-infrastructure-destruction-cameroon-case-study-kumbo-kumfutu/) | Video mit vorläufiger Ortsbehauptung → auffälliges **rotes Dach**, Shops und unfertiges Gebäude benennen → Luftbilder absuchen → Position durch weitere Bilddetails prüfen. Keine Identifizierung eines konkreten Täters allein durch Ortsbestimmung. | M1 | 1 Video, 3 visuelle Marker, 2 konkurrierende Orte; Quellenanker auf Frames |
| **S02** | [Prag: Datierung durch wechselnde Galerieaufschrift, Bellingcat 2018](https://www.bellingcat.com/resources/how-tos/2018/10/24/dali-warhol-boshirov-determining-time-alleged-photograph-skripal-suspect-chepiga/) | Öffentliches Foto mit Uploaddatum → temporäres Detail an Kunstgalerie → archivierte Bilder von VK, Street View, Suchmaschinen und Tourismusplattformen → engeres **Zeitintervall**, kein exaktes Aufnahmedatum. Die Echtheit eines möglichen Social-Media-Profils wird dadurch **nicht** bewiesen. | M1 | Aufnahmezeit ≠ Uploadzeit; Negativbeleg und Zeitintervall statt Punktdatum |
| **S03** | [Moskauer Gruppenfoto: Herkunftsort verifizieren, Bellingcat 2022](https://www.bellingcat.com/resources/2022/10/28/how-we-geolocated-a-photo-of-a-russian-missile-programming-team/) | Anonym eingesandtes Gruppenfoto → Ortsangabe **unbestätigt** → Tor, Treppe, Ziegel, Fenster, Regenrinne katalogisieren → geogetaggtes unabhängiges Referenzbild auf VK → Mikro-Merkmale abgleichen. | M1 | Hinweise aus anonymer Quelle, Geoverifikation und Personenzuordnung gesondert |
| **S04** | [Ein Foto zeigt eine Buk-Stellung: Standort aus öffentlich bekannten Straßenmerkmalen, Bellingcat 2014](https://www.bellingcat.com/resources/case-studies/2014/07/18/identifying-the-location-of-the-mh17-linked-missile-launcher-from-one-photograph/) | Ein Ausgangsfoto → auffälliger Laden und gestreifter Wohnblock → andere lokal beschriftete Dashcam-/Fahrvideos → Straßenzug auf Karte nachverfolgen → Standort der Aufnahme rekonstruieren. | M1 | Such-Pivot `Foto→Geschäft→Fahrvideo→Satellitenkarte`, alle Schritte als nachvollziehbare Evidence-Links |
| **S05** | [Falsch zugeordnetes Aldi-Video in den Niederlanden, Bellingcat 2021](https://www.bellingcat.com/resources/2021/11/01/a-beginners-guide-to-social-media-verification/) | TikTok behauptet Pandemie-Panikkäufe in Haarlem → Screenshot als Reverse-Image-Suche (Bing) → älterer YouTube-Upload zu **Kiel 2011** → Schild einer deutschen Friseurkette als Zusatzmarker. | M1 | absichtliche Fehlbeschriftung; ursprünglichen Kontext finden und Falschclaim widerrufen |
| **S06** | [12 Fotos im Fall Babiš: Ort/Zeit, aber nicht Freiwilligkeit, Bellingcat 2019](https://www.bellingcat.com/news/2019/02/07/wheres-babis-geolocating-the-alleged-father-son-kidnapping-mystery/) | Öffentlich verbreitete und wieder entfernte Fotos → Medienarchive und alternative Versionen → einzelne Bilder an Geomerkmalen abgleichen → teils nur ungefähre zeitliche Einordnung → **12/12 Orte** lokalisiert, kein Schluss auf Freiwilligkeit. | M1 | viele unabhängige Bildanker, unterschiedliche Prüfsicherheit; sensibles Ergebnis begrenzen |
| **S07** | [Historische Foto-Rätsel des Zweiten Weltkriegs, Bellingcat 2023](https://www.bellingcat.com/news/2023/08/04/solving-world-war-ii-photo-mysteries-with-open-source-techniques/) | Archivfotos mit unklarem Aufnahmeort → sichtbare Landschafts-/Gebäudemerkmale → historische Karten und Vergleichsbilder → Orts- und Datierungshypothesen prüfen. | M1/M2 | datenschutzarmes Anfängertraining mit historischen Bildern, keine aktuelle Zielperson |
| **S08** | [Colombia: Bildmanipulations-/Kontextprüfung, Bellingcat 2023](https://www.bellingcat.com/resources/2023/05/02/testing-for-manipulation-a-case-study-from-colombia/) | virale Fotos/Video mit behauptetem Ort → Straßenkreuzung in Street View vergleichen → historische Satellitenbilder zur Erklärung veränderter Merkmale → Bilder und weitergehende Gruppenbehauptungen separat bewerten. | M1 | manipulierten Kontext aufdecken, ohne aus visuellem Match Urheberschaft abzuleiten |
| **S09** | [Memphis Belle: historische Luftaufnahmen geolokalisieren, Bellingcat 2020](https://www.bellingcat.com/resources/2020/08/12/historic-bombing-runs-the-memphis-belle-case/) | Filmsequenzen aus Kriegsdokumentation → auffällige Landschafts-/Infrastrukturpunkte → Karten und weitere Bildquellen → Aufnahmepositionen identifizieren. | M1/M2 | historische Bild-/Videobefunde, Raum-Zeit-Unsicherheit |
| **S10** | [Künstler-/Bauwerkmerkmale statt EXIF: Bellingcat-Tutorial OpenStreetMap](https://www.bellingcat.com/resources/how-tos/2023/05/08/finding-geolocation-leads-with-bellingcats-openstreetmap-search-tool/) | Objektklasse (z. B. Supermarkt/Eisenbahn/Brücke) erkennen → OSM-Objekte nach Merkmalen filtern → Kartenkandidaten mit Bild vergleichen → falsche Kandidaten ausschließen. **Methodenübung, kein konkretes abgeschlossenes Strafverfahren.** | M1 | nachvollziehbare Query-Bedingung, Trefferliste, Kandidaten-Widerlegung |

### 8.3 Kleine bis mittlere journalistische Recherchen mit transparentem Arbeitsweg

| ID | Reportage und veröffentlichte Methodik | Rechercheverlauf | M | EagleEye-Kompetenz |
|---|---|---|---|---|
| **J01** | [Ein Journalist findet einen gesuchten ehemaligen ruandischen Militärangehörigen, GIJN 2020](https://gijn.org/stories/how-they-did-it-tracking-down-a-rwandan-genocide-suspect/) | historische Gerichtsverfahren → Verwaltungs- und Asylunterlagen → rechtmäßige Dokumentenanfragen → Quervergleich und Vor-Ort-Verifikation. **Historische, veröffentlichte Ermittlung; keine aktuellen privaten Aufenthaltsdaten ins Lernmaterial.** | M2 | Rechercheplan/Document-Pivot, Identifizierung nur nach unabhängiger Prüfung |
| **J02** | [Argentinien: Vernachlässigte Pferde / illegale Pferdefleischlieferkette, GIJN 2025](https://gijn.org/stories/unravelled-mystery-field-starving-horses-argentina/) | alte Lokalnachricht → lokale NGO und Rechtsvertretung → Gerichtsakten → Schlachtbetriebe, Preise, Geschäftsbeziehungen und europäische Abnehmer → Gegenanfragen. Reporter beschreibt auch **nicht beantwortete Interviewanfragen**. | M2 | Folgerecherche aus kleinem Hinweis, Dokumente/Zeugen/Handelsgraph, offene Fragen |
| **J03** | [Basel: Wo sind freie private Parkplätze?, CORRECTIV/Bajour 2023](https://correctiv.org/aktuelles/international/2023/06/27/klima-quartierparking-parkplatz-not-in-basel-leser-decken-tausende-freie-parkplaetze-auf/) | Crowd-Meldungen → Adressen mit drei übereinstimmenden Meldungen als vorläufig bestätigt → Detailerhebung → Immobilienbesitzer befragen → Ausschluss bekannter öffentlicher Parkhäuser erklären. **Kein Straffall**, jedoch nahezu ideale kleine dokumentierte Recherche. | M2 | Crowdsourcing, korrelierte Aussagen ≠ drei unabhängige Belege, Auswahlverzerrung |
| **J04** | [Somalia: Holzkohlehandel, CORRECTIV 2022](https://correctiv.org/aktuelles/2022/12/12/hauptsache-kohle/) | anonyme Smartphone-Hinweise → Fotos → Satellitenabgleich → Einzelinterviews → lokale journalistische Prüfung. Starker **Quellenschutz** erforderlich. | M2 | Remote-Feldhinweise und Satellitenvergleich; anonyme Quelle nicht automatisch legitimiert |
| **J05** | [Bangladesch: vermeintlich falsche Sozialhilfe-Bezieherinnen, GIJN 2019](https://gijn.org/?p=135684) | Beschwerden aus Dörfern → Auskunftsbegehren zu rund 7.500 Empfängern → Stichprobenmethodik → ergänzende Verwaltungsakten und Feldbesuche → Hypothese über Systemfehler revidieren/erweitern. | M2 | seriöse Stichprobe, Verzerrung, Dokument↔Interview↔Sachverhalt |
| **J06** | [OpenCorporates: deutsche Handelsregistereinträge verknüpfen, GIJN 2019](https://gijn.org/stories/how-they-did-it-gathering-data-on-over-5-million-german-companies/) | unstrukturierte Bekanntmachungen → Identifikatoren und Registergericht prüfen → Registerabgleich → Namens-/Organrollen mit Fehlerflag → Qualität vor Vollständigkeit. | M2 | deutsches Register, Entity Resolution, Dubletten, gleichnamige Personen, falsche Positivtreffer |
| **J07** | [US-Krankenhausschulden: Gerichtsdaten auswerten, ProPublica/MLK50](https://www.propublica.org/article/what-it-looks-like-when-a-hospital-we-investigated-erases-millions-in-medical-debt) | Erledigungsmitteilungen des Gerichts → Fallnummern in Online-Zahlungsregister zurückverfolgen → Betrag aggregieren → Einschränkung bei Erlass und unvollstreckbaren Schulden offenlegen. | M2 | Dokument-ID-Abgleich, transparente Rechnungen, Zahlen mit nicht abgedecktem Rest |
| **J08** | [UK Post Office / Horizon: kleine Lokal-/Fachredaktionen decken Fehlverurteilungen auf, GIJN 2025](https://gijn.org/stories/exposing-uk-post-office-scandal/) | frühe Betroffenenhinweise → technische Systemprobleme als Alternativhypothese → weitere gleichartige Fälle → langjährige Dokumenten-/Expertenrecherche → spätere gerichtliche Feststellungen. | M2 | Gegenhypothese, Fehlerkorrektur, Hypothesenpflege über Jahre |
| **J09** | [ProPublica: Videobelege zu mutmaßlich unzulässigen Festnahmetechniken, 2026](https://www.propublica.org/article/videos-ice-dhs-immigration-agents-using-chokeholds-citizens) | Social-Media-/Lokalmedien-/Gerichtsrecherche → Kontextverifikation → acht unabhängige Fachgutachter → Betroffenen-/Zeugenanfragen → Vorwürfe gegen Dokumente prüfen → Anfrage an betroffene Behörden. **Bewertung der Reporter/Experten, keine pauschale gerichtliche Feststellung.** | M2 | externe Expertise, Gegenseite anhören, Kontext/Zeitlinie, methodischer Vorbehalt |
| **J10** | [Öffentliches Yachttracking und Bildabgleich, Bellingcat 2015](https://www.bellingcat.com/resources/case-studies/2015/08/19/yachtspotting/) | Fotos und öffentliche Reise-/Schiffsdaten → Merkmale des Schiffsinterieurs → Orts-/Zeitvergleich → Beziehungsbehauptungen kritisch abgrenzen. **Nur rückblickende veröffentlichte Belege; keine Live-Verfolgung privater Personen.** | M1/M2 | Orts-/Zeit-Korrelation ist kein Identitäts- oder Tatnachweis |
| **J11** | [Gaza: Wie BBC Verify öffentliche Trainingsvideos und Orte verifizierte, GIJN 2024](https://gijn.org/stories/bbc-open-source-investigate-gaza/) | Themenbezogene öffentliche Kanäle organisieren → Videoarchiv anlegen → anhand von Satellitenmerkmalen Trainingsorte lokalisieren → historische Satellitenstände prüfen → redaktionell abgleichen. | M2 | viele Teilbelege, Video-/Ort-Deduplikation und zeitliche Kontextprüfung |
| **J12** | [Forensic Architecture / Al-Haq: Shireen Abu Akleh, Methodikbericht 2022](https://forensic-architecture.org/investigation/the-extrajudicial-killing-of-shireen-abu-akleh-extended-report/) | 30+ Videos/Fotos/Zeugnisse/Spuren → synchronisierte Medien-Timeline → Geolokalisierung, Audio- und 3D-Raumanalyse → Bericht mit Einzelschritten und Belegbezügen. **Fachliche Schlussfolgerungen der Autoren, nicht mit Gerichtsurteil gleichsetzen.** | M1 (umfangreich) | multimodale Synchronisation und alternative Erklärungen |
| **J13** | [Syrien: verschwundene Kinder, internationale Reportagerecherche 2026](https://gijn.org/stories/uncovering-syrias-stolen-children/) | Presse-/Social-Media-Hinweise → Dokumente verschiedener Einrichtungen → Datenbank mit überprüften Fällen → Interviews/Quervergleiche. **Besonders schutzbedürftige Minderjährige: nur synthetische Modelle übernehmen.** | M2 | datensparsames Abgleichen und sichere Quellen-/Opferrechte |
| **J14** | [Kryptowährungs-Börse unter neuem Namen, GIJN 2026](https://gijn.org/?p=2836007) | Sanktions- und Unternehmenshinweise → offen dokumentierte Geschäfts- und Zahlungsbeziehungen → zusätzliche journalistische Nachweise. **Verdeckte Originalmethoden nicht als automatisierbare EagleEye-Funktion nachbauen.** | M2 | Corporate-Entity-Resolution, wirtschaftliche Identität getrennt von Claim |
| **J15** | [OCCRP-Recherchehandbuch zur Personensuche, GIJN 2026](https://gijn.org/stories/reporters-notebook-how-to-track-down-people-who-dont-want-to-be-found/) | methodische Übersicht zu öffentlichen Datenspuren, Archiven, Datenbanken und Gegenprüfung; ausdrücklich: ein mit Mail/Telefon angezeigtes Profil **belegt nicht** die Inhaberschaft. **Methodenartikel, kein vollständig reproduzierbarer Einzelfall.** | M2 | Suchhypothesen, Fehlidentifikationen, Datenminimierung, rechtmäßige Quelle |

### 8.4 Konkreter Standard einer „Rechercheweg-Karte“ in EagleEye

Diese Karte wird **über die vorhandenen Fall-/Evidence-/Review-/Lernservices** umgesetzt; wenn ein Feld fehlt, möglichst zunächst als strukturierte Metadaten statt neuer Hauptnavigation:

```text
Fall-ID / methodische Übungs-ID:
Fragestellung und erlaubter Untersuchungsumfang:
Ausgangshinweis: Wortlaut, Kontext, Provenienz, Stand der Prüfung:
Suchschritt-ID:
  Hypothese:
  verwendete Quelle/Toolversion/Datum:
  nachvollziehbare Suchbedingungen (sensible Kennungen redigieren):
  gefundenes Original und URI/Archiv-ID:
  Originalhash (falls Datei verfügbar):
  relevanter Ausschnitt/Seiten- oder Frameanker:
  Warum dieser Fund zum nächsten Suchschritt führte:
  Alternative Erklärung / Fehlzuordnung:
  Beurteilung: unbestätigt / teilweise / unabhängig geprüft / widerlegt:
  Bearbeiter und Auditzeit:
  zulässiger nächster Schritt / explizite Genehmigung:
Ergebnis und Aussagegrenzen:
Quellen-/Lizenz-/Datenschutzprüfung:
Menschlicher Review und Korrekturen:
Übertragbare methodische Lehre (erst nach Freigabe):
```

Ein **negativer Suchschritt** (kein Treffer, ungültiger Link, verworfene Hypothese, keine Berechtigung) bleibt sichtbar. Damit kann EagleEye später unterscheiden: „nicht gefunden“ ist **nicht** „gibt es nicht“.

### 8.5 Priorisierte Miniübungen und konkrete Soll-Ergebnisse

**Übung E01, 20–30 Minuten – falsches TikTok-/Kiel-Video (S05):**
- Nur veröffentlichte Standbilder und Kontextaussagen aus dem Bellingcat-Beispiel bzw. rechtmäßig frei verwendbares Ersatzmaterial.
- Lernziel: Reverse-Image-Fund, **2011er Erst-/Frühveröffentlichung**, widersprechender Orts-/Zeit-Claim, zwei Quellenanker.
- Fehlerfall: aktuelles Uploaddatum wird als Aufnahmedatum angenommen.

**Übung E02, 30–45 Minuten – Kumbo-Dach (S01):**
- Sichtbare Dach-/Straßenmerkmale in annotiertem Bild; mindestens zwei alternative Kartenausschnitte anbieten.
- Lernziel: 3 Marker dokumentieren, nachvollziehbar einen Kartenkandidaten verwerfen, Ortsbestimmung **ohne** Täterzuordnung.
- Fehlerfall: ein einzelnes rotes Dach wird voreilig als zweifelsfrei passend gewertet.

**Übung E03, 30–60 Minuten – Prag-Galerie (S02):**
- Historische Fassadenansichten mit verschiedenen Ausstellungsaufschriften und **getrennten** Aufnahme-/Uploadzeitpunkten.
- Lernziel: frühestes/spätestes mögliches Aufnahmedatum als Intervall mit Provenienz und konkurrierender Erklärung.
- Fehlerfall: nachträglich hochgeladenes Bild als zeitgenössisches Datum behandeln.

**Übung E04, 45–90 Minuten – deutsches Firmenregister (J06):**
- Kleine **synthetische** Handelsregisterbekanntmachungen mit gleichen Namen, verschiedenen Registergerichten und überlappenden Jahreszahlen.
- Lernziel: Gesellschaften anhand Registerkennung unterscheiden, Organrolle mit Zeitraum, keine unbestätigte Familienbeziehung.
- Fehlerfall: Name+Ort als Personenidentität missbrauchen.

**Übung E05, 60–120 Minuten – Recherche vom lokalen Hinweis zum Dossier (J02 oder J05):**
- Anonymisierte Ausgangsmeldung, einige Gerichts-/Registerdokumente, eine Aussage und ein entlastendes Dokument.
- Lernziel: Recherchewelle planen, Belege und Aussagen trennen, einen Suchpivot begründen, Widerspruch im Bericht offenlegen.
- Fehlerfall: Hypothese als erwiesene Straftat darstellen.

**Übung E06, 60–120 Minuten – Personensuche als historische Dokumentenprüfung (J01):**
- Nur **synthetische** Personendaten und allgemein zugängliche Verfahrensdokumente, keine aktuelle reale Privatperson.
- Lernziel: 2 gleichnamige Personen getrennt halten, Dokumentenbezug und rechtmäßige Quelle prüfen, frühere falsche Zuordnung zurücknehmen.
- Fehlerfall: Telefonnummer, Account oder räumliche Nähe als exakte Identifizierung ausgeben.

### 8.6 Ergänzung der bestehenden Post-500-Builds

- **501–505 (Fallbibliothek):** vor allem E01–E04 als erste öffentliche/synthetische, rechtlich freigegebene Einsteigerkarten; die umfangreicheren Fälle als Modulreferenzen. Gleicher sechs Bereiche umfassender Workflow, keine siebte Hauptnavigation.
- **506–510 (Evidence-Provenienz):** Suchschritt→Original/Derivat→Folgesuche→Claim-Anker inklusive **Fehlschritten** und Datenrechten durchgängig testen.
- **511–520 (Geo-/Chrono-/Bildprüfung):** E02/E03 und GVC-Bildvergleich, unabhängige Referenzen und Zeitfenster statt eindimensionalem „Match“.
- **521–535 (Netzwerk-/Dokumentmethoden):** E04/E05 und behördliche/sekundäre Datensätze, öffentliche Firmen-/Registeridentitäten, Aussagen versus externe Fachberichte.
- **536–540 (Fehlerkontrolle):** E06 plus Mayfield und Post-Office-Fälle; auch nach Neustart/Restore wird eine **zurückgenommene** Entity-Kante nicht als aktueller Treffer angezeigt.
- **541–545 (Montessori-Lernwerkstatt):** vorbereitete Mini-Fälle nach Schwierigkeitsgrad; Hinweise stufenweise; Selbstkontrolle anhand veröffentlichter Suchwege; Reflexion „warum dieser Pivot?“ statt reiner Trefferquote.
- **546–550 (Pilot/Qualität):** neue Übungsfälle als zusätzliche Regressionen, aber unverändert drei robuste übergreifende Pilotdossiers und formale Review-/Integritätsprüfungen.

### 8.7 Juristische und reproduktionstechnische Sicherungen

1. Öffentlich dokumentierte Journalistenrecherche ist nicht automatisch ein für private Ermittler **zulässiger** Suchvorgang. Keine unbefugten Kontozugriffe, Passwortreset-Tricks, De-Anonymisierung nicht öffentlicher Konten, Täuschungshandlungen oder Übernahme verdeckter behördlicher Befugnisse als Standardaufgabe.
2. Veröffentlichung eines Fotos/Videos bedeutet nicht, dass die Datei frei lizenziert und in die App redistributierbar ist. Falls Rechte/Original unklar sind: **nur Originalquelle verlinken und synthetisches Ersatzmaterial erzeugen**, Quelle im Literaturverzeichnis sichern.
3. „Personensuche“ als Übung nur mit öffentlichen historischen Fällen oder synthetischen Personen. Bei aktuellen Vermisstenfällen nur gesondert legitimierte Aufträge mit Einwilligung/Zuständigkeit und schützendem Umgang mit Daten, keine eigenständige Veröffentlichung privater Adressen/Bewegungsmuster.
4. Der **Nachvollziehbarkeitsgrad M1/M2/M3** ist etwas anderes als die **Beweis- und Gerichtsqualität A/B/C/D** des Hauptdokuments; beide separat anzeigen.
5. Eigene Testerfolge sind nur dann „reproduziert“, wenn ein unabhängiger Bearbeiter mit zulässigen öffentlich zugänglichen oder rechtmäßig lizenzierten Eingabedaten die gleichen entscheidenden **Zwischenschritte** durchführen kann. Eine mit Quelle beschriftete, nachträglich erstellte Erzählung allein reicht nicht.

**Zusammenfassung:** Diese Ergänzung verschiebt den Schwerpunkt des Nach-500-Lernens von spektakulären großen Fällen zu **kleinen, reproduzierbaren Fallketten**, in denen Suchentscheidungen, verworfene Treffer, Gegenprüfung und Quellenanker im Mittelpunkt stehen – weiterhin ohne Änderungen am Build-500-Release-Gate.
