# Palantir Gotham – Architekturanalyse aus öffentlichen Quellen

Stand 10. Nov. 2026.

## 0. Was das ist und was nicht

Ein Reverse Engineering im eigentlichen Sinn (Software zerlegen, dekompilieren) war **nicht möglich und
wurde nicht versucht**: Gotham ist nicht frei erhältlich, Palantir verkauft es an Behörden und Unternehmen.
Dieser Bericht rekonstruiert den Aufbau aus dem, was Palantir selbst veröffentlicht hat, und aus
öffentlichen Dokumenten Dritter.

Jede Aussage trägt eine Kennzeichnung, wie belastbar sie ist:

| Kürzel | Bedeutung |
|---|---|
| **[A]** | Primärquelle selbst gelesen: Palantirs öffentliche GitHub-Repositories (Apache-2.0). |
| **[B]** | Aus Suchergebnissen zu offiziellen Dokumenten (Palantir-Doku, britische G-Cloud-Leistungsbeschreibung, Patentschrift, Gerichtsentscheidung). Die Seiten selbst waren in dieser Umgebung gesperrt und wurden **nicht im Volltext gelesen**. |
| **[C]** | Sekundärquellen oder Vorwissen, nicht überprüft. Als Hinweis zu lesen, nicht als Tatsache. |

Gelesene Primärquellen [A]:

| Repository | Stand | Inhalt |
|---|---|---|
| `palantir/gotham-platform-python` | 25.04.2025, 345 Dateien | Offizielle Python-Bibliothek für die Gotham-API, automatisch aus der API-Spezifikation erzeugt; 231 Dokumentationsseiten zu Endpunkten und Datenmodellen |
| `palantir/atlasdb` | archiviert 13.11.2024 | Transaktionsschicht über Schlüssel-Wert-Datenbanken, mit Architekturdokumentation |
| `palantir/conjure` | 09.11.2026 | Beschreibungssprache für HTTP/JSON-Schnittstellen mit Code-Erzeugung |
| `palantir/defense-sdk-examples` | 28.05.2026 | Beispielanwendungen für das „Defense SDK“ |
| Verzeichnis der Organisation `palantir` | 257 öffentliche Repositories | u. a. `blueprint` (React-Oberflächenbaukasten, 22 000 Sterne) |

## 1. Einordnung

Gotham ist Palantirs Plattform für Verteidigung, Nachrichtendienste und Polizei [B]. Die Schwesterplattform
Foundry richtet sich an Unternehmen. Beide teilen das Grundmodell aus Objekten, Eigenschaften und
Verknüpfungen [B]. Gothams Anwendungen können inzwischen auf einer in Foundry verwalteten Ontologie
laufen („Type Mapping“) [B]; im Gotham-SDK tauchen entsprechend Verweise auf Foundry-Objekttypen und
-Objektmengen auf [A].

Der Zweck unterscheidet sich grundlegend von EagleEye: Gotham führt **interne Datenbestände einer Behörde**
in großem Maßstab zusammen. EagleEye ist ein Einzelplatz-Werkzeug für **öffentliche Quellen**. Übertragbar
sind deshalb Konzepte, nicht die Großarchitektur.

## 2. Aufbau

### 2.1 Kern: Objektdatenbank mit dynamischer Ontologie

Die offizielle API-Beschreibung nennt als Kern „RevDB“, eine Objektdatenbank auf Basis einer dynamischen
Ontologie [B]. Aus dem SDK ergibt sich das Datenmodell [A]:

* **Objekte** mit Primärschlüssel und einem Objekttyp, der über einen API-Namen angesprochen wird.
* **Eigenschaften** mit eigener Kennung und Wert.
* **Verknüpfungen** über benannte Verknüpfungstypen.
* **Medien**, die an Objekten hängen und getrennt abrufbar sind.

„Dynamisch“ heißt: Objekt-, Eigenschafts- und Verknüpfungstypen sind Konfiguration und nicht Programmcode.
Eine Behörde kann ihr Fachmodell ändern, ohne die Software neu zu bauen [B/C]. Die Web-Dokumentation führt
Endpunkte zum Lesen, Anlegen und Durchsuchen von Objekten sowie zum Auflisten und Anlegen verknüpfter
Objekte [B]; im gelesenen SDK-Stand sind diese noch nicht enthalten [A].

### 2.2 Sicherheit an jedem einzelnen Datenbestandteil

Das ist der architektonisch auffälligste Punkt, direkt aus den SDK-Modellen [A]:

* Sicherheit wird **je Bestandteil eines Objekts** vergeben: jede Eigenschaft, jedes Medium und jede
  Verknüpfung hat eine eigene Sicherheitsangabe.
* Eine Sicherheitsangabe besteht aus **Einstufungsmarkierungen** („portion markings“) und
  **Gruppenrechten**.
* Markierungen werden gegen die Regeln einer einstufungsbasierten Zugriffskontrolle geprüft; ungültige
  Kombinationen werden abgewiesen.
* Gruppenrechte kennen drei Stufen: Lesen, Schreiben, Besitzen. Jede höhere Stufe schließt die niedrigeren
  ein. Bei mehreren Gruppen zählt das höchste Recht.
* Markierungen sind beim Anlegen eines Objekts und beim Hinzufügen einer Eigenschaft Pflicht.
* Folge, ausdrücklich so beschrieben: Ein Nutzer kann ein Objekt sehen, ohne alle seine Eigenschaften zu
  sehen. Wer eine hoch eingestufte Eigenschaft anlegt, sieht sie unter Umständen bei der nächsten Abfrage
  selbst nicht mehr.
* Auch Nachrichten und weitere Artefakte tragen eine eigene Sicherheitsangabe.

Zwei Deployments mit unterschiedlichen Einstufungsschemata können Daten austauschen, wenn
Übersetzungsregeln zwischen den Schemata bestehen; dazu gibt es eine Palantir-Patentanmeldung
(US20150261847A1) [B].

### 2.3 Zeit und Ort als eigener Datenbereich

Bewegungsdaten liegen nicht als Objekteigenschaften vor, sondern in einem eigenen Bereich („Geotime“) [A]:

* Eine **Beobachtung** hat Quellsystem, Sammlung, Position, Zeitstempel und eine Spur-Kennung.
* Eigenschaften sind getrennt in **gleichbleibende** (z. B. ein Kennzeichen) und **laufend veränderliche**
  (z. B. ein Kurs).
* Beobachtungen mit gleicher Kennung bilden eine **Spur**. Spuren lassen sich untereinander und mit
  Objekten verknüpfen und wieder lösen.
* Abfragen gibt es für den jeweils letzten Stand und für den Verlauf.

Dahinter steht ein allgemeines Muster: Massendaten mit hoher Schreibrate bleiben außerhalb des
Objektgraphen und werden nur per Verweis angebunden.

### 2.4 Föderierte Suche

Externe Systeme werden als „föderierte Quellen“ mit Namensräumen geführt [A]. Suchanfragen sind als Baum
aus Und-, Oder-, Nicht- und Begriffsknoten formuliert [A]. Daten können also dort durchsucht werden, wo sie
liegen, ohne sie vorher vollständig zu übernehmen.

### 2.5 Abgleich zwischen Installationen

„Nexus Peering“ gleicht Daten zwischen Gotham-Installationen ab. Laut Herstellerbroschüre arbeitet eine
Installation auch ohne Verbindung weiter und stellt ausgehende Daten zurück, bis die Verbindung wieder
steht [B]. Für Foundry ist „Ontology Peering“ dokumentiert: Abgleich je Objekttyp, mit einstellbarer
Richtung [B]. Ob der Abgleich gleichberechtigtes Schreiben auf beiden Seiten erlaubt, ließ sich nicht
belegen.

### 2.6 Anwendungen

| Anwendung | Zweck | Quelle |
|---|---|---|
| Object Explorer | Von oben nach unten: große Bestände filtern, eingrenzen, Teilmengen auswerten | [B] |
| Graph | Von unten nach oben: von einem Objekt aus Verbindungen aufdecken („Search Around“) | [B/C] |
| Gaia | Karte und Lagebild; Karten laden, Ebenen und Objekte hinzufügen, Export als KMZ | [A] |
| Dossier | Gemeinsames Schreiben von Berichten | [B] |
| Browser | Eine Suche über interne und externe Quellen | [C] |
| Inbox | Nachrichten an Gruppen, mit eigener Sicherheitsangabe | [A] |
| Target Workbench | Militärische Zielbearbeitung | [A] – existiert in der API, wird hier bewusst nicht weiter betrachtet |

### 2.7 Technische Grundlagen

* **Schnittstellen aus einer Spezifikation.** Das Gotham-SDK ist vollständig maschinell aus der
  API-Spezifikation erzeugt [A]. Mit Conjure hat Palantir ein eigenes Werkzeug veröffentlicht, das aus
  einer Schnittstellenbeschreibung typisierte Clients und Server-Gerüste für mehrere Sprachen erzeugt [A].
* **Versionierte, ressourcenbezogene API.** Jeder Endpunkt trägt die Hauptversion im Pfad [A]; Anmeldung über
  OAuth 2.0 [B]. Fast alles hat eine eigene typisierte Kennung (im SDK Dutzende `…Rid`- und `…Id`-Typen) [A].
* **AtlasDB.** Transaktionsschicht über Schlüssel-Wert-Datenbanken [A]:
  * Gleiche Transaktionssemantik unabhängig von der Datenbank darunter (Cassandra, Postgres, im Test ein
    Speicher im Arbeitsspeicher).
  * Snapshot-Isolation und serialisierbare Isolation, ohne Deadlocks; Konflikte führen zum Wiederholen.
  * Eigene Dienste für Zeitstempel und Sperren.
  * Indizes bleiben konsistent, weil Daten und Index in derselben Transaktion geschrieben werden.
  * Umzug zwischen Datenbanken im laufenden Betrieb.

  Palantir hat AtlasDB für eigene Produkte entwickelt. Ob Gotham es heute noch nutzt, ist öffentlich nicht
  belegt; das Repository ist seit November 2024 archiviert.
* **Oberfläche.** Blueprint ist Palantirs offener Baukasten für datenintensive Desktop-Oberflächen [A].
  Dass Gothams Web-Anwendungen darauf aufbauen, ist naheliegend, aber nicht belegt [C].

## 3. Rechtlicher Rahmen in Deutschland

Gotham läuft in Deutschland unter Namen wie „hessenDATA“ bei Landespolizeien [B/C]. Das
Bundesverfassungsgericht hat am 16. Februar 2023 die damaligen Rechtsgrundlagen in Hessen und Hamburg für
verfassungswidrig erklärt (1 BvR 1547/19, 1 BvR 2634/20) [B]. Automatisierte Datenanalyse ist danach nicht
grundsätzlich unzulässig, aber ein Grundrechtseingriff [B]. Sein Gewicht hängt von Art und Umfang der
Daten und von der Analysemethode ab [C]. Sekundärquellen nennen als zentrale Anforderungen die
Kennzeichnung von Daten und den Grundsatz der hypothetischen Datenneuerhebung [B]: Daten dürfen nur für
Zwecke weiterverwendet werden, für die sie auch neu erhoben werden dürften.

Das Urteil betrifft Polizeibehörden, nicht private Recherche. Die Leitgedanken – Zweckbindung, Kennzeichnung
der Herkunft, Begrenzung der einbezogenen Daten, Nachvollziehbarkeit – decken sich aber mit dem, was die
DSGVO von privaten Ermittlern verlangt. Dies ist keine Rechtsberatung.

## 4. Was EagleEye daraus lernen kann

Abgleich mit dem aktuellen Code (Stand Build 492).

| Gotham-Muster | Stand in EagleEye | Vorschlag |
|---|---|---|
| **Eigenschaften als einzelne, belegte Aussagen** | Eine Entität hat nur Bezeichnung und ein freies Notizfeld (`entity461`: `label`, `notes`). Geburtsdatum, Adresse, Registernummer haben keinen eigenen Platz und keine eigene Quelle. | Eigenschaften als eigene Datensätze: Typ, Wert, Fundstelle, Gültigkeitszeitraum, Prüfstatus. Das ist der größte einzelne Hebel und Voraussetzung für besseren Entitätenabgleich. |
| **Ontologie als Konfiguration** | Sechs fest einprogrammierte Entitätsarten; Beziehungsarten sind Freitext. | Kleines Typenregister: Entitätsarten, Eigenschaftsarten, Beziehungsarten mit erlaubten Endpunkten. Gibt einheitliche Bezeichnungen und eine saubere Abbildung auf FollowTheMoney. |
| **Markierung an jedem Bestandteil** | Rechte gelten je Fall und Rolle. Einzelne Belege, Fundstellen oder Befunde tragen keine Schutzmarkierung. | Markierungen je Beleg und Befund, z. B. „intern“, „mandantenfähig“, „besondere personenbezogene Daten“. Berichte und Exporte filtern danach. Markierung beim Anlegen verpflichtend. |
| **Zwei Wege der Auswertung** | Graph (von einem Knoten aus) und Listen sind vorhanden. Eine Auswertung von oben – filtern, zählen, eingrenzen über alle Entitäten und Dokumente eines Falls – fehlt. | Fallübersicht mit Filtern und Zählungen (nach Art, Quelle, Zeitraum, Prüfstatus) und „Umfeld anzeigen“ an jeder Entität: alle verknüpften Dokumente, Fundstellen, Entitäten. |
| **Zeit und Ort getrennt vom Graph** | Beziehungen haben Gültigkeitsdaten; Ortsangaben aus Bild-Metadaten existieren. Eine Kartenansicht war im aktuellen Arbeitsablauf nicht zu finden. | Ereignisse mit Zeit und Ort als eigener Datensatz, verknüpft mit Entität und Fundstelle. Daraus Zeitleiste und einfache Karte. |
| **Suchanfrage als Baum** | Die Dork-Engine erzeugt Suchlinks je Anbieter. | Eine Anfrage einmal als Und/Oder/Nicht-Baum formulieren und je Quelle übersetzen. |
| **Abgleich zwischen Installationen** | Backup und Wiederherstellung eines ganzen Arbeitsordners. | Für Teamarbeit: Fallpakete mit Hashes, die sich in eine zweite Installation einspielen lassen, mit Konfliktanzeige statt Überschreiben. |
| **Eine Transaktionsgrenze** | Entitäten liegen in einer eigenen SQLite-Datei (`entity_registry_462.sqlite3`), Prüfentscheidungen und Dokumente in der Hauptdatenbank. Eine Transaktion kann nicht beide umfassen. | Entitätenregister in die Hauptdatenbank überführen. Dann sind Entität, Eigenschaft, Fundstelle und Prüfung gemeinsam konsistent. |
| **Schnittstelle aus einer Spezifikation** | Seiten werden als verkettete Zeichenketten mit Hand-Escaping gebaut. | Vorlagen mit automatischem Escaping; für Daten typisierte Endpunkte (FastAPI/Pydantic ist vorhanden). Senkt das XSS-Risiko und den Pflegeaufwand. |

### Bewusst nicht übernehmen

* **Zielbearbeitung** und alles, was auf operative Maßnahmen gegen Personen zielt.
* **Zusammenführen ohne Zweckgrenze.** Gothams Stärke, beliebige Bestände zu verknüpfen, ist zugleich der
  Kern der verfassungsrechtlichen Kritik. EagleEye bleibt beim Fall mit dokumentiertem Auftrag.
* **Automatische Bewertungen** von Personen ohne nachvollziehbare Begründung.
* **Großarchitektur** (verteilte Datenbanken, Abgleichnetze). Für einen Einzelplatz ist SQLite richtig.

## 5. Grenzen dieser Analyse

* Die offizielle Gotham-Dokumentation konnte nicht im Volltext gelesen werden (`www.palantir.com` war in der
  Entwicklungsumgebung gesperrt). Alle [B]-Aussagen stammen aus Suchzusammenfassungen.
* Das SDK ist als „in Erprobung“ gekennzeichnet und bildet nur einen Teil der Plattform ab.
* Über den inneren Aufbau der Objektdatenbank (Versionierung, Herkunftsnachweis je Eigenschaft,
  Suchindex) gibt es in den gelesenen Quellen keine belastbaren Angaben.
* Verbreitete Darstellungen im Netz stammen überwiegend von Beratern, Investoren-Blogs und Kritikern und
  widersprechen sich in Details.

## 6. Quellen

Primär gelesen [A]:
* https://github.com/palantir/gotham-platform-python
* https://github.com/palantir/atlasdb
* https://github.com/palantir/conjure
* https://github.com/palantir/defense-sdk-examples
* https://github.com/palantir/blueprint

Über Suchergebnisse [B]:
* Gotham-API-Dokumentation: https://www.palantir.com/docs/gotham/api/
* Verknüpfte Objekte auflisten: https://www.palantir.com/docs/gotham/api/revdb-resources/objects/list-linked-objects
* Type Mapping Foundry–Gotham: https://www.palantir.com/docs/foundry/object-link-types/enable-gotham-integration
* Ontology Peering: https://www.palantir.com/docs/foundry/peer-manager/ontology-peering-overview
* G-Cloud-14-Leistungsbeschreibung Gotham: https://assets.applytosupply.digitalmarketplace.service.gov.uk/g-cloud-14/documents/92736/801146272055049-service-definition-document-2024-11-26-1253.pdf
* Patentanmeldung US20150261847A1: https://patents.google.com/patent/US20150261847
* Bund Deutscher Kriminalbeamter zum BVerfG-Urteil: https://www.bdk.de/der-bdk/was-wir-tun/aktuelles/keine-palantire-fuer-die-polizei-das-urteil-des-bundesverfassungsgerichts-zum-betrieb-polizeilicher-analyseplattformen-1/aspdf
* netzpolitik.org zur automatisierten Datenanalyse: https://netzpolitik.org/2024/automatisierte-datenanalyse-bei-der-polizei-bundeslaender-nicht-scharf-auf-palantir/

Sekundär [C]:
* https://www.bdemerson.com/article/palantir-gotham
* https://www.researchgate.net/publication/412229812
