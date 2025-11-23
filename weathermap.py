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
        return "aamu"  # ochtend
    elif 12 <= uur < 18:
        return "iltapäivä"  # middag
    elif 18 <= uur < 24:
        return "ilta"  # avond
    else:
        return "yö"  # nacht

def get_volgend_dagdeel(huidig_dagdeel, huidig_uur):
    """
    Geef het volgende dagdeel en of het morgen is
    Returns: (volgend_dagdeel, is_morgen, daaropvolgend_dagdeel, is_overmorgen)
    """
    volgorde = ["yö", "aamu", "iltapäivä", "ilta"]
    huidige_index = volgorde.index(huidig_dagdeel)
    
    volgende_index = (huidige_index + 1) % 4
    volgend_dagdeel = volgorde[volgende_index]
    
    daaropvolgende_index = (huidige_index + 2) % 4
    daaropvolgend_dagdeel = volgorde[daaropvolgende_index]
    
    # Check of we naar de volgende dag gaan
    # We gaan naar morgen als we van ilta->yö gaan (rond middernacht)
    is_morgen = False
    is_overmorgen = False
    
    # Volgend dagdeel is morgen als:
    # - We zijn in 'ilta' (18:00-24:00) en volgend is 'yö' -> morgen nacht
    if huidig_dagdeel == "ilta" and volgend_dagdeel == "yö":
        is_morgen = True
    
    # Daaropvolgend dagdeel is morgen als:
    # - We zijn in 'ilta' en daaropvolgend is 'aamu' -> morgenochtend
    # - We zijn in 'yö' (00:00-06:00) en daaropvolgend is 'iltapäivä' -> nog steeds vandaag->morgen
    # - Het volgend dagdeel was al morgen, dan is daaropvolgend ook morgen
    if huidig_dagdeel == "ilta" and daaropvolgend_dagdeel == "aamu":
        is_overmorgen = True
    elif is_morgen and daaropvolgend_dagdeel == "aamu":
        is_overmorgen = True
    
    return volgend_dagdeel, is_morgen, daaropvolgend_dagdeel, is_overmorgen

def round_tijd_op_15_min():
    """Rond de huidige tijd naar dichtstbijzijnde kwartier"""
    nu = datetime.now()
    # Rond naar dichtstbijzijnde 15 minuten
    minuten = round(nu.minute / 15) * 15
    
    if minuten == 60:
        nu = nu + timedelta(hours=1)
        minuten = 0
    
    afgeronde_tijd = nu.replace(minute=minuten, second=0, microsecond=0)
    return f"Klo {afgeronde_tijd.strftime('%H.%M')}"

def get_finnish_datum():
    """Geef de huidige datum in Fins formaat (16.11.2025)"""
    nu = datetime.now()
    return f"{nu.day:02d}.{nu.month:02d}.{nu.year}"

def get_weer_forecast(locatie, api_key, uren_vooruit=0):
    """
    Haalt weersverwachting op voor een specifieke locatie
    uren_vooruit: aantal uren in de toekomst (0 = nu, 3 = over 3 uur, etc.)
    """
    # Gebruik forecast API voor toekomstige data
    if uren_vooruit > 0:
        url = f"http://api.openweathermap.org/data/2.5/forecast?q={locatie},FI&appid={api_key}&units=metric&lang=fi"
    else:
        # Voor huidige data gebruik current weather API
        url = f"http://api.openweathermap.org/data/2.5/weather?q={locatie},FI&appid={api_key}&units=metric&lang=fi"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            if uren_vooruit > 0:
                # Forecast API geeft lijst met 3-uurs intervallen
                # Zoek de dichtstbijzijnde forecast
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


def maak_weer_kaart(input_bestand="weathermap.tti"):
    """Maakt een teletext weerkaart van Finland met 3 subpagina's"""
    api_key = "bfb1f2b8ee2cc2051070561815d83445"
    
    if not os.path.exists(input_bestand):
        print(f"FOUT: Template bestand '{input_bestand}' niet gevonden.")
        print("Maak eerst een .tti bestand met je kaartdata en placeholders (10, 20, 30, etc.)")
        return
    
    try:
        # Lees het template bestand in
        template = loadTTI(input_bestand)
        
        print("Template bestand ingelezen...")
        
        # Bepaal huidige tijd en dagdelen
        nu = datetime.now()
        datum = get_finnish_datum()
        tijd = round_tijd_op_15_min()
        huidig_dagdeel = get_dagdeel(nu.hour)
        volgend_dagdeel, is_morgen, daaropvolgend_dagdeel, is_overmorgen = get_volgend_dagdeel(huidig_dagdeel, nu.hour)
        
        # Bereken uren vooruit voor elk dagdeel
        # Huidig = 0 uur, volgend = ~6 uur, daaropvolgend = ~12 uur
        uren_huidig = 0
        uren_volgend = 6
        uren_daaropvolgend = 12
        
        # Maak 3 subpagina's
        subpages = []
        
        # === SUBPAGINA 1: Huidig weer ===
        print(f"\nSubpagina 1: {datum} {tijd} - {DAGDELEN_FIN[huidig_dagdeel]}")
        temperaturen_nu = {}
        for placeholder, info in TEMPERATUUR_LOCATIES.items():
            weer_data = get_weer_forecast(info["locatie"], api_key, uren_huidig)
            if weer_data:
                temperaturen_nu[placeholder] = weer_data["temp"]
                print(f"  {info['locatie']}: {weer_data['temp']}°C - {weer_data['beschrijving']}")
            else:
                print(f"  Kon geen weerdata ophalen voor {info['locatie']}")
        
        subpage1 = {"packets": copy.deepcopy(template["subpages"][0]["packets"])}
        
        # Vervang placeholders in packets (zoals demo.py doet)
        for packet in subpage1["packets"]:
            if "text" in packet:
                text = packet["text"]
                
                # Split bij de eerste komma's om OL,XX, te beschermen
                if text.startswith("OL,"):
                    parts = text.split(",", 2)
                    if len(parts) == 3:
                        prefix = f"{parts[0]},{parts[1]},"
                        content = parts[2]
                        
                        # EERST dagdeel vervangen
                        content = re.sub(r'HUOMISILTAAN ASTI:', DAGDELEN_FIN[huidig_dagdeel], content)
                        
                        # DAN temperaturen vervangen (niet in datum/tijd patronen)
                        for placeholder, temp in temperaturen_nu.items():
                            temp_str = f"{int(temp):02d}"
                            # Niet vervangen als het in een tijd/datum staat
                            pattern = rf'(?<!Klo )(?<!\d)(?<!\.){re.escape(placeholder)}(?!\d)(?!\.)'
                            content = re.sub(pattern, temp_str, content)
                        
                        # LAATST datum en tijd vervangen (nadat temperaturen al gedaan zijn)
                        content = re.sub(r'11\.01\.1988', datum, content)
                        content = re.sub(r'Klo 19\.00', tijd, content)
                        
                        packet["text"] = prefix + content
                else:
                    # EERST datum
                    text = re.sub(r'11\.01\.1988', datum, text)
                    text = re.sub(r'HUOMISILTAAN ASTI:', DAGDELEN_FIN[huidig_dagdeel], text)
                    
                    # DAN temperaturen (niet in "Klo XX.XX")
                    for placeholder, temp in temperaturen_nu.items():
                        temp_str = f"{int(temp):02d}"
                        pattern = rf'(?<!Klo )(?<!\d){re.escape(placeholder)}(?!\d)(?!\.)'
                        text = re.sub(pattern, temp_str, text)
                    
                    # LAATST tijd
                    text = re.sub(r'Klo 19\.00', tijd, text)
                    
                    packet["text"] = text
        
        subpages.append(subpage1)
        
        # === SUBPAGINA 2: Volgend dagdeel ===
        geldig_volgend = DAGDELEN_FIN_MORGEN[volgend_dagdeel] if is_morgen else DAGDELEN_FIN[volgend_dagdeel]
        print(f"\nSubpagina 2: {datum} {tijd} - {geldig_volgend}")
        temperaturen_volgend = {}
        for placeholder, info in TEMPERATUUR_LOCATIES.items():
            weer_data = get_weer_forecast(info["locatie"], api_key, uren_volgend)
            if weer_data:
                temperaturen_volgend[placeholder] = weer_data["temp"]
                print(f"  {info['locatie']}: {weer_data['temp']}°C - {weer_data['beschrijving']}")
            else:
                print(f"  Kon geen weerdata ophalen voor {info['locatie']}")
        
        subpage2 = {"packets": copy.deepcopy(template["subpages"][0]["packets"])}
        
        # Vervang placeholders in packets
        for packet in subpage2["packets"]:
            if "text" in packet:
                text = packet["text"]
                
                if text.startswith("OL,"):
                    parts = text.split(",", 2)
                    if len(parts) == 3:
                        prefix = f"{parts[0]},{parts[1]},"
                        content = parts[2]
                        
                        # EERST datum en tijd
                        content = re.sub(r'11\.01\.1988', datum, content)
                        content = re.sub(r'Klo 19\.00', tijd, content)
                        content = re.sub(r'HUOMISILTAAN ASTI:', geldig_volgend, content)
                        
                        # DAN temperaturen (niet in "Klo XX.XX")
                        for placeholder, temp in temperaturen_volgend.items():
                            temp_str = f"{int(temp):02d}"
                            pattern = rf'(?<!Klo )(?<!\d){re.escape(placeholder)}(?!\d)(?!\.)'
                            content = re.sub(pattern, temp_str, content)
                        
                        packet["text"] = prefix + content
                else:
                    text = re.sub(r'11\.01\.1988', datum, text)
                    text = re.sub(r'Klo 19\.00', tijd, text)
                    text = re.sub(r'HUOMISILTAAN ASTI:', geldig_volgend, text)
                    
                    for placeholder, temp in temperaturen_volgend.items():
                        temp_str = f"{int(temp):02d}"
                        pattern = rf'(?<!Klo )(?<!\d){re.escape(placeholder)}(?!\d)(?!\.)'
                        text = re.sub(pattern, temp_str, text)
                    
                    packet["text"] = text
        
        subpages.append(subpage2)
        
        # === SUBPAGINA 3: Daaropvolgend dagdeel ===
        geldig_daarna = DAGDELEN_FIN_MORGEN[daaropvolgend_dagdeel] if is_overmorgen else DAGDELEN_FIN[daaropvolgend_dagdeel]
        print(f"\nSubpagina 3: {datum} {tijd} - {geldig_daarna}")
        temperaturen_daarna = {}
        for placeholder, info in TEMPERATUUR_LOCATIES.items():
            weer_data = get_weer_forecast(info["locatie"], api_key, uren_daaropvolgend)
            if weer_data:
                temperaturen_daarna[placeholder] = weer_data["temp"]
                print(f"  {info['locatie']}: {weer_data['temp']}°C - {weer_data['beschrijving']}")
            else:
                print(f"  Kon geen weerdata ophalen voor {info['locatie']}")
        
        subpage3 = {"packets": copy.deepcopy(template["subpages"][0]["packets"])}
        
        # Vervang placeholders in packets
        for packet in subpage3["packets"]:
            if "text" in packet:
                text = packet["text"]
                
                if text.startswith("OL,"):
                    parts = text.split(",", 2)
                    if len(parts) == 3:
                        prefix = f"{parts[0]},{parts[1]},"
                        content = parts[2]
                        
                        # EERST datum en tijd
                        content = re.sub(r'11\.01\.1988', datum, content)
                        content = re.sub(r'Klo 19\.00', tijd, content)
                        content = re.sub(r'HUOMISILTAAN ASTI:', geldig_daarna, content)
                        
                        # DAN temperaturen (niet in "Klo XX.XX")
                        for placeholder, temp in temperaturen_daarna.items():
                            temp_str = f"{int(temp):02d}"
                            pattern = rf'(?<!Klo )(?<!\d){re.escape(placeholder)}(?!\d)(?!\.)'
                            content = re.sub(pattern, temp_str, content)
                        
                        packet["text"] = prefix + content
                else:
                    text = re.sub(r'11\.01\.1988', datum, text)
                    text = re.sub(r'Klo 19\.00', tijd, text)
                    text = re.sub(r'HUOMISILTAAN ASTI:', geldig_daarna, text)
                    
                    for placeholder, temp in temperaturen_daarna.items():
                        temp_str = f"{int(temp):02d}"
                        pattern = rf'(?<!Klo )(?<!\d){re.escape(placeholder)}(?!\d)(?!\.)'
                        text = re.sub(pattern, temp_str, text)
                    
                    packet["text"] = text
        
        subpages.append(subpage3)
        
        # Maak de volledige pagina met alle 3 subpagina's
        page = {
            "number": 166,
            "subpages": subpages,
            "control": {"cycleTime": "5,T"}
        }
        
        # Exporteer als 1 TTI bestand
        exportTTI(pageLegaliser(page))
        
        print(f"\n✓ Weerkaart met 3 subpagina's opgeslagen als teletext/P166.tti")
        print("Je kunt dit bestand nu importeren in je teletext systeem")
        
    except Exception as e:
        print(f"Fout bij maken van weerkaart: {e}")
        import traceback
        traceback.print_exc()


def test_temperaturen():
    """Test functie om alleen de temperaturen op te halen"""
    api_key = "bfb1f2b8ee2cc2051070561815d83445"
    
    print("Test van weerdata ophalen:")
    print("-" * 50)
    
    print("\nHuidig weer:")
    for placeholder, info in TEMPERATUUR_LOCATIES.items():
        locatie = info["locatie"]
        weer_data = get_weer_forecast(locatie, api_key, 0)
        
        if weer_data:
            print(f"{locatie:12} (placeholder {placeholder:2}): {weer_data['temp']:2}°C - {weer_data['beschrijving']}")
        else:
            print(f"{locatie:12} (placeholder {placeholder:2}): FOUT - geen data")
    
    print("\nOver 6 uur:")
    for placeholder, info in TEMPERATUUR_LOCATIES.items():
        locatie = info["locatie"]
        weer_data = get_weer_forecast(locatie, api_key, 6)
        
        if weer_data:
            print(f"{locatie:12}: {weer_data['temp']:2}°C - {weer_data['beschrijving']}")
    
    # Test datum/tijd functies
    print("\n" + "-" * 50)
    print(f"Datum: {get_finnish_datum()}")
    print(f"Tijd (afgerond): {round_tijd_op_15_min()}")
    
    nu = datetime.now()
    huidig = get_dagdeel(nu.hour)
    volgend, is_morgen, daarna, is_overmorgen = get_volgend_dagdeel(huidig, nu.hour)
    
    geldig_nu = DAGDELEN_FIN[huidig]
    geldig_volgend = DAGDELEN_FIN_MORGEN[volgend] if is_morgen else DAGDELEN_FIN[volgend]
    geldig_daarna = DAGDELEN_FIN_MORGEN[daarna] if is_overmorgen else DAGDELEN_FIN[daarna]
    
    print(f"Huidig dagdeel: {geldig_nu}")
    print(f"Volgend dagdeel: {geldig_volgend}")
    print(f"Daaropvolgend: {geldig_daarna}")


# Automatisch uitvoeren bij import (voor demo.py)
if os.path.exists("weathermap.tti"):
    maak_weer_kaart("weathermap.tti")

# Voor handmatige uitvoering vanaf command line
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            test_temperaturen()
        else:
            # Gebruik aangegeven bestand als template
            maak_weer_kaart(sys.argv[1])
    else:
        print("Gebruik 'python weathermap.py test' voor testen")
        print("Of 'python weathermap.py <bestand.tti>' voor een specifiek template")