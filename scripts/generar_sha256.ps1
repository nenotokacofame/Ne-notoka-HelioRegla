param(
    [string]$InstallerPath = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($InstallerPath)) {
    $candidatos = @(Get-ChildItem -Path (Join-Path $Root "dist_instalador") -Filter "*.exe" -File -ErrorAction SilentlyContinue)
    if ($candidatos.Count -eq 0) {
        throw "No encontré un instalador .exe en dist_instalador. Construye primero el instalador de Windows."
    }
    $InstallerPath = $candidatos[0].FullName
} else {
    if (-not [System.IO.Path]::IsPathRooted($InstallerPath)) {
        $InstallerPath = Join-Path $Root $InstallerPath
    }
    if (-not (Test-Path -LiteralPath $InstallerPath -PathType Leaf)) {
        throw "No existe el archivo indicado: $InstallerPath"
    }
}

$hash = Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256
$relative = (Resolve-Path -LiteralPath $hash.Path -Relative).ToString()
$relative = $relative -replace '^[.][\\/]', ''
$relative = $relative -replace '\\', '/'
$output = Join-Path $Root "SHA256SUMS.txt"
$line = "{0} *{1}" -f $hash.Hash.ToLowerInvariant(), $relative
Set-Content -LiteralPath $output -Value $line -Encoding UTF8

Write-Host "SHA-256 generado correctamente:" -ForegroundColor Green
Write-Host "  $line"
Write-Host "Archivo: $output"
