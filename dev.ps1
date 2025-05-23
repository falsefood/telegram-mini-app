# Get the local IP address
$localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -like "*Ethernet*" -or $_.InterfaceAlias -like "*Wi-Fi*" } | Select-Object -First 1).IPAddress

# Update the webAppURL in main.go
$content = Get-Content main.go
$content = $content -replace 'const webAppURL = ".*"', "const webAppURL = `"http://${localIP}:8080`""
$content | Set-Content main.go

Write-Host "Updated webAppURL to http://${localIP}:8080"
Write-Host "Starting the bot..."

# Run the bot
go run main.go 