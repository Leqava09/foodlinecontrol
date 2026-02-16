# Quick SSH Connection and Deployment Script for Foodline Control
# Usage:
#   .\connect.ps1           - Connect to cPanel server
#   .\connect.ps1 -Deploy   - Connect and run deployment automatically
#   .\connect.ps1 -Setup    - Configure SSH connection details

param(
    [switch]$Deploy,
    [switch]$Setup
)

# ======================================
# CONFIGURATION
# ======================================
# Edit these values to match your cPanel server

$ServerAddress = "your-server-address.com"  # e.g., server123.host.com or foodlinecontrol.com
$ServerUser = "your_cpanel_username"        # e.g., u727558699 or leqavaco
$ServerPort = "22"
$ProjectPath = "~/foodlinecontrol"

# ======================================
# SSH CONFIG ALIAS
# ======================================
$ServerAlias = "foodline"

# ======================================
# FUNCTIONS
# ======================================

function Test-SSHConfig {
    $sshConfigPath = "$env:USERPROFILE\.ssh\config"
    if (Test-Path $sshConfigPath) {
        $content = Get-Content $sshConfigPath -Raw
        return $content -match "Host $ServerAlias"
    }
    return $false
}

function Setup-SSHConfig {
    Write-Host "`n============================================" -ForegroundColor Cyan
    Write-Host "SSH Configuration Setup" -ForegroundColor Cyan
    Write-Host "============================================`n" -ForegroundColor Cyan
    
    # Get server details
    Write-Host "Enter your cPanel server details:`n" -ForegroundColor Yellow
    
    $svrAddress = Read-Host "Server Address (e.g., server123.host.com)"
    $svrUser = Read-Host "cPanel Username (e.g., u727558699)"
    $svrPort = Read-Host "SSH Port (default: 22)"
    
    if ([string]::IsNullOrWhiteSpace($svrPort)) {
        $svrPort = "22"
    }
    
    # Create SSH config
    $sshPath = "$env:USERPROFILE\.ssh"
    if (!(Test-Path $sshPath)) {
        New-Item -ItemType Directory -Path $sshPath | Out-Null
    }
    
    $configPath = "$sshPath\config"
    $configEntry = @"

# Foodline Control cPanel Server (auto-generated)
Host $ServerAlias
    HostName $svrAddress
    User $svrUser
    Port $svrPort
    IdentityFile ~/.ssh/id_rsa
    ServerAliveInterval 60
    ServerAliveCountMax 3
"@
    
    # Check if config exists and update
    if (Test-Path $configPath) {
        $existingContent = Get-Content $configPath -Raw
        if ($existingContent -match "Host $ServerAlias") {
            Write-Host "`nUpdating existing SSH config..." -ForegroundColor Yellow
            # Remove old entry and add new one
            $existingContent = $existingContent -replace "(?ms)# Foodline Control.*?ServerAliveCountMax 3", ""
        }
        $configEntry | Add-Content -Path $configPath
    } else {
        $configEntry | Set-Content -Path $configPath
    }
    
    Write-Host "`n✓ SSH config created at: $configPath" -ForegroundColor Green
    
    # Check for SSH key
    $keyPath = "$sshPath\id_rsa"
    if (!(Test-Path $keyPath)) {
        Write-Host "`n⚠ No SSH key found!" -ForegroundColor Yellow
        $createKey = Read-Host "Generate SSH key now? (Y/n)"
        
        if ($createKey -ne 'n') {
            Write-Host "`nGenerating SSH key..." -ForegroundColor Yellow
            ssh-keygen -t rsa -b 4096 -f $keyPath -N '""'
            Write-Host "✓ SSH key generated" -ForegroundColor Green
        }
    }
    
    # Show public key
    $pubKeyPath = "$keyPath.pub"
    if (Test-Path $pubKeyPath) {
        Write-Host "`n============================================" -ForegroundColor Cyan
        Write-Host "Your SSH Public Key:" -ForegroundColor Cyan
        Write-Host "============================================" -ForegroundColor Cyan
        Get-Content $pubKeyPath
        Write-Host "`n============================================`n" -ForegroundColor Cyan
        
        Write-Host "Next steps:" -ForegroundColor Yellow
        Write-Host "1. Copy the public key above" -ForegroundColor White
        Write-Host "2. Login to cPanel" -ForegroundColor White
        Write-Host "3. Go to: Security → SSH Access → Manage SSH Keys" -ForegroundColor White
        Write-Host "4. Import and Authorize your key" -ForegroundColor White
        Write-Host "5. Test connection: ssh $ServerAlias`n" -ForegroundColor White
        
        # Copy to clipboard if possible
        try {
            Get-Content $pubKeyPath | Set-Clipboard
            Write-Host "✓ Public key copied to clipboard!" -ForegroundColor Green
        } catch {
            # Clipboard might not work in all environments
        }
    }
}

function Connect-Server {
    Write-Host "`nConnecting to cPanel server ($ServerAlias)..." -ForegroundColor Green
    ssh $ServerAlias
}

function Deploy-Application {
    Write-Host "`n============================================" -ForegroundColor Cyan
    Write-Host "Deploying Foodline Control" -ForegroundColor Cyan
    Write-Host "============================================`n" -ForegroundColor Cyan
    
    $deployScript = "cd $ProjectPath && bash deploy_investor_loan.sh"
    
    Write-Host "Running deployment script on server...`n" -ForegroundColor Yellow
    ssh $ServerAlias $deployScript
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✓ Deployment completed successfully!" -ForegroundColor Green
    } else {
        Write-Host "`n✗ Deployment failed. Check errors above." -ForegroundColor Red
    }
}

# ======================================
# MAIN EXECUTION
# ======================================

if ($Setup) {
    Setup-SSHConfig
    exit
}

# Check if SSH config exists
if (!(Test-SSHConfig)) {
    Write-Host "⚠ SSH config not found for '$ServerAlias'" -ForegroundColor Yellow
    Write-Host "Run: .\connect.ps1 -Setup`n" -ForegroundColor Yellow
    
    $runSetup = Read-Host "Run setup now? (Y/n)"
    if ($runSetup -ne 'n') {
        Setup-SSHConfig
    }
    exit
}

# Execute requested action
if ($Deploy) {
    Deploy-Application
} else {
    Connect-Server
}
