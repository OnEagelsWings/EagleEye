<#
  EagleEye – öffentliches Büro-Zertifikat auf einem Büro-Rechner als vertrauenswürdig eintragen.

  Danach zeigt Windows bei EagleEye-Setup-…exe Ihren Büronamen als Herausgeber und erkennt jede
  nachträgliche Veränderung der Datei. Eingetragen wird nur das öffentliche Zertifikat (.cer), nie ein
  privater Schlüssel. Der Fingerabdruck muss mit dem beim Erstellen notierten übereinstimmen.

  Aufruf (PowerShell als Administrator, gilt dann für alle Benutzer dieses Rechners):
    powershell -ExecutionPolicy Bypass -File Buero-Zertifikat-vertrauen.ps1 -Zertifikat EagleEye-Buero-Signatur.cer -Fingerabdruck <SHA-1>
#>
param(
    [Parameter(Mandatory = $true)][string]$Zertifikat,
    [Parameter(Mandatory = $true)][string]$Fingerabdruck
)
$ErrorActionPreference = 'Stop'

$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2((Resolve-Path $Zertifikat).Path)
$erwartet = ($Fingerabdruck -replace '[^0-9A-Fa-f]', '').ToUpper()
if ($cert.Thumbprint -ne $erwartet) {
    throw "Fingerabdruck stimmt nicht: Datei $($cert.Thumbprint), erwartet $erwartet. Nichts eingetragen."
}
if (-not ($cert.Subject -like '*EagleEye intern*')) {
    throw "Das ist kein EagleEye-Büro-Zertifikat ($($cert.Subject)). Nichts eingetragen."
}
if ($cert.HasPrivateKey) { throw "Die Datei enthält einen privaten Schlüssel. Bitte nur die .cer-Datei verwenden." }

$istAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$ort = if ($istAdmin) { 'LocalMachine' } else { 'CurrentUser' }
foreach ($speicher in 'Root', 'TrustedPublisher') {
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store($speicher, $ort)
    $store.Open('ReadWrite')
    $store.Add($cert)
    $store.Close()
}
Write-Host "Eingetragen für $(if ($istAdmin) { 'alle Benutzer dieses Rechners' } else { 'den aktuellen Benutzer' }): $($cert.Subject)"
Write-Host "Entfernen: certlm.msc bzw. certmgr.msc -> Vertrauenswürdige Stammzertifizierungsstellen und Vertrauenswürdige Herausgeber."
