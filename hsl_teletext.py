import copy
from hsl_route_scraper import HSLRouteScraper
from textBlock import tableRow
from page import exportTTI, loadTTI
from legaliser import pageLegaliser

# API KEY
API_KEY = "e9561c686c054ff99c03b9b117cce72a"

# Maak scraper instance
scraper = HSLRouteScraper(api_key=API_KEY)

# HSL route URLs - M1 en M2
routes_urls = {
    "M1": "https://reittiopas.hsl.fi/linjat/HSL:31M1/pysakit/HSL:31M1:0:01",
    "M2": "https://reittiopas.hsl.fi/linjat/HSL:31M2/pysakit/HSL:31M2:0:01"
}

# Haal data op
routes_data = {}
for route_name, route_url in routes_urls.items():
    print(f"Bezig met ophalen van {route_name}...")
    data = scraper.scrape_route(route_url)
    if data:
        routes_data[route_name] = data
    else:
        print(f"Geen data voor {route_name}")

if not routes_data:
    print("Geen HSL data gevonden.")
    exit()

# ============================================================
# PAGINA 401 - ROUTES M1 en M2 (2 subpagina's)
# ============================================================

template_401 = loadTTI("hsl_routes_page.tti")

# Maak deep copy van packets met alle text en control codes
import json

teletextPage401 = {
    "number": 455,
    "control": {"cycleTime": "5,T"},
    "subpages": [
        {
            "packets": json.loads(json.dumps(template_401["subpages"][0]["packets"]))
        },
        {
            "packets": json.loads(json.dumps(template_401["subpages"][0]["packets"]))
        }
    ]
}

# Haal stops op voor beide routes (eerste pattern alleen)
m1_pattern = routes_data.get("M1", {}).get("patterns", [{}])[0]
m1_stops = m1_pattern.get("stops", [])
m1_pattern_code = m1_pattern.get("code", "")

m2_pattern = routes_data.get("M2", {}).get("patterns", [{}])[0]
m2_stops = m2_pattern.get("stops", [])
m2_pattern_code = m2_pattern.get("code", "")

# SUBPAGINA 1 - M1
line = 6

# Voeg M1 header toe
m1_header_dict = {"title": "M1 Kivenlahti-Vuosaari"}
m1_header_row = tableRow(
    [
        {"width": 38, "data": "title", "colour": "white"},
    ],
    m1_header_dict
)
if m1_header_row is not None:
    teletextPage401["subpages"][0]["packets"] += [{"number": line, "text": m1_header_row}]
    line += 1

# Voeg tijdkolom headers toe (SAAPUVA SEURAAVA)
time_header_row = tableRow(
    [
        {"width": 19, "data": "empty", "colour": "white"},
        {"width": 9, "data": "label1", "colour": "yellow", "align": "right"},
        {"width": 9, "data": "label2", "colour": "yellow", "align": "right"},
    ],
    {"empty": "", "label1": "SAAPUVA", "label2": "SEURAAVA"}
)
if time_header_row is not None:
    teletextPage401["subpages"][0]["packets"] += [{"number": line, "text": time_header_row}]
    line += 1

# Verzamel alle stops met tijden
stops_with_times = []
for stop in m1_stops:
    times = scraper.get_stop_times_for_route(stop["gtfsId"], "M1")
    if times and len(times) >= 1:
        # Eerste tijd in minuten voor sortering
        first_time_parts = times[0].split(":")
        hours = int(first_time_parts[0])
        minutes = int(first_time_parts[1])
        minutes_since_midnight = hours * 60 + minutes
        
        # Als tijd < 03:00, behandel als volgende dag (voeg 24 uur toe)
        if hours < 3:
            minutes_since_midnight += 24 * 60
        
        stops_with_times.append({
            "stop": stop,
            "times": times,
            "sort_key": minutes_since_midnight
        })

# Sorteer op tijd
stops_with_times.sort(key=lambda x: x["sort_key"])

# Voeg gesorteerde stops toe
for item in stops_with_times:
    stop = item["stop"]
    times = item["times"]
    
    stop_name = stop["name"][:19]
    
    # Splits eerste en tweede tijd
    time1 = times[0] if len(times) >= 1 else "--:--"
    time2 = times[1] if len(times) >= 2 else "--:--"
    
    rowDict = {
        "name": stop_name,
        "time1": time1,
        "time2": time2
    }
    
    row = tableRow(
        [
            {"width": 19, "data": "name", "colour": "cyan", "align": "left"},
            {"width": 9, "data": "time1", "colour": "cyan", "align": "right"},
            {"width": 9, "data": "time2", "colour": "cyan", "align": "right"},
        ],
        rowDict
    )
    
    if row is None:
        continue
    
    tt_block = [{"number": line, "text": row}]
    
    if (line + len(tt_block)) > 22:
        break
    
    teletextPage401["subpages"][0]["packets"] += tt_block
    line += len(tt_block)

# SUBPAGINA 2 - M2
line = 6

# Voeg M2 header toe
m2_header_dict = {"title": "M2 Tapiola-Mellunmaki"}
m2_header_row = tableRow(
    [
        {"width": 38, "data": "title", "colour": "white"},
    ],
    m2_header_dict
)
if m2_header_row is not None:
    teletextPage401["subpages"][1]["packets"] += [{"number": line, "text": m2_header_row}]
    line += 1

# Voeg tijdkolom headers toe (SAAPUVA SEURAAVA)
time_header_row = tableRow(
    [
        {"width": 19, "data": "empty", "colour": "white"},
        {"width": 9, "data": "label1", "colour": "yellow", "align": "right"},
        {"width": 9, "data": "label2", "colour": "yellow", "align": "right"},
    ],
    {"empty": "", "label1": "SAAPUVA", "label2": "SEURAAVA"}
)
if time_header_row is not None:
    teletextPage401["subpages"][1]["packets"] += [{"number": line, "text": time_header_row}]
    line += 1

# Verzamel alle stops met tijden
stops_with_times = []
for stop in m2_stops:
    times = scraper.get_stop_times_for_route(stop["gtfsId"], "M2")
    if times and len(times) >= 1:
        # Eerste tijd in minuten voor sortering
        first_time_parts = times[0].split(":")
        hours = int(first_time_parts[0])
        minutes = int(first_time_parts[1])
        minutes_since_midnight = hours * 60 + minutes
        
        # Als tijd < 03:00, behandel als volgende dag (voeg 24 uur toe)
        if hours < 3:
            minutes_since_midnight += 24 * 60
        
        stops_with_times.append({
            "stop": stop,
            "times": times,
            "sort_key": minutes_since_midnight
        })

# Sorteer op tijd
stops_with_times.sort(key=lambda x: x["sort_key"])

# Voeg gesorteerde stops toe
for item in stops_with_times:
    stop = item["stop"]
    times = item["times"]
    
    stop_name = stop["name"][:19]
    
    # Splits eerste en tweede tijd
    time1 = times[0] if len(times) >= 1 else "--:--"
    time2 = times[1] if len(times) >= 2 else "--:--"
    
    rowDict = {
        "name": stop_name,
        "time1": time1,
        "time2": time2
    }
    
    row = tableRow(
        [
            {"width": 19, "data": "name", "colour": "yellow", "align": "left"},
            {"width": 9, "data": "time1", "colour": "yellow", "align": "right"},
            {"width": 9, "data": "time2", "colour": "yellow", "align": "right"},
        ],
        rowDict
    )
    
    if row is None:
        continue
    
    tt_block = [{"number": line, "text": row}]
    
    if (line + len(tt_block)) > 22:
        break
    
    teletextPage401["subpages"][1]["packets"] += tt_block
    line += len(tt_block)

exportTTI(pageLegaliser(teletextPage401))
print("HSL Metro Routes Teletextpagina 401 gegenereerd (2 subpagina's).")

# ============================================================
# PAGINA 402 - DISRUPTIONS
# ============================================================

template_402 = loadTTI("hsl_disruptions_page.tti")

# Maak deep copy van packets met alle text en control codes
import json

teletextPage402 = {
    "number": 456,
    "subpages": [{
        "packets": json.loads(json.dumps(template_402["subpages"][0]["packets"]))
    }]
}

line = 6
disruptions_found = False

# Verzamel alle disruptions
all_disruptions = []

for route_name, route_data in routes_data.items():
    # Route-level alerts
    if route_data.get('alerts'):
        for alert in route_data['alerts']:
            all_disruptions.append({
                "route": route_name,
                "level": "Linja",
                "location": route_name,
                "severity": alert.get('alertSeverityLevel', 'INFO')[:4],
                "header": alert.get('alertHeaderText', 'Hairio')[:35]
            })
    
    # Pattern-level alerts
    for pattern in route_data.get('patterns', []):
        if pattern.get('alerts'):
            for alert in pattern['alerts']:
                all_disruptions.append({
                    "route": route_name,
                    "level": "Suun",
                    "location": pattern['headsign'][:15],
                    "severity": alert.get('alertSeverityLevel', 'INFO')[:4],
                    "header": alert.get('alertHeaderText', 'Hairio')[:35]
                })
        
        # Stop-level alerts
        for stop in pattern['stops']:
            if stop.get('alerts'):
                for alert in stop['alerts']:
                    all_disruptions.append({
                        "route": route_name,
                        "level": "Pysa",
                        "location": stop['name'][:15],
                        "severity": alert.get('alertSeverityLevel', 'INFO')[:4],
                        "header": alert.get('alertHeaderText', 'Hairio')[:35]
                    })

if all_disruptions:
    disruptions_found = True
    for disruption in all_disruptions:
        rowDict = {
            "route": disruption["route"][:2],        
            "level": disruption["level"][:4],        
            "location": disruption["location"][:10],  
            "header": disruption["header"][:20]       
        }
        
        row = tableRow(
            [
                {"width": 2,  "data": "route",    "colour": "white"},
                {"width": 4,  "data": "level",    "colour": "yellow"},
                {"width": 10, "data": "location", "colour": "cyan"},
                {"width": 20, "data": "header",   "colour": "white"},
            ],
            rowDict
        )
        
        # Check of row succesvol is
        if row is None:
            continue
        
        tt_block = [{"number": line, "text": row}]
        
        if (line + len(tt_block)) > 22:
            break
        
        teletextPage402["subpages"][0]["packets"] += tt_block
        line += len(tt_block)
else:
    # Geen disruptions
    no_disruption_text = "Ei aktiivisia hairioita"
    rowDict = {"message": no_disruption_text}
    
    row = tableRow(
        [
            {"width": 40, "data": "message", "colour": "green"},
        ],
        rowDict
    )
    
    if row is not None:
        tt_block = [{"number": line, "text": row}]
        teletextPage402["subpages"][0]["packets"] += tt_block

exportTTI(pageLegaliser(teletextPage402))
print("HSL Disruptions Teletextpagina 402 gegenereerd.")

print("\nKlaar! Pagina's 401 en 402 gegenereerd.")