---
name: convert-to-pdf
description: Convert files to PDF format. Supports XPS files, Office files (Word, Excel, PowerPoint), WPS Office files (WPS, ET, DPS), and MHTML web archives. Use when the user wants to convert XPS, DOCX, XLSX, PPTX, DOC, XLS, PPT, WPS, ET, DPS, MHTML, MHT or other documents to PDF.
---

# convert-to-pdf — File to PDF Conversion

## Supported Formats

| Source Format | Tool | Description |
|---------------|------|-------------|
| XPS | PyMuPDF / Ghostscript / PowerShell | XML Paper Specification to PDF |
| DOCX, DOC | python-docx + reportlab / LibreOffice / Word COM / WPS COM | Word documents to PDF |
| XLSX, XLS | openpyxl + reportlab / LibreOffice / Excel COM / WPS COM | Excel spreadsheets to PDF |
| PPTX, PPT | python-pptx + reportlab / LibreOffice / PowerPoint COM / WPS COM | PowerPoint presentations to PDF |
| WPS | LibreOffice / WPS Writer COM | WPS Writer documents to PDF |
| ET | LibreOffice / WPS ET COM | WPS Spreadsheet files to PDF |
| DPS | LibreOffice / WPS WPP COM | WPS Presentation files to PDF |
| MHTML, MHT | Chromium headless (Edge/Chrome) / LibreOffice | Web archive to PDF |

## Prerequisites

### For XPS Conversion

Choose one of the following tools (in order of preference):

#### Option 1: Ghostscript (Recommended, cross-platform)

```bash
# Windows (via scoop)
scoop install ghostscript

# Windows (via chocolatey)
choco install ghostscript

# Linux
sudo apt install ghostscript
```

Verify: `gxps --version` or `gswin64c --version`

#### Option 2: Windows Built-in (no install needed)

Use PowerShell with `Microsoft XPS Document Writer` and `Microsoft Print to PDF` printer.

### For Office Conversion

Choose one of the following methods (in order of preference):

#### Option 1: LibreOffice (Recommended, cross-platform, best fidelity)

```bash
# Windows (via scoop)
scoop install libreoffice

# Windows (via chocolatey)
choco install libreoffice-fresh

# Linux
sudo apt install libreoffice
```

Verify: `soffice --version`

#### Option 2: Microsoft Office COM Automation (Windows only, requires MS Office installed)

Uses Word/Excel/PowerPoint COM objects via PowerShell. No extra Python packages needed.

#### Option 3: WPS Office COM Automation (Windows only, requires WPS Office installed)

Uses WPS Writer/ET/WPP COM objects via PowerShell. No extra Python packages needed.

```powershell
# Verify WPS installation (check if COM objects are available)
New-Object -ComObject Wps.Application
New-Object -ComObject Et.Application
New-Object -ComObject Wpp.Application
```

#### Option 4: Python Libraries (cross-platform, no Office needed)

```bash
pip install python-docx reportlab openpyxl python-pptx
```

> Note: Python-only conversion is a fallback with limited formatting fidelity. Prefer LibreOffice or COM when available.

### For MHTML Conversion

Choose one of the following methods (in order of preference):

#### Option 1: Microsoft Edge / Chrome (Recommended, best fidelity)

Uses Chromium `--headless --print-to-pdf` for pixel-perfect web content rendering. No extra install needed on Windows (Edge is pre-installed).

```bash
# Verify
msedge --version
# or
chrome --version
```

#### Option 2: LibreOffice (cross-platform, fallback)

```bash
soffice --headless --convert-to pdf input.mhtml
```

## Conversion Methods

### XPS to PDF

#### Method 1: Ghostscript (Recommended)

```bash
gxps -sDEVICE=pdfwrite -sOutputFile=output.pdf -dNOPAUSE -dBATCH input.xps
```

On Windows, the command may be `gxpsw64` or `gswin64c`:

```powershell
gswin64c -sDEVICE=pdfwrite -sOutputFile=output.pdf -dNOPAUSE -dBATCH input.xps
```

Key parameters:
- `-sDEVICE=pdfwrite` — output as PDF
- `-sOutputFile=<path>` — output PDF path
- `-dNOPAUSE` — don't pause between pages
- `-dBATCH` — exit after processing
- `-dPDFSETTINGS=/prepress` — high quality output (optional)
- `-r300` — set DPI to 300 for higher quality (optional)

#### Method 2: PyMuPDF (Python, cross-platform)

```bash
pip install pymupdf
python scripts/convert2pdf.py input.xps
python scripts/convert2pdf.py input.xps -o output.pdf
```

#### Method 3: PowerShell (Windows only, fallback)

Uses Windows COM automation via `Microsoft Print to PDF`.

### Office to PDF

#### Method 1: LibreOffice (Recommended)

```bash
# Single file
soffice --headless --convert-to pdf input.docx
soffice --headless --convert-to pdf input.xlsx
soffice --headless --convert-to pdf input.pptx

# Specify output directory
soffice --headless --convert-to pdf --outdir ./output input.docx

# Batch convert
soffice --headless --convert-to pdf *.docx *.xlsx *.pptx
```

On Windows, the executable may be at:
```
C:\Program Files\LibreOffice\program\soffice.exe
```

#### Method 2: Microsoft Office COM (Windows, requires MS Office)

```powershell
# Word to PDF
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$doc = $word.Documents.Open("C:\path\to\input.docx")
$doc.SaveAs([ref]"C:\path\to\output.pdf", [ref]17)
$doc.Close()
$word.Quit()

# Excel to PDF
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$wb = $excel.Workbooks.Open("C:\path\to\input.xlsx")
$wb.ExportAsFixedFormat(0, "C:\path\to\output.pdf")
$wb.Close()
$excel.Quit()

# PowerPoint to PDF
$ppt = New-Object -ComObject PowerPoint.Application
$pres = $ppt.Presentations.Open("C:\path\to\input.pptx")
$pres.SaveAs("C:\path\to\output.pdf", 32)
$pres.Close()
$ppt.Quit()
```

#### Method 3: WPS Office COM (Windows, requires WPS Office)

```powershell
# WPS Writer (.wps/.doc) to PDF
$wps = New-Object -ComObject Wps.Application
$wps.Visible = $false
$doc = $wps.Documents.Open("C:\path\to\input.wps")
$doc.ExportAsFixedFormat("C:\path\to\output.pdf", 17)
$doc.Close()
$wps.Quit()

# WPS Spreadsheet (.et/.xls) to PDF
$et = New-Object -ComObject Et.Application
$et.Visible = $false
$wb = $et.Workbooks.Open("C:\path\to\input.et")
$wb.ExportAsFixedFormat(0, "C:\path\to\output.pdf")
$wb.Close()
$et.Quit()

# WPS Presentation (.dps/.ppt) to PDF
$dps = New-Object -ComObject Wpp.Application
$pres = $dps.Presentations.Open("C:\path\to\input.dps")
$pres.SaveAs("C:\path\to\output.pdf", 32)
$pres.Close()
$dps.Quit()
```

#### Method 4: Python Script (cross-platform, fallback)

```bash
pip install python-docx reportlab openpyxl python-pptx
python scripts/convert2pdf.py input.docx
python scripts/convert2pdf.py input.xlsx -o output.pdf
python scripts/convert2pdf.py *.docx *.pptx    # batch convert
```

### MHTML to PDF

#### Method 1: Chromium Headless (Recommended)

```bash
# Microsoft Edge (pre-installed on Windows 10/11)
msedge --headless --disable-gpu --no-pdf-header-footer --print-to-pdf=output.pdf input.mhtml

# Google Chrome
chrome --headless --disable-gpu --no-pdf-header-footer --print-to-pdf=output.pdf input.mhtml
```

Key parameters:
- `--headless` — run without UI
- `--disable-gpu` — disable GPU acceleration
- `--print-to-pdf=<path>` — output PDF path
- `--no-pdf-header-footer` — remove page header/footer
- `--virtual-time-budget=5000` — wait up to 5s for rendering (optional)

#### Method 2: LibreOffice (cross-platform, fallback)

```bash
soffice --headless --convert-to pdf input.mhtml
```

## Utility Script

The helper script `scripts/convert2pdf.py` handles both XPS and Office file conversion with automatic tool detection:

```bash
# Auto-detect file type and convert
python scripts/convert2pdf.py input.xps
python scripts/convert2pdf.py input.docx
python scripts/convert2pdf.py input.xlsx
python scripts/convert2pdf.py input.pptx
python scripts/convert2pdf.py input.wps
python scripts/convert2pdf.py input.et
python scripts/convert2pdf.py input.dps
python scripts/convert2pdf.py input.mhtml

# Batch convert mixed file types
python scripts/convert2pdf.py *.xps *.docx *.xlsx *.pptx *.wps *.et *.dps *.mhtml

# Specify output path (single file only)
python scripts/convert2pdf.py input.docx -o output.pdf

# Custom DPI for XPS conversion
python scripts/convert2pdf.py input.xps -r 300
```

## Workflow

1. **Detect file type** by extension
2. **For XPS files**:
   - Try PyMuPDF → Ghostscript → PowerShell fallback
3. **For Office/WPS files (DOCX/XLSX/PPTX/WPS/ET/DPS/DOC/XLS/PPT)**:
   - Try LibreOffice (`soffice`) → WPS Office COM (Windows) → MS Office COM (Windows) → Python libraries fallback
4. **For MHTML files**:
   - Try Chromium headless (Edge/Chrome) → LibreOffice fallback
5. **Verify** the output PDF exists and is non-empty
6. **Report** the result to the user with the output file path

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `gxps: command not found` | Ghostscript not installed | Install Ghostscript or use PyMuPDF |
| `soffice: command not found` | LibreOffice not installed | Install LibreOffice or use COM/Python |
| `Error: /invalidfileaccess` | File permission issue | Check file read permissions |
| Empty output PDF | Corrupted source file | Verify source file is valid |
| COM error | MS Office / WPS Office not installed | Install Office, WPS, or use LibreOffice |
| WPS COM object not found | WPS Office not installed or COM not registered | Install WPS Office or use LibreOffice |
| Chromium not found | Edge/Chrome not installed | Install Edge/Chrome or use LibreOffice |
| Chromium timeout | Complex MHTML rendering | Increase `--virtual-time-budget` or use LibreOffice |
| Formatting issues (Python fallback) | Limited rendering | Use LibreOffice or COM instead |
