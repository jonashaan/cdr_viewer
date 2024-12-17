import re
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors as reportlab_colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

colors = {
    "header_text": "#FFFFFF",
    "header_background": "#434C5E",
    "row_text": "#000000",
    "row_background": "#ECEFF4",
    "grid": "#000000"
}

def color(hex_value: str) -> reportlab_colors.Color:
    hex_value = hex_value.lstrip("#")

    red = int(hex_value[0:2], 16) / 255
    green = int(hex_value[2:4], 16) / 255
    blue = int(hex_value[4:6], 16) / 255

    return reportlab_colors.Color(red, green, blue)

def remove_size_tags(text: str) -> str:
    return re.sub(r'\[size=\d+\]|\[/size\]', '', text)

def create_pdf(data: list[Any], path: str) -> None:
    pdf = SimpleDocTemplate(path, pagesize=A4)

    # Clean header row
    header_row = data[0]
    header_row = [remove_size_tags(text) for text, _ in header_row]

    data_rows = data[1:]
    style = getSampleStyleSheet()['Normal']

    paragraphs = []
    for row in data_rows:
        for line in row:
            p_row = []
            for text in line:
                p_row.append(Paragraph(str(text), style))
            paragraphs.append(p_row)


    data = [
        header_row,
        *paragraphs
    ]

    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), color(colors["header_background"])),
        ('TEXTCOLOR', (0, 0), (-1, 0), color(colors["header_text"])),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 13),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), color(colors["row_background"])),
        ('TEXTCOLOR', (0, 1), (-1, -1), color(colors["row_text"])),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, color(colors["grid"])),
    ])

    table = Table(data)
    table.setStyle(style)
    pdf.build([table])
