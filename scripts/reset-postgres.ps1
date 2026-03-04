# Reset PostgreSQL Container with Correct Password
# Run this if you get authentication errors

Write-Host "🔄 Resetting PostgreSQL container..." -ForegroundColor Yellow

# Stop and remove existing container
docker stop drs-postgres 2>$null
docker rm drs-postgres 2>$null

# Remove volume to reset password
Write-Host "⚠️  Removing PostgreSQL volume (all data will be lost)..." -ForegroundColor Red
docker volume rm deep-research-spec_pg_data 2>$null

Write-Host "✅ Cleanup complete. Now run:" -ForegroundColor Green
Write-Host "   cd C:\Users\Luca\deep-research-spec" -ForegroundColor Cyan
Write-Host "   docker-compose up -d postgres" -ForegroundColor Cyan
Write-Host "   Start-Sleep -Seconds 15" -ForegroundColor Cyan
Write-Host "   cd backend" -ForegroundColor Cyan
Write-Host "   uvicorn main:app --reload --host 0.0.0.0 --port 8000" -ForegroundColor Cyan
