#!/bin/bash
# Install Python libraries for document/PDF generation
# Run this on cPanel server (no root access needed)

echo "=========================================="
echo "Installing Document/PDF Libraries"
echo "=========================================="

cd /home/leqavaco/foodlinecontrol/foodlinecontrol
source /home/leqavaco/virtualenv/foodlinecontrol/3.11/bin/activate

echo ""
echo "Installing libraries..."
echo ""

# PDF generation from HTML
pip install weasyprint
pip install xhtml2pdf
pip install reportlab

# DOCX handling
pip install python-docx
pip install docx2pdf  # Alternative DOCX to PDF converter

# XLSX handling
pip install openpyxl
pip install xlsxwriter

# Image handling (needed by some PDF libraries)
pip install Pillow

# PDF manipulation
pip install PyPDF2

echo ""
echo "=========================================="
echo "✓ Installation Complete!"
echo "=========================================="
echo ""
echo "Installed libraries:"
echo "  ✓ WeasyPrint - HTML to PDF (CSS support)"
echo "  ✓ xhtml2pdf - HTML to PDF"
echo "  ✓ ReportLab - PDF generation from scratch"
echo "  ✓ python-docx - Read/write DOCX files"
echo "  ✓ openpyxl - Read/write XLSX files"
echo "  ✓ PyPDF2 - PDF manipulation"
echo ""
echo "Next: Update requirements.txt"
pip freeze | grep -E "(weasyprint|xhtml2pdf|reportlab|python-docx|openpyxl|xlsxwriter|Pillow|PyPDF2)" >> requirements.txt
echo "✓ requirements.txt updated"
echo ""
