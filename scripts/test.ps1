$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendPython = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
$desktopDir = Join-Path $repoRoot "apps\desktop"
$cargo = Get-Command cargo -ErrorAction SilentlyContinue

function Assert-NativeSuccess {
    param([Parameter(Mandatory = $true)][string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath $backendPython)) {
    throw "Backend environment is missing. Run .\scripts\bootstrap.ps1 first."
}

Set-Location $repoRoot
& $backendPython -m pytest "backend\tests"
Assert-NativeSuccess "Backend tests"

Push-Location $desktopDir
try {
    npm run typecheck
    Assert-NativeSuccess "Frontend type checking"
    npm run build
    Assert-NativeSuccess "Frontend production build"
}
finally {
    Pop-Location
}

if ($cargo) {
    & $cargo.Source check --manifest-path (Join-Path $desktopDir "src-tauri\Cargo.toml")
    Assert-NativeSuccess "Tauri Rust check"
}
else {
    $cargoFallback = Join-Path $env:USERPROFILE ".cargo\bin\cargo.exe"
    if (-not (Test-Path -LiteralPath $cargoFallback)) {
        throw "Cargo was not found. Install Rust with rustup before running the complete check."
    }
    & $cargoFallback check --manifest-path (Join-Path $desktopDir "src-tauri\Cargo.toml")
    Assert-NativeSuccess "Tauri Rust check"
}

Write-Host "All Ozon Assistant checks passed." -ForegroundColor Green
