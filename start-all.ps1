#Requires -Version 5.1
<#
.SYNOPSIS
  Start AronaAI backend, GPT-SoVITS, and the desktop client; stay running until stopped.

.DESCRIPTION
  1) Start backend and GPT-SoVITS at the same time
  2) Wait until both logs show a ready signal
  3) Start the frontend client
  4) Keep this script alive and accept commands to stop/start/restart one
     service, or stop all and exit. Ctrl+C also stops all tracked process trees.

  Ready signals (case-insensitive substring match):
    - "启动完毕"
    - "startup complete"   (covers uvicorn "Application startup complete.")

.PARAMETER CondaEnv
  Conda env used for the backend. Default: shittim-chest

.PARAMETER TimeoutSec
  Wait timeout in seconds for both backend services to become ready. Default: 600

.PARAMETER FrontendExe
  Optional path to AronaAI_WindowsClient.exe. If omitted, auto-detect.

.PARAMETER TtsStallSec
  Passed to GPT-SoVITS watchdog (stall seconds). Default: 60

.PARAMETER TtsRestartCooldownSec
  Passed to GPT-SoVITS watchdog (restart cooldown). Default: 90

.EXAMPLE
  .\start-all.ps1
  .\start-all.ps1 -CondaEnv arona -TimeoutSec 900

  After launch, in the control window:
    restart backend
    stop gpt
    start frontend
    stop all
#>
[CmdletBinding()]
param(
    [string]$CondaEnv = "shittim-chest",
    [int]$TimeoutSec = 600,
    [string]$FrontendExe = "",
    [int]$TtsStallSec = 60,
    [int]$TtsRestartCooldownSec = 90
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$LogDir = Join-Path $Root ".start-logs"
$ReadyPatterns = @("启动完毕", "startup complete")
$script:BackendProc = $null
$script:GptProc = $null
$script:FrontendProc = $null
$script:ServicesStopped = $false
$script:BackendDir = $null
$script:GptDir = $null
$script:GptWatch = $null
$script:Conda = $null
$script:FrontendInfo = $null
$script:BackendLog = $null
$script:GptLog = $null
$script:GptWatchdogLog = $null

function Write-Step {
    param([string]$Message, [ConsoleColor]$Color = [ConsoleColor]::Cyan)
    Write-Host ""
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message) -ForegroundColor $Color
}

function Assert-Path {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing ${Label}: $Path"
    }
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
    throw "conda not found. Install Miniconda/Anaconda or add conda to PATH."
}

function Resolve-Frontend {
    param([string]$Explicit)

    if ($Explicit) {
        Assert-Path $Explicit "frontend executable"
        $dir = Split-Path -Parent $Explicit
        return @{ Exe = (Resolve-Path $Explicit).Path; WorkDir = $dir }
    }

    $workDir = Join-Path $Root "frontend\AronaAI_Spine_WindowsClient\dist\AronaAI_Client"
    $candidates = @(
        (Join-Path $workDir "AronaAI_WindowsClient.exe"),
        (Join-Path $workDir "AronaAI_Spine_WindowsClient.exe")
    )
    $exe = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $exe) { $exe = $candidates[0] }
    Assert-Path $exe "frontend executable"
    return @{
        Exe     = (Resolve-Path $exe).Path
        WorkDir = (Resolve-Path $workDir).Path
    }
}

function Test-ReadyLog {
    param([string]$LogPath)

    if (-not (Test-Path -LiteralPath $LogPath)) { return $false }
    try {
        # FileShare.ReadWrite so the writer can keep appending
        $fs = [System.IO.File]::Open(
            $LogPath,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite
        )
        try {
            $reader = New-Object System.IO.StreamReader($fs, [System.Text.Encoding]::UTF8, $true)
            $text = $reader.ReadToEnd()
            $reader.Dispose()
        } finally {
            $fs.Dispose()
        }
    } catch {
        return $false
    }

    if ([string]::IsNullOrWhiteSpace($text)) { return $false }
    if ($text -match "启动完毕") { return $true }
    if ($text -match "(?i)startup\s+complete") { return $true }
    return $false
}

function Wait-ServicesReady {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]]$Services,
        [int]$TimeoutSeconds
    )

    $names = ($Services | ForEach-Object { $_.Name }) -join " + "
    Write-Step "Waiting for $names ready (patterns: $($ReadyPatterns -join ' / ')) ..." Yellow
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $ready = @{}
    foreach ($svc in $Services) { $ready[$svc.Name] = $false }

    while ((Get-Date) -lt $deadline) {
        foreach ($svc in $Services) {
            if ($ready[$svc.Name]) { continue }

            $proc = $svc.Process
            if ($proc -and $proc.HasExited) {
                throw "$($svc.Name) exited early (code $($proc.ExitCode)). See log: $($svc.LogPath)"
            }
            if (Test-ReadyLog -LogPath $svc.LogPath) {
                $ready[$svc.Name] = $true
                Write-Step "$($svc.Name) is ready." Green
            }
        }

        $pending = @($ready.GetEnumerator() | Where-Object { -not $_.Value } | ForEach-Object { $_.Key })
        if ($pending.Count -eq 0) { return }

        Start-Sleep -Milliseconds 500
    }

    $stillPending = @($ready.GetEnumerator() | Where-Object { -not $_.Value } | ForEach-Object { $_.Key })
    $details = ($Services | Where-Object { $stillPending -contains $_.Name } | ForEach-Object { "$($_.Name): $($_.LogPath)" }) -join "; "
    throw "Timed out after ${TimeoutSeconds}s waiting for: $($stillPending -join ', '). See logs: $details"
}

function Stop-TrackedProcessTree {
    param(
        [System.Diagnostics.Process]$Process,
        [string]$Label = "process"
    )

    if ($null -eq $Process) { return }

    try {
        $Process.Refresh()
    } catch {
        return
    }

    if ($Process.HasExited) {
        Write-Host ("  {0} already exited (PID {1})." -f $Label, $Process.Id) -ForegroundColor DarkGray
        return
    }

    $procId = $Process.Id
    Write-Host ("  Stopping {0} (PID {1}) and child processes ..." -f $Label, $procId) -ForegroundColor Yellow
    $taskkill = Get-Command taskkill -ErrorAction SilentlyContinue
    if ($taskkill) {
        & taskkill.exe /PID $procId /T /F 2>$null | Out-Null
    }

    try {
        $Process.Refresh()
        if (-not $Process.HasExited) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    } catch {
        # Process may already be gone.
    }
}

function Stop-AllTrackedServices {
    if ($script:ServicesStopped) { return }
    $script:ServicesStopped = $true

    Write-Step "Stopping all services ..." Yellow
    Stop-TrackedProcessTree -Process $script:BackendProc -Label "Backend"
    Stop-TrackedProcessTree -Process $script:GptProc -Label "GPT-SoVITS"
    Stop-TrackedProcessTree -Process $script:FrontendProc -Label "Frontend"

    $deadline = (Get-Date).AddSeconds(5)
    while ((Get-Date) -lt $deadline) {
        $alive = @()
        foreach ($item in @(
                @{ Name = "Backend"; Process = $script:BackendProc },
                @{ Name = "GPT-SoVITS"; Process = $script:GptProc },
                @{ Name = "Frontend"; Process = $script:FrontendProc }
            )) {
            $p = $item.Process
            if ($null -eq $p) { continue }
            try {
                $p.Refresh()
                if (-not $p.HasExited) { $alive += $item.Name }
            } catch {}
        }
        if ($alive.Count -eq 0) { break }
        Start-Sleep -Milliseconds 200
    }

    Write-Step "All tracked services stopped." Green
}

function Start-ServiceWindow {
    param(
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)][string]$WorkDir,
        [Parameter(Mandatory = $true)][string]$ExePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$LogPath
    )

    if (Test-Path -LiteralPath $LogPath) {
        Remove-Item -LiteralPath $LogPath -Force
    }
    New-Item -ItemType File -Path $LogPath -Force | Out-Null

    # Escape for single-quoted PowerShell string literals inside the child script.
    $titleEsc = $Title -replace "'", "''"
    $workDirEsc = $WorkDir -replace "'", "''"
    $logPathEsc = $LogPath -replace "'", "''"
    $exeEsc = $ExePath -replace "'", "''"
    $argLiterals = @($Arguments | ForEach-Object {
            "'" + ($_ -replace "'", "''") + "'"
        }) -join ", "
    if ([string]::IsNullOrEmpty($argLiterals)) {
        $argArrayExpr = "@()"
    } else {
        $argArrayExpr = "@($argLiterals)"
    }

    # Avoid PowerShell 5.1 "& exe 2>&1" capture (mis-decodes UTF-8 Chinese).
    # Launch with ProcessStartInfo UTF-8 readers and tee to console + log.
    $psCommand = @"
`$ErrorActionPreference = 'Continue'
`$Host.UI.RawUI.WindowTitle = '$titleEsc'
try { chcp 65001 | Out-Null } catch {}
`$utf8 = New-Object System.Text.UTF8Encoding `$false
`$OutputEncoding = `$utf8
try {
    [Console]::OutputEncoding = `$utf8
    [Console]::InputEncoding = `$utf8
} catch {}
`$env:PYTHONIOENCODING = 'utf-8'
`$env:PYTHONUTF8 = '1'
`$env:PYTHONLEGACYWINDOWSSTDIO = '0'
Set-Location -LiteralPath '$workDirEsc'
`$logPath = '$logPathEsc'
`$exe = '$exeEsc'
`$argv = $argArrayExpr
Write-Host '=== $titleEsc ===' -ForegroundColor Cyan
Write-Host ("WorkDir: {0}" -f (Get-Location))
Write-Host ("Command: {0} {1}" -f `$exe, (`$argv -join ' '))
Write-Host ("Log: {0}" -f `$logPath)
Write-Host ''

function Start-Utf8StreamPump {
    param([System.IO.StreamReader]`$Reader)
    `$rs = [System.Management.Automation.Runspaces.RunspaceFactory]::CreateRunspace()
    `$rs.Open()
    `$ps = [PowerShell]::Create()
    `$ps.Runspace = `$rs
    [void]`$ps.AddScript({
        param(`$reader, `$logPath, `$utf8)
        try {
            while (`$null -ne (`$line = `$reader.ReadLine())) {
                [Console]::WriteLine(`$line)
                [System.IO.File]::AppendAllText(`$logPath, `$line + [Environment]::NewLine, `$utf8)
            }
        } catch {}
    }).AddArgument(`$Reader).AddArgument(`$logPath).AddArgument(`$utf8)
    return @{
        PowerShell = `$ps
        Runspace   = `$rs
        Handle     = `$ps.BeginInvoke()
    }
}

try {
    `$psi = New-Object System.Diagnostics.ProcessStartInfo
    `$psi.FileName = `$exe
    # Quote args that contain whitespace; keep simple tokens as-is.
    `$psi.Arguments = (`$argv | ForEach-Object {
            `$a = [string]`$_
            if (`$a -match '\s') { '"' + (`$a -replace '"', '\"') + '"' } else { `$a }
        }) -join ' '
    `$psi.WorkingDirectory = (Get-Location).Path
    `$psi.UseShellExecute = `$false
    `$psi.RedirectStandardOutput = `$true
    `$psi.RedirectStandardError = `$true
    `$psi.RedirectStandardInput = `$false
    `$psi.CreateNoWindow = `$true
    `$psi.StandardOutputEncoding = `$utf8
    `$psi.StandardErrorEncoding = `$utf8
    `$psi.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
    `$psi.EnvironmentVariables['PYTHONUTF8'] = '1'
    `$psi.EnvironmentVariables['PYTHONLEGACYWINDOWSSTDIO'] = '0'

    `$proc = New-Object System.Diagnostics.Process
    `$proc.StartInfo = `$psi
    [void]`$proc.Start()

    `$outPump = Start-Utf8StreamPump -Reader `$proc.StandardOutput
    `$errPump = Start-Utf8StreamPump -Reader `$proc.StandardError

    `$proc.WaitForExit()
    try { [void]`$outPump.PowerShell.EndInvoke(`$outPump.Handle) } catch {}
    try { [void]`$errPump.PowerShell.EndInvoke(`$errPump.Handle) } catch {}
    `$outPump.PowerShell.Dispose()
    `$errPump.PowerShell.Dispose()
    `$outPump.Runspace.Close(); `$outPump.Runspace.Dispose()
    `$errPump.Runspace.Close(); `$errPump.Runspace.Dispose()

    Write-Host ''
    Write-Host ("Process exited with code {0}." -f `$proc.ExitCode) -ForegroundColor Yellow
} catch {
    Write-Host `$_ -ForegroundColor Red
    [System.IO.File]::AppendAllText(`$logPath, `$_.ToString() + [Environment]::NewLine, `$utf8)
}
Write-Host 'Close this window when done.' -ForegroundColor Yellow
pause
"@

    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($psCommand))
    return Start-Process -FilePath "powershell.exe" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encoded) `
        -PassThru `
        -WindowStyle Normal
}

function Test-ProcAlive {
    param([System.Diagnostics.Process]$Process)
    if ($null -eq $Process) { return $false }
    try {
        $Process.Refresh()
        return -not $Process.HasExited
    } catch {
        return $false
    }
}

function Get-TrackedProcess {
    param([ValidateSet("backend", "gpt", "frontend")][string]$Name)
    switch ($Name) {
        "backend" { return $script:BackendProc }
        "gpt" { return $script:GptProc }
        "frontend" { return $script:FrontendProc }
    }
}

function Get-ServiceDisplayName {
    param([string]$Name)
    switch ($Name) {
        "backend" { "Backend" }
        "gpt" { "GPT-SoVITS" }
        "frontend" { "Frontend" }
        default { $Name }
    }
}

function Resolve-ServiceToken {
    param([string]$Token)
    if ([string]::IsNullOrWhiteSpace($Token)) { return $null }
    switch -Regex ($Token.Trim()) {
        '^(?i)(backend|be|back|后端)$' { "backend"; break }
        '^(?i)(gpt|gpt-sovits|sovits|tts|语音)$' { "gpt"; break }
        '^(?i)(frontend|fe|client|桌面|前端)$' { "frontend"; break }
        '^(?i)(all|全部)$' { "all"; break }
        default { $null }
    }
}

function Show-ServiceStatus {
    $rows = @(
        @{ Key = "backend"; Label = "Backend" },
        @{ Key = "gpt"; Label = "GPT-SoVITS" },
        @{ Key = "frontend"; Label = "Frontend" }
    )
    Write-Host ""
    foreach ($row in $rows) {
        $p = Get-TrackedProcess -Name $row.Key
        if (Test-ProcAlive $p) {
            Write-Host ("  {0,-12} running  PID {1}" -f $row.Label, $p.Id) -ForegroundColor Green
        } elseif ($null -eq $p) {
            Write-Host ("  {0,-12} stopped" -f $row.Label) -ForegroundColor DarkGray
        } else {
            $code = $null
            try { $code = $p.ExitCode } catch {}
            Write-Host ("  {0,-12} exited   (code {1})" -f $row.Label, $code) -ForegroundColor Yellow
        }
    }
}

function Show-ControlHelp {
    Write-Host @"

Commands:
  status                         Show running state and PIDs
  stop backend|gpt|frontend      Stop one service
  start backend|gpt|frontend     Start a stopped service
  restart backend|gpt|frontend   Restart one service
  stop all  |  0  |  q  |  exit  Stop everything and close
  help                           Show this help

Shortcuts:  1/2/3 = restart backend/gpt/frontend
            4/5/6 = stop backend/gpt/frontend
            s = status
Aliases:    be=backend, tts/gpt=GPT-SoVITS, fe=frontend
            后端 / 语音 / 前端  (e.g. 重启 后端)
"@
}

function Start-BackendService {
    if (Test-ProcAlive $script:BackendProc) {
        Write-Host ("  Backend is already running (PID {0})." -f ($script:BackendProc).Id) -ForegroundColor Yellow
        return $false
    }
    Write-Step "Starting backend ..."
    $script:BackendProc = Start-ServiceWindow `
        -Title "AronaAI Backend" `
        -WorkDir $script:BackendDir `
        -ExePath $script:Conda `
        -Arguments @("run", "-n", $CondaEnv, "--no-capture-output", "python", "-m", "app.main") `
        -LogPath $script:BackendLog
    return $true
}

function Start-GptService {
    if (Test-ProcAlive $script:GptProc) {
        Write-Host ("  GPT-SoVITS is already running (PID {0})." -f ($script:GptProc).Id) -ForegroundColor Yellow
        return $false
    }
    Write-Step "Starting GPT-SoVITS ..."
    # Clear API log so Wait-ServicesReady does not see a stale ready signal.
    if (Test-Path -LiteralPath $script:GptLog) {
        Remove-Item -LiteralPath $script:GptLog -Force -ErrorAction SilentlyContinue
    }
    $script:GptProc = Start-ServiceWindow `
        -Title "GPT-SoVITS API (watchdog)" `
        -WorkDir $script:GptDir `
        -ExePath "powershell.exe" `
        -Arguments @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $script:GptWatch,
            "-LogPath", $script:GptLog,
            "-StallSec", "$TtsStallSec",
            "-RestartCooldownSec", "$TtsRestartCooldownSec"
        ) `
        -LogPath $script:GptWatchdogLog
    return $true
}

function Start-FrontendService {
    if (Test-ProcAlive $script:FrontendProc) {
        Write-Host ("  Frontend is already running (PID {0})." -f ($script:FrontendProc).Id) -ForegroundColor Yellow
        return $false
    }
    Write-Step "Starting frontend ..."
    $script:FrontendProc = Start-Process -FilePath ($script:FrontendInfo).Exe `
        -WorkingDirectory ($script:FrontendInfo).WorkDir `
        -PassThru
    Write-Step ("Frontend launched (PID {0})." -f ($script:FrontendProc).Id) Green
    return $true
}

function Stop-NamedService {
    param([string]$Name)
    $label = Get-ServiceDisplayName $Name
    $p = Get-TrackedProcess -Name $Name
    if (-not (Test-ProcAlive $p)) {
        Write-Host "  $label is not running." -ForegroundColor DarkGray
        return
    }
    Write-Step "Stopping $label ..." Yellow
    Stop-TrackedProcessTree -Process $p -Label $label
    Write-Step "$label stopped." Green
}

function Wait-NamedServiceReady {
    param([string]$Name)
    switch ($Name) {
        "backend" {
            Wait-ServicesReady -TimeoutSeconds $TimeoutSec -Services @(
                @{ Name = "Backend"; LogPath = $script:BackendLog; Process = $script:BackendProc }
            )
        }
        "gpt" {
            Wait-ServicesReady -TimeoutSeconds $TimeoutSec -Services @(
                @{ Name = "GPT-SoVITS"; LogPath = $script:GptLog; Process = $script:GptProc }
            )
        }
    }
}

function Start-NamedService {
    param(
        [string]$Name,
        [switch]$WaitReady
    )
    $started = $false
    switch ($Name) {
        "backend" { $started = Start-BackendService }
        "gpt" { $started = Start-GptService }
        "frontend" { $started = Start-FrontendService }
    }
    if ($started -and $WaitReady -and $Name -ne "frontend") {
        try {
            Wait-NamedServiceReady -Name $Name
        } catch {
            Write-Host ("  {0} failed to become ready: {1}" -f (Get-ServiceDisplayName $Name), $_) -ForegroundColor Red
        }
    }
}

function Restart-NamedService {
    param([string]$Name)
    $label = Get-ServiceDisplayName $Name
    Write-Step "Restarting $label ..."
    Stop-NamedService -Name $Name
    Start-Sleep -Milliseconds 400
    Start-NamedService -Name $Name -WaitReady
}

function Invoke-ControlCommand {
    param([string]$Raw)
    $trimmed = if ($null -eq $Raw) { "" } else { $Raw.Trim() }
    if ($trimmed -eq "") {
        Write-Host "Empty input ignored. Type help, or 0 / q / exit to stop all." -ForegroundColor Yellow
        return "continue"
    }

    switch ($trimmed) {
        "0" { return "exit" }
        "1" { try { Restart-NamedService "backend" } catch { Write-Host "  $_" -ForegroundColor Red }; Show-ServiceStatus; return "continue" }
        "2" { try { Restart-NamedService "gpt" } catch { Write-Host "  $_" -ForegroundColor Red }; Show-ServiceStatus; return "continue" }
        "3" { try { Restart-NamedService "frontend" } catch { Write-Host "  $_" -ForegroundColor Red }; Show-ServiceStatus; return "continue" }
        "4" { Stop-NamedService "backend"; Show-ServiceStatus; return "continue" }
        "5" { Stop-NamedService "gpt"; Show-ServiceStatus; return "continue" }
        "6" { Stop-NamedService "frontend"; Show-ServiceStatus; return "continue" }
        "s" { Show-ServiceStatus; return "continue" }
        "h" { Show-ControlHelp; return "continue" }
        "?" { Show-ControlHelp; return "continue" }
    }

    if ($trimmed -match '^(?i)(q|quit|exit|全部退出)$') {
        return "exit"
    }

    $normalized = $trimmed
    $normalized = $normalized -replace '^(停止|退出|重启|启动)(后端|语音|前端)$', '$1 $2'
    $normalized = $normalized -replace '^(?i)(stop|restart|start|rst)[-_]', '$1 '

    $parts = @($normalized -split '\s+', 2)
    $verb = $parts[0]
    $target = if ($parts.Count -gt 1) { $parts[1].Trim() } else { "" }

    switch -Regex ($verb) {
        '^(?i)(help|帮助)$' {
            Show-ControlHelp
            return "continue"
        }
        '^(?i)(status|stat|状态)$' {
            Show-ServiceStatus
            return "continue"
        }
        '^(?i)(q|quit|exit|退出)$' {
            if ([string]::IsNullOrWhiteSpace($target)) { return "exit" }
            $svc = Resolve-ServiceToken $target
            if (-not $svc -or $svc -eq "all") { return "exit" }
            Stop-NamedService $svc
            Show-ServiceStatus
            return "continue"
        }
        '^(?i)(stop|停止)$' {
            $svc = Resolve-ServiceToken $target
            if (-not $svc) {
                Write-Host "Usage: stop backend|gpt|frontend|all" -ForegroundColor Yellow
                return "continue"
            }
            if ($svc -eq "all") { return "exit" }
            Stop-NamedService $svc
            Show-ServiceStatus
            return "continue"
        }
        '^(?i)(start|启动)$' {
            $svc = Resolve-ServiceToken $target
            if (-not $svc -or $svc -eq "all") {
                Write-Host "Usage: start backend|gpt|frontend" -ForegroundColor Yellow
                return "continue"
            }
            try {
                Start-NamedService -Name $svc -WaitReady
            } catch {
                Write-Host ("  Failed to start {0}: {1}" -f (Get-ServiceDisplayName $svc), $_) -ForegroundColor Red
            }
            Show-ServiceStatus
            return "continue"
        }
        '^(?i)(restart|rst|重启)$' {
            $svc = Resolve-ServiceToken $target
            if (-not $svc -or $svc -eq "all") {
                Write-Host "Usage: restart backend|gpt|frontend" -ForegroundColor Yellow
                return "continue"
            }
            try {
                Restart-NamedService $svc
            } catch {
                Write-Host ("  Failed to restart {0}: {1}" -f (Get-ServiceDisplayName $svc), $_) -ForegroundColor Red
            }
            Show-ServiceStatus
            return "continue"
        }
        default {
            Write-Host "Unrecognized command: $trimmed  (type help)" -ForegroundColor Yellow
            return "continue"
        }
    }
}

# ---- prep ----
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$script:BackendDir = Join-Path $Root "backend"
$script:GptDir = Join-Path $Root "gpt-sovits"
$GptApi = Join-Path $script:GptDir "api_v2.py"
$script:GptWatch = Join-Path $script:GptDir "watch-apiv2.ps1"
$GptRuntimePy = Join-Path $script:GptDir "runtime\python.exe"

Assert-Path $script:BackendDir "backend directory"
Assert-Path (Join-Path $script:BackendDir "app\main.py") "backend entry"
Assert-Path $script:GptDir "gpt-sovits directory"
Assert-Path $GptApi "GPT-SoVITS api_v2.py"
Assert-Path $script:GptWatch "GPT-SoVITS watch-apiv2.ps1"

$script:Conda = Resolve-CondaCmd
$script:FrontendInfo = Resolve-Frontend -Explicit $FrontendExe

$script:BackendLog = Join-Path $LogDir "backend.log"
$script:GptLog = Join-Path $LogDir "gpt-sovits.log"
$script:GptWatchdogLog = Join-Path $LogDir "gpt-sovits-watchdog.log"

Write-Step "AronaAI start-all"
Write-Host "  Root:        $Root"
Write-Host "  Conda:       $($script:Conda)"
Write-Host "  CondaEnv:    $CondaEnv"
Write-Host ("  Frontend:    {0}" -f ($script:FrontendInfo).Exe)
Write-Host ("  FrontendCwd: {0}" -f ($script:FrontendInfo).WorkDir)
Write-Host "  Logs:        $LogDir"
Write-Host "  Timeout:     ${TimeoutSec}s for backend + GPT-SoVITS"

if (-not (Test-Path -LiteralPath $GptRuntimePy)) {
    Write-Host "  runtime\python.exe not found; falling back to python on PATH" -ForegroundColor Yellow
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { throw "Neither gpt-sovits\runtime\python.exe nor python on PATH was found." }
}

# ---- 1) Backend + GPT-SoVITS in parallel ----
try {
    Write-Step "Starting backend and GPT-SoVITS in parallel ..."
    [void](Start-BackendService)
    [void](Start-GptService)

    Wait-ServicesReady -TimeoutSeconds $TimeoutSec -Services @(
        @{ Name = "Backend"; LogPath = $script:BackendLog; Process = $script:BackendProc },
        @{ Name = "GPT-SoVITS"; LogPath = $script:GptLog; Process = $script:GptProc }
    )

    # ---- 2) Frontend ----
    [void](Start-FrontendService)
    Write-Step "All services launched." Green

    Show-ServiceStatus
    Write-Host @"

Logs:
  $($script:BackendLog)
  $($script:GptLog)

This window stays open as a control console.
Type help for commands. Ctrl+C also stops everything.
"@
    Show-ControlHelp

    # ---- 3) Stay alive until user requests stop-all ----
    while ($true) {
        $answer = Read-Host "Command"
        $action = Invoke-ControlCommand $answer
        if ($action -eq "exit") { break }
    }
} finally {
    Stop-AllTrackedServices
}
