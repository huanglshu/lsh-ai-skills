---
name: markdown-converter
description: "Markdown conversion: PDF, Office, HTML, data, OCR, audio, ZIP, YouTube."
---

# Markdown Converter

Convert files to Markdown using `uvx --from "markitdown[all]" markitdown` — no installation required.

## Output Layout

Unless the user explicitly requests another location, save the generated
Markdown next to the source file. Use the source filename without its final
extension as the output basename.

If the conversion produces auxiliary files, create one directory beside the
source file whose name is exactly the source filename without its final
extension, then place all auxiliary files inside it. Preserve the source
basename character for character, including spaces, Chinese characters,
Unicode punctuation, and letter case. Do not transliterate, translate, slugify,
or append suffixes such as `-images` or `-assets`.

For example, `IPS（管理后台）用户手册.doc` must produce this layout:

```text
source-directory/
├── IPS（管理后台）用户手册.doc
├── IPS（管理后台）用户手册.md
└── IPS（管理后台）用户手册/
    ├── image_1.png
    ├── image_2.png
    ├── pdf_1.pdf
    └── pdf_2.pdf
```

- Name images as `image_{序号}` and keep their original extension, such as
  `image_1.png` or `image_2.jpg`.
- Name extracted PDF attachments as `pdf_{序号}.pdf`, such as `pdf_1.pdf`.
- Start numbering at `1` and number each attachment type independently.
- Reference auxiliary files from the Markdown with paths relative to the
  Markdown file, such as `./report/image_1.png` and `./report/pdf_1.pdf`.
  URL-encode spaces and reserved URL characters when the Markdown renderer
  requires it; keep the on-disk directory name unchanged.
- Do not create the auxiliary directory when there are no auxiliary files.
- Reuse the auxiliary directory when it already belongs to this conversion.
  Do not overwrite unrelated existing files; use the next available sequence
  number when a name is taken.

## Verify Attachments

After conversion, verify that every referenced attachment renders correctly
before reporting success. A filename being present on disk is not enough.

1. Parse the Markdown image and file references. Resolve each relative path
   against the Markdown file's directory, then confirm that the target exists
   and is a file.
2. Open the Markdown in a renderer that supports local relative images. Confirm
   that every image loads at its referenced location without a broken-image
   placeholder or link-to-itself fallback.
3. Open each PDF reference or inspect the rendered link, and confirm that it
   resolves to the intended local PDF.
4. If an attachment is missing or broken, fix the path, restore the attachment
   under the required name, or regenerate the Markdown, then repeat the check.
5. If the environment cannot render local attachments, perform the path and
   file checks, report the rendering check as incomplete, and state why.

## Basic Usage

```bash
# Convert to stdout
uvx --from "markitdown[all]" markitdown input.pdf

# Save to file
uvx --from "markitdown[all]" markitdown input.pdf -o input.md
uvx --from "markitdown[all]" markitdown input.docx > input.md

# From stdin
cat input.pdf | uvx --from "markitdown[all]" markitdown
```

## Supported Formats

- **Documents**: PDF, Word (.docx), PowerPoint (.pptx), Excel (.xlsx, .xls)
- **Web/Data**: HTML, CSV, JSON, XML
- **Media**: Images (EXIF + OCR), Audio (EXIF + transcription)
- **Other**: ZIP (iterates contents), YouTube URLs, EPub

## Options

```bash
-o OUTPUT      # Output file
-x EXTENSION   # Hint file extension (for stdin)
-m MIME_TYPE   # Hint MIME type
-c CHARSET     # Hint charset (e.g., UTF-8)
-d             # Use Azure Document Intelligence
-e ENDPOINT    # Document Intelligence endpoint
--use-plugins  # Enable 3rd-party plugins
--list-plugins # Show installed plugins
```

## Examples

```bash
# Convert Word document
uvx --from "markitdown[all]" markitdown report.docx -o report.md

# Convert Excel spreadsheet
uvx --from "markitdown[all]" markitdown data.xlsx > data.md

# Convert PowerPoint presentation
uvx --from "markitdown[all]" markitdown slides.pptx -o slides.md

# Convert with file type hint (for stdin)
cat document | uvx --from "markitdown[all]" markitdown -x .pdf > output.md

# Use Azure Document Intelligence for better PDF extraction
uvx --from "markitdown[all]" markitdown scan.pdf -d -e "https://your-resource.cognitiveservices.azure.com/"
```

## Notes

- Output preserves document structure: headings, tables, lists, links
- First run caches dependencies; subsequent runs are faster
- For complex PDFs with poor extraction, use `-d` with Azure Document Intelligence
- If automatic charset detection picks the wrong encoding for a text file, pass `-c UTF-8` (or the known charset)
