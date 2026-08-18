$ErrorActionPreference = "Stop"

Write-Host "Node.js: $(node --version)"
Write-Host "npm: $(npm --version)"
Write-Host "Installing the exact dependency versions from package-lock.json..."

npm ci

Write-Host "Setup complete. Start the app with: npm run dev"
