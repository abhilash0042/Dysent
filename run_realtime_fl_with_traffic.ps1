# PowerShell script to run FL with automatic traffic generation
# Automates both traffic generation and FL experiment

param(
    [int]$Duration = 120,
    [int]$Nodes = 2,
    [int]$Rounds = 3
)

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "FL + Traffic Generator (Automated)" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Traffic duration: $Duration seconds" -ForegroundColor White
Write-Host "  FL nodes: $Nodes" -ForegroundColor White
Write-Host "  FL rounds: $Rounds" -ForegroundColor White
Write-Host ""

# Step 1: Start traffic generator in background
Write-Host "Step 1: Starting traffic generator..." -ForegroundColor Green
$trafficJob = Start-Job -ScriptBlock {
    param($dur)
    python scripts/advanced_traffic_generator.py $dur
} -ArgumentList $Duration

# Wait 3 seconds for traffic to ramp up
Write-Host "         Waiting for traffic to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Step 2: Run FL experiment
Write-Host ""
Write-Host "Step 2: Starting FL experiment..." -ForegroundColor Green
Write-Host "         (this will capture live traffic)" -ForegroundColor Yellow
Write-Host ""

try {
    python experiments/federated_learning/run_realtime_fl.py
    $exitCode = $LASTEXITCODE
}
finally {
    # Step 3: Stop traffic generator
    Write-Host ""
    Write-Host "Step 3: Stopping traffic generator..." -ForegroundColor Green
    Stop-Job $trafficJob -ErrorAction SilentlyContinue
    Remove-Job $trafficJob -ErrorAction SilentlyContinue
}

# Summary
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
if ($exitCode -eq 0) {
    Write-Host "FL Experiment Complete!" -ForegroundColor Green
}
else {
    Write-Host "FL Experiment encountered errors" -ForegroundColor Red
}
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
