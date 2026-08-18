$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$probe = Join-Path $root "scripts\nexmind-runtime-boot-probe.py"

if (-not (Test-Path $venvPython)) {
    throw "Virtual-environment Python not found: $venvPython"
}
if (-not (Test-Path $probe)) {
    throw "NexMind boot probe not found: $probe"
}
if (-not (Test-Path (Join-Path $root ".env"))) {
    throw ".env not found in NexStudio root."
}

$env:PYTHONUTF8 = "1"

$js = @'
const path = require("path");
const { spawnSync } = require("child_process");

require("dotenv").config({
  path: path.join(process.cwd(), ".env"),
  override: true
});

const py = path.join(process.cwd(), ".venv", "Scripts", "python.exe");
const probe = path.join(process.cwd(), "scripts", "nexmind-runtime-boot-probe.py");

const r = spawnSync(py, [probe], {
  stdio: "inherit",
  env: process.env
});

if (r.error) {
  console.error(r.error);
  process.exit(1);
}
process.exit(r.status == null ? 1 : r.status);
'@

$tmp = Join-Path $env:TEMP "nexmind-run-boot-probe-with-env.cjs"
[System.IO.File]::WriteAllText(
    $tmp,
    $js,
    (New-Object System.Text.UTF8Encoding($false))
)

node $tmp
exit $LASTEXITCODE
