#Requires -Version 5.1
<#
.SYNOPSIS
  Supervise GPT-SoVITS_minimal_inference api_server.py: restart on crash.

.DESCRIPTION
  Runs on the TTS host (same machine as gpt-sovits-minimal). Relaunches the
  PyTorch OpenAI-compatible API if the process exits.

.PARAMETER RestartCooldownSec
  Minimum seconds between restarts. Default: 90

.PARAMETER Port
  API listen port used to clear leftover listeners. Default: 8000

.PARAMETER ListenAddress
  Bind address. Default: 127.0.0.1

.PARAMETER LogPath
  Log file for API stdout/stderr. Default: <repo>/.start-logs/gpt-sovits.log

.PARAMETER ReadyTimeoutSec
  Max seconds to wait for "startup complete" after launch. Default: 180

.PARAMETER PythonExe
  Python interpreter. If omitted, see DEPLOY.md resolution order.

.PARAMETER VoicesConfig
  Path to voices.json relative to this directory. Default: config/voices.json

.EXAMPLE
  .\watch-api.ps1
  .\watch-api.ps1 -LogPath D:\logs\gpt-sovits.log -Port 8000
#>
[CmdletBinding()]
param(
    [int]$RestartCooldownSec = 90,
    [int]$Port = 8000,
    [string]$ListenAddress = "127.0.0.1",
    [string]$LogPath = "",
    [int]$ReadyTimeoutSec = 180,
    [string]$PythonExe = "",
    [string]$VoicesConfig = "config/voices.json"
)

$ErrorActionPreference = "Stop"
$GptDir = $PSScriptRoot
$ApiPy = Join-Path $GptDir "api_server.py"
$RepoRoot = Split-Path -Parent $GptDir
$OfficialDir = Join-Path $RepoRoot "gpt-sovits"
$CnhubertPath = Join-Path $OfficialDir "GPT_SoVITS\pretrained_models\chinese-hubert-base"
$BertPath = Join-Path $OfficialDir "GPT_SoVITS\pretrained_models\chinese-roberta-wwm-ext-large"
$SvPath = Join-Path $OfficialDir "GPT_SoVITS\pretrained_models\sv\pretrained_eres2netv2w24s4ep4.ckpt"
$OfficialPretrained = Join-Path $OfficialDir "GPT_SoVITS\pretrained_models"
$MinimalPretrained = Join-Path $GptDir "pretrained_models"

if (-not (Test-Path -LiteralPath $ApiPy)) {
    throw "api_server.py not found in $GptDir. Clone GPT-SoVITS_minimal_inference into this directory. See DEPLOY.md."
}

function Resolve-CondaCmd {
    $cmd = Get-Command conda -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        (Join-Path $env:USERPROFILE "Miniconda3\Scripts\conda.exe"),
        (Join-Path $env:USERPROFILE "anaconda3\Scripts\conda.exe"),
        "D:\Miniconda\Scripts\conda.exe",
        "C:\Miniconda3\Scripts\conda.exe",
        "C:\ProgramData\miniconda3\Scripts\conda.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { return $c }
    }
    return $null
}

function Resolve-MinimalPython {
    param([string]$Explicit)
    if (-not [string]::IsNullOrWhiteSpace($Explicit) -and (Test-Path -LiteralPath $Explicit)) {
        return (Resolve-Path $Explicit).Path
    }
    if (-not [string]::IsNullOrWhiteSpace($env:GPT_SOVITS_MINIMAL_PYTHON) -and (Test-Path -LiteralPath $env:GPT_SOVITS_MINIMAL_PYTHON)) {
        return (Resolve-Path $env:GPT_SOVITS_MINIMAL_PYTHON).Path
    }
    $venvPy = Join-Path $GptDir ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPy) {
        return (Resolve-Path $venvPy).Path
    }
    $conda = Resolve-CondaCmd
    if ($conda) {
        try {
            $out = & $conda run -n gpt-sovits-minimal --no-capture-output python -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $out) {
                $line = @($out | Where-Object { $_ -and ($_ -match 'python(\.exe)?$') } | Select-Object -Last 1)
                if (-not $line) { $line = @($out | Where-Object { $_ } | Select-Object -Last 1) }
                if ($line -and (Test-Path -LiteralPath $line)) {
                    return $line
                }
            }
        } catch {}
    }
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }
    throw "No Python for gpt-sovits-minimal. Create conda env gpt-sovits-minimal or .venv, or set GPT_SOVITS_MINIMAL_PYTHON. See DEPLOY.md."
}

$PythonExe = Resolve-MinimalPython -Explicit $PythonExe

function Ensure-OfficialPretrainedLink {
    if (-not (Test-Path -LiteralPath $OfficialPretrained)) {
        Write-Watch "Official pretrained_models missing: $OfficialPretrained" Yellow
        return
    }
    if (Test-Path -LiteralPath $MinimalPretrained) {
        return
    }
    try {
        New-Item -ItemType Junction -Path $MinimalPretrained -Target $OfficialPretrained | Out-Null
        Write-Watch "Linked pretrained_models -> $OfficialPretrained"
    } catch {
        Write-Watch "Could not link pretrained_models: $_" Yellow
    }
}

if ([string]::IsNullOrWhiteSpace($LogPath)) {
    $defaultDir = Join-Path $RepoRoot ".start-logs"
    if (-not (Test-Path -LiteralPath $defaultDir)) {
        $defaultDir = Join-Path $GptDir "logs"
    }
    New-Item -ItemType Directory -Path $defaultDir -Force | Out-Null
    $LogPath = Join-Path $defaultDir "gpt-sovits.log"
} else {
    $logParent = Split-Path -Parent $LogPath
    if ($logParent) {
        New-Item -ItemType Directory -Path $logParent -Force | Out-Null
    }
}

$script:ApiProc = $null
$script:LastRestartAt = [datetime]::MinValue
$script:Stopping = $false

function Write-Watch {
    param([string]$Message, [ConsoleColor]$Color = [ConsoleColor]::Cyan)
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message
    Write-Host $line -ForegroundColor $Color
    try {
        $utf8 = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::AppendAllText($LogPath, $line + [Environment]::NewLine, $utf8)
    } catch {}
}

function Stop-ProcessTree {
    param([System.Diagnostics.Process]$Process)
    if ($null -eq $Process) { return }
    try { $Process.Refresh() } catch { return }
    if ($Process.HasExited) { return }

    $procId = $Process.Id
    $taskkill = Get-Command taskkill -ErrorAction SilentlyContinue
    if ($taskkill) {
        & taskkill.exe /PID $procId /T /F 2>$null | Out-Null
    }
    try {
        $Process.Refresh()
        if (-not $Process.HasExited) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    } catch {}
}

function Clear-PortListeners {
    param([int]$ListenPort)
    try {
        $conns = Get-NetTCPConnection -LocalPort $ListenPort -State Listen -ErrorAction SilentlyContinue
        foreach ($c in @($conns)) {
            if ($c.OwningProcess -and $c.OwningProcess -gt 0) {
                Write-Watch "Clearing leftover listener PID $($c.OwningProcess) on port $ListenPort" Yellow
                & taskkill.exe /PID $c.OwningProcess /T /F 2>$null | Out-Null
            }
        }
    } catch {}
}

function Start-ApiProcess {
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONUTF8 = "1"

    $hubertArg = $CnhubertPath
    $bertArg = $BertPath
    if (Test-Path -LiteralPath $SvPath) {
        $env:SV_MODEL_PATH = $SvPath
    }
    $arg = '/c chcp 65001 >nul & set PYTHONIOENCODING=utf-8& set PYTHONUTF8=1& "' +
        $PythonExe + '" -X utf8 api_server.py --host ' + $ListenAddress + ' --port ' + $Port +
        ' --voices_config "' + $VoicesConfig + '"' +
        ' --cnhubert_path "' + $hubertArg + '"' +
        ' --bert_path "' + $bertArg + '"' +
        ' >> "' + $LogPath + '" 2>&1'

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "cmd.exe"
    $psi.Arguments = $arg
    $psi.WorkingDirectory = $GptDir
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    [void]$proc.Start()
    return $proc
}

function Wait-ApiReady {
    param(
        [int]$TimeoutSeconds,
        [long]$LogOffsetBytes = 0
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($script:ApiProc -and $script:ApiProc.HasExited) {
            return $false
        }
        if (Test-Path -LiteralPath $LogPath) {
            try {
                $fs = [System.IO.File]::Open(
                    $LogPath,
                    [System.IO.FileMode]::Open,
                    [System.IO.FileAccess]::Read,
                    [System.IO.FileShare]::ReadWrite
                )
                try {
                    if ($LogOffsetBytes -gt $fs.Length) {
                        $LogOffsetBytes = 0
                    }
                    $fs.Seek($LogOffsetBytes, [System.IO.SeekOrigin]::Begin) | Out-Null
                    $reader = New-Object System.IO.StreamReader($fs, [System.Text.Encoding]::UTF8, $true)
                    $text = $reader.ReadToEnd()
                    $reader.Dispose()
                } finally {
                    $fs.Dispose()
                }
                if ($text -match "(?i)startup\s+complete" -or $text -match "Uvicorn running") {
                    return $true
                }
            } catch {}
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Restart-Api {
    param([string]$Reason)

    $since = ([datetime]::Now - $script:LastRestartAt).TotalSeconds
    if ($script:LastRestartAt -ne [datetime]::MinValue -and $since -lt $RestartCooldownSec) {
        Write-Watch ("Restart skipped (cooldown {0:N0}s left): {1}" -f ($RestartCooldownSec - $since), $Reason) DarkYellow
        return
    }

    Write-Watch "Restarting GPT-SoVITS minimal ($Reason) ..." Yellow
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::AppendAllText(
        $LogPath,
        ("`r`n=== GPT-SoVITS minimal auto-restart ({0}) ===`r`n" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
        $utf8
    )

    $logOffset = 0
    if (Test-Path -LiteralPath $LogPath) {
        $logOffset = (Get-Item -LiteralPath $LogPath).Length
    }

    Stop-ProcessTree -Process $script:ApiProc
    Start-Sleep -Seconds 1
    Clear-PortListeners -ListenPort $Port
    Start-Sleep -Seconds 1

    $script:ApiProc = Start-ApiProcess
    $script:LastRestartAt = [datetime]::Now
    Write-Watch "Launched PID=$($script:ApiProc.Id)"

    if (Wait-ApiReady -TimeoutSeconds $ReadyTimeoutSec -LogOffsetBytes $logOffset) {
        Write-Watch "GPT-SoVITS minimal is ready." Green
    } else {
        Write-Watch "GPT-SoVITS minimal did not become ready within ${ReadyTimeoutSec}s." Red
    }
}

function Stop-Watchdog {
    if ($script:Stopping) { return }
    $script:Stopping = $true
    Write-Watch "Stopping watchdog and API ..." Yellow
    Stop-ProcessTree -Process $script:ApiProc
    Clear-PortListeners -ListenPort $Port
}

$null = Register-EngineEvent -SourceIdentifier ConsoleBreak -Action { } -ErrorAction SilentlyContinue
try {
    [Console]::TreatControlCAsInput = $false
} catch {}

Write-Watch "watch-api starting"
Write-Watch "  WorkDir:  $GptDir"
Write-Watch "  Python:   $PythonExe"
Write-Watch "  LogPath:  $LogPath"
Write-Watch "  Listen:   ${ListenAddress}:${Port} | Cooldown: ${RestartCooldownSec}s"
Ensure-OfficialPretrainedLink

try {
    Restart-Api -Reason "initial start"
    $script:LastRestartAt = [datetime]::Now

    while (-not $script:Stopping) {
        Start-Sleep -Seconds 5

        $dead = $false
        if ($null -eq $script:ApiProc) {
            $dead = $true
        } else {
            try {
                $script:ApiProc.Refresh()
                if ($script:ApiProc.HasExited) { $dead = $true }
            } catch {
                $dead = $true
            }
        }

        if ($dead) {
            Restart-Api -Reason "process exited"
        }
    }
} finally {
    Stop-Watchdog
    Write-Watch "watch-api exited."
}
