#!/bin/bash
# Deployment script for Investor/Loan Costing feature
# Run this on your cPanel server

echo "=========================================="
echo "Deploying Investor/Loan Costing Updates"
echo "=========================================="

# Navigate to project directory
cd ~/foodlinecontrol || { echo "Failed to navigate to project directory"; exit 1; }

echo "Current directory: $(pwd)"
echo ""

# Pull latest changes
echo "Pulling latest changes from GitHub..."
git pull origin master

if [ $? -ne 0 ]; then
    echo "✗ Git pull failed"
    exit 1
fi

echo "✓ Code updated successfully"
echo ""

# Activate virtual environment (adjust path if needed)
echo "Activating virtual environment..."
source ~/virtualenv/foodlinecontrol/3.14/bin/activate || source venv/bin/activate

# Check migrations
echo ""
echo "Checking migrations status..."
python manage.py showmigrations costing | tail -10

# Apply migrations
echo ""
echo "Applying migrations..."
python manage.py migrate costing

if [ $? -ne 0 ]; then
    echo "✗ Migration failed"
    exit 1
fi

echo "✓ Migrations applied successfully"
echo ""

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "✓ Static files collected"
echo ""

# Restart application
echo "Restarting application..."
touch tmp/restart.txt

echo ""
echo "=========================================="
echo "✓ Deployment Complete!"
echo "=========================================="
echo ""
echo "What was deployed:"
echo "- InvestorLoanCosting & InvestorLoanItem models"
echo "- Integrated into ProductCosting & BatchCosting"
echo "- Dynamic AJAX price updates"
echo "- 4 new migrations: 0016, 0017, 0018, 0019"
echo ""
echo "Next: Test in Django Admin"
echo "1. Go to Costing > Investor / Loan Costing"
echo "2. Create a new record with Investment/Loan items"
echo "3. Check 'Use as Default'"
echo "4. Go to Product Costing - verify it appears in dropdown"
echo "5. Change dropdown - verify price updates dynamically"
echo ""
