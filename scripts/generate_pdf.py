#!/usr/bin/env python3
"""
scripts/generate_pdf.py — Generates reports/RESULTS.pdf from reports/RESULTS.md
"""

import os
import sys
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD_PATH = os.path.join(BASE_DIR, "reports", "RESULTS.md")
PDF_PATH = os.path.join(BASE_DIR, "reports", "RESULTS.pdf")

def parse_markdown_to_flowables(md_text, styles):
    flowables = []
    lines = md_text.splitlines()
    in_table = False
    table_lines = []

    def flush_table():
        nonlocal in_table, table_lines
        if not table_lines:
            return
        rows = []
        for tl in table_lines:
            if re.match(r"^\|?\s*[-:]+[-| :]*$", tl):
                continue # delimiter row
            parts = [p.strip() for p in tl.split("|")]
            if tl.startswith("|"): parts = parts[1:]
            if tl.endswith("|"): parts = parts[:-1]
            rows.append(parts)
        if rows:
            col_count = max(len(r) for r in rows)
            padded = [r + [""] * (col_count - len(r)) for r in rows]
            cell_paras = []
            for r_idx, row in enumerate(padded):
                row_paras = []
                for cell in row:
                    clean_cell = cell.replace("**", "<b>").replace("`", "")
                    clean_cell = re.sub(r"<b>(.*?)<b>", r"<b>\1</b>", clean_cell)
                    style = styles["TableHeader"] if r_idx == 0 else styles["TableCell"]
                    row_paras.append(Paragraph(clean_cell, style))
                cell_paras.append(row_paras)

            t = Table(cell_paras, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a365d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
                ("TOPPADDING", (0, 0), (-1, 0), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("TOPPADDING", (0, 1), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
            ]))
            flowables.append(t)
            flowables.append(Spacer(1, 8))
        in_table = False
        table_lines = []

    for line in lines:
        sline = line.strip()
        if not sline:
            if in_table:
                flush_table()
            continue

        if "|" in sline and not sline.startswith("```"):
            in_table = True
            table_lines.append(sline)
            continue
        elif in_table:
            flush_table()

        if sline.startswith("# "):
            title = sline[2:].strip().replace("**", "")
            flowables.append(Paragraph(title, styles["DocTitle"]))
            flowables.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1e3a8a"), spaceAfter=8, spaceBefore=4))
        elif sline.startswith("## "):
            h2 = sline[3:].strip().replace("**", "")
            flowables.append(Spacer(1, 6))
            flowables.append(Paragraph(h2, styles["SectionHeading"]))
            flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94a3b8"), spaceAfter=4, spaceBefore=2))
        elif sline.startswith("### "):
            h3 = sline[4:].strip().replace("**", "")
            flowables.append(Spacer(1, 4))
            flowables.append(Paragraph(h3, styles["SubSectionHeading"]))
        elif sline.startswith("- ") or sline.startswith("* "):
            item = sline[2:].strip()
            item = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", item)
            item = re.sub(r"`(.*?)`", r"<font name='Courier'>\1</font>", item)
            flowables.append(Paragraph(f"• {item}", styles["BulletText"]))
        elif re.match(r"^\d+\.\s", sline):
            num, item = sline.split(".", 1)
            item = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", item.strip())
            item = re.sub(r"`(.*?)`", r"<font name='Courier'>\1</font>", item)
            flowables.append(Paragraph(f"{num}. {item}", styles["BulletText"]))
        else:
            p = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", sline)
            p = re.sub(r"`(.*?)`", r"<font name='Courier'>\1</font>", p)
            flowables.append(Paragraph(p, styles["Body"]))
            flowables.append(Spacer(1, 3))

    if in_table:
        flush_table()

    return flowables

def main():
    if not os.path.exists(MD_PATH):
        print(f"ERROR: {MD_PATH} not found.")
        sys.exit(1)

    with open(MD_PATH, "r", encoding="utf-8") as f:
        md_text = f.read()

    doc = SimpleDocTemplate(
        PDF_PATH,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="DocTitle",
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#0f172a")
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1e3a8a"),
        keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        name="SubSectionHeading",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
        keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        name="Body",
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#1e293b")
    ))
    styles.add(ParagraphStyle(
        name="BulletText",
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        leftIndent=12,
        textColor=colors.HexColor("#1e293b")
    ))
    styles.add(ParagraphStyle(
        name="TableHeader",
        fontName="Helvetica-Bold",
        fontSize=6.5,
        leading=8,
        textColor=colors.whitesmoke
    ))
    styles.add(ParagraphStyle(
        name="TableCell",
        fontName="Helvetica",
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor("#0f172a")
    ))

    flowables = parse_markdown_to_flowables(md_text, styles)
    doc.build(flowables)
    print(f"Generated {PDF_PATH} ({os.path.getsize(PDF_PATH)} bytes)")

if __name__ == "__main__":
    main()
