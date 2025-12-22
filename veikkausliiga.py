import copy
from veikkausliiga_scraper import AiScoreScraper
from textBlock import tableRow, toTeletextBlock
from page import exportTTI, loadTTI
from legaliser import pageLegaliser

print("="*70)
print("VEIKKAUSLIIGA TELETEXT PAGE GENERATOR")
print("="*70)

scraper = AiScoreScraper()
standings = scraper.scrape_standings()

template = loadTTI("veikkausliiga_page.tti")

teletextPage = {
    "number": 314,
    "subpages": [{
        "packets": copy.deepcopy(template["subpages"][0]["packets"])
    }]
}

# Check of er data is
if standings and len(standings) > 0:
    # ===== NORMALE TABEL MET DATA =====
    print(f"\n✓ Veikkausliiga data gevonden: {len(standings)} teams")
    print("  Genereren sarjataulukko...")
    
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
    
    print(f"  ✓ Tabel aangemaakt met {len(standings)} teams")

else:
    # ===== GEEN DATA - "KAUSI PÄÄTTYNYT" PAGINA =====
    print("\n⚠ Geen Veikkausliiga data beschikbaar")
    print("  Seizoen is afgelopen of nog niet begonnen")
    print("  Genereren 'KAUSI PÄÄTTYNYT' pagina...")
    
    line = 11  # Midden van de pagina
    
    # Grote gele tekst: KAUSI PÄÄTTYNYT
    season_ended_block = toTeletextBlock(
        input={"content": [{"align": "center", "content": [{"colour": "yellow", "text": "KAUSI PÄÄTTYNYT"}]}]},
        line=line
    )
    teletextPage["subpages"][0]["packets"] += season_ended_block
    
    line += 2
    
    # Witte tekst: Sarjataulukko ei saatavilla
    info_block = toTeletextBlock(
        input={"content": [{"align": "center", "content": [{"colour": "white", "text": "Sarjataulukko ei saatavilla"}]}]},
        line=line
    )
    teletextPage["subpages"][0]["packets"] += info_block
    
    print("  ✓ 'Season ended' pagina aangemaakt")

teletextPage["subpages"][0]["packets"]

# Exporteer
exportTTI(pageLegaliser(teletextPage))

print("\n" + "="*70)
print("✓ Veikkausliiga Teletext pagina 314 gegenereerd")
print("="*70)