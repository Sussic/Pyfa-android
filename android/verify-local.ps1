param(
    [ValidateSet('start','resume','pause','plan')][string]$Action = 'start',
    [ValidateSet('full','desktop','build','native')][string]$Mode = 'full',
    [string]$Run, [string]$Gate,
    [string]$PythonPath, [string]$ReferencePython, [string]$Source,
    [string]$SdkPath = "$env:LOCALAPPDATA/Android/Sdk",
    [string]$JdkPath, [string]$SdkManager, [switch]$AdoptLauncherFix, [switch]$RestartNative, [switch]$AdoptTankHistoryFix,
    [ValidateRange(1,32)][int]$ArtifactBudgetGiB = 32, [string[]]$ArtifactRoot = @()
)
$ErrorActionPreference = 'Stop'
$localRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonPath) { $PythonPath = Join-Path $localRoot '.venv/headless/Scripts/python.exe' }
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "Headless Python was not found at '$PythonPath'. Use -PythonPath to select the existing pinned Python 3.11 environment."
}
if (-not $JdkPath) { $JdkPath = Join-Path $localRoot 'build/tools/jdk-17.0.20.1+1' }
$localJdkExists = Test-Path -LiteralPath (Join-Path $JdkPath 'bin/java.exe') -PathType Leaf
if ($Action -in @('start','resume') -and $Mode -in @('full','build','native') -and -not $localJdkExists) {
    throw "JDK17 was not found at '$JdkPath'. Use -JdkPath to select an existing JDK17 installation."
}
if (-not $SdkManager) { $SdkManager = Join-Path $SdkPath 'cmdline-tools/22.0/bin/sdkmanager.bat' }
if ($localJdkExists) { $env:JAVA_HOME = $JdkPath }
$env:ANDROID_HOME = $SdkPath
$env:ANDROID_SDK_ROOT = $SdkPath
$env:PYFA_SDKMANAGER = $SdkManager
$env:GRADLE_USER_HOME = "$env:LOCALAPPDATA/PyfaAndroid/PyfaDevelopment/gradle-home"
$env:JAVA_OPTS = '-Djavax.net.ssl.trustStoreType=Windows-ROOT -Djavax.net.ssl.trustStore=NONE -Djava.net.useSystemProxies=true'
$env:PYTHONUTF8 = '1'
$env:PATH = "$SdkPath/platform-tools;C:/Strawberry/c/bin;$env:PATH"
if ($localJdkExists) { $env:PATH = "$JdkPath/bin;$env:PATH" }
$localArguments = @('-I', '-B', (Join-Path $PSScriptRoot 'ci/local_verification.py'), $Action, '--mode', $Mode)
if ($Run) { $localArguments += @('--run', $Run) }
if ($Gate) { $localArguments += @('--gate', $Gate) }
if ($ReferencePython) { $localArguments += @('--reference-python', $ReferencePython) }
if ($Source) { $localArguments += @('--source', $Source) }
if ($AdoptLauncherFix) { $localArguments += '--adopt-launcher-fix' }
if ($RestartNative) { $localArguments += '--restart-native' }
if ($AdoptTankHistoryFix) { $localArguments += '--adopt-tank-history-fix' }
$localArguments += @('--artifact-budget-gib', $ArtifactBudgetGiB.ToString())
foreach ($localArtifactRoot in $ArtifactRoot) { $localArguments += @('--artifact-root', $localArtifactRoot) }
& $PythonPath @localArguments
if ($LASTEXITCODE -ne 0) { throw "Local verification exited $LASTEXITCODE" }
