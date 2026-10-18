"""A small, dependency-free PDF writer, reused from Job to Paid (Netty Labs' first plugin).

Uses the PDF standard Helvetica fonts (no font files needed) with Windows-1252 text, which covers English and
most Western European languages. For other scripts, render.py switches to the HTML + browser route. The page
layouts for Fridge Door's printables are in printables.py.
"""

from __future__ import annotations

import datetime as _dt
import re
import struct
import unicodedata
import zlib
from pathlib import Path

# ---------------------------------------------------------------- metrics

_HELV_ASCII = [
    278,
    278,
    355,
    556,
    556,
    889,
    667,
    191,
    333,
    333,
    389,
    584,
    278,
    333,
    278,
    278,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    278,
    278,
    584,
    584,
    584,
    556,
    1015,
    667,
    667,
    722,
    722,
    667,
    611,
    778,
    722,
    278,
    500,
    667,
    556,
    833,
    722,
    778,
    667,
    778,
    722,
    667,
    611,
    722,
    667,
    944,
    667,
    667,
    611,
    278,
    278,
    278,
    469,
    556,
    333,
    556,
    556,
    500,
    556,
    556,
    278,
    556,
    556,
    222,
    222,
    500,
    222,
    833,
    556,
    556,
    556,
    556,
    333,
    500,
    278,
    556,
    500,
    722,
    500,
    500,
    500,
    334,
    260,
    334,
    584,
]
_BOLD_ASCII = [
    278,
    333,
    474,
    556,
    556,
    889,
    722,
    238,
    333,
    333,
    389,
    584,
    278,
    333,
    278,
    278,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    333,
    333,
    584,
    584,
    584,
    611,
    975,
    722,
    722,
    722,
    722,
    667,
    611,
    778,
    722,
    278,
    556,
    722,
    611,
    833,
    722,
    778,
    667,
    778,
    722,
    667,
    611,
    722,
    667,
    944,
    667,
    667,
    611,
    333,
    278,
    333,
    584,
    556,
    333,
    556,
    611,
    556,
    611,
    556,
    333,
    611,
    611,
    278,
    278,
    556,
    278,
    889,
    611,
    611,
    611,
    611,
    389,
    556,
    333,
    611,
    556,
    778,
    556,
    556,
    500,
    389,
    280,
    389,
    584,
]
_HELV_HIGH = [
    556,
    556,
    222,
    556,
    333,
    1000,
    556,
    556,
    333,
    1000,
    667,
    333,
    1000,
    556,
    611,
    556,
    556,
    222,
    222,
    333,
    333,
    350,
    556,
    1000,
    333,
    1000,
    500,
    333,
    944,
    556,
    500,
    667,
    278,
    333,
    556,
    556,
    556,
    556,
    260,
    556,
    333,
    737,
    370,
    556,
    584,
    333,
    737,
    333,
    400,
    584,
    333,
    333,
    333,
    556,
    537,
    278,
    333,
    333,
    365,
    556,
    834,
    834,
    834,
    611,
    667,
    667,
    667,
    667,
    667,
    667,
    1000,
    722,
    667,
    667,
    667,
    667,
    278,
    278,
    278,
    278,
    722,
    722,
    778,
    778,
    778,
    778,
    778,
    584,
    778,
    722,
    722,
    722,
    722,
    667,
    667,
    611,
    556,
    556,
    556,
    556,
    556,
    556,
    889,
    500,
    556,
    556,
    556,
    556,
    278,
    278,
    278,
    278,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    584,
    611,
    556,
    556,
    556,
    556,
    500,
    556,
    500,
]
_BOLD_HIGH = [
    556,
    556,
    278,
    556,
    500,
    1000,
    556,
    556,
    333,
    1000,
    667,
    333,
    1000,
    556,
    611,
    556,
    556,
    278,
    278,
    500,
    500,
    350,
    556,
    1000,
    333,
    1000,
    556,
    333,
    944,
    556,
    500,
    667,
    278,
    333,
    556,
    556,
    556,
    556,
    280,
    556,
    333,
    737,
    370,
    556,
    584,
    333,
    737,
    333,
    400,
    584,
    333,
    333,
    333,
    611,
    556,
    278,
    333,
    333,
    365,
    556,
    834,
    834,
    834,
    611,
    722,
    722,
    722,
    722,
    722,
    722,
    1000,
    722,
    667,
    667,
    667,
    667,
    278,
    278,
    278,
    278,
    722,
    722,
    778,
    778,
    778,
    778,
    778,
    584,
    778,
    722,
    722,
    722,
    722,
    667,
    667,
    611,
    556,
    556,
    556,
    556,
    556,
    556,
    889,
    556,
    556,
    556,
    556,
    556,
    278,
    278,
    278,
    278,
    611,
    611,
    611,
    611,
    611,
    611,
    611,
    584,
    611,
    611,
    611,
    611,
    611,
    556,
    611,
    556,
]
WIDTHS = {"F1": _HELV_ASCII, "F2": _BOLD_ASCII, "F3": _HELV_ASCII}
HIGH = {"F1": _HELV_HIGH, "F2": _BOLD_HIGH, "F3": _HELV_HIGH}
FONT_NAMES = {"F1": "Helvetica", "F2": "Helvetica-Bold", "F3": "Helvetica-Oblique"}

_REPLACEMENTS = {
    "−": "-",
    "‐": "-",
    "‑": "-",
    " ": " ",
    " ": " ",
    " ": " ",
    "→": "->",
    "≤": "<=",
    "≥": ">=",
    "✓": "v",
    "×": "x",
}


def encodable(text: str) -> bool:
    try:
        _prepare(text).encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def _prepare(text: str) -> str:
    return "".join(_REPLACEMENTS.get(ch, ch) for ch in str(text))


def to_cp1252(text: str) -> bytes:
    out = bytearray()
    for ch in _prepare(text):
        try:
            out += ch.encode("cp1252")
        except UnicodeEncodeError:
            base = unicodedata.normalize("NFKD", ch).encode("cp1252", "ignore")
            out += base or b"?"
    return bytes(out)


def text_width(text: str, font: str, size: float) -> float:
    total = 0
    low, high = WIDTHS[font], HIGH[font]
    for byte in to_cp1252(text):
        if 32 <= byte <= 126:
            total += low[byte - 32]
        elif byte >= 128:
            total += high[byte - 128]
        else:
            total += 278
    return total * size / 1000.0


def wrap(text: str, font: str, size: float, max_width: float) -> list:
    lines = []
    for para in str(text or "").split("\n"):
        words = para.split()
        if not words:
            lines.append("")
            continue
        current = ""
        for word in words:
            candidate = f"{current} {word}" if current else word
            if text_width(candidate, font, size) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            while text_width(word, font, size) > max_width and len(word) > 1:
                cut = len(word)
                while cut > 1 and text_width(word[:cut], font, size) > max_width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        lines.append(current)
    return lines


def _escape(data: bytes) -> str:
    out = []
    for byte in data:
        if byte in (0x28, 0x29, 0x5C):
            out.append("\\" + chr(byte))
        elif 32 <= byte <= 126:
            out.append(chr(byte))
        else:
            out.append("\\%03o" % byte)
    return "".join(out)


def _rgb(color) -> tuple:
    if isinstance(color, tuple):
        return color
    text = str(color or "#000000").lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", text):
        text = "0F766E"
    return tuple(int(text[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def tint(color, amount: float) -> tuple:
    r, g, b = _rgb(color)
    return (r + (1 - r) * amount, g + (1 - g) * amount, b + (1 - b) * amount)


def _num(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


# ----------------------------------------------------------------- images


class ImageError(Exception):
    pass


def _jpeg_info(data: bytes) -> tuple:
    if data[:2] != b"\xff\xd8":
        raise ImageError("not a JPEG")
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            raise ImageError("bad JPEG marker")
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            components = data[i + 9]
            return width, height, components
        i += 2 + length
    raise ImageError("JPEG size not found")


def _png_decode(data: bytes) -> tuple:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ImageError("not a PNG")
    pos = 8
    width = height = depth = ctype = interlace = None
    palette = b""
    trns = b""
    idat = bytearray()
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        kind = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
        elif kind == b"PLTE":
            palette = chunk
        elif kind == b"tRNS":
            trns = chunk
        elif kind == b"IDAT":
            idat += chunk
        elif kind == b"IEND":
            break
    if interlace:
        raise ImageError("interlaced PNGs are not supported; save the logo as a normal PNG or JPEG")
    if ctype not in (0, 2, 3, 4, 6) or depth not in (1, 2, 4, 8, 16):
        raise ImageError("unsupported PNG type")
    raw = zlib.decompress(bytes(idat))
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    bits_pp = channels * depth
    stride = (width * bits_pp + 7) // 8
    bpp = max(1, bits_pp // 8)
    rows = []
    prev = bytearray(stride)
    i = 0
    for _ in range(height):
        ftype = raw[i]
        line = bytearray(raw[i + 1 : i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if ftype == 1:
                line[x] = (line[x] + a) & 0xFF
            elif ftype == 2:
                line[x] = (line[x] + b) & 0xFF
            elif ftype == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 0xFF
            elif ftype == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[x] = (line[x] + pred) & 0xFF
        rows.append(line)
        prev = line
    out = bytearray()
    for line in rows:
        if depth < 8:
            samples = []
            per_byte = 8 // depth
            mask = (1 << depth) - 1
            for byte in line:
                for k in range(per_byte):
                    samples.append((byte >> (8 - depth * (k + 1))) & mask)
            samples = samples[:width]
        elif depth == 16:
            samples = list(line[0::2])
        else:
            samples = list(line)
        for x in range(width):
            if ctype == 3:
                idx = samples[x]
                r, g, b = palette[idx * 3 : idx * 3 + 3]
                alpha = trns[idx] if idx < len(trns) else 255
            elif ctype == 0:
                v = samples[x] * (255 // ((1 << depth) - 1)) if depth < 8 else samples[x]
                r = g = b = v
                alpha = 255
            elif ctype == 4:
                r = g = b = samples[x * 2]
                alpha = samples[x * 2 + 1]
            elif ctype == 2:
                r, g, b = samples[x * 3 : x * 3 + 3]
                alpha = 255
            else:
                r, g, b, alpha = samples[x * 4 : x * 4 + 4]
            if alpha < 255:
                r = (r * alpha + 255 * (255 - alpha)) // 255
                g = (g * alpha + 255 * (255 - alpha)) // 255
                b = (b * alpha + 255 * (255 - alpha)) // 255
            out += bytes((r, g, b))
    return width, height, bytes(out)


def load_image(path: str):
    """Returns (width, height, pdf_dict_extra, stream_bytes) or raises ImageError."""
    data = Path(path).expanduser().read_bytes()
    if data[:2] == b"\xff\xd8":
        width, height, components = _jpeg_info(data)
        space = {1: "/DeviceGray", 3: "/DeviceRGB"}.get(components)
        if not space:
            raise ImageError("CMYK JPEGs are not supported; save the logo as RGB")
        return width, height, f"/ColorSpace {space} /BitsPerComponent 8 /Filter /DCTDecode", data
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        width, height, rgb = _png_decode(data)
        return width, height, "/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode", zlib.compress(rgb, 9)
    raise ImageError("logo must be a PNG or JPEG for the built-in PDF (SVG works in the HTML version)")


# ------------------------------------------------------------- the writer


class PDF:
    def __init__(self, width: float, height: float, title: str = ""):
        self.width = width
        self.height = height
        self.title = title
        self.pages = []
        self.images = {}

    def new_page(self):
        page = {"ops": [], "links": []}
        self.pages.append(page)
        return page

    def add_image(self, name: str, path: str):
        self.images[name] = load_image(path)
        return self.images[name][:2]


class Canvas:
    """Top-left coordinates for layout code; converted to PDF space here."""

    def __init__(self, pdf: PDF):
        self.pdf = pdf
        self.page = None

    def start_page(self):
        self.page = self.pdf.new_page()

    def _y(self, top: float) -> float:
        return self.pdf.height - top

    def text(self, x, top, text, font="F1", size=10, color=(0.12, 0.13, 0.15), align="left"):
        if text is None or text == "":
            return
        width = text_width(text, font, size)
        if align == "right":
            x -= width
        elif align == "center":
            x -= width / 2
        r, g, b = _rgb(color)
        self.page["ops"].append(
            f"BT /{font} {_num(size)} Tf {_num(r)} {_num(g)} {_num(b)} rg {_num(x)} {_num(self._y(top))} Td "
            f"({_escape(to_cp1252(text))}) Tj ET"
        )

    def rotated_text(self, cx, top, text, font, size, color, angle_deg):
        import math

        rad = math.radians(angle_deg)
        cos, sin = math.cos(rad), math.sin(rad)
        width = text_width(text, font, size)
        x = cx - cos * width / 2
        y = self._y(top) - sin * width / 2
        r, g, b = _rgb(color)
        self.page["ops"].insert(
            0,
            f"BT /{font} {_num(size)} Tf {_num(r)} {_num(g)} {_num(b)} rg {_num(cos)} {_num(sin)} {_num(-sin)} "
            f"{_num(cos)} {_num(x)} {_num(y)} Tm ({_escape(to_cp1252(text))}) Tj ET",
        )

    def rect(self, x, top, w, h, fill=None, stroke=None, line_width=0.6, radius=0):
        parts = []
        if fill is not None:
            r, g, b = _rgb(fill)
            parts.append(f"{_num(r)} {_num(g)} {_num(b)} rg")
        if stroke is not None:
            r, g, b = _rgb(stroke)
            parts.append(f"{_num(r)} {_num(g)} {_num(b)} RG {_num(line_width)} w")
        bottom = self._y(top + h)
        if radius:
            k = 0.5523 * radius
            x0, y0, x1, y1 = x, bottom, x + w, bottom + h
            path = (
                f"{_num(x0 + radius)} {_num(y0)} m {_num(x1 - radius)} {_num(y0)} l "
                f"{_num(x1 - radius + k)} {_num(y0)} {_num(x1)} {_num(y0 + radius - k)} {_num(x1)} {_num(y0 + radius)} c "
                f"{_num(x1)} {_num(y1 - radius)} l "
                f"{_num(x1)} {_num(y1 - radius + k)} {_num(x1 - radius + k)} {_num(y1)} {_num(x1 - radius)} {_num(y1)} c "
                f"{_num(x0 + radius)} {_num(y1)} l "
                f"{_num(x0 + radius - k)} {_num(y1)} {_num(x0)} {_num(y1 - radius + k)} {_num(x0)} {_num(y1 - radius)} c "
                f"{_num(x0)} {_num(y0 + radius)} l "
                f"{_num(x0)} {_num(y0 + radius - k)} {_num(x0 + radius - k)} {_num(y0)} {_num(x0 + radius)} {_num(y0)} c h"
            )
        else:
            path = f"{_num(x)} {_num(bottom)} {_num(w)} {_num(h)} re"
        op = "B" if fill is not None and stroke is not None else ("f" if fill is not None else "S")
        self.page["ops"].append(" ".join(parts + [path, op]))

    def line(self, x1, top1, x2, top2, color=(0.85, 0.86, 0.88), width=0.6):
        r, g, b = _rgb(color)
        self.page["ops"].append(
            f"{_num(r)} {_num(g)} {_num(b)} RG {_num(width)} w {_num(x1)} {_num(self._y(top1))} m "
            f"{_num(x2)} {_num(self._y(top2))} l S"
        )

    def image(self, name, x, top, w, h):
        self.page["ops"].append(f"q {_num(w)} 0 0 {_num(h)} {_num(x)} {_num(self._y(top + h))} cm /{name} Do Q")

    def link(self, x, top, w, h, url):
        self.page["links"].append((x, self._y(top + h), x + w, self._y(top), url))


def write_pdf(pdf: PDF, path: Path) -> None:
    objects = []

    def add(body) -> int:
        objects.append(body)
        return len(objects)

    catalog_id = add(None)
    pages_id = add(None)
    font_ids = {}
    for key, base in FONT_NAMES.items():
        font_ids[key] = add(f"<< /Type /Font /Subtype /Type1 /BaseFont /{base} /Encoding /WinAnsiEncoding >>")
    image_ids = {}
    for name, (w, h, extra, stream) in pdf.images.items():
        header = f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} {extra} /Length {len(stream)} >>"
        image_ids[name] = add((header, stream))
    font_res = " ".join(f"/{k} {v} 0 R" for k, v in font_ids.items())
    image_res = " ".join(f"/{k} {v} 0 R" for k, v in image_ids.items())
    resources = f"<< /Font << {font_res} >>" + (f" /XObject << {image_res} >>" if image_res else "") + " >>"
    page_ids = []
    for page in pdf.pages:
        content = zlib.compress("\n".join(page["ops"]).encode("latin-1"), 9)
        content_id = add((f"<< /Length {len(content)} /Filter /FlateDecode >>", content))
        annot_ids = []
        for x1, y1, x2, y2, url in page["links"]:
            annot_ids.append(
                add(
                    f"<< /Type /Annot /Subtype /Link /Rect [{_num(x1)} {_num(y1)} {_num(x2)} {_num(y2)}] /Border [0 0 0] "
                    f"/A << /S /URI /URI ({_escape(url.encode('ascii', 'ignore'))}) >> >>"
                )
            )
        annots = f" /Annots [{' '.join(f'{a} 0 R' for a in annot_ids)}]" if annot_ids else ""
        page_ids.append(
            add(
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {_num(pdf.width)} {_num(pdf.height)}] "
                f"/Resources {resources} /Contents {content_id} 0 R{annots} >>"
            )
        )
    objects[pages_id - 1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] /Count {len(page_ids)} >>"
    )
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>"
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("D:%Y%m%d%H%M%SZ")
    info_id = add(f"<< /Title ({_escape(to_cp1252(pdf.title))}) /Producer (Fridge Door) /CreationDate ({stamp}) >>")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode()
        if isinstance(body, tuple):
            out += body[0].encode("latin-1") + b"\nstream\n" + body[1] + b"\nendstream"
        else:
            out += body.encode("latin-1")
        out += b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R /Info {info_id} 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(out))


# ------------------------------------------------------------------ layout

PAPER = {"letter": (612.0, 792.0), "a4": (595.28, 841.89)}
INK = (0.11, 0.12, 0.14)
MUTED = (0.42, 0.44, 0.48)
RULE = (0.86, 0.87, 0.89)
