# Explicit offline rollback to a previously installed and SHA256-verified RC.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Version,
    [string]$Destination = (Join-Path $env:LOCALAPPDATA 'Programs\EagleEyeResearchBridge'),
    [switch]$NoShortcuts
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($Version -notmatch '^1\.0\.0-rc[0-9]+$') { throw 'Invalid RC version' }
$root = [IO.Path]::GetFullPath($Destination)
$marker = Join-Path $root '.eagleeye-public-research-bridge'
if (-not (Test-Path -LiteralPath $marker -PathType Leaf) -or
    (Get-Content -LiteralPath $marker -Raw).Trim() -ne 'eagleeye-public-research-bridge') {
    throw 'Unrecognized installation'
}
$manifestPath = Join-Path $root ("manifests\" + $Version + '.json')
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw 'No verified manifest for this version'
}
$m = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($m.version -ne $Version -or $m.app_id -ne 'eagleeye-public-research-bridge') {
    throw 'Manifest does not match installed version'
}
$folder = Join-Path $root ("versions\" + $Version)
if (-not (Test-Path -LiteralPath $folder -PathType Container)) {
    throw 'Installed version missing'
}
foreach ($file in $m.files) {
    $relative = [string]$file.path
    if ($relative -notmatch '^payload/ResearchBridge/[A-Za-z0-9_.+/\-]+$' -or
        $relative -match '(^|/)\.\.?(/|$)') { throw 'Manifest path unsafe' }
    $target = Join-Path $folder ($relative.Substring('payload/ResearchBridge/'.Length) -replace '/', '\')
    $info = Get-Item -LiteralPath $target -Force -ErrorAction Stop
    if ($info.Attributes -band [IO.FileAttributes]::ReparsePoint -or
        (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) {
        throw "Installed version modified: $relative"
    }
}
Set-Content -LiteralPath (Join-Path $root 'current-version.txt.tmp') -Value $Version -Encoding ASCII
Move-Item -LiteralPath (Join-Path $root 'current-version.txt.tmp') -Destination (Join-Path $root 'current-version.txt') -Force
if (-not $NoShortcuts) {
    $path = Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'EagleEye Forschungs-Bruecke (Vorschau).lnk'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($path)
    $shortcut.TargetPath = Join-Path $folder 'ResearchBridge.exe'
    $shortcut.WorkingDirectory = $folder
    $shortcut.Save()
}
Write-Output "VERSION_SWITCH_OK version=$Version"
