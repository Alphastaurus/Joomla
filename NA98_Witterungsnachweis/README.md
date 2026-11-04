# NA 98 – Winterbau KARLA: Witterungsnachweis Lufttemperatur

DWD-Station Rheinstetten (Stations-ID 04177), 01.11.2025–31.03.2026 (151 KT), Datenabruf 04.11.2026.

| Datei | Inhalt |
|---|---|
| `NA98_DWD_Rheinstetten_Rohdaten.csv` | DWD-Produktdatei `produkt_klima_tag_20250503_20261103_04177.txt`, byte-identisch (nur umbenannt) |
| `NA98_Temperaturauswertung_2025-2026.csv` | 151 Tage mit Tagesmittel/-min/-max, Klasse, Datenstatus (Semikolon, Dezimalkomma, UTF-8) |
| `NA98_Witterungsnachweis.pdf` | Anlage für den Auftraggeber: Datenauszug Tageswerte mit Klassierung (erzeugt mit `Skripte/na98_auszug.py`) |
| `NA98_Interne_Pruefung.pdf` | Interner Prüfvermerk: Abgleich NA 98, Quellenvergleich, Mehrjahresvergleich – nicht für den AG |
| `Quelldateien/DWD/*.zip` | DWD-Originaldownloads (KL recent + historical, Stundenwerte TU, 10-min TU) |
| `Quelldateien/OtterWetter/*.csv` | Unveränderte OtterWetter-Exporte (Tagesdurchschnitt + genaue Stundenwerte) |
| `Quelldateien/SHA256SUMS.txt` | Prüfsummen |
| `Skripte/na98_auswertung.py` | Erzeugt Auswertungs-CSV und internen Prüfvermerk aus den Quelldateien (`python3 Skripte/na98_auswertung.py`, benötigt reportlab) |

OtterWetter-Auswahl (Teilen-Link):
https://otterwetter.de/baden-wuerttemberg/rheinstetten/archiv?g=month&m=temperature&v=table&a=avg&d=2025-11%2C2025-12%2C2026-01%2C2026-02%2C2026-03
