import requests
import os
import re
from datetime import datetime, timedelta
import copy
from page import exportTTI, loadTTI
from legaliser import pageLegaliser

# Temperatuurlocaties met hun placeholder tekst die vervangen moet worden
TEMPERATUUR_LOCATIES = {
    "10": {"locatie": "Helsinki"},      # Zuid-Finland
    "20": {"locatie": "Tampere"},       # Centraal-Finland
    "30": {"locatie": "Kuopio"},        # Oost-Finland
    "40": {"locatie": "Puolanka"},      # Noord-Centraal
    "50": {"locatie": "Sodankylä"},     # Lapland
}

# Finse dagdelen (geldigheid voorspelling)
# Alle moeten even lang zijn als "HUOMISILTAAN ASTI:" (19 chars inclusief :)
DAGDELEN_FIN = {
    "aamu": "AAMUUN ASTI:",              # tot ochtend
    "iltapäivä": "ILTAPÄIVÄÄN ASTI:",    # tot middag
    "ilta": "ILTAAN ASTI:",              # tot avond
    "yö": "YÖHÖN ASTI:"                  # tot nacht
}

DAGDELEN_FIN_MORGEN = {
    "aamu": "HUOMISAAMUUN ASTI:",        # tot morgenochtend
    "iltapäivä": "HUOMISILTAPÄIVÄÄN:",   # tot morgenmiddag (past niet met ASTI)
    "ilta": "HUOMISILTAAN ASTI:",        # tot morgenavond
    "yö": "HUOMISYÖHÖN ASTI:"            # tot morgennacht
}

# Pad alle strings naar 19 karakters (lengte van "HUOMISILTAAN ASTI:")
for key in DAGDELEN_FIN:
    DAGDELEN_FIN[key] = DAGDELEN_FIN[key].ljust(19)

for key in DAGDELEN_FIN_MORGEN:
    DAGDELEN_FIN_MORGEN[key] = DAGDELEN_FIN_MORGEN[key].ljust(19)

def get_dagdeel(uur):
    """Bepaal het dagdeel op basis van het uur (in het Fins)"""
    if 6 <= uur < 12:
        return "aamu"
    elif 12 <= uur < 18:
        return "iltapäivä"
    elif 18 <= uur < 24:
        return "ilta"
    else:
        return "yö"

def get_volgend_dagdeel(huidig_dagdeel, huidig_uur):
    """Geef het volgende dagdeel en of het morgen is"""
    volgorde = ["yö", "aamu", "iltapäivä", "ilta"]
    huidige_index = volgorde.index(huidig_dagdeel)
    
    volgende_index = (huidige_index + 1) % 4
    volgend_dagdeel = volgorde[volgende_index]
    
    daaropvolgende_index = (huidige_index + 2) % 4
    daaropvolgend_dagdeel = volgorde[daaropvolgende_index]
    
    is_morgen = False
    is_overmorgen = False
    
    if huidig_dagdeel == "ilta" and volgend_dagdeel == "yö":
        is_morgen = True
    
    if huidig_dagdeel == "ilta" and daaropvolgend_dagdeel == "aamu":
        is_overmorgen = True
    elif is_morgen and daaropvolgend_dagdeel == "aamu":
        is_overmorgen = True
    
    return volgend_dagdeel, is_morgen, daaropvolgend_dagdeel, is_overmorgen

def round_tijd_op_15_min():
    """Rond de huidige tijd naar dichtstbijzijnde kwartier"""
    nu = datetime.now()
    minuten = round(nu.minute / 15) * 15
    
    if minuten == 60:
        nu = nu + timedelta(hours=1)
        minuten = 0
    
    afgeronde_tijd = nu.replace(minute=minuten, second=0, microsecond=0)
    return f"Klo {afgeronde_tijd.strftime('%H.%M')}"

def get_finnish_datum():
    """Geef de huidige datum in Fins formaat"""
    nu = datetime.now()
    return f"{nu.day:02d}.{nu.month:02d}.{nu.year}"

def get_weer_forecast(locatie, api_key, uren_vooruit=0):
    """Haalt weersverwachting op voor een specifieke locatie"""
    if uren_vooruit > 0:
        url = f"http://api.openweathermap.org/data/2.5/forecast?q={locatie},FI&appid={api_key}&units=metric&lang=fi"
    else:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={locatie},FI&appid={api_key}&units=metric&lang=fi"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            if uren_vooruit > 0:
                target_time = datetime.now() + timedelta(hours=uren_vooruit)
                closest_forecast = None
                min_diff = float('inf')
                
                for forecast in data['list']:
                    forecast_time = datetime.fromtimestamp(forecast['dt'])
                    diff = abs((forecast_time - target_time).total_seconds())
                    if diff < min_diff:
                        min_diff = diff
                        closest_forecast = forecast
                
                if closest_forecast:
                    return {
                        "temp": round(closest_forecast["main"]["temp"]),
                        "weer_id": str(closest_forecast["weather"][0]["id"]),
                        "beschrijving": closest_forecast["weather"][0]["description"]
                    }
            else:
                return {
                    "temp": round(data["main"]["temp"]),
                    "weer_id": str(data["weather"][0]["id"]),
                    "beschrijving": data["weather"][0]["description"]
                }
        else:
            print(f"Fout bij ophalen van weergegevens voor {locatie}: {response.status_code}")
            return None
    except Exception as e:
        print(f"Fout bij ophalen van weergegevens voor {locatie}: {e}")
        return None

def vervang_placeholders(packet_text, temperaturen, datum, tijd, dagdeel_tekst):
    """Vervang alle placeholders in een packet text"""
    text = packet_text
    
    # Als het een OL regel is, splits dan prefix en content
    if text.startswith("OL,"):
        parts = text.split(",", 2)
        if len(parts) == 3:
            prefix = f"{parts[0]},{parts[1]},"
            content = parts[2]
            
            # EERST dagdeel vervangen
            content = re.sub(r'HUOMISILTAAN ASTI:', dagdeel_tekst, content)
            
            # DAN temperaturen vervangen (niet in datum/tijd patronen)
            for placeholder, temp in temperaturen.items():
                temp_str = f"{int(temp):02d}"
                # Niet vervangen als het in een tijd/datum staat
                pattern = rf'(?<!Klo )(?<!\d)(?<!\.){re.escape(placeholder)}(?!\d)(?!\.)'
                content = re.sub(pattern, temp_str, content)
            
            # LAATST datum en tijd vervangen (nadat temperaturen al gedaan zijn)
            content = re.sub(r'11\.01\.1988', datum, content)
            content = re.sub(r'Klo 19\.00', tijd, content)
            
            return prefix + content
        else:
            return text
    else:
        # Niet-OL regels (hoewel die niet vaak voorkomen)
        text = re.sub(r'11\.01\.1988', datum, text)
        text = re.sub(r'HUOMISILTAAN ASTI:', dagdeel_tekst, text)
        
        for placeholder, temp in temperaturen.items():
            temp_str = f"{int(temp):02d}"
            pattern = rf'(?<!Klo )(?<!\d)(?<!\.){re.escape(placeholder)}(?!\d)(?!\.)'
            text = re.sub(pattern, temp_str, text)
        
        text = re.sub(r'Klo 19\.00', tijd, text)
        
        return text

def get_weather_subpages(input_bestand="weathermap.tti"):
    """
    Retourneert de 3 weerkaart subpages als lijst van packet dictionaries
    Deze functie kan gebruikt worden door newsreel.py
    """
    api_key = "bfb1f2b8ee2cc2051070561815d83445"
    
    if not os.path.exists(input_bestand):
        print(f"FOUT: Template bestand '{input_bestand}' niet gevonden.")
        return []
    
    try:
        template = loadTTI(input_bestand)
        
        # Bepaal huidige tijd en dagdelen
        nu = datetime.now()
        datum = get_finnish_datum()
        tijd = round_tijd_op_15_min()
        huidig_dagdeel = get_dagdeel(nu.hour)
        volgend_dagdeel, is_morgen, daaropvolgend_dagdeel, is_overmorgen = get_volgend_dagdeel(huidig_dagdeel, nu.hour)
        
        subpages = []
        
        # === SUBPAGINA 1: Huidig weer ===
        temperaturen_nu = {}
        for placeholder, info in TEMPERATUUR_LOCATIES.items():
            weer_data = get_weer_forecast(info["locatie"], api_key, 0)
            if weer_data:
                temperaturen_nu[placeholder] = weer_data["temp"]
        
        subpage1 = {"packets": copy.deepcopy(template["subpages"][0]["packets"])}
        for packet in subpage1["packets"]:
            if "text" in packet:
                packet["text"] = vervang_placeholders(
                    packet["text"], 
                    temperaturen_nu, 
                    datum, 
                    tijd, 
                    DAGDELEN_FIN[huidig_dagdeel]
                )
        subpages.append(subpage1)
        
        # === SUBPAGINA 2: Volgend dagdeel ===
        temperaturen_volgend = {}
        for placeholder, info in TEMPERATUUR_LOCATIES.items():
            weer_data = get_weer_forecast(info["locatie"], api_key, 6)
            if weer_data:
                temperaturen_volgend[placeholder] = weer_data["temp"]
        
        geldig_volgend = DAGDELEN_FIN_MORGEN[volgend_dagdeel] if is_morgen else DAGDELEN_FIN[volgend_dagdeel]
        subpage2 = {"packets": copy.deepcopy(template["subpages"][0]["packets"])}
        for packet in subpage2["packets"]:
            if "text" in packet:
                packet["text"] = vervang_placeholders(
                    packet["text"], 
                    temperaturen_volgend, 
                    datum, 
                    tijd, 
                    geldig_volgend
                )
        subpages.append(subpage2)
        
        # === SUBPAGINA 3: Daaropvolgend dagdeel ===
        temperaturen_daarna = {}
        for placeholder, info in TEMPERATUUR_LOCATIES.items():
            weer_data = get_weer_forecast(info["locatie"], api_key, 12)
            if weer_data:
                temperaturen_daarna[placeholder] = weer_data["temp"]
        
        geldig_daarna = DAGDELEN_FIN_MORGEN[daaropvolgend_dagdeel] if is_overmorgen else DAGDELEN_FIN[daaropvolgend_dagdeel]
        subpage3 = {"packets": copy.deepcopy(template["subpages"][0]["packets"])}
        for packet in subpage3["packets"]:
            if "text" in packet:
                packet["text"] = vervang_placeholders(
                    packet["text"], 
                    temperaturen_daarna, 
                    datum, 
                    tijd, 
                    geldig_daarna
                )
        subpages.append(subpage3)
        
        return subpages
        
    except Exception as e:
        print(f"Fout bij ophalen weerkaart subpages: {e}")
        return []

def maak_weer_kaart(input_bestand="weathermap.tti"):
    """Maakt een teletext weerkaart van Finland met 3 subpagina's en exporteert naar P166"""
    
    subpages = get_weather_subpages(input_bestand)
    
    if not subpages:
        print("Geen weerdata beschikbaar")
        return
    
    # Maak de volledige pagina met alle 3 subpagina's
    page = {
        "number": 166,
        "subpages": subpages,
        "control": {"cycleTime": "5,T"}
    }
    
    # Exporteer als 1 TTI bestand
    exportTTI(pageLegaliser(page))
    
    print(f"\n✓ Weerkaart met {len(subpages)} subpagina's opgeslagen als teletext/P166.tti")

# Automatisch uitvoeren bij import (voor demo.py)
if os.path.exists("weathermap.tti"):
    maak_weer_kaart("weathermap.tti")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        maak_weer_kaart(sys.argv[1])
    else:
        maak_weer_kaart()