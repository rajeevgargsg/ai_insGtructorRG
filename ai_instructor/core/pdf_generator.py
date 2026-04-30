"""
PDF generation using ReportLab.
Converts markdown-formatted lesson artefacts into styled A4 PDFs.
"""

import os
import re
import time
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import GenerationConfig, LessonArtifacts

NAVY   = colors.HexColor("#1B2A47")
TEAL   = colors.HexColor("#00897B")
LTEAL  = colors.HexColor("#B2DFDB")
GREY   = colors.HexColor("#F4F6F8")
DKGREY = colors.HexColor("#455A64")


def _build_styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"],
            textColor=NAVY, fontSize=22, spaceAfter=6,
            fontName="Helvetica-Bold", alignment=1,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base["Normal"],
            textColor=TEAL, fontSize=13, spaceAfter=4,
            fontName="Helvetica-Bold", alignment=1,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"],
            textColor=NAVY, fontSize=15, spaceAfter=5,
            fontName="Helvetica-Bold",
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"],
            textColor=TEAL, fontSize=12, spaceAfter=4,
            spaceBefore=8, fontName="Helvetica-Bold",
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"],
            textColor=DKGREY, fontSize=10.5, spaceAfter=3,
            fontName="Helvetica-BoldOblique",
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontSize=9.5, leading=14, spaceAfter=3,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"],
            fontSize=9.5, leading=13, leftIndent=16,
            bulletIndent=4, spaceAfter=2,
        ),
        "meta": ParagraphStyle(
            "meta", parent=base["Normal"],
            fontSize=8.5, textColor=DKGREY, spaceAfter=2,
        ),
    }


def _safe_html(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*",     r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`",       r"<font name='Courier'>\1</font>", text)
    return text


def _md_to_flowables(text: str, styles: dict) -> list:
    flowables = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        s    = line.strip()

        if not s:
            flowables.append(Spacer(1, 4))
        elif s.startswith("#### ") or s.startswith("### "):
            prefix = "#### " if s.startswith("#### ") else "### "
            flowables.append(Paragraph(_safe_html(s[len(prefix):]), styles["h3"]))
        elif s.startswith("## "):
            flowables.append(Spacer(1, 6))
            flowables.append(Paragraph(_safe_html(s[3:]), styles["h2"]))
        elif s.startswith("# "):
            flowables.append(Spacer(1, 10))
            flowables.append(Paragraph(_safe_html(s[2:]), styles["h1"]))
            flowables.append(HRFlowable(width="100%", color=TEAL, thickness=1.2, spaceAfter=4))
        elif s.startswith(("- ", "• ", "* ")):
            flowables.append(Paragraph("• " + _safe_html(s[2:]), styles["bullet"]))
        elif re.match(r"^\d+\.", s):
            parts = s.split(".", 1)
            text_part = parts[1].strip() if len(parts) > 1 else s
            flowables.append(Paragraph(f"{parts[0]}. {_safe_html(text_part)}", styles["bullet"]))
        elif s.startswith("---") or s.startswith("==="):
            flowables.append(HRFlowable(width="100%", color=colors.lightgrey, thickness=0.5))
        elif s.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            i -= 1
            rows = []
            for tl in table_lines:
                if re.match(r"^\|[-| :]+\|$", tl.strip()):
                    continue
                cells = [c.strip() for c in tl.strip().strip("|").split("|")]
                rows.append(cells)
            if rows:
                col_count = max(len(r) for r in rows)
                rows = [r + [""] * (col_count - len(r)) for r in rows]
                col_width = (A4[0] - 5 * cm) / col_count
                tbl = Table(rows, colWidths=[col_width] * col_count)
                tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), LTEAL),
                    ("TEXTCOLOR",  (0, 0), (-1, 0), NAVY),
                    ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
                    ("GRID",       (0, 0), (-1, -1), 0.4, colors.lightgrey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GREY]),
                    ("VALIGN",     (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ]))
                flowables.append(Spacer(1, 4))
                flowables.append(tbl)
                flowables.append(Spacer(1, 6))
        else:
            flowables.append(Paragraph(_safe_html(s), styles["body"]))
        i += 1
    return flowables


def artifact_to_bytes(label: str, content: str, cfg: GenerationConfig) -> bytes:
    buffer = BytesIO()
    styles = _build_styles()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2.5*cm, rightMargin=2.5*cm,
        topMargin=2.5*cm,  bottomMargin=2.5*cm,
        title=f"{label} — {cfg.topic_title}",
        author="Algorithmic Instructional Designer",
    )
    story = [
        Paragraph(label.replace("_", " ").title(), styles["cover_title"]),
        Spacer(1, 4),
        Paragraph(cfg.topic_title, styles["cover_sub"]),
        HRFlowable(width="100%", color=NAVY, thickness=2, spaceAfter=4),
        Paragraph(
            f"Learner profile: <b>{cfg.learner_profile.value}</b>   |   "
            f"Model: <b>{cfg.groq_model}</b>   |   "
            f"Generated: <b>{time.strftime('%d %b %Y %H:%M')}</b>",
            styles["meta"],
        ),
        HRFlowable(width="100%", color=LTEAL, thickness=0.8),
        Spacer(1, 12),
    ]
    story.extend(_md_to_flowables(content, styles))
    doc.build(story)
    return buffer.getvalue()


def artifacts_to_pdf_bytes(artifacts: LessonArtifacts, cfg: GenerationConfig) -> dict:
    docs = {
        "lesson_plan":        ("Lesson Plan",        artifacts.lesson_plan),
        "student_handout":    ("Student Handout",     artifacts.student_handout),
        "quiz":               ("Quiz",                artifacts.quiz),
        "teacher_answer_key": ("Teacher Answer Key",  artifacts.teacher_answer_key),
    }
    return {
        key: artifact_to_bytes(label, content, cfg)
        for key, (label, content) in docs.items()
        if content
    }


def artifacts_to_pdfs(
    artifacts: LessonArtifacts,
    cfg: GenerationConfig,
    output_dir: str = "outputs",
) -> dict:
    os.makedirs(output_dir, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", cfg.topic_title)[:40]
    ts   = time.strftime("%Y%m%d_%H%M%S")
    paths = {}
    for key, pdf_bytes in artifacts_to_pdf_bytes(artifacts, cfg).items():
        fname = os.path.join(output_dir, f"{safe}_{key}_{ts}.pdf")
        with open(fname, "wb") as f:
            f.write(pdf_bytes)
        paths[key] = fname
    return paths
