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
            import pythoncom
            from docx2pdf import convert as docx2pdf_convert
            
            # Initialize COM for this thread (required for Django multi-threading)
            pythoncom.CoInitialize()
            try:
                if pdf_path:
                    docx2pdf_convert(docx_path, pdf_path)
                    print(f"[OK] Success with docx2pdf -> {pdf_path}")
                    return pdf_path
                else:
                    # docx2pdf needs a file path, use temp file
                    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                        temp_pdf = tmp.name
                    docx2pdf_convert(docx_path, temp_pdf)
                    with open(temp_pdf, 'rb') as f:
                        buffer = BytesIO(f.read())
                    os.unlink(temp_pdf)
                    print(f"[OK] Success with docx2pdf -> BytesIO buffer")
                    return buffer
            finally:
                # Always clean up COM
                pythoncom.CoUninitialize()
        except Exception as e:
            error_msg = f"docx2pdf failed: {str(e)}"
            print(f"[X] {error_msg}")
            errors.append(error_msg)
    
    # Method 2: Try LibreOffice (Linux, best quality conversion)
    try:
        print("Trying Method 2: LibreOffice")
        import subprocess
        
        if pdf_path:
            output_dir = os.path.dirname(pdf_path)
        else:
            output_dir = tempfile.gettempdir()
        
        # Run LibreOffice in headless mode to convert to PDF
        result = subprocess.run([
            'libreoffice', '--headless', '--convert-to', 'pdf',
            '--outdir', output_dir, docx_path
        ], capture_output=True, text=True, timeout=30)
        
        # LibreOffice creates PDF with same name as DOCX but .pdf extension
        docx_basename = os.path.splitext(os.path.basename(docx_path))[0]
        generated_pdf = os.path.join(output_dir, f"{docx_basename}.pdf")
        
        if result.returncode == 0 and os.path.exists(generated_pdf):
            if pdf_path:
                if generated_pdf != pdf_path:
                    os.rename(generated_pdf, pdf_path)
                print(f"[OK] Success with LibreOffice -> {pdf_path}")
                return pdf_path
            else:
                with open(generated_pdf, 'rb') as f:
                    buffer = BytesIO(f.read())
                os.unlink(generated_pdf)
                print(f"[OK] Success with LibreOffice -> BytesIO buffer")
                return buffer
        else:
            raise Exception(f"LibreOffice conversion failed: {result.stderr}")
            
    except FileNotFoundError:
        error_msg = "LibreOffice not found (install with: sudo apt-get install libreoffice)"
        print(f"[X] {error_msg}")
        errors.append(error_msg)
    except Exception as e:
        error_msg = f"LibreOffice failed: {str(e)}"
        print(f"[X] {error_msg}")
        errors.append(error_msg)
    
    # Method 3: Try mammoth + weasyprint (DOCX -> HTML -> PDF, good quality)
    try:
        print("Trying Method 3: mammoth + weasyprint")
        import mammoth
        from weasyprint import HTML, CSS
        
        # Convert DOCX to HTML
        with open(docx_path, 'rb') as docx_file:
            result = mammoth.convert_to_html(docx_file)
            html_content = result.value
        
        # Add basic styling for better PDF output
        styled_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                td, th {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                img {{ max-width: 100%; height: auto; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        # Convert HTML to PDF using weasyprint
        if pdf_path:
            HTML(string=styled_html).write_pdf(pdf_path)
            print(f"[OK] Success with mammoth + weasyprint -> {pdf_path}")
            return pdf_path
        else:
            buffer = BytesIO()
            HTML(string=styled_html).write_pdf(buffer)
            buffer.seek(0)
            print(f"[OK] Success with mammoth + weasyprint -> BytesIO buffer")
            return buffer
            
    except ImportError as ie:
        error_msg = f"mammoth or weasyprint not installed: {str(ie)}"
        print(f"[X] {error_msg}")
        errors.append(error_msg)
    except Exception as e:
        error_msg = f"mammoth + weasyprint failed: {str(e)}"
        print(f"[X] {error_msg}")
        errors.append(error_msg)
    
    # Method 4: Try pypandoc (if pandoc is installed)
    try:
        print("Trying Method 4: pypandoc")
        import pypandoc
        
        if pdf_path:
            pypandoc.convert_file(docx_path, 'pdf', outputfile=pdf_path)
            print(f"[OK] Success with pypandoc -> {pdf_path}")
            return pdf_path
        else:
            pdf_content = pypandoc.convert_file(docx_path, 'pdf', format='docx')
            buffer = BytesIO(pdf_content if isinstance(pdf_content, bytes) else pdf_content.encode())
            print(f"[OK] Success with pypandoc -> BytesIO buffer")
            return buffer
    except ImportError:
        error_msg = "pypandoc not installed"
        print(f"[X] {error_msg}")
        errors.append(error_msg)
    except Exception as e:
        error_msg = f"pypandoc failed: {str(e)}"
        print(f"[X] {error_msg}")
        errors.append(error_msg)
    
    # Method 5: Try python-docx + ReportLab (basic conversion, fallback)
    try:
        print("Trying Method 5: python-docx + ReportLab (basic)")
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
            print(f"[OK] Success with python-docx + ReportLab -> {pdf_path}")
            return pdf_path
        else:
            buffer.seek(0)
            print(f"[OK] Success with python-docx + ReportLab -> BytesIO buffer")
            return buffer
            
    except Exception as e:
        error_msg = f"python-docx + ReportLab failed: {str(e)}"
        print(f"[X] {error_msg}")
        errors.append(error_msg)
    
    # All methods failed
    error_summary = "\n".join(errors)
    print(f"\n[X] All conversion methods failed:\n{error_summary}")
    raise Exception(f"DOCX to PDF conversion failed. Tried 5 methods:\n{error_summary}")


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
