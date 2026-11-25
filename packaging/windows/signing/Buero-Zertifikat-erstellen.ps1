<#
  EagleEye – eigenes Signierzertifikat für das Büro erzeugen (einmalig, auf dem Rechner, der signiert).

  - Der private Schlüssel bleibt im Zertifikatsspeicher dieses Windows-Benutzers und ist NICHT exportierbar.
    Er verlässt den Rechner nie, auch nicht zu GitHub.
  - Ausgegeben wird nur das öffentliche Zertifikat (EagleEye-Buero-Signatur.cer). Das wird auf den
    Büro-Rechnern mit "Buero-Zertifikat-vertrauen.ps1" als vertrauenswürdig eingetragen.
  - Das Zertifikat gilt nur auf Rechnern, auf denen es eingetragen wurde. Für Dritte (Kunden, fremde PCs)
    ist es wertlos; dafür braucht es ein öffentliches Zertifikat (siehe packaging/windows/README.md).

  Aufruf (PowerShell, normaler Benutzer):
    powershell -ExecutionPolicy Bypass -File Buero-Zertifikat-erstellen.ps1 -Name "Detektei Mustermann"
#>
param(
    [Parameter(Mandatory = $true)][string]$Name,
    [int]$Jahre = 3,
    [string]$Ausgabe = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'EagleEye-Buero-Signatur.cer')
)
$ErrorActionPreference = 'Stop'

$vorhanden = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -eq "CN=$Name - EagleEye intern" -and $_.NotAfter -gt (Get-Date) }
if ($vorhanden) {
    Write-Host "Es gibt bereits ein gültiges Büro-Zertifikat: $($vorhanden[0].Thumbprint) (gültig bis $($vorhanden[0].NotAfter))."
    $cert = $vorhanden[0]
} else {
    $cert = New-SelfSignedCertificate -Type CodeSigningCert `
        -Subject "CN=$Name - EagleEye intern" `
        -CertStoreLocation Cert:\CurrentUser\My `
        -KeyAlgorithm RSA -KeyLength 3072 -HashAlgorithm SHA256 `
        -KeyExportPolicy NonExportable `
        -NotAfter (Get-Date).AddYears($Jahre)
    Write-Host "Neues Büro-Zertifikat erzeugt."
}
Export-Certificate -Cert $cert -FilePath $Ausgabe -Type CERT | Out-Null
Write-Host ""
Write-Host "Öffentliches Zertifikat: $Ausgabe"
Write-Host "Fingerabdruck (SHA-1):  $($cert.Thumbprint)"
Write-Host "Diesen Fingerabdruck notieren: Beim Eintragen auf den Büro-Rechnern wird er verglichen."
