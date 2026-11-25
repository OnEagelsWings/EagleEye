# Uninstalls only the user-scoped RC program. Never deletes research data/DPAPI keys.
[CmdletBinding()]
param(
    [string]$Destination = (Join-Path $env:LOCALAPPDATA 'Programs\EagleEyeResearchBridge'),
    [switch]$ConfirmRemoval,
    [switch]$NoShortcuts
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $ConfirmRemoval) { throw "Explicit -ConfirmRemoval required" }
$dest = [IO.Path]::GetFullPath($Destination)
if ($dest -match '^\\\\' -or $dest -match '^[A-Za-z]:\\$' -or
    $dest.StartsWith(([IO.Path]::GetFullPath($env:windir)).TrimEnd('\') + '\',
                     [StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe uninstall target"
}
$marker = Join-Path $dest '.eagleeye-public-research-bridge'
if (-not (Test-Path -LiteralPath $marker -PathType Leaf) -or
    (Get-Content -LiteralPath $marker -Raw).Trim() -ne 'eagleeye-public-research-bridge') {
    throw "Not a recognized Research Bridge installation"
}
foreach ($node in @(Get-Item -LiteralPath $dest -Force) +
            @(Get-ChildItem -LiteralPath $dest -Force -Recurse)) {
    if ($node.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Refusing to delete reparse point: $($node.FullName)"
    }
}
if (-not $NoShortcuts) {
    $link = Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'EagleEye Forschungs-Bruecke (Vorschau).lnk'
    if (Test-Path -LiteralPath $link) {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($link)
        if ($shortcut.TargetPath.StartsWith($dest.TrimEnd('\') + '\',
                                            [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $link -Force
        }
    }
}
Remove-Item -LiteralPath $dest -Force -Recurse
Write-Output 'UNINSTALL_OK'
Write-Output ("RESEARCH_WORKSPACE_PRESERVED=" + (Join-Path $env:LOCALAPPDATA 'EagleEyeResearchBridge'))
