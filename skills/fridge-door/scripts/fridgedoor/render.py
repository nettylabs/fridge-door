"""Write a printable as PDF and/or HTML (the approach from Job to Paid).

Engines:
  builtin  the pure-Python PDF in pdf.py (default; the same everywhere; Western European text)
  browser  the HTML printed by a Chrome, Chromium or Edge that's already installed (any language)
  auto     builtin, unless the text has characters it can't show and a browser is installed
Emoji are left out of the built-in PDF (its fonts have none); the HTML keeps them.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

from . import pdf
from .util import ToolError

_BROWSERS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "microsoft-edge",
             "microsoft-edge-stable", "msedge")  # fmt: skip
_FIXED_PATHS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
)


def find_browser() -> str | None:
    env = os.environ.get("FRIDGE_BROWSER")
    if env and Path(env).exists():
        return env
    for name in _BROWSERS:
        found = shutil.which(name)
        if found:
            return found
    for path in _FIXED_PATHS:
        if Path(path).exists():
            return path
    return None


def pdf_text(text) -> str:
    """Text the built-in fonts can draw: emoji and other symbols removed, spaces tidied."""
    out = []
    for char in str(text or ""):
        if unicodedata.category(char) in ("So", "Cs", "Co") or char in "\ufe0f\u200d":
            continue
        out.append(char)
    return re.sub(r"\s{2,}", " ", "".join(out)).strip()


def needs_browser(strings) -> bool:
    return not all(pdf.encodable(pdf_text(s)) for s in strings if s)


def browser_pdf(html_text: str, pdf_path: Path, browser: str, landscape: bool = False) -> None:
    if landscape:  # a browser prints the page the way its CSS asks: the fridge sheet is landscape
        html_text = html_text.replace("</head>", "<style>@page { size: landscape; }</style></head>", 1)
    with tempfile.TemporaryDirectory(prefix="fridge-") as tmp:
        html_file = Path(tmp) / "page.html"
        html_file.write_text(html_text, encoding="utf-8")
        base = [browser, "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                "--disable-background-networking", "--disable-sync", f"--user-data-dir={Path(tmp) / 'profile'}",
                "--no-pdf-header-footer", "--print-to-pdf-no-header", f"--print-to-pdf={pdf_path}"]  # fmt: skip
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            base.append("--no-sandbox")  # browsers refuse to start as root without it
        last_error = ""
        for headless in ("--headless=new", "--headless"):
            if pdf_path.exists():
                pdf_path.unlink()
            try:
                result = subprocess.run(base[:1] + [headless] + base[1:] + [html_file.as_uri()], capture_output=True,
                                        text=True, timeout=90)  # fmt: skip
                last_error = (result.stderr or "")[-400:]
            except (OSError, subprocess.TimeoutExpired) as exc:
                last_error = str(exc)
                continue
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                return
        raise ToolError("The browser couldn't print the PDF.", hint=last_error.strip() or "Use --format html.",
                        code="browser_failed")  # fmt: skip


def write(out_dir: Path, name: str, fmt: str, build_pdf, html_text: str, strings, landscape: bool = False,
          engine: str = "auto") -> dict:  # fmt: skip
    """Write <name>.pdf and/or <name>.html. build_pdf(path) draws the built-in PDF."""
    if fmt not in ("pdf", "html", "both"):
        raise ToolError(f"{fmt!r} isn't a format.", hint="Use pdf, html or both.", code="usage")
    files, notes = [], []
    if fmt in ("html", "both"):
        path = out_dir / f"{name}.html"
        path.write_text(html_text, encoding="utf-8")
        files.append(str(path))
    if fmt in ("pdf", "both"):
        path = out_dir / f"{name}.pdf"
        use_browser = engine == "browser" or (engine == "auto" and needs_browser(strings))
        browser = find_browser() if use_browser else None
        if use_browser and browser:
            browser_pdf(html_text, path, browser, landscape)
        else:
            if use_browser:
                notes.append("Some text uses letters the built-in PDF can't show and no browser is installed: the "
                             "HTML version shows everything.")  # fmt: skip
            build_pdf(path)
        files.append(str(path))
    return {"files": files, "notes": notes}
