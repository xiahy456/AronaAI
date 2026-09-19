#Requires -Version 5.1
<#
.SYNOPSIS
  Pack Arona-owned GPT-SoVITS overlay files and the minimal Python runtime into release/.

.DESCRIPTION
  在仓库根目录执行。把 tts/ 下属于本仓库的启动脚本、文档、launch_api.py、
  voices.json、参考音频，以及 gpt-sovits-minimal/runtime 打成 zip，不包含：

    - 上游 clone（api_v2.py、api_server.py、GPT_SoVITS/ 源码等）
    - 模型与预训练（*.ckpt / *.pth / pretrained_models / GPT_weights* / SoVITS_weights*）
    - 官方整合包 runtime、.venv、conda 环境本身

  压缩包根目录是 tts/，解压到仓库根即可与现有布局对齐。
  需先有 tts\gpt-sovits-minimal\runtime\python.exe（.\tts\gpt-sovits-minimal\pack-runtime.ps1）。

    .\pack-tts.ps1
    → release\AronaAI_GPTSoVITS_v<version>_x64.zip

.PARAMETER SkipZip
  只组装临时目录，不写 zip。

.EXAMPLE
  .\pack-tts.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipZip
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$TtsRoot = Join-Path $Root "tts"
$IssPath = Join-Path $Root "frontend\AronaAI_Spine_WindowsClient\AronaAI.iss"
$ArtifactDir = Join-Path $Root "release"
$StageRoot = Join-Path $ArtifactDir ".tts-pack-stage"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message) -ForegroundColor Cyan
}

function Get-PackVersion {
    param([string]$Path)
    if ($Path -and (Test-Path -LiteralPath $Path)) {
        $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
        if ($raw -match '#define\s+MyAppVersion\s+"([^"]+)"') {
            return $Matches[1]
        }
    }
    return "unknown"
}

function Copy-RelFile {
    param(
        [Parameter(Mandatory = $true)][string]$Relative,
        [switch]$Optional
    )
    $src = Join-Path $Root $Relative
    if (-not (Test-Path -LiteralPath $src)) {
        if ($Optional) {
            Write-Host "  skip missing: $Relative" -ForegroundColor Yellow
            return
        }
        throw "Missing overlay file: $src"
    }
    $dst = Join-Path $StageRoot $Relative
    $parent = Split-Path -Parent $dst
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Copy-Item -LiteralPath $src -Destination $dst -Force
    Write-Host "  $Relative"
}

if (-not (Test-Path -LiteralPath $TtsRoot)) {
    throw "tts/ not found: $TtsRoot"
}

$PackVersion = Get-PackVersion -Path $IssPath
$ZipPath = Join-Path $ArtifactDir "AronaAI_GPTSoVITS_v${PackVersion}_x64.zip"

Write-Step "Staging Arona GPT-SoVITS overlay + minimal runtime (no models, no upstream clone)"
if (Test-Path -LiteralPath $StageRoot) {
    Remove-Item -LiteralPath $StageRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $StageRoot -Force | Out-Null

$FixedFiles = @(
    "tts\README.md",
    "tts\gpt-sovits\DEPLOY.md",
    "tts\gpt-sovits\go-apiv2.bat",
    "tts\gpt-sovits\go-apiv2.sh",
    "tts\gpt-sovits\watch-apiv2.ps1",
    "tts\gpt-sovits\watch-apiv2.sh",
    "tts\gpt-sovits-minimal\DEPLOY.md",
    "tts\gpt-sovits-minimal\go-api.bat",
    "tts\gpt-sovits-minimal\go-api.ps1",
    "tts\gpt-sovits-minimal\watch-api.ps1",
    "tts\gpt-sovits-minimal\launch_api.py",
    "tts\gpt-sovits-minimal\pack-runtime.ps1",
    "tts\gpt-sovits-minimal\config\voices.json"
)

foreach ($rel in $FixedFiles) {
    Copy-RelFile -Relative $rel
}

$RefDir = Join-Path $Root "tts\gpt-sovits\ref_audio\Arona"
if (Test-Path -LiteralPath $RefDir) {
    Get-ChildItem -LiteralPath $RefDir -File | Where-Object {
        $_.Extension -match '^\.(ogg|wav|mp3|txt)$'
    } | ForEach-Object {
        $rel = $_.FullName.Substring($Root.Length).TrimStart('\', '/')
        Copy-RelFile -Relative $rel
    }
}
else {
    Write-Host "  skip missing: tts\gpt-sovits\ref_audio\Arona" -ForegroundColor Yellow
}

$overlayCount = @(Get-ChildItem -LiteralPath $StageRoot -Recurse -File).Count
if ($overlayCount -lt 1) {
    throw "Stage is empty; nothing to pack."
}

$RuntimeSrc = Join-Path $Root "tts\gpt-sovits-minimal\runtime"
$RuntimePy = Join-Path $RuntimeSrc "python.exe"
if (-not (Test-Path -LiteralPath $RuntimePy)) {
    throw "minimal runtime not found: $RuntimePy. Run tts\gpt-sovits-minimal\pack-runtime.ps1 first."
}
$RuntimeDst = Join-Path $StageRoot "tts\gpt-sovits-minimal\runtime"
Write-Host "  tts\gpt-sovits-minimal\runtime  (junction, not copied)"
New-Item -ItemType Junction -Path $RuntimeDst -Target (Resolve-Path -LiteralPath $RuntimeSrc).Path | Out-Null
Write-Host ("Staged {0} overlay files + runtime\." -f $overlayCount) -ForegroundColor Green

if ($SkipZip) {
    Write-Host "SkipZip: left stage at $StageRoot"
    return
}

New-Item -ItemType Directory -Force -Path $ArtifactDir | Out-Null
if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

Write-Step "Zipping -> $ZipPath (runtime is several GB; this can take a few minutes)"
$tar = Get-Command tar.exe -ErrorAction SilentlyContinue
if (-not $tar) {
    throw "tar.exe is required to pack the multi-GB runtime. Compress-Archive cannot be used."
}
Push-Location $StageRoot
try {
    & tar.exe -a -c -f $ZipPath "tts"
    if ($LASTEXITCODE -ne 0) {
        throw "tar.exe failed ($LASTEXITCODE)"
    }
}
finally {
    Pop-Location
    if (Test-Path -LiteralPath $RuntimeDst) {
        cmd.exe /c "rmdir `"$RuntimeDst`"" | Out-Null
    }
    if (Test-Path -LiteralPath $StageRoot) {
        Remove-Item -LiteralPath $StageRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host ("[{0}] TTS pack finished." -f (Get-Date -Format "HH:mm:ss")) -ForegroundColor Green
Write-Host "Zip: $ZipPath"
Write-Host "Extract into the repository root so paths are tts\gpt-sovits\ and tts\gpt-sovits-minimal\ (including runtime\python.exe)."
Write-Host "Weights, pretrained models, and upstream clone are not in this zip."
