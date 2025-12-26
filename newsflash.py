import feedparser
import copy
from datetime import datetime
import unicodedata
from page import loadTTI, exportTTI
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

def clean_text_aggressive(text):
    """Verwijdert/normaliseert alle problematische karakters voor teletext"""
    if not text:
        return text
    
    # Vervang problematische karakters VOOR normalisatie
    replacements = {
        '\u2013': '-',  # en-dash
        '\u2014': '-',  # em-dash
        '\u2018': "'",  # left single quotation mark
        '\u2019': "'",  # right single quotation mark
        '\u201C': '"',  # left double quotation mark
        '\u201D': '"',  # right double quotation mark
        '\u2026': '...',  # horizontal ellipsis
        '\u00AD': '',   # soft hyphen
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
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

def vervang_datum_in_packets(packets):
    """Vervangt DAY en DATE placeholders in packets met Finse datum"""
    dag = get_finnish_day()
    datum = get_finnish_date()
    
    for packet in packets:
        if "text" in packet:
            packet["text"] = packet["text"].replace("DAY", dag)
            packet["text"] = packet["text"].replace("DATE", datum)
    
    return packets

def clean_title_for_ticker(title):
    """Maakt titel geschikt voor ticker (verwijder extra whitespace, soft hyphens, etc.)"""
    if not title:
        return title
    
    # fix: verwijder soft hyphen (U+00AD)
    title = title.strip().replace("\u00AD", "")
    # Dan aggressive cleaning voor alle andere problemen
    title = clean_text_aggressive(title)
    return title

def wrap_text_to_lines(text, max_width=32, max_lines=5):
    """
    Breekt tekst op in meerdere regels, max_width karakters per regel
    """
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        if len(current_line) + len(word) + 1 <= max_width:
            if current_line:
                current_line += " " + word
            else:
                current_line = word
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
            
            if len(lines) >= max_lines:
                break
    
    if current_line and len(lines) < max_lines:
        lines.append(current_line)
    
    return lines

def create_newsflash_subpage(template, headline_text, page_number):
    """
    Creëert een newsflash subpage met de headline tekst
    
    Args:
        template: De geladen TTI template
        headline_text: De headline tekst
        page_number: Het paginanummer waar het volledige artikel staat
    
    Returns:
        Dictionary met subpage packets
    """
    # Maak een kopie van de template packets
    subpage_packets = copy.deepcopy(template["subpages"][0]["packets"])
    
    # Vervang DAY/DATE placeholders
    subpage_packets = vervang_datum_in_packets(subpage_packets)
    
    # Breek de headline op in meerdere regels (max 32 chars breed, max 5 regels voor packets 18-22)
    headline_lines = wrap_text_to_lines(headline_text, max_width=32, max_lines=5)
    
    # Vervang P105 placeholder en voeg headline toe op regels 5-18
    for packet in subpage_packets:
        if "text" in packet:
            # Vervang paginanummer placeholder overal
            packet["text"] = packet["text"].replace("P105", f"P{page_number}")
            
            # Voeg headline tekst toe op packets 18-22 (tussen kolom 5 en 37)
            if 18 <= packet["number"] <= 22:
                line_index = packet["number"] - 18
                
                if line_index < len(headline_lines):
                    # Haal het begin en eind van de regel op (kolom 0-4 en 37-39)
                    prefix = packet["text"][:5] if len(packet["text"]) >= 5 else packet["text"].ljust(5)
                    suffix = packet["text"][37:] if len(packet["text"]) > 37 else ""
                    
                    # Plaats de headline tekst in het midden (kolom 5-36 = 32 karakters)
                    headline_part = headline_lines[line_index].ljust(32)
                    
                    # Combineer alles
                    packet["text"] = prefix + headline_part + suffix
                else:
                    # Lege regel - behoud alleen prefix en suffix
                    prefix = packet["text"][:5] if len(packet["text"]) >= 5 else packet["text"].ljust(5)
                    suffix = packet["text"][37:] if len(packet["text"]) > 37 else ""
                    packet["text"] = prefix + (" " * 32) + suffix
    
    return {"packets": subpage_packets}

def generate_newsflash():
    """
    Hoofdfunctie die alle newsflash subpages genereert voor P180
    """
    
    # Dictionary met alle feeds en hun templates
    feeds_config = [
        {
            "name": "paauutiset",
            "url": "https://yle.fi/rss/uutiset/paauutiset",
            "template": "newsflash_paauutiset.tti",
            "start_page": 102,
            "max_items": 9
        },
        {
            "name": "tuoreimmat",
            "url": "https://yle.fi/rss/uutiset/tuoreimmat",
            "template": "newsflash_tuoreimmat.tti",
            "start_page": 112,
            "max_items": 11
        },
        {
            "name": "politics",
            "url": "https://yle.fi/rss/t/18-220306/fi",
            "template": "newsflash_politics.tti",
            "start_page": 124,
            "max_items": 11
        },
        {
            "name": "talous",
            "url": "https://yle.fi/rss/t/18-204933/fi",
            "template": "newsflash_talous.tti",
            "start_page": 202,
            "max_items": 4
        },
        {
            "name": "urheilu",
            "url": "https://yle.fi/rss/urheilu",
            "template": "newsflash_sport.tti",
            "start_page": 302,
            "max_items": 5
        }
    ]
    
    # Verzamel alle subpages
    all_subpages = []
    
    for feed_config in feeds_config:
        print(f"Processing {feed_config['name']}...")
        
        try:
            # Load de template voor deze categorie
            template = loadTTI(feed_config["template"])
            
            # Download de RSS feed
            news_data = feedparser.parse(feed_config["url"])
            
            # Verwerk elk artikel
            for idx, article in enumerate(news_data['entries']):
                if idx >= feed_config['max_items']:
                    break
                
                # Haal de titel op en maak deze geschikt voor ticker
                headline = clean_title_for_ticker(article["title"])
                
                # Bereken het paginanummer waar het volledige artikel staat
                article_page = feed_config['start_page'] + idx
                
                # Creëer de subpage
                subpage = create_newsflash_subpage(template, headline, article_page)
                
                # Voeg toe aan de lijst
                all_subpages.append(subpage)
                
                print(f"  Added: {headline[:50]}... -> P{article_page}")
        
        except Exception as e:
            print(f"Error processing {feed_config['name']}: {e}")
            continue
    
    # Maak de finale P180 pagina met alle subpages
    if all_subpages:
        newsflash_page = {
            "number": 180,
            "control": {
                "cycleTime": "10,T",  # Cycle time voor newsflash
                "newsFlash": True     # Activeer newsflash mode
            },
            "subpages": all_subpages
        }
        
        print(f"\nGenerating P180 with {len(all_subpages)} subpages...")
        exportTTI(pageLegaliser(newsflash_page))
        print("P180 newsflash page created successfully!")
    else:
        print("No subpages generated - check feed configurations")

def run_newsflash():
    """Convenience functie om te importeren in demo.py"""
    generate_newsflash()

if __name__ == "__main__":
    # Als script direct wordt uitgevoerd
    run_newsflash()
