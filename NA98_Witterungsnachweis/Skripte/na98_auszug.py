#!/usr/bin/env python3
"""Erzeugt ../NA98_Witterungsnachweis.pdf (Datenauszug Lufttemperatur, Anlage zu NA 98)
direkt aus der unveränderten DWD-Datei ../Quelldateien/DWD/tageswerte_KL_04177_akt.zip.
Aufruf: python3 Skripte/na98_auszug.py   (benötigt reportlab)"""
import csv
import datetime as dt
import io
import os
import zipfile

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIP = os.path.join(BASE, "Quelldateien", "DWD", "tageswerte_KL_04177_akt.zip")
ZIP_TU = os.path.join(BASE, "Quelldateien", "DWD", "stundenwerte_TU_04177_akt.zip")
URL = ("https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
       "daily/kl/recent/tageswerte_KL_04177_akt.zip")
ABRUF = "04.11.2026"
START, END = dt.date(2025, 11, 1), dt.date(2026, 3, 31)


def read(zpath):
    with zipfile.ZipFile(zpath) as z:
        name = [n for n in z.namelist() if n.startswith("produkt_")][0]
        text = z.read(name).decode("latin-1")
    out, head = {}, None
    for row in csv.reader(io.StringIO(text), delimiter=";"):
        row = [x.strip() for x in row]
        if not row or not row[0]:
            continue
        if row[0] == "STATIONS_ID":
            head = row
            continue
        d = dict(zip(head, row))
        out[d["MESS_DATUM"]] = d
    return out, name


KL, KL_NAME = read(ZIP)
TU, _ = read(ZIP_TU)


def v(x):
    return None if x in (None, "", "-999") else float(x)


def cls(t):
    if t is None:
        return "–"
    return "D" if t >= 5 else "A" if t > -3 else "B" if t >= -10 else "C"


def f1(x):
    return "–" if x is None else f"{x:.1f}".replace(".", ",").replace("-", "−")


days = [START + dt.timedelta(i) for i in range((END - START).days + 1)]
rows = []
for d in days:
    k = d.strftime("%Y%m%d")
    r = KL.get(k, {})
    nh = sum(v(TU.get(k + "%02d" % h, {}).get("TT_TU")) is not None for h in range(24))
    t = v(r.get("TMK"))
    rows.append(dict(d=d, tmk=t, tnk=v(r.get("TNK")), txk=v(r.get("TXK")), qn=r.get("QN_4", "–"),
                     k=cls(t), nh=nh))
N = len(rows)
valid = [x for x in rows if x["tmk"] is not None]
cnt = {c: sum(1 for x in valid if x["k"] == c) for c in "ABCD"}
missing = N - len(valid)
notes_h = [x for x in valid if x["nh"] < 21]
edge = [x for x in valid if x["tmk"] in (-3.0, 5.0, -10.0)]

# ------------------------------------------------------------------ Layout
FD = "/usr/share/fonts/truetype/liberation/"
pdfmetrics.registerFont(TTFont("LS", FD + "LiberationSans-Regular.ttf"))
pdfmetrics.registerFont(TTFont("LSB", FD + "LiberationSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("LM", FD + "LiberationMono-Regular.ttf"))
K = colors.black
G = colors.HexColor("#555555")
L = colors.HexColor("#999999")
BG = colors.HexColor("#ececec")


def S(**k):
    base = dict(fontName="LS", fontSize=8.5, leading=11, textColor=K)
    base.update(k)
    return ParagraphStyle("s", **base)


P, PS, PB = S(), S(fontSize=7.5, leading=9.5), S(fontName="LSB")
TITLE = S(fontName="LSB", fontSize=13, leading=16)
H = S(fontName="LSB", fontSize=9.5, leading=12, spaceBefore=8, spaceAfter=3)

GRID = [("FONT", (0, 0), (-1, -1), "LS", 8), ("GRID", (0, 0), (-1, -1), 0.4, L),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]


def table(data, widths, head=True, extra=()):
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    st = list(GRID)
    if head:
        st += [("FONT", (0, 0), (-1, 0), "LSB", 8), ("BACKGROUND", (0, 0), (-1, 0), BG)]
    t.setStyle(TableStyle(st + list(extra)))
    return t


class NumCanvas(rl_canvas.Canvas):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._pages = []

    def showPage(self):
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._pages)
        for p in self._pages:
            self.__dict__.update(p)
            self._chrome(n)
            super().showPage()
        super().save()

    def _chrome(self, n):
        w, h = A4
        self.setFont("LS", 7.5)
        self.setFillColor(G)
        self.drawString(18 * mm, h - 11 * mm, "Anlage zu NA 98 – Winterbau KARLA")
        self.drawRightString(w - 18 * mm, h - 11 * mm, "Tageswerte Lufttemperatur 01.11.2025 – 31.03.2026")
        self.setStrokeColor(L)
        self.setLineWidth(0.4)
        self.line(18 * mm, h - 12.5 * mm, w - 18 * mm, h - 12.5 * mm)
        self.line(18 * mm, 13 * mm, w - 18 * mm, 13 * mm)
        self.drawString(18 * mm, 9.5 * mm, "Datenquelle: Deutscher Wetterdienst (DWD), CC BY 4.0 – Klassierung nicht durch den DWD")
        self.drawRightString(w - 18 * mm, 9.5 * mm, f"Seite {self._pageNumber} von {n}")


MN = {11: "November 2025", 12: "Dezember 2025", 1: "Januar 2026", 2: "Februar 2026", 3: "März 2026"}

story = [Paragraph("Tageswerte Lufttemperatur – Station Rheinstetten (DWD 04177)", TITLE),
         Paragraph(f"Zeitraum 01.11.2025 – 31.03.2026 ({N} Tage) · Abruf {ABRUF} · Quelle: Deutscher Wetterdienst, "
                   f"<font name='LM' size='6.8'>{URL}</font>", PS),
         Spacer(1, 6)]


def month_table(y, m):
    xs = [x for x in rows if (x["d"].year, x["d"].month) == (y, m)]
    data = [[MN[m], "", "", "", ""], ["Datum", "Mittel", "Min", "Max", "Kl."]]
    for x in xs:
        mark = "¹" if x in notes_h else ""
        data.append([x["d"].strftime("%d.%m.%Y") + mark, f1(x["tmk"]), f1(x["tnk"]), f1(x["txk"]), x["k"]])
    while len(data) < 33:
        data.append([""] * 5)
    t = Table(data, colWidths=[17 * mm, 11 * mm, 11 * mm, 11 * mm, 6 * mm])
    t.setStyle(TableStyle(GRID + [
        ("SPAN", (0, 0), (-1, 0)), ("FONT", (0, 0), (-1, 0), "LSB", 8), ("BACKGROUND", (0, 0), (-1, 1), BG),
        ("ALIGN", (1, 1), (3, -1), "RIGHT"), ("ALIGN", (4, 1), (4, -1), "CENTER"),
        ("FONT", (0, 1), (-1, 1), "LSB", 7.2), ("FONT", (0, 2), (-1, -1), "LS", 7.4),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
    return t


def pc(n):
    return f"{100 * n / N:.1f} %".replace(".", ",")


summ = Table([["Auswertung", "", "", ""], ["Kl.", "Tagesmittel T", "Tage", "Anteil"],
              ["A", "−3 < T < +5 °C", str(cnt["A"]), pc(cnt["A"])],
              ["B", "−10 ≤ T ≤ −3 °C", str(cnt["B"]), pc(cnt["B"])],
              ["C", "T < −10 °C", str(cnt["C"]), pc(cnt["C"])],
              ["D", "T ≥ +5 °C", str(cnt["D"]), pc(cnt["D"])],
              ["A+B", "", str(cnt["A"] + cnt["B"]), pc(cnt["A"] + cnt["B"])],
              ["–", "ohne Messwert", str(missing), pc(missing)],
              ["", "Summe", str(N), "100,0 %"]],
             colWidths=[8 * mm, 24 * mm, 10 * mm, 14 * mm])
summ.setStyle(TableStyle(GRID + [
    ("SPAN", (0, 0), (-1, 0)), ("FONT", (0, 0), (-1, 0), "LSB", 8), ("BACKGROUND", (0, 0), (-1, 1), BG),
    ("FONT", (0, 1), (-1, 1), "LSB", 7.2), ("FONT", (0, 2), (-1, -1), "LS", 7.4),
    ("FONT", (0, 6), (-1, 6), "LSB", 7.4), ("FONT", (0, -1), (-1, -1), "LSB", 7.4),
    ("ALIGN", (2, 1), (3, -1), "RIGHT"), ("ALIGN", (0, 1), (0, -1), "CENTER"),
    ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))

groups = [[month_table(2025, 11), month_table(2025, 12), month_table(2026, 1)],
          [month_table(2026, 2), month_table(2026, 3), summ]]
for i, grp in enumerate(groups):
    wrap = Table([[grp[0], "", grp[1], "", grp[2]]], colWidths=[56 * mm, 3 * mm, 56 * mm, 3 * mm, 56 * mm])
    wrap.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(wrap)
    story.append(Spacer(1, 5))
    if i == 0:
        story.append(PageBreak())

legend = ("Werte in °C. Mittel = Tagesmittel (DWD TMK), Min/Max = Tagesminimum/-maximum (TNK/TXK), "
          "jeweils 00–24 UTC. Kl. = Temperaturklasse nach Tagesmittel: A = +5 °C bis −3 °C, B = −3 °C bis −10 °C "
          "(−3,0 °C zählt zu B), C = unter −10 °C, D = ab +5 °C.")
story.append(Paragraph(legend, PS))
for x in notes_h:
    story.append(Paragraph(f"¹ {x['d'].strftime('%d.%m.%Y')}: Stundenwerte 01–11 UTC nicht vorhanden; "
                           f"Tagesmittel wie vom DWD veröffentlicht.", PS))

out = os.path.join(BASE, "NA98_Witterungsnachweis.pdf")
doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm,
                        bottomMargin=18 * mm, title="Tageswerte Lufttemperatur Station Rheinstetten (DWD 04177)",
                        author="", subject="Anlage zu NA 98 – Winterbau KARLA", creator="")
doc.build(story, canvasmaker=NumCanvas)
print(cnt, "fehlend", missing, "->", out)
