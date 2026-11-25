# Local, manifest-verified, no-admin EagleEye Research Bridge RC installer.
[CmdletBinding()]
param(
    [string]$Destination = (Join-Path $env:LOCALAPPDATA 'Programs\EagleEyeResearchBridge'),
    [switch]$NoShortcuts
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function Get-LocalSHA256([string]$path) {
    $stream = [IO.File]::OpenRead($path)
    try {
        $sha = [Security.Cryptography.SHA256]::Create()
        try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
        finally { $sha.Dispose() }
    } finally { $stream.Dispose() }
}
function Assert-Safe([string]$candidate) {
    $full = [IO.Path]::GetFullPath($candidate)
    if ($full -match '^\\\\' -or $full -match '^[A-Za-z]:\\$') {
        throw "UNC / drive root destinations forbidden"
    }
    foreach ($blocked in @($env:windir, $env:ProgramFiles, [Environment]::GetEnvironmentVariable('ProgramFiles(x86)'))) {
        if (-not $blocked) { continue }
        if ($full.StartsWith(([IO.Path]::GetFullPath($blocked)).TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw "System installation path forbidden"
        }
    }
    $cursor = $full
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $info = Get-Item -LiteralPath $cursor -Force
            if ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Reparse point forbidden: $cursor"
            }
        }
        $next = Split-Path -Path $cursor -Parent
        if (-not $next -or $next -eq $cursor) { break }
        $cursor = $next
    }
    return $full
}
$manifestFile = Join-Path $PSScriptRoot 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestFile -PathType Leaf)) { throw 'Manifest missing' }
$m = Get-Content -LiteralPath $manifestFile -Raw -Encoding UTF8 | ConvertFrom-Json
if ($m.app_id -ne 'eagleeye-public-research-bridge' -or
    $m.version -notmatch '^1\.0\.0-rc[0-9]+$' -or $m.files.Count -lt 2) {
    throw 'Manifest invalid'
}
$source = Join-Path $PSScriptRoot 'payload\ResearchBridge'
if (-not (Test-Path -LiteralPath (Join-Path $source 'ResearchBridge.exe'))) {
    throw 'Executable missing'
}
$paths = @{}
foreach ($item in $m.files) {
    $rel = [string]$item.path
    if ($rel -notmatch '^payload/ResearchBridge/[A-Za-z0-9_.+/\-]+$' -or
        $rel -match '(^|/)\.\.?(/|$)' -or $paths.ContainsKey($rel) -or
        $item.sha256 -notmatch '^[0-9a-f]{64}$') {
        throw "Unsafe manifest entry: $rel"
    }
    $file = Join-Path $PSScriptRoot ($rel -replace '/', '\')
    $info = Get-Item -LiteralPath $file -Force -ErrorAction Stop
    if (-not ($info -is [IO.FileInfo]) -or
        ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        $info.Length -ne [long]$item.size -or
        (Get-LocalSHA256 $file) -ne $item.sha256) {
        throw "Payload integrity failure: $rel"
    }
    $paths[$rel] = $true
}
if (@(Get-ChildItem -LiteralPath $source -Recurse -File -Force).Count -ne $m.files.Count) {
    throw 'Undeclared payload files'
}
$dest = Assert-Safe $Destination
$marker = Join-Path $dest '.eagleeye-public-research-bridge'
if (Test-Path -LiteralPath $dest) {
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
        throw 'Destination exists but is not a Research Bridge installation'
    }
} else {
    New-Item -Path $dest -ItemType Directory -Force | Out-Null
    Set-Content -LiteralPath $marker -Value 'eagleeye-public-research-bridge' -Encoding ASCII
}
$versions = Join-Path $dest 'versions'
New-Item -Path $versions -ItemType Directory -Force | Out-Null
$target = Join-Path $versions $m.version
if (Test-Path -LiteralPath $target) {
    if (@(Get-ChildItem -LiteralPath $target -Recurse -File -Force).Count -ne $m.files.Count) {
        throw 'Installed version was modified'
    }
    foreach ($item in $m.files) {
        $relative = ([string]$item.path).Substring('payload/ResearchBridge/'.Length)
        $file = Join-Path $target ($relative -replace '/', '\')
        if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or
            (Get-LocalSHA256 $file) -ne $item.sha256) {
            throw "Installed version was modified: $relative"
        }
    }
} else {
    $stage = Join-Path $versions ('.staging-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage | Out-Null
    try {
        Get-ChildItem -LiteralPath $source -Force | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $stage -Recurse -Force
        }
        foreach ($item in $m.files) {
            $relative = ([string]$item.path).Substring('payload/ResearchBridge/'.Length)
            $file = Join-Path $stage ($relative -replace '/', '\')
            if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or
                (Get-LocalSHA256 $file) -ne $item.sha256) {
                throw "Staged version hash mismatch: $relative"
            }
        }
        Move-Item -LiteralPath $stage -Destination $target
    } finally {
        if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
    }
}
$manifestDir = Join-Path $dest 'manifests'
New-Item -ItemType Directory -Path $manifestDir -Force | Out-Null
$installedManifest = Join-Path $manifestDir ($m.version + '.json')
if (Test-Path -LiteralPath $installedManifest) {
    if ((Get-LocalSHA256 $installedManifest) -ne
        (Get-LocalSHA256 $manifestFile)) {
        throw 'Installed version manifest unexpectedly differs'
    }
} else {
    Copy-Item -LiteralPath $manifestFile -Destination $installedManifest
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Uninstall-ResearchBridge.ps1') -Destination (Join-Path $dest 'Uninstall-ResearchBridge.ps1') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Uninstall.cmd') -Destination (Join-Path $dest 'Uninstall.cmd') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Switch-ResearchBridge-Version.ps1') -Destination (Join-Path $dest 'Switch-ResearchBridge-Version.ps1') -Force
Set-Content -LiteralPath (Join-Path $dest 'current-version.txt.tmp') -Value $m.version -Encoding ASCII
Move-Item -LiteralPath (Join-Path $dest 'current-version.txt.tmp') -Destination (Join-Path $dest 'current-version.txt') -Force
if (-not $NoShortcuts) {
    $link = Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'EagleEye Forschungs-Bruecke (Vorschau).lnk'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($link)
    $shortcut.TargetPath = Join-Path $target 'ResearchBridge.exe'
    $shortcut.WorkingDirectory = $target
    $shortcut.Description = 'EagleEye Forschung, nur öffentliche Sachthemen (Release Candidate)'
    $shortcut.Save()
}
Write-Output ("INSTALL_OK version=" + $m.version)
Write-Output ("PROGRAM=" + (Join-Path $target 'ResearchBridge.exe'))
Write-Output 'USER_RESEARCH_DATA_PRESERVED'
