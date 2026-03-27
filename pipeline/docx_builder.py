"""
Step 4: Assemble .docx by filling the IV_template.docx with content.

Strategy: copy the template (which carries the logo, header, footer, styles, and
numbering), then replace document.xml body content with generated paragraphs while
preserving the sectPr (page layout, header/footer references).
"""

import io
import re
import zipfile
from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent.parent / "template" / "IV_template.docx"

# Read template once at module load — avoids repeated disk I/O on every request
_TEMPLATE_BYTES: bytes = TEMPLATE_PATH.read_bytes()

def _load_sect_pr() -> str:
    with zipfile.ZipFile(io.BytesIO(_TEMPLATE_BYTES), "r") as zf:
        raw = zf.read("word/document.xml").decode("utf-8")
    m = re.search(r"<w:sectPr[\s\S]*?</w:sectPr>", raw)
    if not m:
        raise RuntimeError("Could not find sectPr in template document.xml")
    return m.group(0)

_CACHED_SECT_PR: str = _load_sect_pr()

# ── XML namespace block copied from template's document.xml root ─────────────
_NS = (
    'xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" '
    'xmlns:cx="http://schemas.microsoft.com/office/drawing/2014/chartex" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:o="urn:schemas-microsoft-com:office:office" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
    'xmlns:v="urn:schemas-microsoft-com:vml" '
    'xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:w10="urn:schemas-microsoft-com:office:word" '
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
    'xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml" '
    'xmlns:w16="http://schemas.microsoft.com/office/word/2018/wordml" '
    'xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    'mc:Ignorable="w14 w15 w16 wp14"'
)

NOTES_SECTIONS = [
    "Key Themes",
    "Notable Quotes",
    "IVD Platform & Competitive Landscape",
    "Workflow & Utilization Patterns",
    "Reimbursement & Coding",
    "Forward-Looking Signals",
]


# ── Public entry points ───────────────────────────────────────────────────────

def build_transcript_docx(payload: dict, output_path: Path) -> None:
    """
    Build a transcript-only .docx: header block + horizontal rule + cleaned turns.
    payload keys: header (dict), transcript (list of {speaker, text})
    """
    sectPr = _extract_sectPr()
    body_paragraphs = _build_transcript_body(payload, sectPr)
    new_doc_xml = _wrap_document(body_paragraphs)
    _write_docx(new_doc_xml, output_path)


def build_notes_docx(payload: dict, output_path: Path) -> None:
    """
    Build a notes-only .docx: header block + horizontal rule + 6 notes sections.
    payload keys: header (dict), notes (dict: section -> list of strings)
    """
    sectPr = _extract_sectPr()
    body_paragraphs = _build_notes_body(payload, sectPr)
    new_doc_xml = _wrap_document(body_paragraphs)
    _write_docx(new_doc_xml, output_path)


# ── sectPr extraction ─────────────────────────────────────────────────────────

def _extract_sectPr() -> str:
    """Return the cached sectPr block from the template."""
    return _CACHED_SECT_PR


# ── Body assembly ─────────────────────────────────────────────────────────────

def _header_block(h: dict) -> list[str]:
    return [
        _header_para("Interview Subject:", "IVD Sequencing Landscape"),
        _header_para("Interview Date:", h["date"]),
        _header_para("Interviewee Demographics:", f"{h['role']}, {h['setting']}, {h['location']}"),
        _HRULE,
        _blank_para(),
    ]


def _build_transcript_body(payload: dict, sectPr: str) -> str:
    parts = _header_block(payload["header"])

    for turn in payload["transcript"]:
        parts.append(_transcript_para(turn["speaker"], turn["text"]))
        parts.append(_blank_para())

    parts.append(sectPr)
    return "\n".join(parts)


def _build_notes_body(payload: dict, sectPr: str) -> str:
    parts = _header_block(payload["header"])
    parts.append(_notes_title())

    notes = payload["notes"]
    for section in NOTES_SECTIONS:
        items = notes.get(section, [])
        parts.append(_section_heading(section))
        if not items:
            parts.append(_italic_para("(No content)"))
        else:
            for item in items:
                if item.startswith('"') or item.startswith("\u201c"):
                    parts.append(_quote_para(item))
                else:
                    parts.append(_bullet_para(item))

    parts.append(sectPr)
    return "\n".join(parts)


def _wrap_document(body_content: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<w:document {_NS}>\n'
        '  <w:body>\n'
        f'{body_content}\n'
        '  </w:body>\n'
        '</w:document>'
    )


# ── Zip assembly ──────────────────────────────────────────────────────────────

def _write_docx(new_doc_xml: str, output_path: Path) -> None:
    """Build output docx entirely in memory — no temp files, single zip pass."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc_xml_bytes = new_doc_xml.encode("utf-8")
    out_buf = io.BytesIO()

    with zipfile.ZipFile(io.BytesIO(_TEMPLATE_BYTES), "r") as zf_src:
        with zipfile.ZipFile(out_buf, "w") as zf_out:
            for item in zf_src.infolist():
                if item.filename == "word/document.xml":
                    zf_out.writestr(item, doc_xml_bytes)
                else:
                    zf_out.writestr(item, zf_src.read(item.filename))

    output_path.write_bytes(out_buf.getvalue())


# ── Paragraph XML builders ────────────────────────────────────────────────────

def _x(text: str) -> str:
    """XML-escape a string."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


_RFonts = '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
_Sz = '<w:sz w:val="22"/><w:szCs w:val="22"/>'
_SzSm = '<w:sz w:val="20"/><w:szCs w:val="20"/>'
_SzLg = '<w:sz w:val="28"/><w:szCs w:val="28"/>'
_Line360 = '<w:spacing w:line="360" w:lineRule="auto"/>'
_Bold = '<w:b/><w:bCs/>'


def _run(text: str, bold=False, italic=False, sz=_Sz, color=None) -> str:
    color_tag = f'<w:color w:val="{color}"/>' if color else ""
    bold_tag = _Bold if bold else ""
    italic_tag = "<w:i/><w:iCs/>" if italic else ""
    space = ' xml:space="preserve"' if text.startswith(" ") or text.endswith(" ") else ""
    return (
        f"    <w:r>\n"
        f"      <w:rPr>{_RFonts}{bold_tag}{italic_tag}{sz}{color_tag}</w:rPr>\n"
        f"      <w:t{space}>{_x(text)}</w:t>\n"
        f"    </w:r>"
    )


def _para(ppr_inner: str, runs: list[str]) -> str:
    runs_xml = "\n".join(runs)
    return (
        f"  <w:p>\n"
        f"    <w:pPr>{ppr_inner}</w:pPr>\n"
        f"{runs_xml}\n"
        f"  </w:p>"
    )


def _header_para(label: str, value: str) -> str:
    ppr = f"{_Line360}<w:rPr>{_RFonts}{_Sz}</w:rPr>"
    return _para(ppr, [
        _run(label + " ", bold=True),
        _run(value),
    ])


def _blank_para() -> str:
    ppr = f"{_Line360}<w:rPr>{_RFonts}{_Sz}</w:rPr>"
    return _para(ppr, [])


def _transcript_para(speaker: str, text: str) -> str:
    ppr = f"{_Line360}<w:rPr>{_RFonts}{_Sz}</w:rPr>"
    return _para(ppr, [
        _run(speaker + ": ", bold=True),
        _run(text),
    ])


def _page_break() -> str:
    ppr = f"<w:rPr>{_RFonts}{_Sz}</w:rPr>"
    return (
        "  <w:p>\n"
        f"    <w:pPr>{ppr}</w:pPr>\n"
        "    <w:r>\n"
        f"      <w:rPr>{_RFonts}{_Sz}</w:rPr>\n"
        '      <w:br w:type="page"/>\n'
        "    </w:r>\n"
        "  </w:p>"
    )


def _notes_title() -> str:
    ppr = (
        '<w:spacing w:before="0" w:after="120" w:line="360" w:lineRule="auto"/>'
        f"<w:rPr>{_RFonts}{_Bold}{_SzLg}</w:rPr>"
    )
    return _para(ppr, [_run("INTERVIEW NOTES", bold=True, sz=_SzLg)])


def _section_heading(text: str) -> str:
    ppr = (
        '<w:spacing w:before="240" w:after="60" w:line="360" w:lineRule="auto"/>'
        f"<w:rPr>{_RFonts}{_Bold}{_Sz}</w:rPr>"
    )
    return _para(ppr, [_run(text, bold=True)])


def _bullet_para(text: str) -> str:
    ppr = (
        "<w:numPr><w:ilvl w:val=\"0\"/><w:numId w:val=\"6\"/></w:numPr>"
        f"{_Line360}"
        "<w:ind w:left=\"720\" w:hanging=\"360\"/>"
        f"<w:rPr>{_RFonts}{_Sz}</w:rPr>"
    )
    return _para(ppr, [_run(text)])


def _quote_para(text: str) -> str:
    """Italic, indented, slightly smaller — supporting quote under a bullet."""
    ppr = (
        '<w:spacing w:before="0" w:after="80" w:line="276" w:lineRule="auto"/>'
        "<w:ind w:left=\"864\"/>"
        f"<w:rPr>{_RFonts}<w:i/><w:iCs/>{_SzSm}<w:color w:val=\"595959\"/></w:rPr>"
    )
    return _para(ppr, [_run(text, italic=True, sz=_SzSm, color="595959")])


def _italic_para(text: str) -> str:
    ppr = f"{_Line360}<w:rPr>{_RFonts}<w:i/><w:iCs/>{_Sz}</w:rPr>"
    return _para(ppr, [_run(text, italic=True)])


# Horizontal rule paragraph (preserved from template verbatim)
_HRULE = """\
  <w:p>
    <w:pPr>
      <w:spacing w:line="360" w:lineRule="auto"/>
      <w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr>
    </w:pPr>
    <w:r>
      <w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr>
      <w:pict><v:rect style="width:0;height:1.5pt" o:hralign="center" o:hrstd="t" o:hr="t" fillcolor="#a0a0a0" stroked="f"/></w:pict>
    </w:r>
  </w:p>"""
