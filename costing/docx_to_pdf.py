"""
DOCX to PDF Conversion
Uses MS Word COM on Windows, LibreOffice on Linux (including userspace install),
or falls back to python-docx + weasyprint for pure-Python conversion.
"""

import glob
import logging
from io import BytesIO
import os
import sys
import tempfile

logger = logging.getLogger(__name__)


def _find_libreoffice():
    """Find LibreOffice binary, including userspace installs on cPanel."""
    home = os.path.expanduser("~")
    candidates = [
        # Standard system paths
        "/usr/bin/libreoffice",
        "/usr/bin/soffice",
        "/opt/libreoffice/program/soffice",
        # Userspace install (cPanel / shared hosting)
        os.path.join(home, "libreoffice", "opt", "libreoffice*", "program", "soffice"),
        os.path.join(home, "libreoffice", "usr", "bin", "libreoffice"),
        os.path.join(home, "bin", "libreoffice"),
        os.path.join(home, "bin", "soffice"),
        # Windows
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for pattern in candidates:
        if '*' in pattern:
            matches = glob.glob(pattern)
            for match in sorted(matches, reverse=True):
                if os.path.isfile(match) and os.access(match, os.X_OK):
                    return match
        elif os.path.isfile(pattern) and os.access(pattern, os.X_OK):
            return pattern
    return None


def _convert_with_weasyprint(docx_path, pdf_path=None):
    """
    Fallback: convert DOCX to PDF using python-docx to extract content
    and weasyprint to render it. Not as high-fidelity as LibreOffice but
    works on any host with no system dependencies beyond what pip provides.
    """
    from docx import Document
    from weasyprint import HTML

    doc = Document(docx_path)

    # Build HTML from document content
    html_parts = [
        '<!DOCTYPE html><html><head><meta charset="utf-8">',
        '<style>',
        'body { font-family: Arial, Helvetica, sans-serif; margin: 2cm; font-size: 11pt; }',
        'table { border-collapse: collapse; width: 100%; margin: 8px 0; }',
        'td, th { border: 1px solid #999; padding: 4px 8px; text-align: left; }',
        'th { background: #f0f0f0; font-weight: bold; }',
        'h1 { font-size: 18pt; } h2 { font-size: 14pt; } h3 { font-size: 12pt; }',
        'p { margin: 4px 0; }',
        '</style></head><body>',
    ]

    for element in doc.element.body:
        tag = element.tag.split('}')[-1]

        if tag == 'p':
            from docx.text.paragraph import Paragraph
            para = Paragraph(element, doc)
            style_name = (para.style.name or '').lower()
            text = para.text.strip()
            if not text:
                html_parts.append('<p>&nbsp;</p>')
                continue
            from xml.sax.saxutils import escape
            escaped = escape(text)
            if 'heading 1' in style_name:
                html_parts.append(f'<h1>{escaped}</h1>')
            elif 'heading 2' in style_name:
                html_parts.append(f'<h2>{escaped}</h2>')
            elif 'heading 3' in style_name:
                html_parts.append(f'<h3>{escaped}</h3>')
            else:
                # Preserve bold/italic from runs
                run_html = []
                for run in para.runs:
                    chunk = escape(run.text)
                    if run.bold:
                        chunk = f'<b>{chunk}</b>'
                    if run.italic:
                        chunk = f'<i>{chunk}</i>'
                    if run.underline:
                        chunk = f'<u>{chunk}</u>'
                    run_html.append(chunk)
                html_parts.append(f'<p>{"".join(run_html)}</p>')

        elif tag == 'tbl':
            from docx.table import Table
            table = Table(element, doc)
            html_parts.append('<table>')
            for i, row in enumerate(table.rows):
                html_parts.append('<tr>')
                cell_tag = 'th' if i == 0 else 'td'
                for cell in row.cells:
                    from xml.sax.saxutils import escape as esc
                    html_parts.append(f'<{cell_tag}>{esc(cell.text)}</{cell_tag}>')
                html_parts.append('</tr>')
            html_parts.append('</table>')

    html_parts.append('</body></html>')
    html_string = '\n'.join(html_parts)

    if pdf_path:
        HTML(string=html_string).write_pdf(pdf_path)
        return pdf_path
    else:
        pdf_bytes = HTML(string=html_string).write_pdf()
        return BytesIO(pdf_bytes)


def convert_docx_to_pdf(docx_path, pdf_path=None):
    """
    Convert DOCX to PDF using best available method:
    1. docx2pdf (Windows with MS Word COM)
    2. LibreOffice (system or userspace install)
    3. python-docx + weasyprint (pure Python fallback)
    """
    logger.debug('DOCX to PDF conversion: Input=%s, Output=%s', docx_path, pdf_path or 'BytesIO buffer')
    
    errors = []
    
    # Method 1: docx2pdf (Windows with MS Word COM)
    if sys.platform == 'win32':
        try:
            logger.debug('Trying Method 1: docx2pdf (MS Word COM)')
            import pythoncom
            from docx2pdf import convert as docx2pdf_convert
            
            # Initialize COM for this thread (required for Django multi-threading)
            pythoncom.CoInitialize()
            try:
                if pdf_path:
                    docx2pdf_convert(docx_path, pdf_path)
                    logger.debug('Success with docx2pdf -> %s', pdf_path)
                    return pdf_path
                else:
                    # docx2pdf needs a file path, use temp file
                    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                        temp_pdf = tmp.name
                    docx2pdf_convert(docx_path, temp_pdf)
                    with open(temp_pdf, 'rb') as f:
                        buffer = BytesIO(f.read())
                    os.unlink(temp_pdf)
                    logger.debug('Success with docx2pdf -> BytesIO buffer')
                    return buffer
            finally:
                # Always clean up COM
                pythoncom.CoUninitialize()
        except Exception as e:
            error_msg = f"docx2pdf failed: {str(e)}"
            logger.debug(error_msg)
            errors.append(error_msg)
    
    # Method 2: LibreOffice (system or userspace install — best quality on Linux)
    libreoffice_bin = _find_libreoffice()
    if libreoffice_bin:
        try:
            logger.debug('Trying Method 2: LibreOffice at %s', libreoffice_bin)
            import subprocess
            
            if pdf_path:
                output_dir = os.path.dirname(pdf_path)
            else:
                output_dir = tempfile.gettempdir()
            
            result = subprocess.run([
                libreoffice_bin, '--headless', '--convert-to', 'pdf',
                '--outdir', output_dir, docx_path
            ], capture_output=True, text=True, timeout=60)
            
            docx_basename = os.path.splitext(os.path.basename(docx_path))[0]
            generated_pdf = os.path.join(output_dir, f"{docx_basename}.pdf")
            
            if result.returncode == 0 and os.path.exists(generated_pdf):
                if pdf_path:
                    if generated_pdf != pdf_path:
                        os.rename(generated_pdf, pdf_path)
                    logger.debug('Success with LibreOffice -> %s', pdf_path)
                    return pdf_path
                else:
                    with open(generated_pdf, 'rb') as f:
                        buffer = BytesIO(f.read())
                    os.unlink(generated_pdf)
                    logger.debug('Success with LibreOffice -> BytesIO buffer')
                    return buffer
            else:
                raise Exception(f"LibreOffice conversion failed: {result.stderr}")
                
        except Exception as e:
            error_msg = f"LibreOffice failed: {str(e)}"
            logger.debug(error_msg)
            errors.append(error_msg)
    else:
        errors.append("LibreOffice not found (checked system and ~/libreoffice/)")

    # Method 3: python-docx + weasyprint (pure Python, no system deps)
    try:
        logger.debug('Trying Method 3: python-docx + weasyprint')
        result = _convert_with_weasyprint(docx_path, pdf_path)
        logger.debug('Success with weasyprint fallback')
        return result
    except Exception as e:
        error_msg = f"weasyprint fallback failed: {str(e)}"
        logger.debug(error_msg)
        errors.append(error_msg)
    
    # All methods failed
    error_summary = " | ".join(errors)
    logger.warning('PDF conversion failed: %s', error_summary)
    raise Exception(f"PDF conversion not available: {error_summary}")


def docx_to_pdf_bytes(docx_path):
    """
    Convert DOCX to PDF and return as bytes.
    """
    result = convert_docx_to_pdf(docx_path, pdf_path=None)
    if isinstance(result, bytes):
        return result
    return result.getvalue()
