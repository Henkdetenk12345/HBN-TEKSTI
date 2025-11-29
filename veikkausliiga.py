import copy
from veikkausliiga_scraper import AiScoreScraper
from textBlock import tableRow
from page import exportTTI, loadTTI
from legaliser import pageLegaliser

scraper = AiScoreScraper()
standings = scraper.scrape_standings()

if not standings:
    print("Geen Veikkausliiga data gevonden.")
    exit()

template = loadTTI("veikkausliiga_page.tti")

teletextPage = {
    "number": 314,
    "subpages": [{
        "packets": copy.deepcopy(template["subpages"][0]["packets"])
    }]
}

line = 6

for t in standings:

    rowDict = {
        "P": t["position"],
        "C": t["team"][:13],   # clubnaam inkorten naar 13 chars
        "Pt": t["points"],
        "G": t["goals"],
        "WDG": f"{t['wins']}/{t['draws']}/{t['losses']}"
    }

    row = tableRow(
        [
            {"width": 2,  "data": "P",   "colour": "yellow", "align": "right"},
            {"width": 13, "data": "C",   "colour": "cyan"},
            {"width": 3,  "data": "Pt",  "colour": "yellow", "align": "right"},
            {"width": 7,  "data": "G",   "colour": "white"},
            {"width": 6,  "data": "WDG", "colour": "white"},
        ],
        rowDict
    )

    tt_block = [{"number": line, "text": row}]

    if (line + len(tt_block)) > 22:
        break

    teletextPage["subpages"][0]["packets"] += tt_block
    line += len(tt_block)

exportTTI(pageLegaliser(teletextPage))

print("Veikkausliiga Teletextpagina 314 gegenereerd.")
