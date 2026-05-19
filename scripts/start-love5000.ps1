param(
    [string]$JavaModule = "website",
    [int]$PythonPort = 5174,
    [string]$PythonCommand = "python",
    [string]$MavenCommand = "mvn",
    [switch]$SkipPython,
    [switch]$SkipJava
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$PythonDir = Join-Path $RootDir "python-a"
$HealthUrl = "http://127.0.0.1:$PythonPort/api/health"

function Test-PythonAHealth {
    param(
        [string]$Url
    )

    try {
        $response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 5
        return $null -ne $response -and $response.ok -eq $true
    } catch {
        return $false
    }
}

function Wait-PythonAHealth {
    param(
        [string]$Url,
        [int]$MaxAttempts = 20
    )

    for ($i = 1; $i -le $MaxAttempts; $i++) {
        if (Test-PythonAHealth -Url $Url) {
            return $true
        }

        Start-Sleep -Seconds 1
    }

    return $false
}

Set-Location -LiteralPath $RootDir

if (-not $SkipPython) {
    if (-not (Test-Path -LiteralPath $PythonDir)) {
        throw "python-a directory does not exist: $PythonDir"
    }

    if (Test-PythonAHealth -Url $HealthUrl) {
        Write-Host "python-a is already running: $HealthUrl"
    } else {
        Write-Host "Starting python-a on port $PythonPort"

        $oldPort = $env:PORT
        $oldPythonUnbuffered = $env:PYTHONUNBUFFERED

        try {
            $env:PORT = [string]$PythonPort
            $env:PYTHONUNBUFFERED = "1"

            $pythonProcess = Start-Process `
                -FilePath $PythonCommand `
                -ArgumentList @("server.py") `
                -WorkingDirectory $PythonDir `
                -WindowStyle Hidden `
                -PassThru

            Write-Host "python-a PID: $($pythonProcess.Id)"
        } finally {
            $env:PORT = $oldPort
            $env:PYTHONUNBUFFERED = $oldPythonUnbuffered
        }

        if (-not (Wait-PythonAHealth -Url $HealthUrl)) {
            throw "python-a health check failed after startup: $HealthUrl"
        }

        Write-Host "python-a health check passed: $HealthUrl"
    }
}

if (-not $SkipJava) {
    Write-Host "Starting Java module: $JavaModule"
    & $MavenCommand -pl $JavaModule -am spring-boot:run
}
