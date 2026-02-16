"""
DOCX to PDF Conversion Without LibreOffice
Uses python-docx + ReportLab as a replacement for LibreOffice
"""

from docx import Document
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from io import BytesIO
import os


def convert_docx_to_pdf(docx_path, pdf_path=None):
    """
    Convert DOCX to PDF using python-docx + ReportLab
    Returns PDF path or BytesIO buffer if pdf_path is None
    
    Args:
        docx_path: Path to input DOCX file
        pdf_path: Path to output PDF file (optional)
    
    Returns:
        str or BytesIO: PDF file path or buffer
    """
    # Load DOCX
    doc = Document(docx_path)
    
    # Create PDF
    if pdf_path:
        buffer = pdf_path
    else:
        buffer = BytesIO()
    
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18,
    )
    
    # Container for PDF elements
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(
        name='CustomHeading',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=12,
        spaceBefore=12,
    ))
    
    styles.add(ParagraphStyle(
        name='CustomBody',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
    ))
    
    # Process DOCX content
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        
        if not text:
            story.append(Spacer(1, 0.1*inch))
            continue
        
        # Determine style based on paragraph formatting
        if paragraph.style.name.startswith('Heading'):
            style = styles['CustomHeading']
        else:
            style = styles['CustomBody']
            
        # Handle text alignment
        if paragraph.alignment == 1:  # Center
            style = ParagraphStyle('TempCenter', parent=style, alignment=TA_CENTER)
        elif paragraph.alignment == 2:  # Right
            style = ParagraphStyle('TempRight', parent=style, alignment=TA_RIGHT)
        elif paragraph.alignment == 3:  # Justify
            style = ParagraphStyle('TempJustify', parent=style, alignment=TA_JUSTIFY)
        
        # Add paragraph to story
        try:
            p = Paragraph(text, style)
            story.append(p)
            story.append(Spacer(1, 0.1*inch))
        except:
            # Fallback for special characters
            safe_text = text.encode('ascii', 'ignore').decode('ascii')
            p = Paragraph(safe_text, style)
            story.append(p)
            story.append(Spacer(1, 0.1*inch))
    
    # Process tables
    for table in doc.tables:
        table_data = []
        for row in table.rows:
            row_data = []
            for cell in row.cells:
                cell_text = cell.text.strip()
                row_data.append(cell_text)
            table_data.append(row_data)
        
        if table_data:
            # Create PDF table
            pdf_table = Table(table_data)
            pdf_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ]))
            story.append(pdf_table)
            story.append(Spacer(1, 0.2*inch))
    
    # Build PDF
    pdf.build(story)
    
    if pdf_path:
        return pdf_path
    else:
        buffer.seek(0)
        return buffer


def docx_to_pdf_bytes(docx_path):
    """
    Convert DOCX to PDF and return as bytes
    
    Args:
        docx_path: Path to input DOCX file
    
    Returns:
        bytes: PDF content
    """
    buffer = convert_docx_to_pdf(docx_path, pdf_path=None)
    return buffer.getvalue()
