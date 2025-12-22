from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from datetime import datetime
import json
import time
import copy
import os

# Import teletext modules
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

class YleRadioScraper:
    def __init__(self):
        self.base_url = "https://areena.yle.fi"
        self.channels = {
            'radio1': {'name': 'Yle Radio 1', 'page': 506, 'template': 'RADIO1_template.tti'},
            'ylex': {'name': 'YleX', 'page': 507, 'template': 'YLEX_template.tti'},
            'radiosuomi': {'name': 'Yle Radio Suomi', 'page': 508, 'template': 'RADIOSUOM_template.tti'}
        }
    
    def setup_driver(self):
        """Setup Chrome driver met headless optie"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    
    def scrape_radio_guide(self, date=None):
        """Scrape radio gids met Selenium"""
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        print(f"\nScraping radio gids voor {date}")
        print("="*70)
        
        driver = None
        all_schedules = {}
        
        try:
            print("\nOpstarten Chrome driver...")
            driver = self.setup_driver()
            
            url = f"{self.base_url}/podcastit/opas?t={date}"
            print(f"Laden pagina: {url}")
            driver.get(url)
            
            # Wacht tot de pagina geladen is
            print("Wachten op pagina laden...")
            time.sleep(5)
            
            # Wacht tot er kanaal secties zijn
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "Channel_channelRoot__QG36Q"))
                )
                print("[OK] Pagina geladen")
            except:
                print("[!] Timeout")
                return {}
            
            # Zoek alle kanaal secties
            channel_sections = driver.find_elements(By.CLASS_NAME, "Channel_channelRoot__QG36Q")
            print(f"\n[OK] {len(channel_sections)} kanalen gevonden")
            
            # Map van scrape namen naar onze channel keys
            channel_mapping = {
                'Yle Radio 1': 'radio1',
                'YleX': 'ylex',
                'Yle Radio Suomi': 'radiosuomi'
            }
            
            for section in channel_sections:
                try:
                    # Haal kanaal naam op
                    header = section.find_element(By.TAG_NAME, "h2")
                    channel_img = header.find_element(By.TAG_NAME, "img")
                    channel_name = channel_img.get_attribute("alt")
                    
                    # Check of dit een kanaal is dat we willen
                    if channel_name not in channel_mapping:
                        continue
                    
                    print(f"\n{channel_name}...")
                    
                    # Zoek de programma lijst (ol element)
                    try:
                        program_list = section.find_element(By.CLASS_NAME, "ChannelPrograms_programList__2P7EZ")
                    except:
                        print(f"  [X] Geen programma lijst gevonden")
                        all_schedules[channel_name] = []
                        continue
                    
                    # Zoek en klik op "Näytä lisää ohjelmia" knop als die er is
                    try:
                        # Probeer verschillende manieren om de knop te vinden
                        show_more_button = None
                        
                        # Methode 1: Via tekst
                        try:
                            show_more_button = section.find_element(By.XPATH, ".//button[contains(., 'Näytä lisää')]")
                        except:
                            pass
                        
                        # Methode 2: Via class name (de knop heeft vaak een specifieke class)
                        if not show_more_button:
                            try:
                                buttons = section.find_elements(By.TAG_NAME, "button")
                                for btn in buttons:
                                    if "Näytä" in btn.text or "lisää" in btn.text:
                                        show_more_button = btn
                                        break
                            except:
                                pass
                        
                        if show_more_button:
                            print(f"  [i] 'Näytä lisää' knop gevonden, klikken...")
                            driver.execute_script("arguments[0].scrollIntoView(true);", show_more_button)
                            time.sleep(0.5)
                            show_more_button.click()
                            time.sleep(2)  # Wacht tot alle programma's geladen zijn
                            print(f"  [OK] Alle programma's geladen")
                    except Exception as e:
                        # Geen knop gevonden = alle programma's zijn al zichtbaar
                        print(f"  [i] Geen 'Näytä lisää' knop gevonden (alle programma's al zichtbaar)")
                        pass
                    
                    # Wacht even voor lazy loading
                    time.sleep(1)
                    
                    # Zoek alle li items (programma's)
                    program_items = program_list.find_elements(By.TAG_NAME, "li")
                    
                    if not program_items:
                        print(f"  [!] Geen programma items gevonden")
                        all_schedules[channel_name] = []
                        continue
                    
                    programs = []
                    
                    for item in program_items:
                        try:
                            # Zoek de time element
                            time_elem = item.find_element(By.TAG_NAME, "time")
                            time_text = time_elem.text.strip()
                            
                            # Zoek de button voor de titel
                            button = item.find_element(By.CLASS_NAME, "Program_programHeader__8nQJI")
                            
                            # Zoek h3 binnen de button voor de titel
                            try:
                                title_elem = button.find_element(By.TAG_NAME, "h3")
                                title = title_elem.text.strip()
                            except:
                                # Soms staat de titel direct in de button
                                title = button.text.strip()
                                # Verwijder de tijd uit de titel als die erin zit
                                if time_text and time_text in title:
                                    title = title.replace(time_text, '').strip()
                            
                            if title and time_text:
                                program = {
                                    'title': title,
                                    'start_time': time_text,
                                    'end_time': '',
                                    'channel': channel_name,
                                    'genre': ''
                                }
                                programs.append(program)
                        
                        except Exception as e:
                            # Sla items over die niet goed geparsed kunnen worden
                            continue
                    
                    all_schedules[channel_name] = programs
                    print(f"  [OK] {len(programs)} programma's gevonden")
                
                except Exception as e:
                    print(f"  [X] Fout bij verwerken kanaal: {e}")
                    continue
            
            return all_schedules
            
        except Exception as e:
            print(f"[X] Fout: {e}")
            import traceback
            traceback.print_exc()
            return {}
        
        finally:
            if driver:
                driver.quit()
                print("\n[OK] Browser gesloten")
    
    def create_teletext_page(self, channel_key, programs):
        """Maak een teletext pagina voor een radiokanaal"""
        channel_info = self.channels[channel_key]
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
            
            # Start op regel 5 (na header)
            current_line = 5
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
                tijd = program['start_time']
                
                # Maak de programma regel
                full_title = program['title']
                
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
                    current_line = 5
                    
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
            import traceback
            traceback.print_exc()
            return False
    
    def create_all_teletext_pages(self, programs_data):
        """Maak teletext pagina's voor alle radiokanalen"""
        print("\n" + "="*70)
        print("TELETEXT PAGINA'S GENEREREN")
        print("="*70)
        
        # Map van scrape namen naar onze channel keys
        channel_mapping = {
            'Yle Radio 1': 'radio1',
            'YleX': 'ylex',
            'Yle Radio Suomi': 'radiosuomi'
        }
        
        for scraped_name, channel_key in channel_mapping.items():
            channel_info = self.channels[channel_key]
            programs = programs_data.get(scraped_name, [])
            
            print(f"\n{scraped_name} → P{channel_info['page']}")
            
            if len(programs) == 0:
                print(f"  [!] Geen programma's om te exporteren")
                continue
            
            self.create_teletext_page(channel_key, programs)
    
    def save_to_json(self, data, filename='radio_gids.json'):
        """Sla data op als JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nData opgeslagen in {filename}")
    
    def print_summary(self, data):
        """Print een samenvatting van de data"""
        print("\n" + "="*70)
        print("RADIO GIDS SAMENVATTING")
        print("="*70)
        
        total_programs = sum(len(programs) for programs in data.values())
        print(f"\nTotaal aantal programma's: {total_programs}")
        
        for channel, programs in data.items():
            if len(programs) == 0:
                print(f"\n[X] {channel}: Geen programma's gevonden")
                continue
                
            print(f"\n[OK] {channel} ({len(programs)} programma's):")
            for i, prog in enumerate(programs[:15], 1):
                genre = f" ({prog['genre']})" if prog['genre'] else ""
                end = f" - {prog['end_time']}" if prog['end_time'] else ""
                print(f"  {i}. {prog['start_time']}{end}: {prog['title']}{genre}")
            
            if len(programs) > 15:
                print(f"  ... en {len(programs) - 15} meer programma's")


if __name__ == "__main__":
    print("="*70)
    print("YLE RADIO SCRAPER (Selenium)")
    print("="*70)
    print("\nDit script scraped ECHTE live data van Yle Areena")
    print("="*70)
    
    scraper = YleRadioScraper()
    
    # Scrape ECHTE data
    radio_data = scraper.scrape_radio_guide()
    
    # Print samenvatting
    scraper.print_summary(radio_data)
    
    # Sla op als JSON
    if radio_data:
        scraper.save_to_json(radio_data)
    
    # Genereer teletext pagina's
    if radio_data:
        scraper.create_all_teletext_pages(radio_data)
    
    print("\n[OK] Klaar!")