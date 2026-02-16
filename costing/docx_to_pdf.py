"""
DOCX to PDF Conversion Without LibreOffice
Tries multiple methods for maximum compatibility
"""

from io import BytesIO
import os
import sys
import tempfile


def convert_docx_to_pdf(docx_path, pdf_path=None):
    """
    Convert DOCX to PDF using best available method
    Tries multiple approaches for compatibility
    
    Args:
        docx_path: Path to input DOCX file
        pdf_path: Path to output PDF file (optional)
    
    Returns:
        str or BytesIO: PDF file path or buffer
    """
    print(f"\n=== DOCX to PDF Conversion ===")
    print(f"Input: {docx_path}")
    print(f"Output: {pdf_path or 'BytesIO buffer'}")
    
    errors = []
    
    # Method 1: Try docx2pdf (Windows with MS Word via COM)
    if sys.platform == 'win32':
        try:
            print("Trying Method 1: docx2pdf (MS Word COM)")
            from docx2pdf import convert as docx2pdf_convert
            
            if pdf_path:
                docx2pdf_convert(docx_path, pdf_path)
                print(f"✓ Success with docx2pdf -> {pdf_path}")
                return pdf_path
            else:
                # docx2pdf needs a file path, use temp file
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                    temp_pdf = tmp.name
                docx2pdf_convert(docx_path, temp_pdf)
                with open(temp_pdf, 'rb') as f:
                    buffer = BytesIO(f.read())
                os.unlink(temp_pdf)
                print(f"✓ Success with docx2pdf -> BytesIO buffer")
                return buffer
        except Exception as e:
            error_msg = f"docx2pdf failed: {str(e)}"
            print(f"✗ {error_msg}")
            errors.append(error_msg)
    
    # Method 2: Try pypandoc (if pandoc is installed)
    try:
        print("Trying Method 2: pypandoc")
        import pypandoc
        
        if pdf_path:
            pypandoc.convert_file(docx_path, 'pdf', outputfile=pdf_path)
            print(f"✓ Success with pypandoc -> {pdf_path}")
            return pdf_path
        else:
            pdf_content = pypandoc.convert_file(docx_path, 'pdf', format='docx')
            buffer = BytesIO(pdf_content if isinstance(pdf_content, bytes) else pdf_content.encode())
            print(f"✓ Success with pypandoc -> BytesIO buffer")
            return buffer
    except ImportError:
        error_msg = "pypandoc not installed"
        print(f"✗ {error_msg}")
        errors.append(error_msg)
    except Exception as e:
        error_msg = f"pypandoc failed: {str(e)}"
        print(f"✗ {error_msg}")
        errors.append(error_msg)
    
    # Method 3: Try python-docx + ReportLab (basic conversion)
    try:
        print("Trying Method 3: python-docx + ReportLab")
        from docx import Document
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import inch
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        
        doc = Document(docx_path)
        
        if pdf_path:
            buffer = pdf_path
        else:
            buffer = BytesIO()
        
        pdf = SimpleDocTemplate(buffer, pagesize=A4, 
                                rightMargin=50, leftMargin=50,
                                topMargin=50, bottomMargin=30)
        
        story = []
        styles = getSampleStyleSheet()
        
        # Add paragraphs
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if text:
                try:
                    story.append(Paragraph(text, styles['Normal']))
                    story.append(Spacer(1, 0.1*inch))
                except:
                    pass
        
        # Add tables
        for table in doc.tables:
            table_data = [[cell.text.strip() for cell in row.cells] for row in table.rows]
            if table_data:
                try:
                    pdf_table = Table(table_data)
                    pdf_table.setStyle(TableStyle([
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ]))
                    story.append(pdf_table)
                    story.append(Spacer(1, 0.2*inch))
                except:
                    pass
        
        pdf.build(story)
        
        if pdf_path:
            print(f"✓ Success with python-docx + ReportLab -> {pdf_path}")
            return pdf_path
        else:
            buffer.seek(0)
            print(f"✓ Success with python-docx + ReportLab -> BytesIO buffer")
            return buffer
            
    except Exception as e:
        error_msg = f"python-docx + ReportLab failed: {str(e)}"
        print(f"✗ {error_msg}")
        errors.append(error_msg)
    
    # All methods failed
    error_summary = "\n".join(errors)
    print(f"\n✗ All conversion methods failed:\n{error_summary}")
    raise Exception(f"DOCX to PDF conversion failed. Tried 3 methods:\n{error_summary}")


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
