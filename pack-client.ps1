#Requires -Version 5.1
<#
.SYNOPSIS
  依次执行前端两种打包：保留密钥包 + 脱敏发布包。

.DESCRIPTION
  在项目根目录调用：
    1) frontend\AronaAI_Spine_WindowsClient\pack_keep_secrets.ps1
       → dist\AronaAI_Client（明文密钥，本机自用）
    2) frontend\AronaAI_Spine_WindowsClient\pack_sanitize_secrets.ps1
       → dist\AronaAI_Client_Release（脱敏，对外分发）

  任一脚本失败则立即退出。

.PARAMETER QtBin
  传给两个打包脚本的 Qt bin 路径。

.PARAMETER ExePath
  可选；传给两个打包脚本的 exe 路径。省略则由各自脚本 / pack.ps1 自动检测。

.EXAMPLE
  .\pack-client.ps1
  .\pack-client.ps1 -QtBin "D:\Qt68\6.5.3\msvc2019_64\bin"
#>
[CmdletBinding()]
param(
    [string]$QtBin = "D:\Qt68\6.5.3\msvc2019_64\bin",
    [string]$ExePath = ""
)

$ErrorActionPreference = "Stop"
$ClientRoot = Join-Path $PSScriptRoot "frontend\AronaAI_Spine_WindowsClient"
$KeepScript = Join-Path $ClientRoot "pack_keep_secrets.ps1"
$SanitizeScript = Join-Path $ClientRoot "pack_sanitize_secrets.ps1"

foreach ($p in @($KeepScript, $SanitizeScript)) {
    if (-not (Test-Path -LiteralPath $p)) {
        throw "Missing pack script: $p"
    }
}

$packArgs = @{ QtBin = $QtBin }
if ($ExePath) { $packArgs.ExePath = $ExePath }

function Invoke-PackScript {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [Parameter(Mandatory = $true)][hashtable]$Arguments,
        [Parameter(Mandatory = $true)][string]$Label
    )
    Write-Host ""
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Label) -ForegroundColor Cyan
    & $ScriptPath @Arguments
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
        exit $LASTEXITCODE
    }
}

Invoke-PackScript -ScriptPath $KeepScript -Arguments $packArgs -Label "Pack KEEP secrets"
Invoke-PackScript -ScriptPath $SanitizeScript -Arguments $packArgs -Label "Pack SANITIZE secrets"

Write-Host ""
Write-Host ("[{0}] Both client packs finished." -f (Get-Date -Format "HH:mm:ss")) -ForegroundColor Green
