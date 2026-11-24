# Windows-Codesignierung für EagleEye Research Bridge

Stand: 20.11.2026. **Freigabe zur ausschließlichen internen Verwendung der unsignierten RC3 ist vom Nutzer ausdrücklich erteilt.** Das ist keine digital bestätigte Herausgeberidentität und keine Genehmigung für einen öffentlichen Release. Das Release-Gate bleibt solange auf HOLD, wie die vollständige EagleEye-Gesamt-CI fehlschlägt.

## Drei unterschiedliche Schutz- und Vertrauensebenen

1. **SHA-256 + manifestgeprüfter Installer**: stellt Dateiintegrität fest, beweist aber nicht die Identität des Herausgebers. RC3 bereits vorhanden, auf DoMi313 getestet.
2. **Kostenloses selbstsigniertes Authenticode-Zertifikat**: möglich für die eigene Entwicklungs-/Privatumgebung. Ermöglicht eine überprüfbare Signatur, **ist aber nicht allgemein vertrauenswürdig**, erzeugt keine Windows-SmartScreen-Reputation und sollte keinesfalls als öffentliche Code-Signatur beworben werden. Private Schlüssel bleiben im persönlichen Windows-Zertifikatsspeicher. Nur bewusst ausgewählte Nutzergeräte dürfen diesem eigenen Zertifikat vertrauen.
3. **Öffentlich vertrauenswürdige Herausgebersignatur**: Microsoft Azure Artifact Signing (vormals Trusted Signing) oder ein von einer anerkannten Zertifizierungsstelle ausgestelltes OV-/EV-Code-Signing-Zertifikat; benötigt Identitätsprüfung und üblicherweise kostenpflichtigen Dienst bzw. Zertifikat. Auch eine solche Signatur garantiert nicht die Unterdrückung sämtlicher SmartScreen-Warnungen.

## Kostenlose private Signierung (OPTIONAL, noch NICHT durchgeführt)

**Keine Änderung an Zertifikatsspeicher, Root-Trust oder ausführbaren Programmdateien ohne bewusste Freigabe.** PowerShell auf dem eigenen Entwicklerkonto (Windows), ein neues, nur lokal genutztes Schlüsselmaterial:

```powershell
$cert = New-SelfSignedCertificate `
  -Type CodeSigningCert `
  -Subject 'CN=EagleEye Research Bridge - Internal' `
  -CertStoreLocation 'Cert:\CurrentUser\My' `
  -KeyAlgorithm RSA -KeyLength 3072 `
  -KeyExportPolicy NonExportable `
  -NotAfter (Get-Date).AddYears(2)

# Erst einen frisch gebauten Arbeits-Klon des RC-Payloads signieren.
# Kein bestehendes manifestgeprüftes Paket und keine installierte Datei verändern.
$exe = 'D:\EagleEyeResearchBuild\new-unsigned-staging\payload\ResearchBridge\ResearchBridge.exe'
$signature = Set-AuthenticodeSignature -FilePath $exe -Certificate $cert -HashAlgorithm SHA256
$signature | Select-Object Status, StatusMessage, SignerCertificate
```

Eine selbstsignierte Signatur wird auf einem **nicht ausdrücklich vertrauten** Windows-Gerät voraussichtlich als nicht vertrauenswürdig bewertet. Es ist möglich, das **öffentliche** Zertifikat gezielt für den aktuellen Windows-Benutzer als `TrustedPublisher` und Root-Zertifikat zu hinterlegen; das bedeutet aber einen weitreichenden Vertrauensentscheid und sollte nur mit Kenntnis des genauen Fingerabdrucks durchgeführt werden. Nie die private Schlüsseldatei verbreiten oder ein unbekanntes Fremdzertifikat vertrauen. **Keine Sicherheitsfunktionen, Antivirenprüfung, SmartScreen oder Smart App Control global deaktivieren.**

Nach Signaturänderung muss das **Paket vollständig neu manifestiert und als neues RC-ZIP** (neue Version, neuer SHA-256-Wert) gebaut werden. Der ursprüngliche RC3-ZIP-Hash darf nicht mehr als Verifikation eines signierten Pakets genutzt werden. Der interne Buildprozess muss daher die optionale Signierung **vor** Manifest-Berechnung und ZIP-Erstellung unterstützen und danach auf einem Test-Windows-Profil installieren, den Signaturstatus prüfen und die gesamte Testmatrix erneut durchlaufen. Eine eigene Signatur schützt vor unbeabsichtigter Binärmanipulation, ersetzt aber weder die externe Code-Validierung noch das Benutzervertrauen.

## Öffentlich vertrauenswürdige Signierung (später, falls nötig)

1. Identität des Herausgebers bestimmen (Privatperson oder rechtlich eingetragene Organisation).
2. Angebote für Microsoft Azure Artifact Signing oder ein zertifizierungsstellenbasiertes OV/EV-Zertifikat vergleichen; Vertragsbedingungen, Land und Identitätsprüfung vorab prüfen. Keine Ausgabe ohne Budgetfreigabe.
3. Schlüsselverwaltung und Zugriffskontrolle nach Anbieter- und Windows-Richtlinien festlegen.
4. Auf dem **Release-Build vor der finalen Manifestierung** signieren, nach Möglichkeit mit vertrauenswürdigem Zeitstempel, Signatur und Zeitstempel auf einem sauberen Zielgerät überprüfen.
5. Release-Artefakte mit Signatur, SHA-256, Quellcommit und abgeschlossenen Tests dokumentieren.

Microsoft-Originalquellen:
- https://learn.microsoft.com/windows/apps/package-and-deploy/code-signing-options
- https://learn.microsoft.com/windows/apps/package-and-deploy/smartscreen-reputation
- https://learn.microsoft.com/powershell/module/pki/new-selfsignedcertificate
- https://learn.microsoft.com/powershell/module/microsoft.powershell.security/set-authenticodesignature
- https://learn.microsoft.com/azure/artifact-signing/quickstart
