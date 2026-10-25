"""Markdown -> HTML (pandoc) -> PDF (headless Chrome). Usage: python tools/md2pdf.py file.md [file2.md ...]"""
import subprocess, sys
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CSS = """
body { font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #0b0b0b;
       max-width: 860px; margin: 28px auto; padding: 0 24px; }
h1 { font-size: 19pt; margin: 0 0 10px; } h2 { font-size: 14pt; margin: 22px 0 8px; border-bottom: 1px solid #e1e0d9; padding-bottom: 4px; }
table { border-collapse: collapse; margin: 8px 0 14px; font-size: 9.5pt; width: 100%; }
th, td { border: 1px solid #d9d8d2; padding: 5px 8px; text-align: left; vertical-align: top; }
th { background: #f1f0eb; } td:nth-child(n+2), th:nth-child(n+2) { white-space: nowrap; }
td:nth-child(2), td:nth-child(3), td:nth-child(4) { white-space: normal; }
code { font-family: Menlo, monospace; font-size: 9pt; background: #f1f0eb; padding: 1px 4px; border-radius: 3px; }
img { max-width: 100%; display: block; margin: 12px auto; page-break-inside: avoid; }
hr { border: 0; border-top: 1px solid #e1e0d9; margin: 18px 0; }
ul, ol { padding-left: 22px; } li { margin: 3px 0; } p { margin: 7px 0; }
@page { size: A4; margin: 16mm 14mm; }
"""
for md in sys.argv[1:]:
    md = Path(md).resolve()
    html = md.with_suffix(".html"); pdf = md.with_suffix(".pdf"); css = md.parent / "_print.css"
    css.write_text(CSS)
    subprocess.run(["pandoc", str(md), "-f", "gfm", "-t", "html5", "-s", "--metadata", f"title={md.stem}",
                    "--css", css.name, "-o", str(html)], check=True)
    # strip pandoc's auto title block so the markdown's own H1 is the only title
    t = html.read_text(); t = t.replace(f'<h1 class="title">{md.stem}</h1>', ''); html.write_text(t)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-margins",
                    f"--print-to-pdf={pdf}", f"file://{html}"], check=True, capture_output=True)
    html.unlink(); css.unlink()
    print(f"{pdf.relative_to(Path.cwd())}  ({pdf.stat().st_size // 1024} KB)")
