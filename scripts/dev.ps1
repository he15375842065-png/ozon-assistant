param(
    [switch]$Web
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendPython = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
$desktopDir = Join-Path $repoRoot "apps\desktop"
$apiPort = 8001
$healthUri = "http://127.0.0.1:$apiPort/api/v1/health"

function Assert-NativeSuccess {
    param([Parameter(Mandatory = $true)][string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath $backendPython)) {
    throw "Backend environment is missing. Run .\scripts\bootstrap.ps1 first."
}

if (-not (Test-Path -LiteralPath (Join-Path $desktopDir "node_modules"))) {
    throw "Frontend dependencies are missing. Run .\scripts\bootstrap.ps1 first."
}

$listener = Get-NetTCPConnection -LocalPort $apiPort -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "Port $apiPort is already in use. Stop that process before starting Ozon Assistant."
}

$backend = Start-Process `
    -FilePath $backendPython `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "$apiPort") `
    -WorkingDirectory $repoRoot `
    -WindowStyle Hidden `
    -PassThru

try {
    $apiReady = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        $backend.Refresh()
        if ($backend.HasExited) {
            throw "The backend exited before its health check succeeded (exit code $($backend.ExitCode))."
        }

        try {
            $health = Invoke-RestMethod -Uri $healthUri -Method Get -TimeoutSec 1 -ErrorAction Stop
            if ($health.status -eq "ok") {
                $apiReady = $true
                break
            }
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
    }

    if (-not $apiReady) {
        throw "The backend did not become ready at $healthUri within 10 seconds."
    }

    $env:VITE_API_URL = "http://127.0.0.1:$apiPort/api/v1"
    Push-Location $desktopDir
    try {
        if ($Web) {
            npm run dev
            Assert-NativeSuccess "Vite development server"
        }
        else {
            npm run tauri dev
            Assert-NativeSuccess "Tauri development application"
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id
    }
}
