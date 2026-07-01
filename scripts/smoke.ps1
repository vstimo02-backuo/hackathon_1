param(
    [switch]$KeepRunning
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Invoke-Compose {
    param([string[]]$Arguments)

    docker compose @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $($Arguments -join ' ') failed. Confirm Docker Desktop is running and this terminal can access the Docker daemon."
    }
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

Invoke-Compose -Arguments @("up", "--build", "-d")

$backendReady = $false
for ($attempt = 1; $attempt -le 30; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 2
        if ($health.status -eq "ok") {
            $backendReady = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $backendReady) {
    docker compose logs backend
    throw "Backend health check failed."
}

$frontendReady = $false
for ($attempt = 1; $attempt -le 30; $attempt++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 2 -UseBasicParsing
        if ($response.StatusCode -eq 200 -and $response.Content -match "MergeWise AI") {
            $frontendReady = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $frontendReady) {
    docker compose logs frontend
    throw "Frontend smoke check failed."
}

Write-Host "Smoke validation passed: backend /health and frontend shell are reachable."

if (-not $KeepRunning) {
    Invoke-Compose -Arguments @("down")
}