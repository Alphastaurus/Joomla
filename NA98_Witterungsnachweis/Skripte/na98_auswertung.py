#!/usr/bin/env python3
"""NA 98 – Winterbau KARLA: Witterungsnachweis Lufttemperatur, DWD-Station Rheinstetten (04177).

Reproduzierbare Auswertung. Liest ausschließlich die unveränderten Quelldateien aus
../Quelldateien und erzeugt:
  ../NA98_Temperaturauswertung_2025-2026.csv
  ../NA98_Interne_Pruefung.pdf (interner Prüfvermerk)

Aufruf:  python3 Skripte/na98_auswertung.py   (benötigt reportlab)
"""
import csv
import datetime as dt
import hashlib
import io
import os
import statistics as st
import zipfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Q = os.path.join(BASE, "Quelldateien")
DWD = os.path.join(Q, "DWD")
OTT = os.path.join(Q, "OtterWetter")

START, END = dt.date(2025, 11, 1), dt.date(2026, 3, 31)
DAYS = [START + dt.timedelta(i) for i in range((END - START).days + 1)]
assert len(DAYS) == 151

NA98 = {"A": 74, "B": 3, "AB": 77, "KT": 151}

URL_BASE = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
URL_KL = URL_BASE + "daily/kl/recent/tageswerte_KL_04177_akt.zip"
URL_KL_HIST = URL_BASE + "daily/kl/historical/tageswerte_KL_04177_19480101_20251231_hist.zip"
URL_TU = URL_BASE + "hourly/air_temperature/recent/stundenwerte_TU_04177_akt.zip"
URL_TU10 = URL_BASE + "10_minutes/air_temperature/recent/10minutenwerte_TU_04177_akt.zip"
URL_OTTER = "https://otterwetter.de/baden-wuerttemberg/rheinstetten/archiv"
URL_OTTER_SEL = (URL_OTTER + "?g=month&m=temperature&v=table&a=avg"
                 "&d=2025-11%2C2025-12%2C2026-01%2C2026-02%2C2026-03")


# ------------------------------------------------------------------ Einlesen
def read_produkt(zpath, key_len):
    """DWD-Produktdatei (Semikolon) aus ZIP lesen -> {MESS_DATUM: {Spalte: Wert}}"""
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
        assert d["STATIONS_ID"] == "4177" and len(d["MESS_DATUM"]) == key_len
        out[d["MESS_DATUM"]] = d
    return out, name


def val(x):
    return None if x in (None, "", "-999") else float(x)


KL, KL_NAME = read_produkt(os.path.join(DWD, "tageswerte_KL_04177_akt.zip"), 8)
KLH, _ = read_produkt(os.path.join(DWD, "tageswerte_KL_04177_19480101_20251231_hist.zip"), 8)
TU, _ = read_produkt(os.path.join(DWD, "stundenwerte_TU_04177_akt.zip"), 10)
TU10, _ = read_produkt(os.path.join(DWD, "10minutenwerte_TU_04177_akt.zip"), 12)

# Rohdatei im Ergebnisordner muss byte-identisch mit der DWD-Produktdatei sein
with zipfile.ZipFile(os.path.join(DWD, "tageswerte_KL_04177_akt.zip")) as z:
    raw = z.read(KL_NAME)
with open(os.path.join(BASE, "NA98_DWD_Rheinstetten_Rohdaten.csv"), "rb") as f:
    assert f.read() == raw, "Rohdatendatei weicht von DWD-Original ab"


def cls(t):
    if t is None:
        return None
    if t >= 5:
        return "D"
    if t > -3:
        return "A"
    if t >= -10:
        return "B"
    return "C"


# ------------------------------------------------------------- Tagesauswertung
rows = []
for d in DAYS:
    k = d.strftime("%Y%m%d")
    r = KL.get(k)
    tmk = val(r["TMK"]) if r else None
    tnk = val(r["TNK"]) if r else None
    txk = val(r["TXK"]) if r else None
    hours = [val(TU.get(k + "%02d" % h, {}).get("TT_TU")) for h in range(24)]
    n_h = sum(v is not None for v in hours)
    n_10 = sum(val(TU10.get(k + "%02d%02d" % (h, m), {}).get("TT_10")) is not None
               for h in range(24) for m in range(0, 60, 10))
    c = cls(tmk)
    if tmk is None:
        status = "fehlt – kein DWD-Tagesmittel (nicht als 0 °C gewertet)"
    elif n_h < 21:
        status = ("gültig mit Vorbehalt – DWD-Tageswert veröffentlicht, Stundenreihe nur "
                  f"{n_h}/24 h (10-min: {n_10}/144); Herleitung nicht aus Rohdaten nachprüfbar")
    elif tmk == -3.0:
        status = "gültig – Grenzwert exakt -3,0 °C: Klasse B (−10 °C ≤ T ≤ −3 °C)"
    elif tmk == 5.0:
        status = "gültig – Grenzwert exakt +5,0 °C: Klasse D (T ≥ +5 °C)"
    else:
        status = "gültig"
    status += f" | DWD QN {r['QN_4']}" if r else ""
    rows.append(dict(d=d, tmk=tmk, tnk=tnk, txk=txk, c=c, status=status, n_h=n_h,
                     mean_h=(sum(v for v in hours if v is not None) / n_h) if n_h else None))


def fz(x):
    return "" if x is None else f"{x:.1f}".replace(".", ",")


out_csv = os.path.join(BASE, "NA98_Temperaturauswertung_2025-2026.csv")
with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, delimiter=";", lineterminator="\r\n")
    w.writerow(["Datum", "Tagesmitteltemperatur °C", "Tagesminimum °C", "Tagesmaximum °C",
                "Temperaturklasse", "Datenstatus"])
    for x in rows:
        w.writerow([x["d"].strftime("%d.%m.%Y"), fz(x["tmk"]), fz(x["tnk"]), fz(x["txk"]),
                    x["c"] or "–", x["status"]])

# ----------------------------------------------------------------- Kennzahlen
valid = [x for x in rows if x["tmk"] is not None]
N, NV = len(rows), len(valid)
missing = [x for x in rows if x["tmk"] is None]
caveat = [x for x in valid if x["n_h"] < 21]
cnt = {k: sum(1 for x in valid if x["c"] == k) for k in "ABCD"}
cnt["AB"] = cnt["A"] + cnt["B"]
# Alternative Grenzziehung (−3,0 °C zu A) zur Information
alt_B = sum(1 for x in valid if -10 <= x["tmk"] < -3.0)
alt_A = sum(1 for x in valid if -3.0 <= x["tmk"] < 5)
edge_m3 = [x for x in valid if x["tmk"] == -3.0]
edge_p5 = [x for x in valid if x["tmk"] == 5.0]
# Sensitivität Vorbehaltstag
excl = [x for x in valid if x["n_h"] >= 21]
cnt_ex = {k: sum(1 for x in excl if x["c"] == k) for k in "ABCD"}

# Abgleich recent vs. historical (Überlappung Nov/Dez 2025)
overlap = [k for k in KLH if "20251101" <= k <= "20251231"]
hist_diff = [k for k in overlap
             if (KLH[k]["TMK"], KLH[k]["TNK"], KLH[k]["TXK"]) != (KL[k]["TMK"], KL[k]["TNK"], KL[k]["TXK"])]

# Monatsübersicht
months = [(2025, 11), (2025, 12), (2026, 1), (2026, 2), (2026, 3)]
MN = {11: "Nov 2025", 12: "Dez 2025", 1: "Jan 2026", 2: "Feb 2026", 3: "Mär 2026"}
mon = []
for y, m in months:
    xs = [x for x in rows if x["d"].year == y and x["d"].month == m]
    v = [x for x in xs if x["tmk"] is not None]
    mon.append([MN[m], len(xs), len(xs) - len(v)] + [sum(1 for x in v if x["c"] == k) for k in "ABCD"]
               + [st.mean(x["tmk"] for x in v)])

# OtterWetter-Abgleich
oh = {}
with open(os.path.join(OTT, "otterwetter-Rheinstetten-stundenwerte.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        oh[r["Zeitstempel"]] = r["Temperatur (°C)"]
o_match = o_mis = o_empty = 0
for ts, v in oh.items():
    if v == "":
        o_empty += 1
        continue
    t = dt.datetime.fromisoformat(ts)
    off = 2 if t >= dt.datetime(2026, 3, 29, 3) else 1  # MEZ/MESZ -> UTC
    u = (t - dt.timedelta(hours=off)).strftime("%Y%m%d%H")
    ref = val(TU.get(u, {}).get("TT_TU"))
    if ref is not None and abs(ref - float(v)) < 0.05:
        o_match += 1
    else:
        o_mis += 1
od = {}
with open(os.path.join(OTT, "otterwetter-Rheinstetten-temperature-avg.csv"), encoding="utf-8-sig") as f:
    rr = list(csv.reader(f))
for row in rr[1:]:
    n = int(row[0].split()[1])
    for i, (y, m) in enumerate(months):
        try:
            if row[i + 1] != "":
                od[dt.date(y, m, n)] = float(row[i + 1])
        except ValueError:
            pass
o_diff = [od[x["d"]] - x["tmk"] for x in valid if x["d"] in od]
o_cls = sum(1 for x in valid if x["d"] in od and cls(od[x["d"]]) != x["c"])
o_cnt = {k: sum(1 for x in valid if x["d"] in od and cls(od[x["d"]]) == k) for k in "ABCD"}

# Mehrjahresvergleich (gleiche Station, seit Neuaufnahme 28.10.2008)
ALL = {**KLH, **KL}
winters = []
for y in range(2008, 2026):
    s, e = dt.date(y, 11, 1), dt.date(y + 1, 3, 31)
    n = (e - s).days + 1
    c = {k: 0 for k in "ABCD"}
    miss = 0
    for i in range(n):
        r = ALL.get((s + dt.timedelta(i)).strftime("%Y%m%d"))
        t = val(r["TMK"]) if r else None
        if t is None:
            miss += 1
        else:
            c[cls(t)] += 1
    winters.append(dict(w=f"{y}/{(y + 1) % 100:02d}", n=n, v=n - miss, miss=miss, **c))
wv = [w for w in winters if w["miss"] == 0]
share = {k: [w[k] / w["v"] for w in wv] for k in "ABCD"}
share["AB"] = [(w["A"] + w["B"]) / w["v"] for w in wv]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


FILES = [
    ("NA98_DWD_Rheinstetten_Rohdaten.csv", os.path.join(BASE, "NA98_DWD_Rheinstetten_Rohdaten.csv")),
    ("NA98_Temperaturauswertung_2025-2026.csv", out_csv),
    ("Quelldateien/DWD/tageswerte_KL_04177_akt.zip", os.path.join(DWD, "tageswerte_KL_04177_akt.zip")),
    ("Quelldateien/DWD/tageswerte_KL_04177_19480101_20251231_hist.zip",
     os.path.join(DWD, "tageswerte_KL_04177_19480101_20251231_hist.zip")),
    ("Quelldateien/DWD/stundenwerte_TU_04177_akt.zip", os.path.join(DWD, "stundenwerte_TU_04177_akt.zip")),
    ("Quelldateien/DWD/10minutenwerte_TU_04177_akt.zip", os.path.join(DWD, "10minutenwerte_TU_04177_akt.zip")),
    ("Quelldateien/OtterWetter/otterwetter-Rheinstetten-temperature-avg.csv",
     os.path.join(OTT, "otterwetter-Rheinstetten-temperature-avg.csv")),
    ("Quelldateien/OtterWetter/otterwetter-Rheinstetten-stundenwerte.csv",
     os.path.join(OTT, "otterwetter-Rheinstetten-stundenwerte.csv")),
]
HASHES = [(n, sha(p)) for n, p in FILES]
with open(os.path.join(Q, "SHA256SUMS.txt"), "w") as f:
    for n, h in HASHES:
        f.write(f"{h}  {n}\n")


def pct(a, b):
    return f"{100 * a / b:.1f} %".replace(".", ",")


def de(x, nd=1):
    return f"{x:.{nd}f}".replace(".", ",").replace("-", "−")


ITWO_T = (f"Temperaturanteile lt. DWD-Station Rheinstetten (ID 04177), Tagesmittel TMK, "
          f"01.11.2025–31.03.2026 = {N} KT, {len(missing)} Fehlwerte: "
          f"A (−3 < T < +5 °C) {cnt['A']} KT = {pct(cnt['A'], NV)}; "
          f"B (−10 ≤ T ≤ −3 °C) {cnt['B']} KT = {pct(cnt['B'], NV)}; C {cnt['C']} KT; "
          f"A+B {cnt['AB']} KT = {pct(cnt['AB'], NV)}; Anteile × {N} KT. "
          f"Nachweis: Anlage NA98_Witterungsnachweis.pdf")

# ---------------------------------------------------------------- Konsole
print("Klassen:", cnt, "gültig", NV, "fehlend", len(missing), "Vorbehalt", [x["d"] for x in caveat])
print("Alternative (-3,0 zu A):", "A", alt_A, "B", alt_B)
print("ohne Vorbehaltstag:", cnt_ex)
print("hist/recent Differenzen:", hist_diff)
print("Otter Stunden: match", o_match, "mismatch", o_mis, "leer", o_empty,
      "| Tagesmittel Abw. mean %.2f max %.2f, Klassenabw. %d" % (st.mean(o_diff), max(o_diff), o_cls), o_cnt)
print("iTWO:", ITWO_T)

# ------------------------------------------------------------------- PDF
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)
from reportlab.graphics.shapes import Drawing, Line, Rect, String

FD = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("DV", FD + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVB", FD + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DVM", FD + "DejaVuSansMono.ttf"))
from reportlab.lib.fonts import addMapping
addMapping("DV", 0, 0, "DV"); addMapping("DV", 1, 0, "DVB")

INK, MUTED, RULE, TINT = colors.HexColor("#1d1d1b"), colors.HexColor("#5b5a56"), colors.HexColor("#c9c7c0"), colors.HexColor("#f2f1ec")
ACC = colors.HexColor("#1f4e79")
WARN = colors.HexColor("#a4262c")
OK = colors.HexColor("#2e6b30")
COL = {"A": colors.HexColor("#2a78d6"), "B": colors.HexColor("#6250d6"),
       "C": colors.HexColor("#0b2a55"), "D": colors.HexColor("#eb6834")}

sty = lambda **k: ParagraphStyle("x", **{**dict(fontName="DV", fontSize=9, leading=12.2, textColor=INK, alignment=TA_LEFT), **k})
P = sty()
PS = sty(fontSize=7.6, leading=9.8, textColor=MUTED)
PT = sty(fontSize=8, leading=10)
H1 = sty(fontName="DVB", fontSize=15, leading=19, textColor=ACC)
H2 = sty(fontName="DVB", fontSize=10.5, leading=14, spaceBefore=9, spaceAfter=3, textColor=ACC)
MONO = sty(fontName="DVM", fontSize=6.6, leading=8.4)


def tbl(data, widths, head=True, font=8, zebra=False, align_right_from=None):
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    s = [("FONT", (0, 0), (-1, -1), "DV", font), ("TEXTCOLOR", (0, 0), (-1, -1), INK),
         ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2.2),
         ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2), ("LEFTPADDING", (0, 0), (-1, -1), 4),
         ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("LINEBELOW", (0, -1), (-1, -1), 0.5, RULE)]
    if head:
        s += [("FONT", (0, 0), (-1, 0), "DVB", font), ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
              ("BACKGROUND", (0, 0), (-1, 0), TINT)]
    if zebra:
        for i in range(1 if head else 0, len(data)):
            if i % 2 == 0:
                s.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f8f7f4")))
    if align_right_from is not None:
        s.append(("ALIGN", (align_right_from, 0), (-1, -1), "RIGHT"))
    t.setStyle(TableStyle(s))
    return t


def chart(w=170 * mm, h=62 * mm):
    d = Drawing(w, h)
    l, r, b, t = 26, 6, 26, 10
    pw, ph = w - l - r, h - b - t
    lo, hi = -12, 16
    y = lambda v: b + (v - lo) / (hi - lo) * ph
    for g in range(-10, 16, 5):
        d.add(Line(l, y(g), l + pw, y(g), strokeColor=colors.HexColor("#e4e2dc"), strokeWidth=0.4))
        d.add(String(l - 4, y(g) - 2.5, de(g, 0), fontName="DV", fontSize=6.5, fillColor=MUTED, textAnchor="end"))
    for g, lab in [(5, "+5 °C"), (-3, "−3 °C"), (-10, "−10 °C")]:
        d.add(Line(l, y(g), l + pw, y(g), strokeColor=INK, strokeWidth=0.6, strokeDashArray=[2, 2]))
        d.add(String(l + pw - 1, y(g) + 1.8, lab, fontName="DV", fontSize=6, fillColor=INK, textAnchor="end"))
    bw = pw / len(rows)
    for i, x in enumerate(rows):
        if x["tmk"] is None:
            continue
        v = x["tmk"]
        y0, y1 = sorted([y(0), y(v)])
        d.add(Rect(l + i * bw + 0.25, y0, max(bw - 0.5, 0.3), max(y1 - y0, 0.4),
                   fillColor=COL[x["c"]], strokeColor=None))
    d.add(Line(l, y(0), l + pw, y(0), strokeColor=MUTED, strokeWidth=0.5))
    i = 0
    for (yy, m) in months:
        d.add(String(l + i * bw + 2, b - 10, MN[m], fontName="DV", fontSize=6.5, fillColor=MUTED))
        d.add(Line(l + i * bw, b - 3, l + i * bw, b + ph, strokeColor=colors.HexColor("#d6d4cd"), strokeWidth=0.4))
        i += sum(1 for x in rows if x["d"].year == yy and x["d"].month == m)
    d.add(String(4, b + ph / 2, "°C", fontName="DV", fontSize=6.5, fillColor=MUTED))
    lx = l
    for k, lab in [("A", f"A  −3 < T < +5 °C ({cnt['A']} KT)"), ("B", f"B  −10 ≤ T ≤ −3 °C ({cnt['B']} KT)"),
                   ("C", f"C  T < −10 °C ({cnt['C']} KT)"), ("D", f"D  T ≥ +5 °C ({cnt['D']} KT)")]:
        d.add(Rect(lx, 3, 7, 7, fillColor=COL[k], strokeColor=None))
        d.add(String(lx + 10, 4, lab, fontName="DV", fontSize=6.6, fillColor=INK))
        lx += 112
    return d


def on_page(c, doc):
    c.saveState()
    c.setFont("DV", 7)
    c.setFillColor(MUTED)
    c.drawString(18 * mm, 10 * mm, "Anlage zu NA 98 – Winterbau KARLA · Witterungsnachweis Lufttemperatur DWD-Station Rheinstetten (04177)")
    c.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Seite {doc.page}")
    c.setStrokeColor(RULE)
    c.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
    c.restoreState()


story = []
story += [Paragraph("Anlage zu Nachtrag NA 98 – Winterbau KARLA", sty(fontSize=9, textColor=MUTED)),
          Paragraph("Witterungsnachweis Lufttemperatur", H1),
          Paragraph("Zeitraum 01.11.2025 – 31.03.2026 (151 KT) · DWD-Messstation Rheinstetten, Stations-ID 04177 · Datenabruf und Auswertung am 04.11.2026", sty(textColor=MUTED)),
          Spacer(1, 6)]

ok_ab = cnt["AB"] == NA98["AB"]
summary = [
    ["Kennwert", "NA 98 (iTWO)", "DWD-Messdaten", "Abweichung", "Ergebnis"],
    ["Betrachtungszeitraum", f"{NA98['KT']} KT", f"{N} KT", "±0 KT", "bestätigt"],
    ["Klasse A  (−3 °C < T < +5 °C)", f"{NA98['A']} KT", f"{cnt['A']} KT", (f"{cnt['A'] - NA98['A']:+d} KT" if cnt['A'] != NA98['A'] else '±0 KT'),
     "bestätigt" if cnt["A"] == NA98["A"] else "NICHT bestätigt"],
    ["Klasse B  (−10 °C ≤ T ≤ −3 °C)", f"{NA98['B']} KT", f"{cnt['B']} KT", (f"{cnt['B'] - NA98['B']:+d} KT" if cnt['B'] != NA98['B'] else '±0 KT'),
     "bestätigt" if cnt["B"] == NA98["B"] else "NICHT bestätigt"],
    ["Summe A + B", f"{NA98['AB']} KT", f"{cnt['AB']} KT", (f"{cnt['AB'] - NA98['AB']:+d} KT" if cnt['AB'] != NA98['AB'] else '±0 KT'),
     "bestätigt" if ok_ab else "NICHT bestätigt"],
    ["Klasse C  (T < −10 °C)", "–", f"{cnt['C']} KT", "", ""],
    ["Klasse D  (T ≥ +5 °C)", "–", f"{cnt['D']} KT", "", ""],
    ["Fehlende Tagesmittel", "–", f"{len(missing)} KT", "", ""],
]
t = tbl(summary, [58 * mm, 26 * mm, 28 * mm, 24 * mm, 38 * mm])
st_ = []
for i, row in enumerate(summary[1:], start=1):
    if row[4] == "NICHT bestätigt":
        st_ += [("TEXTCOLOR", (4, i), (4, i), WARN), ("FONT", (4, i), (4, i), "DVB", 8)]
    elif row[4] == "bestätigt":
        st_ += [("TEXTCOLOR", (4, i), (4, i), OK)]
t.setStyle(TableStyle(st_ + [("ALIGN", (1, 0), (3, -1), "RIGHT")]))
story += [Paragraph("Ergebnis auf einen Blick", H2), t, Spacer(1, 5)]
e3 = ", ".join(x["d"].strftime("%d.%m.%Y") for x in edge_m3)

story.append(Paragraph(
    f"<b>Die in NA 98 angesetzten {NA98['A']} Tage in Klasse A und {NA98['B']} Tage in Klasse B sind durch die Messdaten "
    f"bestätigt.</b> Klassenzuordnung gemäß LV-Kategorien »+5 °C bis −3 °C« (A) und »−3 °C bis −10 °C« (B); der Grenzwert "
    f"−3,0 °C gehört zur kälteren Kategorie B. Betroffen sind {len(edge_m3)} Tage mit exakt −3,0 °C ({e3}); würden diese "
    f"Klasse A zugeordnet, ergäben sich {alt_A} / {alt_B} bei unveränderter Summe A + B. "
    f"Hinweis: Am 16.01.2026 betrug das Tagesmittel exakt +5,0 °C; dieser Tag ist Klasse D zugeordnet (T ≥ +5 °C).", P))

story.append(Paragraph("1  Datenquelle", H2))
src = [
    ["Messstation", Paragraph("Rheinstetten, DWD-Stations-ID <b>04177</b>, 48,9726° N / 8,3301° O, 116 m ü. NHN; "
                              "Lufttemperatur 2 m über Grund, Sensor PT 100 (lt. DWD-Metadaten). Keine Ersatz- oder Nachbarstation.", PT)],
    ["Primärquelle (maßgebend)", Paragraph(f"Deutscher Wetterdienst, Climate Data Center (CDC), Tageswerte »KL«, Datensatz recent:<br/>"
                                           f"<font name='DVM' size='6.8'>{URL_KL}</font><br/>Datei {KL_NAME}; Spalten TMK (Tagesmittel), "
                                           f"TNK (Minimum), TXK (Maximum), QN_4 (Qualitätsniveau). Lizenz: CC BY 4.0, © DWD.", PT)],
    ["Kontrolldaten DWD", Paragraph(f"Stundenwerte Lufttemperatur: <font name='DVM' size='6.8'>{URL_TU}</font><br/>"
                                    f"10-Minuten-Werte: <font name='DVM' size='6.8'>{URL_TU10}</font><br/>"
                                    f"Tageswerte historical (bis 31.12.2025): <font name='DVM' size='6.8'>{URL_KL_HIST}</font>", PT)],
    ["Interaktives Archiv OtterWetter", Paragraph(
        f"<font name='DVM' size='6.8'>{URL_OTTER}</font><br/>Auswahl Temperatur / Monat / Durchschnitt, Termine Nov 2025 – Mär 2026 "
        f"(Teilen-Link: <font name='DVM' size='6.2'>{URL_OTTER_SEL}</font>). Exportiert: »Als CSV exportieren« (Tagesdurchschnitt) "
        f"und »Genaue Stundenwerte als CSV exportieren«; Dateien unverändert unter Quelldateien/OtterWetter abgelegt.", PT)],
    ["Abruf", Paragraph("04.11.2026; SHA-256-Prüfsummen aller Dateien siehe Abschnitt 8.", PT)],
]
src = [[Paragraph(a, sty(fontName="DVB", fontSize=8, leading=10)), b] for a, b in src]
story.append(tbl(src, [36 * mm, 138 * mm], head=False))

story.append(Paragraph("2  Vergleichszeitraum", H2))
story.append(Paragraph(f"01.11.2025 bis einschließlich 31.03.2026 = 30 + 31 + 31 + 28 + 31 = <b>{N} Kalendertage</b>.", P))

story.append(Paragraph("3  Auswertungsmethode", H2))
story.append(Paragraph(
    "Maßgebend ist das vom DWD veröffentlichte Tagesmittel der Lufttemperatur <b>TMK</b> (lt. DWD-Metadaten arithmetisches Mittel "
    "aus mindestens 21 Stundenwerten, Bezugstag 00–24 UTC); Tagesminimum TNK und Tagesmaximum TXK ebenfalls 00–24 UTC. "
    "Die Werte werden unverändert mit 0,1 K Auflösung übernommen und ohne Rundung mit den Klassengrenzen verglichen. "
    "Der Grenzwert −3,0 °C gehört zur kälteren Kategorie B (LV »−3 °C bis −10 °C«), +5,0 °C zu D. Es werden keine Werte interpoliert, ersetzt oder geschätzt. "
    "Fehlende Tagesmittel (DWD-Kennung −999 oder fehlender Datensatz) erhalten den Status »fehlt«, keine Klasse und werden "
    "nie als 0 °C gewertet; Anteile werden auf die gültigen Messtage bezogen. Die Auswertung erfolgt automatisiert mit dem "
    "beigefügten Skript (Skripte/na98_auswertung.py) direkt aus den unveränderten Quelldateien.", P))
story.append(Spacer(1, 4))
story.append(KeepTogether(tbl([["Klasse", "Grenzen Tagesmitteltemperatur T", "Grenztag-Regel"],
                  ["A", "−3 °C < T < +5 °C", "T = +5,0 °C → D"],
                  ["B", "−10 °C ≤ T ≤ −3 °C", "T = −3,0 °C → B;  T = −10,0 °C → B"],
                  ["C", "T < −10 °C", "–"],
                  ["D", "T ≥ +5 °C", "T = +5,0 °C → D"]], [18 * mm, 60 * mm, 96 * mm])))

story.append(Paragraph("4  Fehlende Messwerte und Datenqualität", H2))
cv = caveat[0] if caveat else None
qtext = (f"<b>Fehlende Tagesmittel: {len(missing)} von {N} Tagen.</b> TMK, TNK und TXK liegen für alle {N} Tage vor "
         f"(die DWD-Fehldatenliste der Station weist im Zeitraum keine Temperaturlücken aus). ")
if cv:
    qtext += (f"<b>Hinweis {cv['d'].strftime('%d.%m.%Y')}:</b> Der DWD veröffentlicht TMK = {de(cv['tmk'])} °C (Klasse {cv['c']}), "
              f"die Stunden- und 10-Minuten-Reihen der Station sind an diesem Tag jedoch lückenhaft ({cv['n_h']}/24 Stundenwerte, "
              f"Lücke 01–11 UTC). Die Herleitung des Tagesmittels ist aus den veröffentlichten Rohdaten daher nicht nachprüfbar; "
              f"das Mittel der vorhandenen Stundenwerte ({de(cv['mean_h'])} °C) ist wegen der fehlenden Nachtstunden nicht "
              f"repräsentativ. Der Tag ist in der Tagestabelle als »gültig mit Vorbehalt« gekennzeichnet. Ohne diesen Tag: "
              f"A {cnt_ex['A']} / B {cnt_ex['B']} / C {cnt_ex['C']} / D {cnt_ex['D']} bei {len(excl)} vollständig belegten Tagen "
              f"(A + B = {pct(cnt_ex['A'] + cnt_ex['B'], len(excl))}). ")
qtext += (f"Qualitätsniveau aller Tage: QN 9 (DWD-Routineprüfung erfolgt, Daten noch nicht endgültig korrigiert). "
          f"Abgleich Nov./Dez. 2025 mit dem DWD-Datensatz historical: {len(overlap)} Tage, "
          f"{'keine Abweichungen' if not hist_diff else str(len(hist_diff)) + ' Abweichungen'}.")
story.append(Paragraph(qtext, P))
story.append(Spacer(1, 3))
story.append(Paragraph(
    f"<b>OtterWetter-Export:</b> Die exportierten Stundenwerte sind DWD-Messwerte derselben Station in Ortszeit (MEZ/MESZ): "
    f"{o_match} von {o_match + o_mis} belegten Stunden stimmen exakt mit den DWD-Stundenwerten überein ({o_empty} Stunden leer). "
    f"Der exportierte <i>Tagesdurchschnitt</i> ist dagegen auf ganze Grad gerundet und weicht im Mittel um "
    f"{de(st.mean(o_diff), 1)} K (max. {de(max(o_diff), 1)} K) vom DWD-Tagesmittel ab; an {o_cls} Tagen ergäbe sich eine andere "
    f"Klasse. Diese Werte sind für die Klassenzuordnung ungeeignet und wurden nur als Quelldatei dokumentiert, nicht ausgewertet.", P))

story.append(Paragraph("5  Ergebnisse", H2))
res = [["Klasse", "Grenzen", "Tage", "Anteil an 151 KT", "Anteil an gültigen Messtagen"]]
for k, g in [("A", "−3 < T < +5 °C"), ("B", "−10 ≤ T ≤ −3 °C"), ("C", "T < −10 °C"), ("D", "T ≥ +5 °C")]:
    res.append([k, g, str(cnt[k]), pct(cnt[k], N), pct(cnt[k], NV)])
res.append(["A + B", "−10 ≤ T < +5 °C", str(cnt["AB"]), pct(cnt["AB"], N), pct(cnt["AB"], NV)])
res.append(["fehlt", "–", str(len(missing)), pct(len(missing), N), "–"])
res.append(["Summe", "", str(N), "100,0 %", f"{NV} gültige Tage"])
t = tbl(res, [18 * mm, 40 * mm, 18 * mm, 46 * mm, 52 * mm], align_right_from=2)
t.setStyle(TableStyle([("FONT", (0, 5), (-1, 5), "DVB", 8), ("LINEABOVE", (0, 7), (-1, 7), 0.8, INK)]))
story.append(t)
story.append(Spacer(1, 6))
mt = [["Monat", "KT", "fehlt", "A", "B", "C", "D", "Ø TMK °C"]] + \
     [[m[0], m[1], m[2], m[3], m[4], m[5], m[6], de(m[7])] for m in mon] + \
     [["Summe", N, len(missing), cnt["A"], cnt["B"], cnt["C"], cnt["D"], de(st.mean(x["tmk"] for x in valid))]]
t = tbl([[str(c) for c in r] for r in mt], [30 * mm] + [17 * mm] * 6 + [24 * mm], align_right_from=1)
t.setStyle(TableStyle([("FONT", (0, -1), (-1, -1), "DVB", 8), ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK)]))
story.append(t)
story.append(Spacer(1, 6))
story.append(Paragraph("Tagesmitteltemperatur TMK je Kalendertag, eingefärbt nach Temperaturklasse", sty(fontName="DVB", fontSize=8.5)))
story.append(chart())

story.append(Paragraph("6  Prüfung der Kalkulationsgrundlage NA 98", H2))
story.append(Paragraph(
    f"Betrachtungszeitraum ({N} KT), Klasse A ({cnt['A']} KT), Klasse B ({cnt['B']} KT) und Summe A + B ({cnt['AB']} KT) "
    f"stimmen mit NA 98 überein. Die Zuordnung hängt an den Grenztagen mit T = −3,0 °C ({e3}): Sie sind gemäß "
    f"LV-Kategorie »−3 °C bis −10 °C« der Klasse B zugeordnet. Bei Zuordnung zu A ergäben sich {alt_A} / {alt_B}. "
    f"Der Tag 16.01.2026 (T = +5,0 °C) ist Klasse D zugeordnet; bei Zuordnung zur Kategorie »+5 °C bis −3 °C« wären es "
    f"A = {cnt['A'] + 1} KT und A + B = {cnt['AB'] + 1} KT. "
    f"Zum Vorbehaltstag {cv['d'].strftime('%d.%m.%Y') if cv else ''} siehe Abschnitt 4.", P))

story.append(Paragraph(f"7  Übertragung auf den Prognosezeitraum von {N} KT", H2))
fac = N / NV
story.append(Paragraph(
    f"Alle {N} Kalendertage haben ein gültiges Tagesmittel; die Anteile an den gültigen Messtagen sind damit identisch mit den "
    f"Anteilen am Gesamtzeitraum, Hochrechnungsfaktor {N}/{NV} = {de(fac, 3)}: A {pct(cnt['A'], NV)} × {N} KT = {cnt['A']} KT; "
    f"B {pct(cnt['B'], NV)} × {N} KT = {cnt['B']} KT; A + B {pct(cnt['AB'], NV)} × {N} KT = {cnt['AB']} KT. "
    f"<b>Ist der Prognosezeitraum mit dem Betrachtungszeitraum 01.11.2025–31.03.2026 identisch, handelt es sich um einen "
    f"Ist-Nachweis; die Übertragung ist sachgerecht</b>, weil Messtage und Kalendertage deckungsgleich sind und keine "
    f"Hochrechnung erforderlich ist.", P))
story.append(Spacer(1, 3))
story.append(Paragraph(
    f"Soll der Anteil dagegen auf einen <i>anderen bzw. künftigen</i> Winterzeitraum übertragen werden, ist ein Einzelwinter "
    f"nur eine Stichprobe. Vergleich derselben Station (Daten seit Neuaufnahme 28.10.2008, {len(wv)} vollständige Winter "
    f"Nov.–März 2008/09–2025/26, gleiche Methode): A + B im Mittel {de(100 * st.mean(share['AB']))} % "
    f"(≈ {de(N * st.mean(share['AB']), 0)} KT von {N}), Spanne {de(100 * min(share['AB']))}–{de(100 * max(share['AB']))} %; "
    f"B im Mittel {de(100 * st.mean(share['B']))} % (≈ {de(N * st.mean(share['B']), 0)} KT), Spanne 0–{max(w['B'] for w in wv)} KT; "
    f"C im Mittel {de(100 * st.mean(share['C']))} %. Der Winter 2025/26 liegt mit {pct(cnt['AB'], NV)} (A + B) nahe am "
    f"Mehrjahresmittel und ist für den Gesamtansatz A + B plausibel. Der B-Anteil schwankt dagegen stark von Jahr zu Jahr "
    f"und lag 2025/26 unter dem Mittel; eine getrennte Prognose der B-Tage aus nur einem Winter ist nicht belastbar. "
    f"Der Mehrjahresvergleich ist eine Plausibilitätsinformation (kürzer als eine 30-jährige Klimanormalperiode) und "
    f"nicht Grundlage der obigen Ist-Werte.", P))
wt = [["Winter", "KT", "A", "B", "C", "D", "A+B %"]] + \
     [[w["w"], w["n"], w["A"], w["B"], w["C"], w["D"], de(100 * (w["A"] + w["B"]) / w["v"])] for w in winters]
wtt = tbl([[str(c) for c in r] for r in wt], [20 * mm] + [12 * mm] * 5 + [16 * mm], font=6.8, align_right_from=1)
wtt.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 0.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.8),
                         ("FONT", (0, -1), (-1, -1), "DVB", 6.8)]))
story.append(Spacer(1, 4))
story.append(KeepTogether([Paragraph("Mehrjahresvergleich DWD-Station Rheinstetten, Tage je Klasse (Nov.–März)", PS), wtt]))

story.append(Paragraph("iTWO-T-Zeile (Vorschlag)", H2))
it = Table([[Paragraph(ITWO_T, sty(fontSize=8.5, leading=11.5))]], colWidths=[174 * mm])
it.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, ACC), ("BACKGROUND", (0, 0), (-1, -1), TINT),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
story.append(it)

story.append(Paragraph("8  Reproduzierbarkeit und Dateien", H2))
story.append(Paragraph(
    "Nachvollzug: (1) DWD-Datei von der o. g. URL laden und mit der Prüfsumme vergleichen (Inhalt kann sich durch DWD-Korrekturen "
    "ändern; maßgebend ist der Abrufstand 04.11.2026), (2) in produkt_klima_tag_…_04177.txt die Zeilen MESS_DATUM 20251101 bis "
    "20260331 filtern, (3) Spalte TMK nach Abschnitt 3 klassieren, (4) je Klasse zählen. Das Skript führt genau diese Schritte "
    "aus und prüft, dass NA98_DWD_Rheinstetten_Rohdaten.csv byte-identisch mit der DWD-Produktdatei ist.", P))
story.append(Spacer(1, 3))
story.append(KeepTogether(tbl([["Datei", "SHA-256"]] + [[Paragraph(n, sty(fontSize=6.8, leading=8.4)), Paragraph(h, MONO)] for n, h in HASHES],
                 [78 * mm, 96 * mm], font=6.8)))

# Anhang: Tageswerte
story.append(PageBreak())
story.append(Paragraph("Anhang  Tageswerte 01.11.2025 – 31.03.2026 (DWD TMK / TNK / TXK, °C)", H2))
story.append(Paragraph("Status: g = gültig; G = gültig, Grenzwert exakt −3,0 °C bzw. +5,0 °C; V = gültig mit Vorbehalt (Abschnitt 4); "
                       "f = fehlt. Vollständige Statustexte in NA98_Temperaturauswertung_2025-2026.csv.", PS))
story.append(Spacer(1, 3))


def short(x):
    s = x["status"]
    return "f" if s.startswith("fehlt") else "V" if "Vorbehalt" in s else "G" if "Grenzwert" in s else "g"


half = (len(rows) + 1) // 2
hdr = ["Datum", "Mittel", "Min", "Max", "Kl.", "St."]
data = [hdr + [""] + hdr]
for i in range(half):
    a = rows[i]
    L = [a["d"].strftime("%d.%m.%Y"), de(a["tmk"]) if a["tmk"] is not None else "–", de(a["tnk"]), de(a["txk"]), a["c"] or "–", short(a)]
    if i + half < len(rows):
        b_ = rows[i + half]
        R = [b_["d"].strftime("%d.%m.%Y"), de(b_["tmk"]) if b_["tmk"] is not None else "–", de(b_["tnk"]), de(b_["txk"]), b_["c"] or "–", short(b_)]
    else:
        R = [""] * 6
    data.append(L + [""] + R)
cw = [17 * mm, 12 * mm, 12 * mm, 12 * mm, 8 * mm, 8 * mm]
t = Table(data, colWidths=cw + [6 * mm] + cw, repeatRows=1)
ts = [("FONT", (0, 0), (-1, -1), "DV", 6.5), ("FONT", (0, 0), (-1, 0), "DVB", 6.5),
      ("TOPPADDING", (0, 0), (-1, -1), 0.35), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.35),
      ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
      ("ALIGN", (1, 0), (3, -1), "RIGHT"), ("ALIGN", (8, 0), (10, -1), "RIGHT"),
      ("ALIGN", (4, 0), (5, -1), "CENTER"), ("ALIGN", (11, 0), (12, -1), "CENTER"),
      ("LINEBELOW", (0, 0), (5, 0), 0.6, INK), ("LINEBELOW", (7, 0), (12, 0), 0.6, INK)]
for i in range(1, len(data)):
    for off, x in ((0, rows[i - 1]), (7, rows[i - 1 + half] if i - 1 + half < len(rows) else None)):
        if x is None:
            continue
        if x["c"] in ("B", "C"):
            ts.append(("BACKGROUND", (off, i), (off + 5, i), colors.HexColor("#e6e2fa")))
        if short(x) in ("G", "V"):
            ts.append(("FONT", (off, i), (off + 5, i), "DVB", 6.5))
        if x["d"].day == 1 and i > 1:
            ts.append(("LINEABOVE", (off, i), (off + 5, i), 0.4, RULE))
t.setStyle(TableStyle(ts))
story.append(t)

doc = SimpleDocTemplate(os.path.join(BASE, "NA98_Interne_Pruefung.pdf"), pagesize=A4,
                        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm, bottomMargin=18 * mm,
                        title="NA 98 – Witterungsnachweis Lufttemperatur DWD Rheinstetten 04177",
                        author="Auswertung NA 98 Winterbau KARLA", subject="Temperaturklassen 01.11.2025–31.03.2026")
doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
print("PDF erstellt")
