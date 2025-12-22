import requests
from bs4 import BeautifulSoup

class FMITextScraper:
    """
    Scraper voor FMI tekstuele weerbeschrijvingen
    UPDATED voor nieuwe day1.php / day2.php structuur
    """
    
    def __init__(self):
        self.land_url = "https://cdn.fmi.fi/apps/weather-forecast-texts/index.php"
        self.marine_day1_url = "https://cdn.fmi.fi/apps/sea-weather-forecasts-texts/day1.php"
        self.marine_day2_url = "https://cdn.fmi.fi/apps/sea-weather-forecasts-texts/day2.php"
    
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
        NIEUWE VERSIE: day1.php + day2.php
        Returns: dict met intro, warnings, forecast_sections, en vrk2_sections
        """
        try:
            result = {
                'intro': '',
                'warnings': [],           # ALLE warning content als 1 blok
                'forecast_sections': [],  # Day 1 forecasts
                'vrk2_sections': []       # Day 2 forecasts
            }
            
            # ===== HAAL DAY1.PHP OP =====
            print("  Fetching day1.php...")
            response1 = requests.get(self.marine_day1_url, timeout=10)
            response1.raise_for_status()
            soup1 = BeautifulSoup(response1.content, 'html.parser')
            
            # Haal intro op (marine-inference sectie)
            inference_section = soup1.find('section', id='marine-inference')
            if inference_section:
                inference_p = inference_section.find('p', class_='weather-forecast__weather')
                if inference_p:
                    result['intro'] = inference_p.get_text(strip=True)
            
            # Haal warnings op (marine-warnings sectie)
            warning_section = soup1.find('section', id='marine-warnings')
            if warning_section:
                warning_p = warning_section.find('p', class_='weather-forecast__weather')
                if warning_p:
                    warning_text = warning_p.get_text(strip=True)
                    # Als het niet "Ei varoituksia" is, voeg toe
                    if 'ei varoituksia' not in warning_text.lower():
                        # Parse warnings als er echte zijn
                        # Voor nu: sla hele tekst op
                        result['warnings'].append(('text', warning_text))
            
            # Haal forecast secties op (alle sections behalve marine-warnings en marine-inference)
            all_sections = soup1.find_all('section', class_='weather-forecast--marine')
            for section in all_sections:
                section_id = section.get('id')
                
                # Skip special sections
                if section_id in ['marine-warnings', 'marine-inference']:
                    continue
                
                # Haal gebied naam
                h3 = section.find('h3', class_='weather-forecast__title')
                if not h3:
                    continue
                
                area_name = h3.get_text(strip=True)
                # Verwijder timestamp uit naam
                area_name = area_name.split('\n')[0].strip()
                
                # Haal wind + weather info
                wind_p = section.find('p', class_='weather-forecast__wind')
                weather_p = section.find('p', class_='weather-forecast__weather')
                
                forecast_text = ""
                if wind_p:
                    forecast_text += wind_p.get_text(strip=True) + " "
                if weather_p:
                    forecast_text += weather_p.get_text(strip=True)
                
                forecast_text = forecast_text.strip()
                
                if forecast_text:
                    result['forecast_sections'].append({
                        'area': area_name,
                        'forecast': forecast_text
                    })
            
            # ===== HAAL DAY2.PHP OP =====
            print("  Fetching day2.php...")
            try:
                response2 = requests.get(self.marine_day2_url, timeout=10)
                response2.raise_for_status()
                soup2 = BeautifulSoup(response2.content, 'html.parser')
                
                # Haal alle forecast secties op
                all_sections2 = soup2.find_all('section', class_='weather-forecast--marine')
                for section in all_sections2:
                    # Haal gebied naam
                    h3 = section.find('h3', class_='weather-forecast__title')
                    if not h3:
                        continue
                    
                    area_name = h3.get_text(strip=True)
                    area_name = area_name.split('\n')[0].strip()
                    
                    # Haal wind + weather info
                    wind_p = section.find('p', class_='weather-forecast__wind')
                    weather_p = section.find('p', class_='weather-forecast__weather')
                    
                    forecast_text = ""
                    if wind_p:
                        forecast_text += wind_p.get_text(strip=True) + " "
                    if weather_p:
                        forecast_text += weather_p.get_text(strip=True)
                    
                    forecast_text = forecast_text.strip()
                    
                    if forecast_text:
                        result['vrk2_sections'].append({
                            'area': area_name,
                            'forecast': forecast_text
                        })
            
            except Exception as e:
                print(f"  ⚠ Warning: Could not fetch day2.php: {e}")
            
            # Clean up whitespace
            result['intro'] = result['intro'].strip()
            
            print(f"✓ Marine forecast opgehaald:")
            print(f"  - Intro: {len(result['intro'])} chars")
            if result['warnings']:
                print(f"  - Waarschuwingen: {len(result['warnings'])} items")
            else:
                print(f"  - Waarschuwingen: geen")
            print(f"  - Forecast secties (day1): {len(result['forecast_sections'])}")
            print(f"  - VRK2 secties (day2): {len(result['vrk2_sections'])}")
            
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