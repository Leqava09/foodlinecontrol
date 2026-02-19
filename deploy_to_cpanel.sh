#!/bin/bash
# Deployment script for cPanel
# Upload this file to /home/leqavaco/foodlinecontrol/ and run: bash deploy_to_cpanel.sh

echo "==================================="
echo "Starting Deployment to cPanel"
echo "==================================="

# Navigate to the app directory
cd ~/foodlinecontrol/foodlinecontrol || exit 1

echo "Current directory: $(pwd)"
echo ""

# Fetch latest changes using token
echo "Fetching latest changes from GitHub..."
git fetch https://REDACTED@github.com/Leqava14/Foodlinecontrol.git master

# Force update to match remote (this overwrites local changes without touching filesystem first)
echo "Updating to latest code..."
git reset --soft FETCH_HEAD
git checkout FETCH_HEAD -- .

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Successfully pulled changes!"
    echo ""
    echo "Files updated:"
    git log -1 --stat
    echo ""
    echo "Collecting static files..."
    cd ~/foodlinecontrol
    python manage.py collectstatic --noinput
    
    if [ $? -eq 0 ]; then
        echo "✓ Static files collected successfully!"
    else
        echo "⚠ Warning: Static files collection failed. Check permissions."
    fi
    echo ""
    echo "==================================="
    echo "Deployment Complete!"
    echo "==================================="
    echo ""
    echo "Next step: Restart your Python app in cPanel"
    echo "Go to: Setup Python App -> Click Restart button"
else
    echo ""
    echo "✗ Pull failed. Please check the error above."
    exit 1
fi
