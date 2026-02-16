"""
DOCX to PDF Conversion
Uses MS Word COM on Windows or LibreOffice on Linux
"""

from io import BytesIO
import os
import sys
import tempfile


def convert_docx_to_pdf(docx_path, pdf_path=None):
    """
    Convert DOCX to PDF using best available method
    
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
    
    # Method 1: docx2pdf (Windows with MS Word COM)
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
    
    # Method 2: LibreOffice (Linux - best quality, requires LibreOffice installed)
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
        error_msg = "LibreOffice not found - please contact hosting provider to install"
        print(f"[X] {error_msg}")
        errors.append(error_msg)
    except Exception as e:
        error_msg = f"LibreOffice failed: {str(e)}"
        print(f"[X] {error_msg}")
        errors.append(error_msg)
    
    # All methods failed - PDF conversion not available
    error_summary = " | ".join(errors)
    print(f"\n[X] PDF conversion failed: {error_summary}")
    raise Exception(f"PDF conversion not available - LibreOffice not installed on server")


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
