import feedparser
from bs4 import BeautifulSoup
import copy
from datetime import datetime
import unicodedata

from textBlock import toTeletextBlock, tableRow
from page import exportTTI, loadTTI
from legaliser import pageLegaliser

# Finse dag- en maandnamen
FINNISH_DAYS = ["MAANANTAI", "TIISTAI", "KESKIVIIKKO", "TORSTAI", "PERJANTAI", "LAUANTAI", "SUNNUNTAI"]
FINNISH_MONTHS = ["TAMMIKUU", "HELMIKUU", "MAALISKUU", "HUHTIKUU", "TOUKOKUU", "KESÃ„KUU", 
                  "HEINÃ„KUU", "ELOKUU", "SYYSKUU", "LOKAKUU", "MARRASKUU", "JOULUKUU"]

def get_finnish_day():
    """Geeft de huidige dag in het Fins terug"""
    now = datetime.now()
    return FINNISH_DAYS[now.weekday()]

def get_finnish_date():
    """Geeft volledige datum in het Fins (bijv. MAANANTAI 16.11.)"""
    now = datetime.now()
    day_name = FINNISH_DAYS[now.weekday()]
    return f"{day_name} {now.day}.{now.month}."

def get_intro_template():
    """Bepaalt welke intro template te gebruiken op basis van de datum"""
    now = datetime.now()
    day = now.day
    month = now.month
    
    # 6 december: Independence Day intro
    if month == 12 and day == 6:
        return "independent_intro.tti"
    
    # 29 november t/m 27 december (exclusief 6 december)
    # Let op: 29/11 t/m 31/12 in december, plus 1/12 t/m 27/12
    if month == 11 and day >= 29:
        return "jouluterveiset_intro.tti"
    elif month == 12 and day <= 27 and day != 6:
        return "jouluterveiset_intro.tti"
    
    # Standaard intro voor alle andere dagen
    return "newsreel_intro.tti"

def clean_text_aggressive(text):
    """Verwijdert/normaliseert alle problematische karakters voor teletext"""
    if not text:
        return text
    
    # Normaliseer Unicode (bijv. gecombineerde accenten naar enkele karakters)
    text = unicodedata.normalize('NFKC', text)
    
    # Verwijder alle control characters en invisible characters
    cleaned = []
    for char in text:
        cat = unicodedata.category(char)
        # Cc = Control, Cf = Format, Zs = Space separator
        if cat == 'Cc' or cat == 'Cf':
            # Skip control en format characters
            continue
        elif cat == 'Zs' and char != ' ':
            # Vervang alle niet-standaard spaties met normale spatie
            cleaned.append(' ')
        else:
            cleaned.append(char)
    
    return ''.join(cleaned)

def vervang_datum_in_tti(tti_data):
    """Vervangt DAY en DATE placeholders in TTI data met Finse datum"""
    dag = get_finnish_day()
    datum = get_finnish_date()
    
    # Loop door alle packets en vervang placeholders in de text
    for subpage in tti_data.get("subpages", []):
        for packet in subpage.get("packets", []):
            if "text" in packet:
                packet["text"] = packet["text"].replace("DAY", dag)
                packet["text"] = packet["text"].replace("DATE", datum)
    
    return tti_data

def fetch_articles_from_feed(rss_url, max_articles, clean_aggressive=False):
    """Haal artikelen op van een specifieke RSS feed"""
    all_articles = []
    
    parsed = feedparser.parse(rss_url)
    count = 0
    
    for entry in parsed["entries"]:
        if count >= max_articles:
            break
        
        clean_title = entry.get("title", "Geen titel").strip()
        
        # Gebruik aggressive cleaning voor jalkapallo feed
        if clean_aggressive:
            clean_title = clean_text_aggressive(clean_title)
        
        if "description" in entry:
            article_text = entry["description"]
        else:
            article_text = clean_title
        
        article_text = article_text.replace("\u00AD", "")
        
        # Gebruik aggressive cleaning voor jalkapallo feed
        if clean_aggressive:
            article_text = clean_text_aggressive(article_text)
        
        soup = BeautifulSoup(article_text, "lxml")
        text = soup.get_text().strip()
        paragraphs = [text] if text else ["Geen inhoud beschikbaar"]
        
        all_articles.append({
            "title": clean_title,
            "content": paragraphs
        })
        count += 1
    
    return all_articles

def create_index_subpage(template, headlines, section_title):
    """Maak een index subpagina met headlines"""
    packets = copy.deepcopy(template["subpages"][0]["packets"])
    line = 5
    
    for headline in headlines:
        para_block = toTeletextBlock(
            input={
                "content": [
                    {"align": "left", "content": [{"colour": "white", "text": headline["title"]}]},
                    {"align": "right", "content": [{"colour": "yellow", "text": headline["number"]}]}
                ]
            },
            line=line
        )
        
        if (len(para_block) + line) > 22:
            break
        
        line += len(para_block) + 1
        packets += para_block
    
    return {"packets": packets}

def create_article_subpage(template, article, page_number):
    """Maak een artikel subpagina"""
    packets = copy.deepcopy(template["subpages"][0]["packets"])
    line = 5
    
    # Titel toevoegen
    title_block = toTeletextBlock(
        input={"content": [{"align": "left", "content": [{"colour": "yellow", "text": article["title"]}]}]},
        line=line
    )
    line += len(title_block) + 1
    packets += title_block
    
    # Content toevoegen
    for paragraph in article["content"]:
        para_block = toTeletextBlock(
            input={"content": [{"align": "left", "content": [{"colour": "white", "text": paragraph}]}]},
            line=line
        )
        if line + len(para_block) > 22:
            break
        line += len(para_block) + 1
        packets += para_block
    
    # Voeg paginanummer toe onderaan met hoofdletter P
    page_ref_block = toTeletextBlock(
        input={"content": [{"align": "right", "content": [{"colour": "cyan", "text": f"P{page_number}"}]}]},
        line=23
    )
    packets += page_ref_block
    
    return {"packets": packets}

def create_newsreel_page(page_number=185):
    """Maak de volledige newsreel met alle feeds"""
    subpages = []
    
    # INTRO SUBPAGINA - laad uit TTI template op basis van datum
    intro_filename = get_intro_template()
    print(f"Loading intro template: {intro_filename}")
    intro_template = loadTTI(intro_filename)
    intro_subpage = {"packets": copy.deepcopy(intro_template["subpages"][0]["packets"])}
    subpages.append(intro_subpage)
    print(f"Intro loaded with {len(intro_subpage['packets'])} packets")
    
    # ===== PÃ„Ã„UUTISET (10 subpages: 1 index + 9 artikelen) =====
    print("Fetching PÃ¤Ã¤uutiset...")
    paauutiset_articles = fetch_articles_from_feed("https://yle.fi/rss/uutiset/paauutiset", 9)
    paauutiset_headlines = [{"title": art["title"], "number": str(102 + i)} for i, art in enumerate(paauutiset_articles)]
    
    # Index subpagina voor PÃ¤Ã¤uutiset (zoals p101)
    paauutiset_index_template = loadTTI("paauutiset_index.tti")
    index_subpage = create_index_subpage(paauutiset_index_template, paauutiset_headlines, "PÃ„Ã„UUTISET")
    subpages.append(index_subpage)
    
    # Artikel subpagina's voor PÃ¤Ã¤uutiset
    paauutiset_page_template = loadTTI("paauutiset_page.tti")
    for i, article in enumerate(paauutiset_articles):
        article_subpage = create_article_subpage(paauutiset_page_template, article, 102 + i)
        subpages.append(article_subpage)
    
    # ===== TUOREIMMAT (6 subpages: 1 index + 5 artikelen) =====
    print("Fetching Tuoreimmat...")
    tuoreimmat_articles = fetch_articles_from_feed("https://yle.fi/rss/uutiset/tuoreimmat", 5)
    tuoreimmat_headlines = [{"title": art["title"], "number": str(112 + i)} for i, art in enumerate(tuoreimmat_articles)]
    
    # Index subpagina voor Tuoreimmat (zoals p111)
    tuoreimmat_index_template = loadTTI("tuoreimmat_index.tti")
    index_subpage = create_index_subpage(tuoreimmat_index_template, tuoreimmat_headlines, "TUOREIMMAT")
    subpages.append(index_subpage)
    
    # Artikel subpagina's voor Tuoreimmat
    tuoreimmat_page_template = loadTTI("tuoreimmat_page.tti")
    for i, article in enumerate(tuoreimmat_articles):
        article_subpage = create_article_subpage(tuoreimmat_page_template, article, 112 + i)
        subpages.append(article_subpage)
    
    # ===== URHEILU (6 subpages: 1 index + 5 artikelen) =====
    print("Fetching Urheilu...")
    urheilu_articles = fetch_articles_from_feed("https://yle.fi/rss/urheilu", 5)
    urheilu_headlines = [{"title": art["title"], "number": str(302 + i)} for i, art in enumerate(urheilu_articles)]
    
    # Index subpagina voor Urheilu (zoals p301)
    urheilu_index_template = loadTTI("sportgeneral_index.tti")
    index_subpage = create_index_subpage(urheilu_index_template, urheilu_headlines, "URHEILU")
    subpages.append(index_subpage)
    
    # Artikel subpagina's voor Urheilu
    urheilu_page_template = loadTTI("sportgeneral_page.tti")
    for i, article in enumerate(urheilu_articles):
        article_subpage = create_article_subpage(urheilu_page_template, article, 302 + i)
        subpages.append(article_subpage)
    
    # ===== JALKAPALLO (6 subpages: 1 index + 5 artikelen) - MET AGGRESSIVE CLEANING =====
    print("Fetching Jalkapallo...")
    jalkapallo_articles = fetch_articles_from_feed(
        "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_URHEILU&concepts=18-205598", 
        5, 
        clean_aggressive=True  # Gebruik aggressive cleaning voor jalkapallo!
    )
    jalkapallo_headlines = [{"title": art["title"], "number": str(309 + i)} for i, art in enumerate(jalkapallo_articles)]
    
    # Index subpagina voor Jalkapallo (zoals p308)
    jalkapallo_index_template = loadTTI("jalkapallo_index.tti")
    index_subpage = create_index_subpage(jalkapallo_index_template, jalkapallo_headlines, "JALKAPALLO")
    subpages.append(index_subpage)
    
    # Artikel subpagina's voor Jalkapallo
    jalkapallo_page_template = loadTTI("jalkapallo_page.tti")
    for i, article in enumerate(jalkapallo_articles):
        article_subpage = create_article_subpage(jalkapallo_page_template, article, 309 + i)
        subpages.append(article_subpage)
    
    # ===== VEIKKAUSLIIGA SCORE TABLE (1 subpage) =====
    print("Adding Veikkausliiga score table...")
    try:
        from veikkausliiga_scraper import AiScoreScraper
        
        scraper = AiScoreScraper()
        standings = scraper.scrape_standings()
        
        if standings:
            # Laad de Veikkausliiga template
            veikkausliiga_template = loadTTI("veikkausliiga_page.tti")
            veikkausliiga_packets = copy.deepcopy(veikkausliiga_template["subpages"][0]["packets"])
            
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
                
                veikkausliiga_packets += tt_block
                line += len(tt_block)
            
            # Voeg paginanummer P314 toe rechtsonderaan
            page_ref_block = toTeletextBlock(
                input={"content": [{"align": "right", "content": [{"colour": "cyan", "text": "P314"}]}]},
                line=23
            )
            veikkausliiga_packets += page_ref_block
            
            # Voeg Veikkausliiga subpage toe
            veikkausliiga_subpage = {"packets": veikkausliiga_packets}
            subpages.append(veikkausliiga_subpage)
            print(f"✓ Added Veikkausliiga score table with {len(standings)} teams")
        else:
            print("⚠ No Veikkausliiga data available")
            
    except Exception as e:
        print(f"⚠ Could not add Veikkausliiga score table: {e}")
        import traceback
        traceback.print_exc()
    
    # ===== WEERKAART (3 subpages) =====
    print("Adding weather map subpages...")
    try:
        import weathermap
        
        # Haal de weerkaart subpages op via de functie
        weather_subpages = weathermap.get_weather_subpages("weathermap.tti")
        
        if weather_subpages:
            for weather_subpage in weather_subpages:
                subpages.append(weather_subpage)
            print(f"✓ Added {len(weather_subpages)} weather map subpages with live data")
        else:
            print("⚠ No weather subpages available")
            
    except Exception as e:
        print(f"⚠ Could not add weather map subpages: {e}")
        import traceback
        traceback.print_exc()
    
    # Exporteer de complete newsreel pagina
    page = {
        "number": page_number, 
        "subpages": subpages, 
        "control": {
            "cycleTime": "25,T",
            "erasePage": True,
            "update": True
        }
    }
    page = vervang_datum_in_tti(page)
    exportTTI(pageLegaliser(page))
    
    print(f"\nNewsreel complete!")
    print(f"Total subpages: {len(subpages)}")
    print(f"  - Intro: 1 ({intro_filename})")
    print(f"  - Pääuutiset: 1 index + 9 articles = 10")
    print(f"  - Tuoreimmat: 1 index + 5 articles = 6")
    print(f"  - Urheilu: 1 index + 5 articles = 6")
    print(f"  - Jalkapallo: 1 index + 5 articles = 6")
    print(f"  - Veikkausliiga: 1 score table")
    print(f"  - Weather map: 3 subpages")
    print(f"  = Total: {len(subpages)} subpages")

def run_newsreel():
    """Hoofdfunctie om de newsreel te genereren"""
    print("=== COMPREHENSIVE NEWSREEL WITH ALL YLE FEEDS ===")
    create_newsreel_page()
    print("Done.")

if __name__ == "__main__":
    run_newsreel()