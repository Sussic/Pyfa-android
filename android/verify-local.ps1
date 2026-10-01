param(
    [ValidateSet('start','resume','pause','plan')][string]$Action = 'start',
    [ValidateSet('full','desktop','build','native')][string]$Mode = 'full',
    [string]$Run, [string]$Gate,
    [string]$SdkPath = "$env:LOCALAPPDATA/Android/Sdk",
    [string]$JdkPath, [string]$SdkManager, [switch]$AdoptLauncherFix, [switch]$RestartNative
)
$ErrorActionPreference = 'Stop'
$localRoot = Split-Path -Parent $PSScriptRoot
if (-not $JdkPath) { $JdkPath = Join-Path $localRoot 'build/tools/jdk-17.0.20.1+1' }
if (-not $SdkManager) { $SdkManager = Join-Path $SdkPath 'cmdline-tools/22.0/bin/sdkmanager.bat' }
$env:JAVA_HOME = $JdkPath
$env:ANDROID_HOME = $SdkPath
$env:ANDROID_SDK_ROOT = $SdkPath
$env:PYFA_SDKMANAGER = $SdkManager
$env:GRADLE_USER_HOME = "$env:LOCALAPPDATA/PyfaAndroid/PyfaDevelopment/gradle-home"
$env:JAVA_OPTS = '-Djavax.net.ssl.trustStoreType=Windows-ROOT -Djavax.net.ssl.trustStore=NONE -Djava.net.useSystemProxies=true'
$env:PYTHONUTF8 = '1'
$env:PATH = "$SdkPath/platform-tools;$JdkPath/bin;C:/Strawberry/c/bin;$env:PATH"
$localPython = Join-Path $localRoot '.venv/headless/Scripts/python.exe'
$localArguments = @('-I', (Join-Path $PSScriptRoot 'ci/local_verification.py'), $Action, '--mode', $Mode)
if ($Run) { $localArguments += @('--run', $Run) }
if ($Gate) { $localArguments += @('--gate', $Gate) }
if ($AdoptLauncherFix) { $localArguments += '--adopt-launcher-fix' }
if ($RestartNative) { $localArguments += '--restart-native' }
& $localPython @localArguments
if ($LASTEXITCODE -ne 0) { throw "Local verification exited $LASTEXITCODE" }
