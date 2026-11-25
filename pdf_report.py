"""Builds the one-page PDF summary of a rent estimate (uses reportlab)."""
from io import BytesIO

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY = colors.HexColor("#0e3d7e")
BLUE = colors.HexColor("#338ced")
RED = colors.HexColor("#d6336c")
LIGHT = colors.HexColor("#eaf2fc")
INK = colors.HexColor("#222222")
MUTED = colors.HexColor("#666666")
VERDICT_COLORS = {"good": "#1b7f5c", "fair": "#1757ac", "high": "#b4531a"}


def _kes(v):
    return f"KSh {v:,.0f}"


def _range_drawing(low, predicted, high, asking, width):
    """Small chart: shaded likely range, blue estimate line, red asking line."""
    height = 62
    d = Drawing(width, height)
    lo_axis = min(low, asking or low) * 0.85
    hi_axis = max(high, asking or high) * 1.15
    left, right = 10, width - 10

    def x(v):
        return left + (v - lo_axis) / (hi_axis - lo_axis) * (right - left)

    d.add(Line(left, 22, right, 22, strokeColor=colors.HexColor("#bbbbbb"), strokeWidth=1))
    d.add(Rect(x(low), 14, x(high) - x(low), 20, fillColor=LIGHT, strokeColor=BLUE, strokeWidth=0.6))
    d.add(Line(x(predicted), 8, x(predicted), 40, strokeColor=BLUE, strokeWidth=3))
    d.add(String(x(predicted), 46, "Estimate", fontName="Helvetica", fontSize=8, fillColor=BLUE, textAnchor="middle"))
    if asking:
        d.add(Line(x(asking), 8, x(asking), 40, strokeColor=RED, strokeWidth=3))
        d.add(String(x(asking), 52, "Asking", fontName="Helvetica", fontSize=8, fillColor=RED, textAnchor="middle"))
    d.add(String(x(low), 2, _kes(low), fontName="Helvetica", fontSize=7, fillColor=MUTED, textAnchor="middle"))
    d.add(String(x(high), 2, _kes(high), fontName="Helvetica", fontSize=7, fillColor=MUTED, textAnchor="middle"))
    return d


def build_pdf(d):
    """d: dict of the estimate and its context (see keys used below). Returns PDF bytes."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title="SmartRent Nairobi - rent estimate", author="SmartRent Nairobi",
    )
    width = A4[0] - 36 * mm

    base = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=base["BodyText"], fontName="Helvetica",
                          fontSize=10, leading=14, textColor=INK)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=11, textColor=MUTED)
    h2 = ParagraphStyle("h2", parent=body, fontName="Helvetica-Bold", fontSize=12,
                        textColor=NAVY, spaceBefore=10, spaceAfter=4)
    big = ParagraphStyle("big", parent=body, fontName="Helvetica-Bold", fontSize=24,
                         leading=28, textColor=NAVY)

    story = []

    # Header band
    head = Table(
        [[Paragraph('<font color="white" size="17"><b>SmartRent Nairobi</b></font><br/>'
                    '<font color="white" size="9">Rent estimate summary</font>', body),
          Paragraph(f'<font color="white" size="9">{d["date"]}</font>',
                    ParagraphStyle("r", parent=body, alignment=2))]],
        colWidths=[width * 0.7, width * 0.3],
    )
    head.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story += [head, Spacer(1, 10)]

    # Estimate
    story += [
        Paragraph("Estimated monthly rent", h2),
        Paragraph(_kes(d["predicted"]), big),
        Paragraph(f'Likely range: {_kes(d["low"])} to {_kes(d["high"])}. In testing, about half of '
                  f'real rents fell inside this range, and estimates were typically off by about '
                  f'{_kes(d["typical_error"])}.', body),
        Spacer(1, 6),
        _range_drawing(d["low"], d["predicted"], d["high"], d.get("asking") or 0, width),
    ]

    # Verdict
    if d.get("verdict"):
        c = VERDICT_COLORS.get(d["verdict"], "#1757ac")
        story += [
            Paragraph("Price check", h2),
            Paragraph(f'<font color="{c}"><b>{d["verdict_title"]}</b></font> '
                      f'(asking {_kes(d["asking"])}). {d["verdict_text"]}', body),
        ]

    # Apartment details
    amen = ", ".join(d["amenities"]) if d["amenities"] else "None selected"
    rows = [
        ["Neighborhood", d["neighborhood"], "Security", d["security"]],
        ["Bedrooms", str(d["bedrooms"]), "Building age", f'{d["age"]} years'],
        ["Bathrooms", str(d["bathrooms"]), "Size", f'{d["size"]} sq m'],
        ["Distance to centre", f'{d["distance"]:.1f} km (area typical)', "Amenities", Paragraph(amen, small)],
    ]
    t = Table(rows, colWidths=[width * 0.2, width * 0.3, width * 0.2, width * 0.3])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [Paragraph("Apartment details", h2), t]

    # Market snapshot
    snap = [["", "Typical rent", "Listings"]]
    if d.get("area"):
        snap.append([d["neighborhood"] + " (all sizes)", _kes(d["area"]["rent"]), f'{d["area"]["listings"]:,}'])
    if d.get("same_bedrooms"):
        sb = d["same_bedrooms"]
        snap.append([f'Whole market, {sb["label"]}', _kes(sb["rent"]), f'{sb["listings"]:,}'])
    if d.get("market"):
        snap.append(["Whole market, all apartments", _kes(d["market"]["rent"]), f'{d["market"]["listings"]:,}'])
    if len(snap) > 1:
        t2 = Table(snap, colWidths=[width * 0.5, width * 0.3, width * 0.2])
        t2.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT), ("TEXTCOLOR", (0, 0), (-1, -1), INK),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story += [Paragraph("Market snapshot", h2), t2,
                  Paragraph("Typical means the median asking rent in the dataset. Listings show how many "
                            "were advertised, not how many people want to rent.", small)]

    # Model note and disclaimer
    story += [
        Paragraph("About this estimate", h2),
        Paragraph("Produced by a Gradient Boosting machine learning model trained on 1,790 Nairobi-area "
                  "apartment listings. It cannot see the condition, finish, view or management of a "
                  "building, and each amenity counts equally. Figures are asking rents, not final "
                  "agreed rents.", body),
        Spacer(1, 8),
        Paragraph("For guidance only. This is not financial or legal advice. View the property and "
                  "confirm the terms before paying any deposit. SmartRent Nairobi is a final year "
                  "project, Dedan Kimathi University of Technology.", small),
    ]

    doc.build(story)
    return buf.getvalue()
