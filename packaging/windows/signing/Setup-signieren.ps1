<#
  EagleEye – heruntergeladenes Installationsprogramm mit dem Büro-Zertifikat signieren und prüfen.

  1. Prüft zuerst die SHA-256-Prüfsumme gegen die .sha256-Datei aus dem GitHub-Lauf
     (signiert wird nur, was unverändert aus dem Bau kommt).
  2. Signiert mit SHA-256 und einem Zeitstempel (RFC 3161). Mit Zeitstempel bleibt die Signatur gültig,
     auch wenn das Zertifikat später abläuft.
  3. Prüft die Signatur und schreibt eine neue Prüfsumme (die alte gilt nach dem Signieren nicht mehr).

  Aufruf (PowerShell, als der Benutzer, der das Zertifikat erstellt hat):
    powershell -ExecutionPolicy Bypass -File Setup-signieren.ps1 -Setup EagleEye-Setup-500.0.12.exe
#>
param(
    [Parameter(Mandatory = $true)][string]$Setup,
    [string]$Zeitstempeldienst = 'http://timestamp.digicert.com'
)
$ErrorActionPreference = 'Stop'

$datei = (Resolve-Path $Setup).Path
$pruefdatei = "$datei.sha256"
if (-not (Test-Path $pruefdatei)) { throw "Prüfsummendatei fehlt: $pruefdatei (liegt im GitHub-Download neben dem Setup)." }
$soll = ((Get-Content $pruefdatei -Raw).Trim() -split '\s+')[0].ToLower()
$ist = (Get-FileHash $datei -Algorithm SHA256).Hash.ToLower()
if ($soll -ne $ist) { throw "Prüfsumme stimmt nicht – Datei verändert oder unvollständig. Nicht signiert." }

$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -like '*EagleEye intern*' -and $_.NotAfter -gt (Get-Date) } | Sort-Object NotAfter -Descending | Select-Object -First 1
if (-not $cert) { throw "Kein gültiges Büro-Zertifikat gefunden. Zuerst Buero-Zertifikat-erstellen.ps1 ausführen." }

$ergebnis = Set-AuthenticodeSignature -FilePath $datei -Certificate $cert -HashAlgorithm SHA256 -TimestampServer $Zeitstempeldienst
if ($ergebnis.Status -ne 'Valid') {
    Write-Host "Signiert, aber auf diesem Rechner nicht als vertrauenswürdig erkannt: $($ergebnis.StatusMessage)"
    Write-Host "Auf diesem Rechner zuerst Buero-Zertifikat-vertrauen.ps1 ausführen."
}
$pruefung = Get-AuthenticodeSignature $datei
if (-not $pruefung.TimeStamperCertificate) { throw "Kein Zeitstempel in der Signatur. Internetverbindung zum Zeitstempeldienst prüfen." }
(Get-FileHash $datei -Algorithm SHA256).Hash.ToLower() + "  " + (Split-Path $datei -Leaf) | Set-Content -Encoding ascii "$datei.signiert.sha256"
Write-Host "Signiert von:   $($pruefung.SignerCertificate.Subject)"
Write-Host "Zeitstempel:    $($pruefung.TimeStamperCertificate.Subject)"
Write-Host "Status:         $($pruefung.Status)"
Write-Host "Neue Prüfsumme: $datei.signiert.sha256"
