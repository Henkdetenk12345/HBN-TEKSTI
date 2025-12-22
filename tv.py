import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import copy
import sys
import os

# Import je teletext modules
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
    """Geeft volledige datum in het Fins (bijv. MAANANTAI 16.12.)"""
    now = datetime.now()
    day_name = FINNISH_DAYS[now.weekday()]
    return f"{day_name} {now.day}.{now.month}."

def vervang_datum_in_tti(tti_data):
    """Vervangt DAY en DATE placeholders in TTI data met Finse datum"""
    dag = get_finnish_day()
    datum = get_finnish_date()
    
    for subpage in tti_data.get("subpages", []):
        for packet in subpage.get("packets", []):
            if "text" in packet:
                packet["text"] = packet["text"].replace("DAY", dag)
                packet["text"] = packet["text"].replace("DATE", datum)
    
    return tti_data

class TelsuScraper:
    def __init__(self):
        self.base_url = "https://www.telsu.fi"
        self.channels = {
            'yle1': {'name': 'Yle TV1', 'page': 501, 'template': 'YLE1_template.tti'},
            'yle2': {'name': 'Yle TV2', 'page': 502, 'template': 'YLE2_template.tti'},
            'mtv3': {'name': 'MTV3', 'page': 503, 'template': 'MTV3_template.tti'},
            'nelonen': {'name': 'Nelonen', 'page': 504, 'template': 'Nelonen_template.tti'}
        }
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    
    def scrape_all_channels(self):
        """Scrape alle kanalen van de hoofdpagina"""
        url = self.base_url
        all_programs = {info['name']: [] for info in self.channels.values()}
        
        try:
            print(f"Ophalen hoofdpagina: {url}")
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            for channel_id, channel_info in self.channels.items():
                channel_name = channel_info['name']
                print(f"\nScraping {channel_name} (rel={channel_id})...")
                
                channel_div = soup.find('div', {'class': 'ch', 'rel': channel_id})
                
                if not channel_div:
                    print(f"  [!] Kanaal div niet gevonden voor {channel_id}")
                    continue
                
                data_divs = channel_div.find_all('div', {'class': 'data'})
                print(f"  Gevonden {len(data_divs)} data divs")
                
                programs = []
                
                for data_div in data_divs:
                    program_links = data_div.find_all('a', href=True)
                    
                    for link in program_links:
                        try:
                            time_elem = link.find('i')
                            time_text = time_elem.get_text(strip=True) if time_elem else ''
                            
                            title_elem = link.find('b')
                            title = title_elem.get_text(strip=True) if title_elem else ''
                            
                            if not title:
                                continue
                            
                            imdb_rating = ''
                            imdb_elem = link.find('em', {'class': 'im'})
                            if imdb_elem:
                                rating_strong = imdb_elem.find('strong')
                                if rating_strong:
                                    imdb_rating = rating_strong.get_text(strip=True)
                            
                            program_id = link.get('rel', '')
                            end_time = link.get('data-end', '')
                            
                            program_url = link.get('href', '')
                            if program_url and not program_url.startswith('http'):
                                program_url = self.base_url + program_url
                            
                            if not any(p['program_id'] == program_id for p in programs):
                                program = {
                                    'title': title,
                                    'start_time': time_text,
                                    'end_time': end_time,
                                    'channel': channel_name,
                                    'imdb_rating': imdb_rating,
                                    'program_id': program_id,
                                    'url': program_url
                                }
                                
                                programs.append(program)
                            
                        except Exception as e:
                            print(f"  Fout bij verwerken programma: {e}")
                            continue
                
                all_programs[channel_name] = programs
                print(f"  [OK] {len(programs)} programma's gevonden")
            
            return all_programs
            
        except requests.RequestException as e:
            print(f"Fout bij ophalen {url}: {e}")
            return all_programs
    
    def create_teletext_page(self, channel_id, programs):
        """Maak een teletext pagina voor een kanaal"""
        channel_info = self.channels[channel_id]
        template_file = channel_info['template']
        page_number = channel_info['page']
        
        # Check of template bestaat
        if not os.path.exists(template_file):
            print(f"  [!] Template niet gevonden: {template_file}")
            return False
        
        try:
            # Load template
            pageTemplate = loadTTI(template_file)
            
            # Create teletext page met subpages
            teletextPage = {
                "number": page_number,
                "subpages": [],
                "control": {
                    "cycleTime": "10,T",
                    "erasePage": True,
                    "update": True
                }
            }
            
            # Start op regel 7 (na header)
            current_line = 7
            current_subpage = {
                "packets": copy.deepcopy(pageTemplate["subpages"][0]["packets"])
            }
            
            # Vervang datum placeholders
            for packet in current_subpage["packets"]:
                if "text" in packet:
                    packet["text"] = packet["text"].replace("DAY", get_finnish_day())
                    packet["text"] = packet["text"].replace("DATE", get_finnish_date())
            
            # Voeg programma's toe
            for i, program in enumerate(programs):
                # Format tijd
                tijd = program['start_time'].split('-')[0].strip()
                if '<small>' in tijd:
                    tijd = tijd.split('<small>')[0]
                
                # Maak de programma regel
                imdb = f" [{program['imdb_rating']}]" if program['imdb_rating'] else ""
                full_title = program['title'] + imdb
                
                # Als de titel langer is dan 33 karakters (40 - 7 voor tijd), laat het wrappen
                paraBlock = toTeletextBlock(
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
                    line=current_line,
                    maxWidth=40
                )
                
                # Check of de pagina niet te lang wordt (max regel 21)
                if (len(paraBlock) + current_line) > 21:
                    # Voeg huidige subpage toe
                    teletextPage["subpages"].append(current_subpage)
                    
                    # Start nieuwe subpage
                    current_subpage = {
                        "packets": copy.deepcopy(pageTemplate["subpages"][0]["packets"])
                    }
                    
                    # Vervang datum placeholders in nieuwe subpage
                    for packet in current_subpage["packets"]:
                        if "text" in packet:
                            packet["text"] = packet["text"].replace("DAY", get_finnish_day())
                            packet["text"] = packet["text"].replace("DATE", get_finnish_date())
                    
                    # Reset line counter
                    current_line = 7
                    
                    # Herbereken paraBlock voor nieuwe subpage met volledige titel
                    paraBlock = toTeletextBlock(
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
                        line=current_line,
                        maxWidth=40
                    )
                
                # Voeg programma toe aan huidige subpage
                current_subpage["packets"] += paraBlock
                current_line += len(paraBlock)
            
            # Voeg laatste subpage toe als die nog niet toegevoegd is
            if current_subpage not in teletextPage["subpages"]:
                teletextPage["subpages"].append(current_subpage)
            
            # Export de pagina
            exportTTI(pageLegaliser(teletextPage))
            
            num_subpages = len(teletextPage["subpages"])
            if num_subpages > 1:
                print(f"  [OK] Teletext pagina P{page_number} aangemaakt ({num_subpages} subpagina's)")
            else:
                print(f"  [OK] Teletext pagina P{page_number} aangemaakt")
            return True
            
        except Exception as e:
            print(f"  [X] Fout bij maken teletext pagina: {e}")
            return False
    
    def create_all_teletext_pages(self, programs_data):
        """Maak teletext pagina's voor alle kanalen"""
        print("\n" + "="*70)
        print("TELETEXT PAGINA'S GENEREREN")
        print("="*70)
        
        for channel_id, channel_info in self.channels.items():
            channel_name = channel_info['name']
            programs = programs_data.get(channel_name, [])
            
            print(f"\n{channel_name} → P{channel_info['page']}")
            
            if len(programs) == 0:
                print(f"  [!] Geen programma's om te exporteren")
                continue
            
            self.create_teletext_page(channel_id, programs)
    
    def save_to_json(self, data, filename='tv_gids.json'):
        """Sla data op als JSON bestand"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nData opgeslagen in {filename}")
    
    def print_summary(self, data):
        """Print een samenvatting van de data"""
        print("\n" + "="*70)
        print("TV GIDS SAMENVATTING")
        print("="*70)
        
        total_programs = sum(len(programs) for programs in data.values())
        print(f"\nTotaal aantal programma's: {total_programs}")
        
        for channel, programs in data.items():
            if len(programs) == 0:
                print(f"\n[X] {channel}: Geen programma's gevonden")
                continue
                
            print(f"\n[OK] {channel} ({len(programs)} programma's):")
            for i, prog in enumerate(programs[:8], 1):
                imdb = f" [IMDb: {prog['imdb_rating']}]" if prog['imdb_rating'] else ""
                end = f" - {prog['end_time']}" if prog['end_time'] else ""
                print(f"  {i}. {prog['start_time']}{end}: {prog['title']}{imdb}")
            
            if len(programs) > 8:
                print(f"  ... en {len(programs) - 8} meer programma's")


if __name__ == "__main__":
    scraper = TelsuScraper()
    
    print("Start scraping Telsu.fi...")
    print("="*70)
    
    # Scrape alle kanalen
    tv_data = scraper.scrape_all_channels()
    
    # Print samenvatting
    scraper.print_summary(tv_data)
    
    # Sla op als JSON
    scraper.save_to_json(tv_data)
    
    # Genereer teletext pagina's
    scraper.create_all_teletext_pages(tv_data)
    
    print("\n[OK] Klaar!")