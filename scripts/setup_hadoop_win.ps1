# Windows-only: Spark needs winutils.exe + hadoop.dll to use the local filesystem.
# This downloads them into a gitignored .hadoop\ folder and is a no-op on Linux/Mac
# (where CI runs Spark without winutils). Run once:  pwsh scripts\setup_hadoop_win.ps1
$ErrorActionPreference = "Stop"
$hadoopVersion = "3.3.6"
$root = Split-Path -Parent $PSScriptRoot
$binDir = Join-Path $root ".hadoop\bin"
New-Item -ItemType Directory -Force -Path $binDir | Out-Null

$base = "https://raw.githubusercontent.com/cdarlint/winutils/master/hadoop-$hadoopVersion/bin"
foreach ($file in @("winutils.exe", "hadoop.dll")) {
    $dest = Join-Path $binDir $file
    if (-not (Test-Path $dest)) {
        Write-Host "Downloading $file ..."
        Invoke-WebRequest -Uri "$base/$file" -OutFile $dest
    }
}
Write-Host "Done. HADOOP_HOME -> $(Split-Path -Parent $binDir)"
Write-Host "Set it for this session:  `$env:HADOOP_HOME = '$(Split-Path -Parent $binDir)'"
