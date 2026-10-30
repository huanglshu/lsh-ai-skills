#!/usr/bin/env python3
"""
Convert2Pdf — Convert files to PDF with automatic tool detection.

Supported formats:
  - XPS  → PyMuPDF / Ghostscript / PowerShell
  - DOCX / DOC / WPS → LibreOffice / Word COM / WPS COM / python-docx
  - XLSX / XLS / ET  → LibreOffice / Excel COM / WPS COM / openpyxl
  - PPTX / PPT / DPS → LibreOffice / PowerPoint COM / WPS COM / python-pptx
  - MHTML / MHT → Chromium headless / LibreOffice

Usage:
  python convert2pdf.py input.xps
  python convert2pdf.py input.docx -o output.pdf
  python convert2pdf.py *.docx *.xlsx *.pptx   # batch convert
  python convert2pdf.py input.xps -r 300        # custom DPI
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# File type detection
# ---------------------------------------------------------------------------

XPS_EXTENSIONS = {".xps", ".oxps"}
OFFICE_WORD_EXTENSIONS = {".docx", ".doc", ".rtf", ".odt", ".wps"}
OFFICE_EXCEL_EXTENSIONS = {".xlsx", ".xls", ".ods", ".csv", ".et"}
OFFICE_PPT_EXTENSIONS = {".pptx", ".ppt", ".odp", ".dps"}
WPS_EXTENSIONS = {".wps", ".et", ".dps"}
MHTML_EXTENSIONS = {".mht", ".mhtml"}
OFFICE_EXTENSIONS = OFFICE_WORD_EXTENSIONS | OFFICE_EXCEL_EXTENSIONS | OFFICE_PPT_EXTENSIONS
ALL_EXTENSIONS = XPS_EXTENSIONS | OFFICE_EXTENSIONS | MHTML_EXTENSIONS


def detect_file_type(path: str) -> str:
    """Return 'xps', 'word', 'excel', 'ppt', or 'unknown'."""
    ext = Path(path).suffix.lower()
    if ext in XPS_EXTENSIONS:
        return "xps"
    if ext in OFFICE_WORD_EXTENSIONS:
        return "word"
    if ext in OFFICE_EXCEL_EXTENSIONS:
        return "excel"
    if ext in OFFICE_PPT_EXTENSIONS:
        return "ppt"
    if ext in MHTML_EXTENSIONS:
        return "mhtml"
    return "unknown"


# ---------------------------------------------------------------------------
# Tool availability checks
# ---------------------------------------------------------------------------

def has_pymupdf() -> bool:
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def find_ghostscript() -> str | None:
    for cmd in ["gxps", "gxpsw64", "gswin64c", "gswin32c", "gs"]:
        if shutil.which(cmd):
            return cmd
    return None


def find_libreoffice() -> str | None:
    """Find LibreOffice soffice executable."""
    # Check PATH first
    soffice = shutil.which("soffice")
    if soffice:
        return soffice
    # Windows common install paths
    if sys.platform == "win32":
        candidates = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
    return None


def find_wps() -> str | None:
    """Find WPS Office installation path (Windows)."""
    if sys.platform != "win32":
        return None
    # Check registry common paths
    candidates = [
        r"C:\Users\{user}\AppData\Local\Kingsoft\WPS Office\ksolaunch.exe",
        r"C:\Program Files (x86)\Kingsoft\WPS Office\ksolaunch.exe",
        r"C:\Program Files\Kingsoft\WPS Office\ksolaunch.exe",
    ]
    import getpass
    user = getpass.getuser()
    for p in candidates:
        path = p.format(user=user)
        if os.path.isfile(path):
            return os.path.dirname(path)
    # Try to find via registry
    try:
        import winreg
        for key_path in [
            r"SOFTWARE\Kingsoft\Office",
            r"SOFTWARE\WOW6432Node\Kingsoft\Office",
        ]:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    install_dir, _ = winreg.QueryValueEx(key, "InstallPath")
                    if os.path.isdir(install_dir):
                        return install_dir
            except (FileNotFoundError, OSError):
                continue
    except ImportError:
        pass
    return None


def find_chromium() -> str | None:
    """Find Chromium-based browser (Edge or Chrome) for headless PDF generation."""
    # Check PATH first
    for cmd in ["msedge", "chrome", "google-chrome"]:
        if shutil.which(cmd):
            return cmd
    # Windows common install paths
    if sys.platform == "win32":
        candidates = [
            # Edge
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            # Chrome
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
    # Linux
    if sys.platform.startswith("linux"):
        for cmd in ["/usr/bin/microsoft-edge", "/usr/bin/google-chrome-stable"]:
            if os.path.isfile(cmd):
                return cmd
    return None


def has_python_docx() -> bool:
    try:
        import docx  # noqa: F401
        return True
    except ImportError:
        return False


def has_openpyxl() -> bool:
    try:
        import openpyxl  # noqa: F401
        return True
    except ImportError:
        return False


def has_python_pptx() -> bool:
    try:
        import pptx  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# XPS conversion
# ---------------------------------------------------------------------------

def xps_with_pymupdf(input_path: str, output_path: str, dpi: int = 150) -> bool:
    import fitz
    doc = fitz.open(input_path)
    pdf = fitz.open()
    for i in range(doc.page_count):
        page = doc[i]
        rect = page.rect
        pdf_page = pdf.new_page(width=rect.width, height=rect.height)
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        pdf_page.insert_image(rect, pixmap=pix)
    pdf.save(output_path, deflate=True, garbage=4, clean=True)
    pdf.close()
    doc.close()
    return True


def xps_with_ghostscript(input_path: str, output_path: str, gs_cmd: str, dpi: int = 150) -> bool:
    cmd = [
        gs_cmd,
        "-sDEVICE=pdfwrite",
        f"-sOutputFile={output_path}",
        "-dNOPAUSE", "-dBATCH", "-dSAFER",
        f"-r{dpi}",
        input_path,
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Ghostscript error:\n{result.stderr}", file=sys.stderr)
        return False
    return True


def xps_with_powershell(input_path: str, output_path: str) -> bool:
    abs_input = os.path.abspath(input_path).replace("'", "''")
    abs_output = os.path.abspath(output_path).replace("'", "''")
    ps_script = (
        "Add-Type -AssemblyName ReachFramework\n"
        "Add-Type -AssemblyName System.Printing\n"
        f"$xpsDoc = New-Object System.Windows.Xps.Packaging.XpsDocument('{abs_input}', [System.IO.FileAccess]::Read)\n"
        f"$printServer = New-Object System.Printing.LocalPrintServer\n"
        f"$queue = $printServer.GetPrintQueue('Microsoft Print to PDF')\n"
        "$printTicket = $queue.DefaultPrintTicket\n"
        "$writer = [System.Windows.Xps.XpsDocumentWriter]::CreateXpsDocumentWriter($queue)\n"
        "$writer.Write($xpsDoc.GetFixedDocumentSequence(), $printTicket)\n"
        "$xpsDoc.Close()\n"
        f"if (Test-Path '{abs_output}') {{ Write-Host 'Conversion complete' }} else {{ exit 1 }}\n"
    )
    cmd = ["powershell", "-NoProfile", "-STA", "-Command", ps_script]
    print("Running PowerShell XPS conversion...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"PowerShell error:\n{result.stderr}", file=sys.stderr)
        return False
    return True


# ---------------------------------------------------------------------------
# Office conversion — LibreOffice
# ---------------------------------------------------------------------------

def office_with_libreoffice(input_path: str, output_path: str) -> bool:
    soffice = find_libreoffice()
    if not soffice:
        return False
    out_dir = os.path.dirname(os.path.abspath(output_path)) or "."
    cmd = [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, input_path]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"LibreOffice error:\n{result.stderr}", file=sys.stderr)
        return False
    # LibreOffice names output as <basename>.pdf; rename if needed
    generated = os.path.join(out_dir, Path(input_path).stem + ".pdf")
    abs_output = os.path.abspath(output_path)
    if os.path.isfile(generated) and os.path.abspath(generated) != abs_output:
        os.replace(generated, abs_output)
    return os.path.isfile(abs_output)


# ---------------------------------------------------------------------------
# Office conversion — WPS Office COM (Windows only)
# ---------------------------------------------------------------------------

def wps_writer_com(input_path: str, output_path: str) -> bool:
    """Convert WPS/DOC file to PDF using WPS Writer COM."""
    abs_input = os.path.abspath(input_path).replace("'", "''")
    abs_output = os.path.abspath(output_path).replace("'", "''")
    ps_script = (
        f"$wps = New-Object -ComObject Wps.Application\n"
        f"$wps.Visible = $false\n"
        f"$doc = $wps.Documents.Open('{abs_input}')\n"
        f"$doc.ExportAsFixedFormat('{abs_output}', 17)\n"
        f"$doc.Close()\n"
        f"$wps.Quit()\n"
        f"[System.Runtime.Interopservices.Marshal]::ReleaseComObject($wps) | Out-Null\n"
    )
    cmd = ["powershell", "-NoProfile", "-STA", "-Command", ps_script]
    print("Running WPS Writer COM conversion...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"WPS Writer COM error:\n{result.stderr}", file=sys.stderr)
        return False
    return os.path.isfile(os.path.abspath(output_path))


def wps_et_com(input_path: str, output_path: str) -> bool:
    """Convert WPS Spreadsheet/ET file to PDF using WPS ET COM."""
    abs_input = os.path.abspath(input_path).replace("'", "''")
    abs_output = os.path.abspath(output_path).replace("'", "''")
    ps_script = (
        f"$et = New-Object -ComObject Et.Application\n"
        f"$et.Visible = $false\n"
        f"$et.DisplayAlerts = $false\n"
        f"$wb = $et.Workbooks.Open('{abs_input}')\n"
        f"$wb.ExportAsFixedFormat(0, '{abs_output}')\n"
        f"$wb.Close($false)\n"
        f"$et.Quit()\n"
        f"[System.Runtime.Interopservices.Marshal]::ReleaseComObject($et) | Out-Null\n"
    )
    cmd = ["powershell", "-NoProfile", "-STA", "-Command", ps_script]
    print("Running WPS ET COM conversion...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"WPS ET COM error:\n{result.stderr}", file=sys.stderr)
        return False
    return os.path.isfile(os.path.abspath(output_path))


def wps_dps_com(input_path: str, output_path: str) -> bool:
    """Convert WPS Presentation/DPS file to PDF using WPS WPP COM."""
    abs_input = os.path.abspath(input_path).replace("'", "''")
    abs_output = os.path.abspath(output_path).replace("'", "''")
    ps_script = (
        f"$dps = New-Object -ComObject Wpp.Application\n"
        f"$pres = $dps.Presentations.Open('{abs_input}')\n"
        f"$pres.SaveAs('{abs_output}', 32)\n"
        f"$pres.Close()\n"
        f"$dps.Quit()\n"
        f"[System.Runtime.Interopservices.Marshal]::ReleaseComObject($dps) | Out-Null\n"
    )
    cmd = ["powershell", "-NoProfile", "-STA", "-Command", ps_script]
    print("Running WPS WPP COM conversion...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"WPS WPP COM error:\n{result.stderr}", file=sys.stderr)
        return False
    return os.path.isfile(os.path.abspath(output_path))


# ---------------------------------------------------------------------------
# Office conversion — MS Office COM (Windows only)
# ---------------------------------------------------------------------------

def office_word_com(input_path: str, output_path: str) -> bool:
    abs_input = os.path.abspath(input_path).replace("'", "''")
    abs_output = os.path.abspath(output_path).replace("'", "''")
    ps_script = (
        f"$word = New-Object -ComObject Word.Application\n"
        f"$word.Visible = $false\n"
        f"$doc = $word.Documents.Open('{abs_input}')\n"
        f"$doc.SaveAs([ref]'{abs_output}', [ref]17)\n"
        f"$doc.Close()\n"
        f"$word.Quit()\n"
        f"[System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null\n"
    )
    cmd = ["powershell", "-NoProfile", "-STA", "-Command", ps_script]
    print("Running Word COM conversion...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Word COM error:\n{result.stderr}", file=sys.stderr)
        return False
    return os.path.isfile(os.path.abspath(output_path))


def office_excel_com(input_path: str, output_path: str) -> bool:
    abs_input = os.path.abspath(input_path).replace("'", "''")
    abs_output = os.path.abspath(output_path).replace("'", "''")
    ps_script = (
        f"$excel = New-Object -ComObject Excel.Application\n"
        f"$excel.Visible = $false\n"
        f"$excel.DisplayAlerts = $false\n"
        f"$wb = $excel.Workbooks.Open('{abs_input}')\n"
        f"$wb.ExportAsFixedFormat(0, '{abs_output}')\n"
        f"$wb.Close($false)\n"
        f"$excel.Quit()\n"
        f"[System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null\n"
    )
    cmd = ["powershell", "-NoProfile", "-STA", "-Command", ps_script]
    print("Running Excel COM conversion...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Excel COM error:\n{result.stderr}", file=sys.stderr)
        return False
    return os.path.isfile(os.path.abspath(output_path))


def office_ppt_com(input_path: str, output_path: str) -> bool:
    abs_input = os.path.abspath(input_path).replace("'", "''")
    abs_output = os.path.abspath(output_path).replace("'", "''")
    ps_script = (
        f"$ppt = New-Object -ComObject PowerPoint.Application\n"
        f"$pres = $ppt.Presentations.Open('{abs_input}', [Microsoft.Office.Core.MsoTriState]::msoTrue, [Microsoft.Office.Core.MsoTriState]::msoFalse, [Microsoft.Office.Core.MsoTriState]::msoFalse)\n"
        f"$pres.SaveAs('{abs_output}', 32)\n"
        f"$pres.Close()\n"
        f"$ppt.Quit()\n"
        f"[System.Runtime.Interopservices.Marshal]::ReleaseComObject($ppt) | Out-Null\n"
    )
    cmd = ["powershell", "-NoProfile", "-STA", "-Command", ps_script]
    print("Running PowerPoint COM conversion...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"PowerPoint COM error:\n{result.stderr}", file=sys.stderr)
        return False
    return os.path.isfile(os.path.abspath(output_path))


# ---------------------------------------------------------------------------
# Office conversion — Python libraries (fallback, limited formatting)
# ---------------------------------------------------------------------------

def word_with_python(input_path: str, output_path: str) -> bool:
    """Convert DOCX to PDF using python-docx + reportlab (basic text only)."""
    try:
        from docx import Document
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
    except ImportError as e:
        print(f"Missing Python library: {e}", file=sys.stderr)
        return False

    try:
        doc = Document(input_path)
        pdf = SimpleDocTemplate(output_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                story.append(Spacer(1, 12))
                continue
            style_name = "Normal"
            if para.style and para.style.name:
                sname = para.style.name.lower()
                if "heading 1" in sname:
                    style_name = "Heading1"
                elif "heading 2" in sname:
                    style_name = "Heading2"
                elif "heading 3" in sname:
                    style_name = "Heading3"
            story.append(Paragraph(text, styles[style_name]))
        if not story:
            story.append(Paragraph("(empty document)", styles["Normal"]))
        pdf.build(story)
        return True
    except Exception as e:
        print(f"python-docx error: {e}", file=sys.stderr)
        return False


def excel_with_python(input_path: str, output_path: str) -> bool:
    """Convert XLSX to PDF using openpyxl + reportlab (basic table only)."""
    try:
        from openpyxl import load_workbook
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
    except ImportError as e:
        print(f"Missing Python library: {e}", file=sys.stderr)
        return False

    try:
        wb = load_workbook(input_path, data_only=True)
        pdf = SimpleDocTemplate(output_path, pagesize=landscape(A4))
        styles = getSampleStyleSheet()
        story = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            story.append(Paragraph(f"Sheet: {sheet_name}", styles["Heading2"]))
            story.append(Spacer(1, 6))
            data = []
            for row in ws.iter_rows(values_only=True):
                data.append([str(cell) if cell is not None else "" for cell in row])
            if not data:
                story.append(Paragraph("(empty sheet)", styles["Normal"]))
                continue
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#D9E2F3")]),
            ]))
            story.append(table)
            story.append(Spacer(1, 18))
        if not story:
            story.append(Paragraph("(empty workbook)", styles["Normal"]))
        pdf.build(story)
        return True
    except Exception as e:
        print(f"openpyxl error: {e}", file=sys.stderr)
        return False


def ppt_with_python(input_path: str, output_path: str) -> bool:
    """Convert PPTX to PDF using python-pptx + reportlab (text extraction only)."""
    try:
        from pptx import Presentation
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet
    except ImportError as e:
        print(f"Missing Python library: {e}", file=sys.stderr)
        return False

    try:
        prs = Presentation(input_path)
        pdf = SimpleDocTemplate(output_path, pagesize=landscape(A4))
        styles = getSampleStyleSheet()
        story = []
        for idx, slide in enumerate(prs.slides, 1):
            story.append(Paragraph(f"Slide {idx}", styles["Heading1"]))
            story.append(Spacer(1, 12))
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if text:
                            story.append(Paragraph(text, styles["Normal"]))
            story.append(PageBreak())
        if not story:
            story.append(Paragraph("(empty presentation)", styles["Normal"]))
        pdf.build(story)
        return True
    except Exception as e:
        print(f"python-pptx error: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# MHTML conversion
# ---------------------------------------------------------------------------

def mhtml_with_chromium(input_path: str, output_path: str) -> bool:
    """Convert MHTML to PDF using Chromium headless (Edge/Chrome)."""
    browser = find_chromium()
    if not browser:
        return False
    abs_input = os.path.abspath(input_path)
    abs_output = os.path.abspath(output_path)
    # Use file:// URI for local file
    file_uri = Path(abs_input).as_uri()
    cmd = [
        browser,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-software-rasterizer",
        f"--print-to-pdf={abs_output}",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=5000",
        file_uri,
    ]
    print(f"Running: {' '.join(cmd[:3])} ... --print-to-pdf")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"Chromium error:\n{result.stderr}", file=sys.stderr)
        return False
    return os.path.isfile(abs_output)


def mhtml_with_libreoffice(input_path: str, output_path: str) -> bool:
    """Convert MHTML to PDF using LibreOffice (Web Writer)."""
    return office_with_libreoffice(input_path, output_path)


# ---------------------------------------------------------------------------
# Unified conversion dispatcher
# ---------------------------------------------------------------------------

def convert_file(input_path: str, output_path: str | None = None, dpi: int = 150) -> bool:
    """Convert a single file to PDF with automatic tool detection."""
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        return False

    if output_path is None:
        output_path = str(input_file.with_suffix(".pdf"))

    file_type = detect_file_type(input_path)
    if file_type == "unknown":
        print(f"Error: Unsupported file type: {input_file.suffix}", file=sys.stderr)
        return False

    # --- XPS conversion ---
    if file_type == "xps":
        return _convert_xps(input_path, output_path, dpi)

    # --- MHTML conversion ---
    if file_type == "mhtml":
        return _convert_mhtml(input_path, output_path)

    # --- Office conversion ---
    return _convert_office(input_path, output_path, file_type)


def _convert_xps(input_path: str, output_path: str, dpi: int) -> bool:
    if has_pymupdf():
        print(f"[XPS] Using PyMuPDF: {input_path} -> {output_path}")
        try:
            if xps_with_pymupdf(input_path, output_path, dpi):
                _report_success(output_path)
                return True
        except Exception as e:
            print(f"PyMuPDF error: {e}", file=sys.stderr)

    gs_cmd = find_ghostscript()
    if gs_cmd:
        print(f"[XPS] Using Ghostscript ({gs_cmd}): {input_path} -> {output_path}")
        if xps_with_ghostscript(input_path, output_path, gs_cmd, dpi):
            _report_success(output_path)
            return True
        print("Ghostscript failed, trying PowerShell fallback...")

    if sys.platform == "win32":
        print(f"[XPS] Using PowerShell: {input_path} -> {output_path}")
        if xps_with_powershell(input_path, output_path):
            if os.path.exists(output_path):
                _report_success(output_path)
                return True

    print("Error: No XPS conversion tool available. Install Ghostscript or PyMuPDF.", file=sys.stderr)
    return False


def _convert_mhtml(input_path: str, output_path: str) -> bool:
    # 1. Chromium headless (best fidelity for web content)
    browser = find_chromium()
    if browser:
        print(f"[MHTML] Using Chromium ({browser}): {input_path} -> {output_path}")
        try:
            if mhtml_with_chromium(input_path, output_path):
                _report_success(output_path)
                return True
        except subprocess.TimeoutExpired:
            print("Chromium timed out, trying LibreOffice fallback...")
        except Exception as e:
            print(f"Chromium error: {e}, trying LibreOffice fallback...")

    # 2. LibreOffice (fallback)
    soffice = find_libreoffice()
    if soffice:
        print(f"[MHTML] Using LibreOffice: {input_path} -> {output_path}")
        if mhtml_with_libreoffice(input_path, output_path):
            _report_success(output_path)
            return True
        print("LibreOffice failed.")

    print("Error: No MHTML conversion tool available. Install Edge/Chrome or LibreOffice.", file=sys.stderr)
    return False


def _convert_office(input_path: str, output_path: str, file_type: str) -> bool:
    label = file_type.upper()

    # 1. LibreOffice (best fidelity)
    soffice = find_libreoffice()
    if soffice:
        print(f"[{label}] Using LibreOffice: {input_path} -> {output_path}")
        if office_with_libreoffice(input_path, output_path):
            _report_success(output_path)
            return True
        print("LibreOffice failed, trying next method...")

    # 2. WPS Office COM (Windows only, if WPS installed)
    if sys.platform == "win32" and find_wps():
        wps_func = {"word": wps_writer_com, "excel": wps_et_com, "ppt": wps_dps_com}.get(file_type)
        if wps_func:
            print(f"[{label}] Using WPS Office COM: {input_path} -> {output_path}")
            if wps_func(input_path, output_path):
                _report_success(output_path)
                return True
            print("WPS COM failed, trying MS Office COM...")

    # 3. MS Office COM (Windows only)
    if sys.platform == "win32":
        com_func = {"word": office_word_com, "excel": office_excel_com, "ppt": office_ppt_com}.get(file_type)
        if com_func:
            print(f"[{label}] Using MS Office COM: {input_path} -> {output_path}")
            if com_func(input_path, output_path):
                _report_success(output_path)
                return True
            print("COM conversion failed, trying Python fallback...")

    # 4. Python libraries (fallback)
    py_func = {"word": word_with_python, "excel": excel_with_python, "ppt": ppt_with_python}.get(file_type)
    if py_func:
        print(f"[{label}] Using Python libraries: {input_path} -> {output_path}")
        if py_func(input_path, output_path):
            _report_success(output_path)
            return True

    print(f"Error: No conversion tool available for {label}. Install LibreOffice, WPS Office, or MS Office.", file=sys.stderr)
    return False


def _report_success(output_path: str) -> None:
    if os.path.isfile(output_path):
        size = os.path.getsize(output_path)
        print(f"Success: {output_path} ({size:,} bytes)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert2Pdf — Convert XPS, Office, WPS, and MHTML files to PDF"
    )
    parser.add_argument(
        "input", nargs="+",
        help="Input file(s) or glob pattern(s). Supported: .xps .docx .doc .wps .xlsx .xls .et .pptx .ppt .dps .mht .mhtml .odt .ods .odp .rtf .csv"
    )
    parser.add_argument("-o", "--output", help="Output PDF path (single file only)")
    parser.add_argument("-r", "--dpi", type=int, default=150, help="DPI for XPS conversion (default: 150)")
    args = parser.parse_args()

    # Expand globs
    files = []
    for pattern in args.input:
        expanded = glob.glob(pattern)
        files.extend(expanded if expanded else [pattern])

    if not files:
        print("Error: No input files found.", file=sys.stderr)
        sys.exit(1)

    if len(files) > 1 and args.output:
        print("Error: -o/--output cannot be used with multiple files.", file=sys.stderr)
        sys.exit(1)

    success_count = 0
    for f in files:
        out = args.output if len(files) == 1 else None
        if convert_file(f, out, args.dpi):
            success_count += 1

    total = len(files)
    print(f"\nConverted {success_count}/{total} file(s)")
    sys.exit(0 if success_count == total else 1)


if __name__ == "__main__":
    main()
