# AFSC Batch Processing Script
# Place this file in the SAME DIRECTORY as your 12 AFSC .txt files
# Then run: .\run_batch.ps1

# Load environment variables from repo root
$repoRoot = "C:\Dev\fall-2025-group6"
Get-Content "$repoRoot\.env" | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}

# Set PYTHONPATH to repo src
$env:PYTHONPATH = "$repoRoot\src"

Write-Host "Starting batch processing of 12 AFSCs..." -ForegroundColor Green
Write-Host "Text files location: $(Get-Location)" -ForegroundColor Cyan
Write-Host "Repo root: $repoRoot" -ForegroundColor Cyan

# Run the batch processor (assumes it's in same directory)
python .\batch_process_afscs.py

Write-Host "`nDone! Check results above." -ForegroundColor Green
Write-Host "Run 'python $repoRoot\quick_check.py' to verify database counts." -ForegroundColor Yellow
