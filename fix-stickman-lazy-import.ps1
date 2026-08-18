$ErrorActionPreference = "Stop"

$path = ".\services\studio-family-engines\worker.py"

if (-not (Test-Path $path)) {
    throw "worker.py not found at $path. Run this script from C:\Users\USER\nexstudio-test."
}

$lines = Get-Content $path -Encoding UTF8
$index = -1

for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match 'elif\s+family\s*==\s*["'']STICKMAN["'']\s*:') {
        $index = $i
        break
    }
}

if ($index -lt 0) {
    throw "STICKMAN branch not found in worker.py"
}

$alreadyPresent = $false
for ($j = $index + 1; $j -le [Math]::Min($index + 5, $lines.Count - 1); $j++) {
    if ($lines[$j] -match 'from\s+stickman_adapter\s+import\s+build_internal_evidence\s+as\s+build_stickman_evidence') {
        $alreadyPresent = $true
        break
    }
}

if (-not $alreadyPresent) {
    $branchIndent = ([regex]::Match($lines[$index], '^\s*')).Value
    $childIndent = $branchIndent + "    "
    $importLine = $childIndent + "from stickman_adapter import build_internal_evidence as build_stickman_evidence"

    $before = @()
    if ($index -ge 0) {
        $before = $lines[0..$index]
    }

    $after = @()
    if ($index + 1 -lt $lines.Count) {
        $after = $lines[($index + 1)..($lines.Count - 1)]
    }

    $newLines = @($before) + $importLine + @($after)

    [System.IO.File]::WriteAllLines(
        (Resolve-Path $path),
        $newLines,
        (New-Object System.Text.UTF8Encoding($false))
    )

    Write-Host "STICKMAN lazy import inserted."
} else {
    Write-Host "STICKMAN lazy import already present."
}

Write-Host ""
Write-Host "Current STICKMAN branch:"
Select-String -Path $path -Pattern 'STICKMAN' -Context 1,4
