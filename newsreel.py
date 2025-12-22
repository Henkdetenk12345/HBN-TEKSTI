import feedparser
from bs4 import BeautifulSoup
import copy
from datetime import datetime
import unicodedata
import os

from textBlock import toTeletextBlock, tableRow
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

def get_intro_template():
    """Bepaalt welke intro template te gebruiken op basis van de datum"""
    now = datetime.now()
    day = now.day
    month = now.month
    
    # 31 december en 1 januari: New Year intro
    if (month == 12 and day == 31) or (month == 1 and day == 1):
        return "newyear_intro.tti"
    
    # 6 december: Independence Day intro
    if month == 12 and day == 6:
        return "independent_intro.tti"
    
    # 29 november t/m 27 december (exclusief 6 december)
    if month == 11 and day >= 29:
        return "jouluterveiset_intro.tti"
    elif month == 12 and day <= 27 and day != 6:
        return "jouluterveiset_intro.tti"
    
    # Standaard intro voor alle andere dagen
    return "newsreel_intro.tti"

def load_intro(intro_filename):
    """Laad een intro subpage als deze bestaat"""
    if os.path.exists(intro_filename):
        try:
            intro_template = loadTTI(intro_filename)
            intro_subpage = {"packets": copy.deepcopy(intro_template["subpages"][0]["packets"])}
            # Vervang datum placeholders
            for packet in intro_subpage["packets"]:
                if "text" in packet:
                    packet["text"] = packet["text"].replace("DAY", get_finnish_day())
                    packet["text"] = packet["text"].replace("DATE", get_finnish_date())
            print(f"  ✓ Intro loaded: {intro_filename}")
            return intro_subpage
        except Exception as e:
            print(f"  ⚠ Could not load {intro_filename}: {e}")
            return None
    else:
        print(f"  ℹ No intro found: {intro_filename}")
        return None

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
        line=21
    )
    packets += page_ref_block
    
    return {"packets": packets}

def calculate_text_lines(text, width=40):
    """Bereken EXACT hoeveel regels een tekst nodig heeft"""
    if not text:
        return 0
    import math
    return math.ceil(len(text) / width)

def create_newsreel_page(page_number=185):
    """Maak de volledige newsreel met alle feeds"""
    subpages = []
    
    # ===== HOOFDINTRO =====
    intro_filename = get_intro_template()
    print(f"Loading main intro: {intro_filename}")
    intro_template = loadTTI(intro_filename)
    intro_subpage = {"packets": copy.deepcopy(intro_template["subpages"][0]["packets"])}
    subpages.append(intro_subpage)
    print(f"Main intro loaded with {len(intro_subpage['packets'])} packets")
    
    # ===== PÄÄUUTISET (10 subpages: 1 index + 9 artikelen) =====
    print("\n--- PÄÄUUTISET ---")
    paauutiset_articles = fetch_articles_from_feed("https://yle.fi/rss/uutiset/paauutiset", 9)
    paauutiset_headlines = [{"title": art["title"], "number": str(102 + i)} for i, art in enumerate(paauutiset_articles)]
    
    paauutiset_index_template = loadTTI("paauutiset_index.tti")
    index_subpage = create_index_subpage(paauutiset_index_template, paauutiset_headlines, "PÄÄUUTISET")
    subpages.append(index_subpage)
    
    paauutiset_page_template = loadTTI("paauutiset_page.tti")
    for i, article in enumerate(paauutiset_articles):
        article_subpage = create_article_subpage(paauutiset_page_template, article, 102 + i)
        subpages.append(article_subpage)
    print(f"✓ Pääuutiset: {len(paauutiset_articles) + 1} subpages")
    
    # ===== TUOREIMMAT INTRO + CONTENT =====
    print("\n--- TUOREIMMAT ---")
    tuoreimmat_intro = load_intro("tuoreimmat_intro.tti")
    if tuoreimmat_intro:
        subpages.append(tuoreimmat_intro)
    
    tuoreimmat_articles = fetch_articles_from_feed("https://yle.fi/rss/uutiset/tuoreimmat", 5)
    tuoreimmat_headlines = [{"title": art["title"], "number": str(112 + i)} for i, art in enumerate(tuoreimmat_articles)]
    
    tuoreimmat_index_template = loadTTI("tuoreimmat_index.tti")
    index_subpage = create_index_subpage(tuoreimmat_index_template, tuoreimmat_headlines, "TUOREIMMAT")
    subpages.append(index_subpage)
    
    tuoreimmat_page_template = loadTTI("tuoreimmat_page.tti")
    for i, article in enumerate(tuoreimmat_articles):
        article_subpage = create_article_subpage(tuoreimmat_page_template, article, 112 + i)
        subpages.append(article_subpage)
    print(f"✓ Tuoreimmat: {len(tuoreimmat_articles) + 1} subpages (+ intro if exists)")
    
    # ===== SPORTS INTRO + CONTENT =====
    print("\n--- URHEILU (SPORTS) ---")
    sports_intro = load_intro("sports_intro.tti")
    if sports_intro:
        subpages.append(sports_intro)
    
    urheilu_articles = fetch_articles_from_feed("https://yle.fi/rss/urheilu", 5)
    urheilu_headlines = [{"title": art["title"], "number": str(302 + i)} for i, art in enumerate(urheilu_articles)]
    
    urheilu_index_template = loadTTI("sportgeneral_index.tti")
    index_subpage = create_index_subpage(urheilu_index_template, urheilu_headlines, "URHEILU")
    subpages.append(index_subpage)
    
    urheilu_page_template = loadTTI("sportgeneral_page.tti")
    for i, article in enumerate(urheilu_articles):
        article_subpage = create_article_subpage(urheilu_page_template, article, 302 + i)
        subpages.append(article_subpage)
    
    # ===== JALKAPALLO =====
    jalkapallo_articles = fetch_articles_from_feed(
        "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_URHEILU&concepts=18-205598", 
        5, 
        clean_aggressive=True
    )
    jalkapallo_headlines = [{"title": art["title"], "number": str(309 + i)} for i, art in enumerate(jalkapallo_articles)]
    
    jalkapallo_index_template = loadTTI("jalkapallo_index.tti")
    index_subpage = create_index_subpage(jalkapallo_index_template, jalkapallo_headlines, "JALKAPALLO")
    subpages.append(index_subpage)
    
    jalkapallo_page_template = loadTTI("jalkapallo_page.tti")
    for i, article in enumerate(jalkapallo_articles):
        article_subpage = create_article_subpage(jalkapallo_page_template, article, 309 + i)
        subpages.append(article_subpage)

    # ===== VEIKKAUSLIIGA SCORE TABLE =====
    veikkausliiga_added = False
    try:
        from veikkausliiga_scraper import AiScoreScraper
        
        scraper = AiScoreScraper()
        standings = scraper.scrape_standings()
        
        if standings and len(standings) > 0:
            veikkausliiga_template = loadTTI("veikkausliiga_page.tti")
            veikkausliiga_packets = copy.deepcopy(veikkausliiga_template["subpages"][0]["packets"])
            
            line = 6
            for t in standings:
                rowDict = {
                    "P": t["position"],
                    "C": t["team"][:13],
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
            
            page_ref_block = toTeletextBlock(
                input={"content": [{"align": "right", "content": [{"colour": "cyan", "text": "P314"}]}]},
                line=21
            )
            veikkausliiga_packets += page_ref_block
            
            veikkausliiga_subpage = {"packets": veikkausliiga_packets}
            subpages.append(veikkausliiga_subpage)
            veikkausliiga_added = True
            print(f"  ✓ Veikkausliiga: 1 score table ({len(standings)} teams)")
        else:
            # Geen data - maak "KAUSI PÄÄTTYNYT" pagina
            print(f"  ℹ Veikkausliiga: No data - creating 'season ended' page")
            
            veikkausliiga_template = loadTTI("veikkausliiga_page.tti")
            veikkausliiga_packets = copy.deepcopy(veikkausliiga_template["subpages"][0]["packets"])
            
            # Maak centered message
            line = 11  # Midden van de pagina
            
            season_ended_block = toTeletextBlock(
                input={"content": [{"align": "center", "content": [{"colour": "yellow", "text": "KAUSI PÄÄTTYNYT"}]}]},
                line=line
            )
            veikkausliiga_packets += season_ended_block
            
            line += 2
            info_block = toTeletextBlock(
                input={"content": [{"align": "center", "content": [{"colour": "white", "text": "Sarjataulukko ei saatavilla"}]}]},
                line=line
            )
            veikkausliiga_packets += info_block
            
            # Voeg P314 toe
            page_ref_block = toTeletextBlock(
                input={"content": [{"align": "right", "content": [{"colour": "cyan", "text": "P314"}]}]},
                line=21
            )
            veikkausliiga_packets += page_ref_block
            
            veikkausliiga_subpage = {"packets": veikkausliiga_packets}
            subpages.append(veikkausliiga_subpage)
            veikkausliiga_added = True
            print(f"  ✓ Veikkausliiga: 'Season ended' page created")
            
    except Exception as e:
        # Error - maak ook "KAUSI PÄÄTTYNYT" pagina
        print(f"  ⚠ Veikkausliiga error: {e} - creating fallback page")
        try:
            veikkausliiga_template = loadTTI("veikkausliiga_page.tti")
            veikkausliiga_packets = copy.deepcopy(veikkausliiga_template["subpages"][0]["packets"])
            
            line = 11
            season_ended_block = toTeletextBlock(
                input={"content": [{"align": "center", "content": [{"colour": "yellow", "text": "KAUSI PÄÄTTYNYT"}]}]},
                line=line
            )
            veikkausliiga_packets += season_ended_block
            
            line += 2
            info_block = toTeletextBlock(
                input={"content": [{"align": "center", "content": [{"colour": "white", "text": "Sarjataulukko ei saatavilla"}]}]},
                line=line
            )
            veikkausliiga_packets += info_block
            
            page_ref_block = toTeletextBlock(
                input={"content": [{"align": "right", "content": [{"colour": "cyan", "text": "P314"}]}]},
                line=21
            )
            veikkausliiga_packets += page_ref_block
            
            veikkausliiga_subpage = {"packets": veikkausliiga_packets}
            subpages.append(veikkausliiga_subpage)
            veikkausliiga_added = True
        except:
            pass
    
    print(f"✓ Sports total: {len(urheilu_articles) + len(jalkapallo_articles) + 2 + (1 if veikkausliiga_added else 0)} subpages (intro + Urheilu + Jalkapallo{' + Veikkausliiga' if veikkausliiga_added else ''})")
        
    # ===== TRAVEL INTRO + CONTENT =====
    print("\n--- MATKAILU (TRAVEL) ---")
    travel_intro = load_intro("travel_intro.tti")
    if travel_intro:
        subpages.append(travel_intro)
    
    travel_articles = fetch_articles_from_feed("https://yle.fi/rss/t/18-206851/fi", 5)
    travel_headlines = [{"title": art["title"], "number": str(402 + i)} for i, art in enumerate(travel_articles)]
    
    travel_index_template = loadTTI("matkailu_index.tti")
    index_subpage = create_index_subpage(travel_index_template, travel_headlines, "MATKAILU")
    subpages.append(index_subpage)
    
    travel_page_template = loadTTI("matkailu_page.tti")
    for i, article in enumerate(travel_articles):
        article_subpage = create_article_subpage(travel_page_template, article, 402 + i)
        subpages.append(article_subpage)
    print(f"✓ Travel: {len(travel_articles) + 1} subpages (+ intro if exists)")
    
    # ===== WEATHER INTRO =====
    print("\n--- SÄÄ (WEATHER) ---")
    weather_intro = load_intro("weather_intro.tti")
    if weather_intro:
        subpages.append(weather_intro)
    
    # ===== 1. WEER TEXT (P161, P168, P169 - variabel aantal subpages) =====
    print("  1. Weather text forecasts...")
    weather_subpages_added = 0
    
    try:
        from FMI import FMITextScraper
        
        weather_scraper = FMITextScraper()
        
        # P161: LANDELIJK WEERBERICHT
        forecast_text = weather_scraper.get_land_forecast()
        
        if forecast_text:
            weather_template = loadTTI("weather_land_template.tti")
            weather_packets = copy.deepcopy(weather_template["subpages"][0]["packets"])
            
            for packet in weather_packets:
                if "text" in packet:
                    packet["text"] = packet["text"].replace("DATE", get_finnish_date())
            
            line = 5
            forecast_block = toTeletextBlock(
                input={"content": [{"align": "left", "content": [{"colour": "white", "text": forecast_text}]}]},
                line=line
            )
            weather_packets += forecast_block
            
            weather_subpage = {"packets": weather_packets}
            subpages.append(weather_subpage)
            weather_subpages_added += 1
        
        # P168: MARITIEM WEERBERICHT
        marine_data = weather_scraper.get_structured_marine_forecast()
        
        if marine_data:
            MAX_LINE = 20
            
            def split_area_name(area):
                if len(area) <= 40:
                    return [area]
                parts = [p.strip() for p in area.split(',')]
                lines = []
                current = ""
                for i, part in enumerate(parts):
                    if i == 0:
                        current = part
                    else:
                        test = current + ", " + part
                        if len(test) <= 40:
                            current = test
                        else:
                            lines.append(current + ",")
                            current = part
                if current:
                    lines.append(current)
                return lines
            
            try:
                marine_template = loadTTI("weather_marine_template.tti")
            except:
                marine_template = {
                    "subpages": [{
                        "packets": [
                            {"number": 0, "text": "ÿ^ƒÿCÿ]¾\u001f€€€€€€°°°°°°Pÿ GMERISÄÄ        168    DATE  "},
                            {"number": 24, "text": "£ Sää 161 Alueet 169 TEXT-TV Yle 100"}
                        ]
                    }]
                }
            
            # Groepeer warnings
            warning_groups = []
            if marine_data['warnings']:
                current_group = []
                for item_type, content in marine_data['warnings']:
                    if item_type == 'heading':
                        if current_group:
                            warning_groups.append(current_group)
                        current_group = [(item_type, content)]
                    else:
                        current_group.append((item_type, content))
                if current_group:
                    warning_groups.append(current_group)
            
            # Maak warning subpages
            if warning_groups:
                current_groups = []
                current_line = 5 + 2
                
                for group in warning_groups:
                    group_size = 0
                    for item_type, content in group:
                        if item_type == 'heading':
                            group_size += len(split_area_name(content))
                        else:
                            group_size += calculate_text_lines(content)
                    group_size += 1
                    
                    if current_line + group_size > MAX_LINE:
                        if current_groups:
                            subpage = {"packets": copy.deepcopy(marine_template["subpages"][0]["packets"])}
                            for packet in subpage["packets"]:
                                if "text" in packet:
                                    packet["text"] = packet["text"].replace("DATE", get_finnish_date())
                            
                            line = 5
                            warning_header = "Kovan tuulen varoitus:"
                            warning_header_block = toTeletextBlock(
                                input={"content": [{"align": "left", "content": [{"colour": "red", "text": warning_header}]}]},
                                line=line
                            )
                            subpage["packets"] += warning_header_block
                            line += 2
                            
                            for grp in current_groups:
                                for itype, icontent in grp:
                                    if itype == 'heading':
                                        for heading_line in split_area_name(icontent):
                                            block = toTeletextBlock(
                                                input={"content": [{"align": "left", "content": [{"colour": "cyan", "text": heading_line}]}]},
                                                line=line
                                            )
                                            subpage["packets"] += block
                                            line += 1
                                    else:
                                        block = toTeletextBlock(
                                            input={"content": [{"align": "left", "content": [{"colour": "white", "text": icontent}]}]},
                                            line=line
                                        )
                                        subpage["packets"] += block
                                        line += calculate_text_lines(icontent)
                                line += 1
                            
                            subpages.append(subpage)
                            weather_subpages_added += 1
                        
                        current_groups = [group]
                        current_line = 5 + 2 + group_size
                    else:
                        current_groups.append(group)
                        current_line += group_size
                
                if current_groups:
                    subpage = {"packets": copy.deepcopy(marine_template["subpages"][0]["packets"])}
                    for packet in subpage["packets"]:
                        if "text" in packet:
                            packet["text"] = packet["text"].replace("DATE", get_finnish_date())
                    
                    line = 5
                    warning_header = "Kovan tuulen varoitus:"
                    warning_header_block = toTeletextBlock(
                        input={"content": [{"align": "left", "content": [{"colour": "red", "text": warning_header}]}]},
                        line=line
                    )
                    subpage["packets"] += warning_header_block
                    line += 2
                    
                    for grp in current_groups:
                        for itype, icontent in grp:
                            if itype == 'heading':
                                for heading_line in split_area_name(icontent):
                                    block = toTeletextBlock(
                                        input={"content": [{"align": "left", "content": [{"colour": "cyan", "text": heading_line}]}]},
                                        line=line
                                    )
                                    subpage["packets"] += block
                                    line += 1
                            else:
                                block = toTeletextBlock(
                                    input={"content": [{"align": "left", "content": [{"colour": "white", "text": icontent}]}]},
                                    line=line
                                )
                                subpage["packets"] += block
                                line += calculate_text_lines(icontent)
                        line += 1
                    
                    subpages.append(subpage)
                    weather_subpages_added += 1
            
            # Maak forecast subpages (1 per gebied)
            for section in marine_data['forecast_sections']:
                subpage = {"packets": copy.deepcopy(marine_template["subpages"][0]["packets"])}
                for packet in subpage["packets"]:
                    if "text" in packet:
                        packet["text"] = packet["text"].replace("DATE", get_finnish_date())
                
                line = 5
                header = "Odotettavissa huomisiltaan asti:"
                header_block = toTeletextBlock(
                    input={"content": [{"align": "left", "content": [{"colour": "yellow", "text": header}]}]},
                    line=line
                )
                subpage["packets"] += header_block
                line += 2
                
                area_lines = split_area_name(section['area'])
                for area_line in area_lines:
                    area_block = toTeletextBlock(
                        input={"content": [{"align": "left", "content": [{"colour": "cyan", "text": area_line}]}]},
                        line=line
                    )
                    subpage["packets"] += area_block
                    line += 1
                
                forecast_block = toTeletextBlock(
                    input={"content": [{"align": "left", "content": [{"colour": "white", "text": section['forecast']}]}]},
                    line=line
                )
                subpage["packets"] += forecast_block
                
                subpages.append(subpage)
                weather_subpages_added += 1
            
            # Maak VRK2 subpages (1 per gebied)
            for section in marine_data['vrk2_sections']:
                subpage = {"packets": copy.deepcopy(marine_template["subpages"][0]["packets"])}
                for packet in subpage["packets"]:
                    if "text" in packet:
                        packet["text"] = packet["text"].replace("DATE", get_finnish_date())
                        packet["text"] = packet["text"].replace("MERISÄÄ", "MERI 2VRK")
                
                line = 5
                header = "Säätiedotus 2 vrk merenkulkijoille"
                header_block = toTeletextBlock(
                    input={"content": [{"align": "left", "content": [{"colour": "yellow", "text": header}]}]},
                    line=line
                )
                subpage["packets"] += header_block
                line += 2
                
                area_lines = split_area_name(section['area'])
                for area_line in area_lines:
                    area_block = toTeletextBlock(
                        input={"content": [{"align": "left", "content": [{"colour": "cyan", "text": area_line}]}]},
                        line=line
                    )
                    subpage["packets"] += area_block
                    line += 1
                
                forecast_block = toTeletextBlock(
                    input={"content": [{"align": "left", "content": [{"colour": "white", "text": section['forecast']}]}]},
                    line=line
                )
                subpage["packets"] += forecast_block
                
                subpages.append(subpage)
                weather_subpages_added += 1
        
        # P169: REGIONALE WEERBERICHTEN
        regions = weather_scraper.get_regional_forecasts()
        
        if regions:
            try:
                regional_template = loadTTI("weather_regional_template.tti")
            except:
                regional_template = {
                    "subpages": [{
                        "packets": [
                            {"number": 0, "text": "ÿ^ƒÿCÿ]¾\u001f€€€€€€°°°°°°Pÿ GALUEET        169    DATE  "},
                            {"number": 24, "text": "£ Sää 161 Meri 168 TEXT-TV Yle 100"}
                        ]
                    }]
                }
            
            for region_data in regions:
                subpage = {"packets": copy.deepcopy(regional_template["subpages"][0]["packets"])}
                
                for packet in subpage["packets"]:
                    if "text" in packet:
                        packet["text"] = packet["text"].replace("DATE", get_finnish_date())
                
                line = 5
                region_block = toTeletextBlock(
                    input={"content": [{"align": "left", "content": [{"colour": "yellow", "text": region_data['region']}]}]},
                    line=line
                )
                subpage["packets"] += region_block
                line += 2
                
                forecast_block = toTeletextBlock(
                    input={"content": [{"align": "left", "content": [{"colour": "white", "text": region_data['forecast']}]}]},
                    line=line
                )
                subpage["packets"] += forecast_block
                
                subpages.append(subpage)
                weather_subpages_added += 1
        
        print(f"    ✓ Weather text: {weather_subpages_added} subpages")
            
    except Exception as e:
        print(f"    ⚠ Weather text error: {e}")
    
    # ===== 2. WEERKAART (3 subpages) =====
    print("  2. Weather map...")
    try:
        import weathermap
        
        weather_map_subpages = weathermap.get_weather_subpages("weathermap.tti")
        
        if weather_map_subpages:
            for weather_subpage in weather_map_subpages:
                subpages.append(weather_subpage)
            print(f"    ✓ Weather map: {len(weather_map_subpages)} subpages")
        else:
            print("    ⚠ No weather map available")
            
    except Exception as e:
        print(f"    ⚠ Weather map error: {e}")
    
    print(f"✓ Weather total: {weather_subpages_added + (len(weather_map_subpages) if 'weather_map_subpages' in locals() else 0)} subpages (+ intro if exists)")
    
    # ===== TV-RADIO INTRO =====
    print("\n--- TV & RADIO ---")
    tv_radio_intro = load_intro("tv-radio_intro.tti")
    if tv_radio_intro:
        subpages.append(tv_radio_intro)
    
    # ===== 3. TV GIDS (4 subpages - één per kanaal) =====
    print("  3. TV guide...")
    tv_subpages_added = 0
    try:
        from tv import TelsuScraper
        
        tv_scraper = TelsuScraper()
        tv_data = tv_scraper.scrape_all_channels()
        
        if tv_data:
            tv_channels = [
                ('yle1', 'Yle TV1', 'YLE1_template.tti'),
                ('yle2', 'Yle TV2', 'YLE2_template.tti'),
                ('mtv3', 'MTV3', 'MTV3_template.tti'),
                ('nelonen', 'Nelonen', 'Nelonen_template.tti')
            ]
            
            for channel_id, channel_name, template_file in tv_channels:
                programs = tv_data.get(channel_name, [])
                
                if programs:
                    try:
                        tv_template = loadTTI(template_file)
                        tv_packets = copy.deepcopy(tv_template["subpages"][0]["packets"])
                        
                        for packet in tv_packets:
                            if "text" in packet:
                                packet["text"] = packet["text"].replace("DAY", get_finnish_day())
                                packet["text"] = packet["text"].replace("DATE", get_finnish_date())
                        
                        line = 7
                        
                        for program in programs:
                            tijd = program['start_time'].split('-')[0].strip()
                            if '<small>' in tijd:
                                tijd = tijd.split('<small>')[0]
                            
                            imdb = f" [{program['imdb_rating']}]" if program['imdb_rating'] else ""
                            full_title = program['title'] + imdb
                            
                            para_block = toTeletextBlock(
                                input={
                                    "content": [
                                        {
                                            "align": "left",
                                            "content": [
                                                {"colour": "yellow", "text": tijd + " "},
                                                {"colour": "white", "text": full_title}
                                            ]
                                        }
                                    ]
                                },
                                line=line,
                                maxWidth=40
                            )
                            
                            if (len(para_block) + line) > 21:
                                break
                            
                            tv_packets += para_block
                            line += len(para_block)
                        
                        tv_subpage = {"packets": tv_packets}
                        subpages.append(tv_subpage)
                        tv_subpages_added += 1
                        
                    except Exception as e:
                        print(f"    ⚠ {channel_name}: {e}")
            
            if tv_subpages_added > 0:
                print(f"    ✓ TV guide: {tv_subpages_added} channels")
            
    except Exception as e:
        print(f"    ⚠ TV guide error: {e}")
    
    # ===== 4. RADIO GIDS (3 subpages - één per kanaal) =====
    print("  4. Radio guide...")
    radio_subpages_added = 0
    try:
        from radio import YleRadioScraper
        
        radio_scraper = YleRadioScraper()
        radio_data = radio_scraper.scrape_radio_guide()
        
        if radio_data:
            radio_channels = [
                ('radio1', 'Yle Radio 1', 'RADIO1_template.tti'),
                ('ylex', 'YleX', 'YLEX_template.tti'),
                ('radiosuomi', 'Yle Radio Suomi', 'RADIOSUOM_template.tti')
            ]
            
            for channel_id, channel_name, template_file in radio_channels:
                programs = radio_data.get(channel_name, [])
                
                if programs:
                    try:
                        radio_template = loadTTI(template_file)
                        radio_packets = copy.deepcopy(radio_template["subpages"][0]["packets"])
                        
                        for packet in radio_packets:
                            if "text" in packet:
                                packet["text"] = packet["text"].replace("DAY", get_finnish_day())
                                packet["text"] = packet["text"].replace("DATE", get_finnish_date())
                        
                        line = 5
                        
                        for program in programs:
                            tijd = program['start_time']
                            full_title = program['title']
                            
                            para_block = toTeletextBlock(
                                input={
                                    "content": [
                                        {
                                            "align": "left",
                                            "content": [
                                                {"colour": "yellow", "text": tijd + " "},
                                                {"colour": "white", "text": full_title}
                                            ]
                                        }
                                    ]
                                },
                                line=line,
                                maxWidth=40
                            )
                            
                            if (len(para_block) + line) > 21:
                                break
                            
                            radio_packets += para_block
                            line += len(para_block)
                        
                        radio_subpage = {"packets": radio_packets}
                        subpages.append(radio_subpage)
                        radio_subpages_added += 1
                        
                    except Exception as e:
                        print(f"    ⚠ {channel_name}: {e}")
            
            if radio_subpages_added > 0:
                print(f"    ✓ Radio guide: {radio_subpages_added} channels")
            
    except Exception as e:
        print(f"    ⚠ Radio guide error: {e}")
    
    print(f"✓ TV & Radio total: {tv_subpages_added + radio_subpages_added} subpages (+ intro if exists)")
    
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
    
    print(f"\n{'='*70}")
    print(f"NEWSREEL COMPLETE!")
    print(f"{'='*70}")
    print(f"Total subpages: {len(subpages)}")
    print(f"")
    print(f"BREAKDOWN:")
    print(f"  • Main intro: 1")
    print(f"  • Pääuutiset: 10 (1 index + 9 articles)")
    print(f"  • Tuoreimmat: 6+ (intro + 1 index + 5 articles)")
    print(f"  • Sports: 12+ (intro + 6 urheilu + 6 jalkapallo + Veikkausliiga)")
    print(f"  • Travel: 6+ (intro + 1 index + 5 articles)")
    print(f"  • Weather: {weather_subpages_added + (len(weather_map_subpages) if 'weather_map_subpages' in locals() else 0)}+ (intro + text + map)")
    print(f"  • TV & Radio: {tv_subpages_added + radio_subpages_added}+ (intro + TV + Radio)")
    print(f"")
    print(f"ORDER: Intro → News → Sports → Travel → Weather → TV/Radio")
    print(f"{'='*70}")

def run_newsreel():
    """Hoofdfunctie om de newsreel te genereren"""
    print("="*70)
    print("COMPREHENSIVE NEWSREEL WITH ALL YLE FEEDS")
    print("="*70)
    create_newsreel_page()
    print("\nDone.")

if __name__ == "__main__":
    run_newsreel()