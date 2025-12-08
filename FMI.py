import requests
from bs4 import BeautifulSoup

class FMITextScraper:
    """
    Scraper voor FMI tekstuele weerbeschrijvingen
    Gebruikt DIRECT de CDN HTML endpoints (geen Selenium!)
    """
    
    def __init__(self):
        self.land_url = "https://cdn.fmi.fi/apps/weather-forecast-texts/index.php"
        self.marine_url = "https://cdn.fmi.fi/apps/sea-weather-forecasts-texts/index.php"
    
    def get_land_forecast(self):
        """
        Haal land forecast op voor teletext
        Returns: vloeiende tekst zonder newlines
        """
        try:
            response = requests.get(self.land_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Vind eerste paragraph na h1 (dit is de intro)
            intro_p = None
            found_h1 = False
            
            for elem in soup.find_all(['h1', 'p']):
                if elem.name == 'h1':
                    found_h1 = True
                    continue
                
                if elem.name == 'p' and found_h1:
                    text = elem.get_text(strip=True)
                    # Skip varoitukset link
                    if 'varoituksia' in text.lower():
                        continue
                    # Dit is de intro
                    intro_p = elem
                    break
            
            if not intro_p:
                return "Säätietoja ei saatavilla."
            
            intro_text = intro_p.get_text(strip=True)
            return intro_text
            
        except Exception as e:
            print(f"✗ Error fetching land forecast: {e}")
            return "Säätietoja ei saatavilla."
    
    def get_structured_marine_forecast(self):
        """
        Haal marine forecast op MET structuur behouden
        Returns: dict met intro, warnings, forecast_sections, en vrk2_sections
        """
        try:
            response = requests.get(self.marine_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            result = {
                'intro': '',
                'warnings': [],           # ALLE warning content als 1 blok
                'forecast_sections': [],  # "Odotettavissa huomisiltaan asti"
                'vrk2_sections': []       # "Säätiedotus 2 vrk" secties
            }
            
            elements = soup.find_all(['h1', 'h2', 'h3', 'p'])
            
            current_section = 'start'
            all_warning_items = []  # Verzamel ALLE warning content (H3 + P)
            current_area = None
            in_vrk2 = False
            
            for elem in elements:
                tag = elem.name
                text = elem.get_text(strip=True)
                
                if not text:
                    continue
                
                # H1 = detect 2 vrk section
                if tag == 'h1':
                    if 'Säätiedotus 2 vrk' in text or '2 vrk' in text:
                        in_vrk2 = True
                        current_section = 'vrk2_waiting'
                    continue
                
                # H2 = major section headers
                if tag == 'h2':
                    # Check voor varoitus section
                    if 'varoitus' in text.lower():
                        current_section = 'warning'
                        continue
                    
                    if 'Odotettavissa huomisiltaan asti' in text or 'Odotettavissa' in text:
                        # Einde van warnings - sla alles op als 1 groep
                        if all_warning_items:
                            result['warnings'] = all_warning_items
                            all_warning_items = []
                        
                        if in_vrk2:
                            current_section = 'vrk2'
                        else:
                            current_section = 'forecast'
                        continue
                
                # H3 = area names OF sub-headers
                if tag == 'h3':
                    if current_section == 'warning':
                        # In warning sectie: verzamel ALLES (H3 + volgende P's)
                        all_warning_items.append(('heading', text))
                    else:
                        current_area = text
                    continue
                
                # P = content
                if tag == 'p':
                    # Skip varoitukset link
                    if 'varoituksia' in text.lower():
                        continue
                    
                    if current_section == 'warning':
                        # Verzamel alle P's in warning sectie
                        all_warning_items.append(('text', text))
                    
                    elif current_section == 'forecast' and current_area:
                        result['forecast_sections'].append({
                            'area': current_area,
                            'forecast': text
                        })
                        current_area = None
                    
                    elif current_section == 'vrk2' and current_area:
                        result['vrk2_sections'].append({
                            'area': current_area,
                            'forecast': text
                        })
                        current_area = None
            
            # Als er nog warnings over zijn
            if all_warning_items:
                result['warnings'] = all_warning_items
            
            # Clean up whitespace
            result['intro'] = result['intro'].strip()
            
            print(f"✓ Marine forecast opgehaald:")
            print(f"  - Intro: {len(result['intro'])} chars")
            if result['warnings']:
                headings = len([x for x in result['warnings'] if x[0] == 'heading'])
                texts = len([x for x in result['warnings'] if x[0] == 'text'])
                print(f"  - Waarschuwingen: {headings} headings + {texts} texts = {len(result['warnings'])} items totaal")
            else:
                print(f"  - Waarschuwingen: geen")
            print(f"  - Forecast secties: {len(result['forecast_sections'])}")
            print(f"  - VRK2 secties: {len(result['vrk2_sections'])}")
            
            return result
            
        except Exception as e:
            print(f"✗ Error fetching marine forecast: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_regional_forecasts(self):
        """
        Haal regionale forecasts op, gesplitst per regio
        Returns: list van dicts met 'region' en 'forecast'
        """
        try:
            response = requests.get(self.land_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            regions = []
            current_region = None
            in_regional_section = False
            
            for elem in soup.find_all(['h2', 'h3', 'p']):
                tag = elem.name
                text = elem.get_text(strip=True)
                
                if not text:
                    continue
                
                # H2 = start van regionale sectie
                if tag == 'h2' and 'Odotettavissa' in text:
                    in_regional_section = True
                    continue
                
                if not in_regional_section:
                    continue
                
                # H3 = regio naam
                if tag == 'h3':
                    current_region = text
                    continue
                
                # P = forecast voor huidige regio
                if tag == 'p' and current_region:
                    regions.append({
                        'region': current_region,
                        'forecast': text
                    })
                    current_region = None
            
            print(f"✓ Regionale forecasts opgehaald: {len(regions)} regio's")
            return regions
            
        except Exception as e:
            print(f"✗ Error fetching regional forecasts: {e}")
            return []