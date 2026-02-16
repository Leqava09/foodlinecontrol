# SSH Setup for Quick cPanel Access

## One-Time Setup

### Step 1: Generate SSH Key (if you don't have one)

Open PowerShell and run:

```powershell
# Generate SSH key pair
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# When prompted:
# - Save location: Press Enter (default: C:\Users\pekva\.ssh\id_rsa)
# - Passphrase: Press Enter for no passphrase (or set one for extra security)
```

This creates two files:
- `C:\Users\pekva\.ssh\id_rsa` (private key - keep secret!)
- `C:\Users\pekva\.ssh\id_rsa.pub` (public key - upload to server)

### Step 2: Copy Public Key to cPanel Server

**Option A - Using ssh-copy-id (if available):**
```powershell
ssh-copy-id username@your-server.com
```

**Option B - Manual Copy:**
```powershell
# 1. Display your public key
Get-Content $env:USERPROFILE\.ssh\id_rsa.pub

# 2. Copy the output
# 3. SSH into cPanel (with password this one time)
ssh username@your-server.com

# 4. On the server, add your key:
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo "PASTE_YOUR_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
exit
```

**Option C - Through cPanel Interface:**
1. Login to cPanel
2. Go to: Security → SSH Access → Manage SSH Keys
3. Click "Import Key"
4. Paste your public key content
5. Click "Import"
6. Click "Manage" → "Authorize"

### Step 3: Create SSH Config File

Create/edit: `C:\Users\pekva\.ssh\config`

```powershell
# Create SSH config file
$sshConfig = @"
# Foodline Control cPanel Server
Host foodline
    HostName your-server-address.com
    User your_cpanel_username
    Port 22
    IdentityFile ~/.ssh/id_rsa
    ServerAliveInterval 60
    ServerAliveCountMax 3
"@

# Save config
$sshPath = "$env:USERPROFILE\.ssh"
if (!(Test-Path $sshPath)) {
    New-Item -ItemType Directory -Path $sshPath
}
$sshConfig | Out-File -FilePath "$sshPath\config" -Encoding ASCII
```

**Replace these values:**
- `your-server-address.com` - Your actual server address
- `your_cpanel_username` - Your cPanel username (e.g., u727558699 or leqavaco)

### Step 4: Test Connection

```powershell
# Now you can connect with just:
ssh foodline

# No password needed!
```

## Quick Deploy Script (connect.ps1)

Save this as `connect.ps1` in your project folder:

```powershell
# Quick SSH connection script
param(
    [switch]$Deploy
)

$ServerAlias = "foodline"

if ($Deploy) {
    Write-Host "Connecting and running deployment..." -ForegroundColor Green
    ssh $ServerAlias "cd ~/foodlinecontrol && bash deploy_investor_loan.sh"
} else {
    Write-Host "Connecting to cPanel server..." -ForegroundColor Green
    ssh $ServerAlias
}
```

### Usage:

```powershell
# Just connect to server
.\connect.ps1

# Connect and deploy automatically
.\connect.ps1 -Deploy
```

## Troubleshooting

### "Permission denied (publickey)"
```powershell
# Check if your key is loaded
ssh-add -l

# If empty or error, add your key:
ssh-add $env:USERPROFILE\.ssh\id_rsa
```

### SSH Config Not Working
```powershell
# Test with verbose mode to see what's happening
ssh -v foodline
```

### Fix File Permissions (Windows)
```powershell
# SSH keys must have restricted permissions
icacls "$env:USERPROFILE\.ssh\id_rsa" /inheritance:r
icacls "$env:USERPROFILE\.ssh\id_rsa" /grant:r "$env:USERNAME:(R)"
```

## Server Details to Fill In

You need to find out from your cPanel:

1. **Server Address**: Check cPanel login URL or hosting provider info
2. **Username**: Usually shown in cPanel (e.g., u727558699, leqavaco)
3. **SSH Access Enabled**: Make sure SSH is enabled in cPanel → Security → SSH Access

Common server formats:
- `server123.hostingprovider.com`
- `foodlinecontrol.com` (if SSH is on main domain)
- `123.45.67.89` (IP address)
- `ssh.yourdomain.com`

## One-Line Deploy (After Setup)

Once configured, you can deploy with just:

```powershell
ssh foodline "cd ~/foodlinecontrol && git pull && python manage.py migrate && python manage.py collectstatic --noinput && touch tmp/restart.txt"
```

Even better, add to your PowerShell profile for a simple command:

```powershell
# Add to: C:\Users\pekva\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1

function Deploy-Foodline {
    ssh foodline "cd ~/foodlinecontrol && bash deploy_investor_loan.sh"
}

# Then just run:
# Deploy-Foodline
```
