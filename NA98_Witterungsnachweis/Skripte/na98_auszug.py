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
    return "D" if t >= 5 else "A" if t >= -3 else "B" if t >= -10 else "C"


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
        self.drawRightString(w - 18 * mm, h - 11 * mm, "Tageswerte Lufttemperatur · DWD-Station 04177 Rheinstetten")
        self.setStrokeColor(L)
        self.setLineWidth(0.4)
        self.line(18 * mm, h - 12.5 * mm, w - 18 * mm, h - 12.5 * mm)
        self.line(18 * mm, 13 * mm, w - 18 * mm, 13 * mm)
        self.drawString(18 * mm, 9.5 * mm, "Datenbasis: Deutscher Wetterdienst (DWD), Climate Data Center, Lizenz CC BY 4.0.")
        self.drawString(18 * mm, 6.3 * mm, "Zusammenstellung und Klassierung nicht durch den DWD.")
        self.drawRightString(w - 18 * mm, 9.5 * mm, f"Seite {self._pageNumber} von {n}")


story = [Paragraph("Auszug Tageswerte Lufttemperatur", TITLE),
         Paragraph("Zeitraum 01.11.2025 bis 31.03.2026 · Anlage zu Nachtrag NA 98 – Winterbau KARLA", P),
         Spacer(1, 6)]

meta = [
    ["Station", "Rheinstetten", "Stations-ID", "04177"],
    ["Geogr. Breite / Länge", "48,9726° N / 8,3301° O", "Stationshöhe", "116 m ü. NHN"],
    ["Messgröße", "Lufttemperatur 2 m über Grund", "Messgerät", "PT 100 (elektrisch)"],
    ["Zeitraum", "01.11.2025 – 31.03.2026", "Kalendertage", str(N)],
    ["Datensatz", "DWD CDC, Tageswerte KL (recent)", "Abruf", ABRUF],
]
story.append(table(meta, [36 * mm, 58 * mm, 28 * mm, 52 * mm], head=False,
                   extra=[("FONT", (0, 0), (0, -1), "LSB", 8), ("FONT", (2, 0), (2, -1), "LSB", 8),
                          ("BACKGROUND", (0, 0), (0, -1), BG), ("BACKGROUND", (2, 0), (2, -1), BG)]))
story.append(Spacer(1, 3))
story.append(Paragraph(f"Quelle: <font name='LM' size='7'>{URL}</font>, Datei {KL_NAME}", PS))

story.append(Paragraph("Erläuterung der Werte", H))
story.append(table([
    ["Spalte", "DWD-Kennung", "Beschreibung"],
    ["Mittel", "TMK", "Tagesmittel der Lufttemperatur, arithm. Mittel aus mind. 21 Stundenwerten, 00–24 UTC"],
    ["Min", "TNK", "Tagesminimum der Lufttemperatur in 2 m Höhe, 00–24 UTC"],
    ["Max", "TXK", "Tagesmaximum der Lufttemperatur in 2 m Höhe, 00–24 UTC"],
    ["QN", "QN_4", "Qualitätsniveau des DWD (9 = Routineprüfung erfolgt, nicht alle Parameter korrigiert)"],
    ["Kl.", "–", "Temperaturklasse nach Tagesmittel T (Einteilung siehe unten)"],
], [16 * mm, 22 * mm, 136 * mm]))

story.append(Paragraph("Temperaturklassen", H))
story.append(table([
    ["Klasse", "Tagesmittel T", "Tage", "Anteil"],
    ["A", "−3 °C ≤ T < +5 °C", str(cnt["A"]), f"{100 * cnt['A'] / N:.1f} %".replace(".", ",")],
    ["B", "−10 °C ≤ T < −3 °C", str(cnt["B"]), f"{100 * cnt['B'] / N:.1f} %".replace(".", ",")],
    ["C", "T < −10 °C", str(cnt["C"]), f"{100 * cnt['C'] / N:.1f} %".replace(".", ",")],
    ["D", "T ≥ +5 °C", str(cnt["D"]), f"{100 * cnt['D'] / N:.1f} %".replace(".", ",")],
    ["A + B", "−10 °C ≤ T < +5 °C", str(cnt["A"] + cnt["B"]),
     f"{100 * (cnt['A'] + cnt['B']) / N:.1f} %".replace(".", ",")],
    ["ohne Wert", "Tagesmittel fehlt", str(missing), f"{100 * missing / N:.1f} %".replace(".", ",")],
    ["Summe", "", str(N), "100,0 %"],
], [22 * mm, 50 * mm, 20 * mm, 24 * mm],
    extra=[("ALIGN", (2, 0), (3, -1), "RIGHT"), ("FONT", (0, 5), (-1, 5), "LSB", 8),
           ("FONT", (0, -1), (-1, -1), "LSB", 8)]))

MN = {11: "November 2025", 12: "Dezember 2025", 1: "Januar 2026", 2: "Februar 2026", 3: "März 2026"}
mon = [["Monat", "Tage", "Mittel °C", "tiefstes Min °C", "höchstes Max °C", "A", "B", "C", "D", "o. W."]]
for y, m in [(2025, 11), (2025, 12), (2026, 1), (2026, 2), (2026, 3)]:
    xs = [x for x in rows if (x["d"].year, x["d"].month) == (y, m)]
    vv = [x for x in xs if x["tmk"] is not None]
    mon.append([MN[m], str(len(xs)), f1(sum(x["tmk"] for x in vv) / len(vv)),
                f1(min(x["tnk"] for x in vv if x["tnk"] is not None)),
                f1(max(x["txk"] for x in vv if x["txk"] is not None))]
               + [str(sum(1 for x in vv if x["k"] == c)) for c in "ABCD"] + [str(len(xs) - len(vv))])
mon.append(["Gesamt", str(N), f1(sum(x["tmk"] for x in valid) / len(valid)),
            f1(min(x["tnk"] for x in valid)), f1(max(x["txk"] for x in valid))]
           + [str(cnt[c]) for c in "ABCD"] + [str(missing)])
story.append(Paragraph("Monatsübersicht", H))
story.append(table(mon, [28 * mm, 12 * mm, 18 * mm, 25 * mm, 25 * mm] + [12 * mm] * 4 + [14 * mm],
                   extra=[("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("FONT", (0, -1), (-1, -1), "LSB", 8)]))

story.append(Paragraph("Anmerkungen", H))
notes = [
    "Die Werte sind unverändert aus der DWD-Datei übernommen (Auflösung 0,1 °C). Es wurden keine Werte ergänzt, "
    "interpoliert oder von anderen Stationen übernommen. Fehlende Tagesmittel würden mit „–“ ausgewiesen und nicht als 0 °C gewertet.",
    "Die Klassenzuordnung erfolgt mit dem ungerundeten Tagesmittel. Untergrenzen gelten einschließlich, Obergrenzen ausschließlich. "
    + ("Grenzwerte traten auf am " + ", ".join(f"{x['d'].strftime('%d.%m.%Y')} ({f1(x['tmk'])} °C → {x['k']})" for x in edge) + "."
       if edge else ""),
]
for x in notes_h:
    notes.append(f"{x['d'].strftime('%d.%m.%Y')}: In den Stundenwerten der Station liegen nur {x['nh']} von 24 Werten vor "
                 f"(fehlend 01–11 UTC). Das Tagesmittel ist wie vom DWD veröffentlicht angegeben.")
notes.append("Qualitätsniveau QN 9: Die Daten können vom DWD nachträglich noch korrigiert werden; maßgebend ist der Abrufstand "
             f"{ABRUF}. Für November und Dezember 2025 stimmen die Werte mit dem DWD-Datensatz „historical“ überein.")
for i, n in enumerate(notes, 1):
    story.append(Paragraph(f"{i}) {n}", PS))
    story.append(Spacer(1, 1.5))

story.append(Spacer(1, 14))
sig = Table([["Aufgestellt (Ort, Datum)", "Name", "Unterschrift"], ["", "", ""]],
            colWidths=[58 * mm] * 3, rowHeights=[None, 13 * mm])
sig.setStyle(TableStyle(GRID + [("FONT", (0, 0), (-1, 0), "LSB", 8), ("BACKGROUND", (0, 0), (-1, 0), BG)]))
story.append(KeepTogether(sig))

# Tageswerte je Monat, zwei Monate nebeneinander
story.append(PageBreak())
story.append(Paragraph("Tageswerte", TITLE))
story.append(Spacer(1, 4))


def month_table(y, m):
    xs = [x for x in rows if (x["d"].year, x["d"].month) == (y, m)]
    data = [[MN[m], "", "", "", "", ""], ["Datum", "Mittel", "Min", "Max", "QN", "Kl."]]
    for x in xs:
        mark = "¹" if x in notes_h else ""
        data.append([x["d"].strftime("%d.%m.%Y") + mark, f1(x["tmk"]), f1(x["tnk"]), f1(x["txk"]), x["qn"], x["k"]])
    while len(data) < 33:
        data.append([""] * 6)
    t = Table(data, colWidths=[16.5 * mm, 10 * mm, 10 * mm, 10 * mm, 5 * mm, 4.5 * mm])
    t.setStyle(TableStyle(GRID + [
        ("SPAN", (0, 0), (-1, 0)), ("FONT", (0, 0), (-1, 1), "LSB", 8), ("BACKGROUND", (0, 0), (-1, 1), BG),
        ("ALIGN", (1, 1), (3, -1), "RIGHT"), ("ALIGN", (4, 1), (5, -1), "CENTER"),
        ("FONT", (0, 1), (-1, 1), "LSB", 7), ("FONT", (0, 2), (-1, -1), "LS", 7.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
    return t


groups = [[(2025, 11), (2025, 12), (2026, 1)], [(2026, 2), (2026, 3), None]]
for i, grp in enumerate(groups):
    cells = []
    for g in grp:
        cells += [month_table(*g) if g else "", ""]
    wrap = Table([cells[:-1]], colWidths=[56 * mm, 3 * mm, 56 * mm, 3 * mm, 56 * mm])
    wrap.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(wrap)
    story.append(Spacer(1, 6))
    if i == 0:
        story.append(PageBreak())
if notes_h:
    story.append(Paragraph("¹ siehe Anmerkung 3 auf Seite 1.", PS))
story.append(Paragraph("Werte in °C. Kl. = Temperaturklasse nach Tagesmittel (A: −3 ≤ T < +5; B: −10 ≤ T < −3; "
                       "C: T < −10; D: T ≥ +5).", PS))

out = os.path.join(BASE, "NA98_Witterungsnachweis.pdf")
doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm,
                        bottomMargin=18 * mm, title="Auszug Tageswerte Lufttemperatur DWD-Station 04177 Rheinstetten",
                        author="", subject="Anlage zu NA 98 – Winterbau KARLA", creator="")
doc.build(story, canvasmaker=NumCanvas)
print(cnt, "fehlend", missing, "->", out)
