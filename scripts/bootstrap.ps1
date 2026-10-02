$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendPython = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
$desktopDir = Join-Path $repoRoot "apps\desktop"

function Assert-NativeSuccess {
    param([Parameter(Mandatory = $true)][string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

Set-Location $repoRoot

if (-not (Test-Path -LiteralPath $backendPython)) {
    $pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pythonLauncher) {
        & $pythonLauncher.Source -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 'Python 3.11 or newer is required.')"
        Assert-NativeSuccess "Checking the Python version"
        & $pythonLauncher.Source -3 -m venv "backend\.venv"
    }
    else {
        $pythonExecutable = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonExecutable) {
            throw "Python 3.11 or newer was not found. Install Python before running bootstrap."
        }
        & $pythonExecutable.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 'Python 3.11 or newer is required.')"
        Assert-NativeSuccess "Checking the Python version"
        & $pythonExecutable.Source -m venv "backend\.venv"
    }
    Assert-NativeSuccess "Creating the Python virtual environment"
}

& $backendPython -m pip install --upgrade pip
Assert-NativeSuccess "Upgrading pip"
& $backendPython -m pip install -e "backend[dev]"
Assert-NativeSuccess "Installing backend dependencies"

Push-Location $desktopDir
try {
    npm ci
    Assert-NativeSuccess "Installing frontend dependencies"
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath (Join-Path $repoRoot ".env"))) {
    Copy-Item -LiteralPath (Join-Path $repoRoot ".env.example") -Destination (Join-Path $repoRoot ".env")
}

Write-Host "Ozon Assistant development dependencies are ready." -ForegroundColor Green
