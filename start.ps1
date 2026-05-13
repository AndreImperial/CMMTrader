$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

function Set-DataMode {
    param([string]$Mode)

    $path = ".env"
    $lines = Get-Content -LiteralPath $path
    $found = $false
    $updated = foreach ($line in $lines) {
        if ($line -match "^DATA_MODE=") {
            $found = $true
            "DATA_MODE=$Mode"
        } else {
            $line
        }
    }
    if (-not $found) {
        $updated += "DATA_MODE=$Mode"
    }
    Set-Content -LiteralPath $path -Value $updated
}

if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
}

python -m pip install -r requirements.txt | Out-Host

while ($true) {
    Clear-Host
    Write-Host "Coach Miranda Miner System" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "1. Health check"
    Write-Host "2. Open web dashboard"
    Write-Host "3. Run one scan"
    Write-Host "4. Run BTC backtest"
    Write-Host "5. Run 15-minute loop"
    Write-Host "6. Use offline demo data"
    Write-Host "7. Use updating free prices"
    Write-Host "8. Open settings file"
    Write-Host "9. Exit"
    Write-Host ""

    $choice = Read-Host "Choose"

    switch ($choice) {
        "1" {
            python -m coach_miranda_miner doctor
            Read-Host "Press Enter to continue"
        }
        "2" {
            python -m streamlit run coach_miranda_miner/dashboard.py --server.address 127.0.0.1 --server.port 8502
            Read-Host "Press Enter to continue"
        }
        "3" {
            python -m coach_miranda_miner scan
            Read-Host "Press Enter to continue"
        }
        "4" {
            python -m coach_miranda_miner backtest --symbol BTC/USDT --timeframe 1h
            Read-Host "Press Enter to continue"
        }
        "5" {
            Write-Host "Starting loop. Press Ctrl+C to stop." -ForegroundColor Yellow
            python -m coach_miranda_miner loop --interval 900
        }
        "6" {
            Set-DataMode -Mode "fixture"
            Write-Host "Set DATA_MODE=fixture" -ForegroundColor Green
            Read-Host "Press Enter to continue"
        }
        "7" {
            Set-DataMode -Mode "paprika"
            Write-Host "Set DATA_MODE=paprika" -ForegroundColor Green
            Read-Host "Press Enter to continue"
        }
        "8" {
            notepad .env
        }
        "9" {
            exit 0
        }
        default {
            Write-Host "Invalid choice." -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }
}
