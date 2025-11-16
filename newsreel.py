import feedparser
from bs4 import BeautifulSoup
import copy
from datetime import datetime

from textBlock import toTeletextBlock
from page import exportTTI, loadTTI
from legaliser import pageLegaliser

# Finse dag- en maandnamen
FINNISH_DAYS = ["MAANANTAI", "TIISTAI", "KESKIVIIKKO", "TORSTAI", "PERJANTAI", "LAUANTAI", "SUNNUNTAI"]
FINNISH_MONTHS = ["TAMMIKUU", "HELMIKUU", "MAALISKUU", "HUHTIKUU", "TOUKOKUU", "KESÄKUU", 
                  "HEINÄKUU", "ELOKUU", "SYYSKUU", "LOKAKUU", "MARRASKUU", "JOULUKUU"]

def get_finnish_day():
    """Geeft de huidige dag in het Fins terug"""
    now = datetime.now()
    return FINNISH_DAYS[now.weekday()]

def get_finnish_date():
    """Geeft volledige datum in het Fins (bijv. MAANANTAI 16.11.)"""
    now = datetime.now()
    day_name = FINNISH_DAYS[now.weekday()]
    return f"{day_name} {now.day}.{now.month}."

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

# RSS feed van Yle
rss_feed_url = "https://yle.fi/rss/uutiset/paauutiset"
max_articles = 10

def fetch_articles():
    all_articles = []
    
    # Parse de Yle RSS feed
    parsed = feedparser.parse(rss_feed_url)
    count = 0
    
    for entry in parsed["entries"]:
        if count >= max_articles:
            break
        
        # Haal de titel op
        clean_title = entry.get("title", "Geen titel").strip()
        
        # Yle gebruikt 'description' voor de samenvatting
        if "description" in entry:
            article_text = entry["description"]
        else:
            article_text = clean_title  # fallback
        
        # Verwijder soft hyphen (U+00AD)
        article_text = article_text.replace("\u00AD", "")
        
        # Parse met BeautifulSoup
        soup = BeautifulSoup(article_text, "lxml")
        
        # Voor Yle is description plain text, dus we maken één paragraaf
        text = soup.get_text().strip()
        paragraphs = [text] if text else ["Geen inhoud beschikbaar"]
        
        all_articles.append({
            "title": clean_title,
            "content": paragraphs
        })
        count += 1
    
    return all_articles

def create_newsreel_page(articles, page_number=185):
    template = loadTTI("newsreel_page.tti")
    subpages = []

    # Intro subpagina
    intro_lines = [
        {"line": 3, "text": "        KATSOT HBN-teksti-TV:tä", "align": "center", "colour": "white"},
        {"line": 5, "text": "UUTISIA JA TIETOJA", "align": "center", "colour": "white"},
        {"line": 7, "text": "    YLE", "align": "center", "colour": "yellow"},
        {"line": 11, "text": " Täysi palvelu tarjoaa paljon", "align": "left", "colour": "white"},
        {"line": 12, "text": "  sivuja ja on saatavilla", "align": "left", "colour": "white"},
        {"line": 13, "text": "   kuka tahansa, jolla on sopiva", "align": "left", "colour": "white"},
        {"line": 14, "text": "  televisiovastaanotin.", "align": "left", "colour": "white"}
    ]
    intro_packets = copy.deepcopy(template["subpages"][0]["packets"])
    for item in intro_lines:
        block = toTeletextBlock(
            input={"content": [{"align": item["align"], "content": [{"colour": item["colour"], "text": item["text"]}]}]},
            line=item["line"]
        )
        intro_packets += block
    subpages.append({"packets": intro_packets})

    # Artikel subpagina's
    for article in articles:
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

        subpages.append({"packets": packets})

    # Exporteer de pagina
    page = {"number": page_number, "subpages": subpages, "control": {"cycleTime": "25,T"}}
    
    # Vervang DAY/DATE placeholders VOOR het exporteren
    page = vervang_datum_in_tti(page)
    
    exportTTI(pageLegaliser(page))
    print(f"Newsreel with {len(subpages)} subpages saved as page {page_number}.")

def run_newsreel():
    """Hoofdfunctie om de newsreel te genereren"""
    print("=== NEWSREEL WITH YLE NEWS ===")
    articles = fetch_articles()
    create_newsreel_page(articles)
    print("Done.")

if __name__ == "__main__":
    run_newsreel()