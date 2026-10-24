# Build 478 – Eigene quellengebundene Arbeitsbefunde

Die Arbeitsbefunde aus dem Windows-Arbeitsstrang sind in den gemeinsamen
Rechercheablauf integriert. Ein Befund wird vom Nutzer formuliert und als
Arbeitsnotiz, Beobachtung, Hypothese, Gegenbeleg oder Unsicherheit eingeordnet.
Die ausgewählte Originalfundstelle, deren Text, Dokument-SHA256 und Anker-Hash
werden zusammen mit Autor und Zeitpunkt gespeichert. Das bestätigt keine Tatsache.

Die Notizen liegen in der vorhandenen Falldatenbank. Ältere Notizen des
Vorab-Entwurfs aus PR #73 können aus ihrer bisherigen Sidecar-Datei übernommen
werden; die Ursprungsdatei bleibt erhalten, bisherige Eigenprüfungen werden
nicht automatisch übernommen. Übernommene Notizen benötigen erneute Prüfung.

Fall und Berechtigung, unveränderte Rohdatei, Dokument-/Ankerzuordnung und
Record-Hashes werden vor dem Speichern innerhalb der Datenbanktransaktion
nochmals geprüft. Unzulässiger CSRF/Origin, veränderte Belege, verworfene
Extraktionen und beschädigte Notizen werden abgewiesen. Ein Formularbudget
begrenzt auch gestreamte Anfragen ohne Content-Length.

Alle Dokumente können ausgewählt, ihre Anker in 50er-Seiten durchgeblättert
werden. Gespeicherte Befunde sind ebenfalls paginiert. Im Quelleninventar führt
„Befund notieren“ direkt zum ausgewählten Dokument. Der nachfolgende Arbeitsbericht
ist noch keine offizielle Dossierfreigabe; er folgt in Build 479.
