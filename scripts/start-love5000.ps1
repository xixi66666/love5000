param(
    [string]$JavaModule = "website",
    [int]$PythonPort = 5174,
    [int]$QuantPort = 5175,
    [string]$PythonCommand = "python",
    [string]$MavenCommand = "mvn",
    [switch]$StartQuant,
    [switch]$SkipPython,
    [switch]$SkipJava
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$PythonDir = Join-Path $RootDir "python-a"
$QuantDir = Join-Path $RootDir "quant-a"
$HealthUrl = "http://127.0.0.1:$PythonPort/api/health"
$QuantHealthUrl = "http://127.0.0.1:$QuantPort/api/health"

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

function Test-QuantAHealth {
    param(
        [string]$Url
    )

    try {
        $response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 5
        return $null -ne $response -and $response.success -eq $true
    } catch {
        return $false
    }
}

function Wait-QuantAHealth {
    param(
        [string]$Url,
        [int]$MaxAttempts = 20
    )

    for ($i = 1; $i -le $MaxAttempts; $i++) {
        if (Test-QuantAHealth -Url $Url) {
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

if ($StartQuant) {
    if (-not (Test-Path -LiteralPath $QuantDir)) {
        throw "quant-a directory does not exist: $QuantDir"
    }

    if (Test-QuantAHealth -Url $QuantHealthUrl) {
        Write-Host "quant-a is already running: $QuantHealthUrl"
    } else {
        Write-Host "Starting quant-a on port $QuantPort"

        $quantProcess = Start-Process `
            -FilePath $PythonCommand `
            -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", [string]$QuantPort) `
            -WorkingDirectory $QuantDir `
            -WindowStyle Hidden `
            -PassThru

        Write-Host "quant-a PID: $($quantProcess.Id)"

        if (-not (Wait-QuantAHealth -Url $QuantHealthUrl)) {
            throw "quant-a health check failed after startup: $QuantHealthUrl"
        }

        Write-Host "quant-a health check passed: $QuantHealthUrl"
    }
}

if (-not $SkipJava) {
    Write-Host "Starting Java module: $JavaModule"
    & $MavenCommand -pl $JavaModule -am spring-boot:run
}
