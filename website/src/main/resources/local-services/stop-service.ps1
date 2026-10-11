param(
    [Parameter(Mandatory=$true)][ValidateSet('strata','aimedia','h3')][string]$Service,
    [Parameter(Mandatory=$true)][string]$Root,
    [Parameter(Mandatory=$true)][ValidateRange(1,65535)][int]$Port
)
$ErrorActionPreference='Stop'
try {
    $projectRoot=[IO.Path]::GetFullPath($Root).TrimEnd('\').ToLowerInvariant()
    if (!(Test-Path -LiteralPath $projectRoot -PathType Container)) { exit 1 }
    $portPattern='--port\s+"?'+[regex]::Escape([string]$Port)+'(?:"|\s|$)'
    $owned=@(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
        $command=([string]$_.CommandLine).Replace('/','\').ToLowerInvariant()
        $matchesPort=$command -match $portPattern
        if ($Service -eq 'strata') {
            $matchesPort -and $command.Contains($projectRoot+'\strata-iq3_s.json') -and $command.Contains('serve\server.py')
        } elseif ($Service -eq 'aimedia') {
            $matchesPort -and $command.Contains($projectRoot+'\services\studio\server.py')
        } else {
            $matchesPort -and ($command.Contains($projectRoot+'\comfyui\main.py') -or
                ($command.Contains($projectRoot+'\comfyui\.venv-rocm\scripts\python.exe') -and $command -match '(?:\s|\\|")main\.py(?:"|\s|$)'))
        }
    })
    $listeners=@(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if ($listeners | Where-Object {$_.OwningProcess -notin $owned.ProcessId}) { exit 1 }
    foreach ($process in $owned) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
    exit 0
} catch { exit 1 }
