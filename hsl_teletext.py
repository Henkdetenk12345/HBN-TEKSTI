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
# PAGINA 401 - ROUTES M1 en M2 (4 subpagina's - beide richtingen)
# ============================================================

template_401 = loadTTI("hsl_routes_page.tti")

# Maak deep copy van packets met alle text en control codes
import json

teletextPage401 = {
    "number": 455,
    "control": {"cycleTime": "5,T"},
    "subpages": [
        {"packets": json.loads(json.dumps(template_401["subpages"][0]["packets"]))},
        {"packets": json.loads(json.dumps(template_401["subpages"][0]["packets"]))},
        {"packets": json.loads(json.dumps(template_401["subpages"][0]["packets"]))},
        {"packets": json.loads(json.dumps(template_401["subpages"][0]["packets"]))}
    ]
}

# Helper functie om subpagina te vullen
def fill_subpage(subpage_idx, route_name, pattern, route_color):
    stops = pattern.get("stops", [])
    pattern_headsign = pattern.get("headsign", "")
    
    line = 6
    
    # Bouw volledige route: eerste stop - laatste stop
    if stops:
        first_stop = stops[0].get("name", "")
        last_stop = stops[-1].get("name", "")
        route_description = f"{first_stop}-{last_stop}"
    else:
        route_description = pattern_headsign
    
    # Voeg route header toe
    header_dict = {"title": f"{route_name} {route_description}"}
    header_row = tableRow(
        [{"width": 38, "data": "title", "colour": "white"}],
        header_dict
    )
    if header_row is not None:
        teletextPage401["subpages"][subpage_idx]["packets"] += [{"number": line, "text": header_row}]
        line += 1
    
    # Voeg tijdkolom headers toe
    time_header_row = tableRow(
        [
            {"width": 19, "data": "empty", "colour": "white"},
            {"width": 9, "data": "label1", "colour": "yellow", "align": "right"},
            {"width": 9, "data": "label2", "colour": "yellow", "align": "right"},
        ],
        {"empty": "", "label1": "SAAPUVA", "label2": "SEURAAVA"}
    )
    if time_header_row is not None:
        teletextPage401["subpages"][subpage_idx]["packets"] += [{"number": line, "text": time_header_row}]
        line += 1
    
    # Verzamel alle stops met tijden
    stops_with_times = []
    for stop in stops:
        times = scraper.get_stop_times_for_route(stop["gtfsId"], route_name)
        if times and len(times) >= 1:
            first_time_parts = times[0].split(":")
            hours = int(first_time_parts[0])
            minutes = int(first_time_parts[1])
            minutes_since_midnight = hours * 60 + minutes
            
            if hours < 3:
                minutes_since_midnight += 24 * 60
            
            stops_with_times.append({
                "stop": stop,
                "times": times,
                "sort_key": minutes_since_midnight
            })
    
    stops_with_times.sort(key=lambda x: x["sort_key"])
    
    # Voeg gesorteerde stops toe
    for item in stops_with_times:
        stop = item["stop"]
        times = item["times"]
        
        stop_name = stop["name"][:19]
        time1 = times[0] if len(times) >= 1 else "--:--"
        time2 = times[1] if len(times) >= 2 else "--:--"
        
        rowDict = {
            "name": stop_name,
            "time1": time1,
            "time2": time2
        }
        
        row = tableRow(
            [
                {"width": 19, "data": "name", "colour": route_color, "align": "left"},
                {"width": 9, "data": "time1", "colour": route_color, "align": "right"},
                {"width": 9, "data": "time2", "colour": route_color, "align": "right"},
            ],
            rowDict
        )
        
        if row is None:
            continue
        
        tt_block = [{"number": line, "text": row}]
        
        if (line + len(tt_block)) > 22:
            break
        
        teletextPage401["subpages"][subpage_idx]["packets"] += tt_block
        line += len(tt_block)

# SUBPAGINA 1 - M1 richting 0 (Kivenlahti-Vuosaari)
m1_patterns = routes_data.get("M1", {}).get("patterns", [])
if len(m1_patterns) > 0:
    fill_subpage(0, "M1", m1_patterns[0], "cyan")

# SUBPAGINA 2 - M2 richting 0 (Tapiola-Mellunmaki)
m2_patterns = routes_data.get("M2", {}).get("patterns", [])
if len(m2_patterns) > 0:
    fill_subpage(1, "M2", m2_patterns[0], "yellow")

# SUBPAGINA 3 - M1 richting 1 (Vuosaari-Kivenlahti)
if len(m1_patterns) > 1:
    fill_subpage(2, "M1", m1_patterns[1], "cyan")

# SUBPAGINA 4 - M2 richting 1 (Mellunmaki-Tapiola)
if len(m2_patterns) > 1:
    fill_subpage(3, "M2", m2_patterns[1], "yellow")

exportTTI(pageLegaliser(teletextPage401))
print("HSL Metro Routes Teletextpagina 401 gegenereerd (4 subpagina's).")

# ============================================================
# PAGINA 402 - DISRUPTIONS (met multi-line text support en subpagina's)
# ============================================================

template_402 = loadTTI("hsl_disruptions_page.tti")

# Verzamel alle unieke disruptions (vermijd duplicaten)
all_disruptions = []
seen_disruptions = set()

for route_name, route_data in routes_data.items():
    # Route-level alerts
    if route_data.get('alerts'):
        for alert in route_data['alerts']:
            alert_key = (
                route_name,
                'route',
                alert.get('alertHeaderText', ''),
                alert.get('alertDescriptionText', '')
            )
            if alert_key not in seen_disruptions:
                seen_disruptions.add(alert_key)
                all_disruptions.append({
                    "route": route_name,
                    "level": "Linja",
                    "location": route_name,
                    "severity": alert.get('alertSeverityLevel', 'INFO')[:4],
                    "header": alert.get('alertHeaderText', 'Hairio'),
                    "description": alert.get('alertDescriptionText', '')
                })
    
    # Pattern-level alerts (vermijd duplicaten per route)
    pattern_alerts_seen = set()
    for pattern in route_data.get('patterns', []):
        if pattern.get('alerts'):
            for alert in pattern['alerts']:
                pattern_alert_key = (
                    alert.get('alertHeaderText', ''),
                    alert.get('alertDescriptionText', '')
                )
                if pattern_alert_key not in pattern_alerts_seen:
                    pattern_alerts_seen.add(pattern_alert_key)
                    all_disruptions.append({
                        "route": route_name,
                        "level": "Suun",
                        "location": pattern['headsign'][:15],
                        "severity": alert.get('alertSeverityLevel', 'INFO')[:4],
                        "header": alert.get('alertHeaderText', 'Hairio'),
                        "description": alert.get('alertDescriptionText', '')
                    })
        
        # Stop-level alerts
        for stop in pattern['stops']:
            if stop.get('alerts'):
                for alert in stop['alerts']:
                    stop_alert_key = (
                        route_name,
                        stop['name'],
                        alert.get('alertHeaderText', ''),
                        alert.get('alertDescriptionText', '')
                    )
                    if stop_alert_key not in seen_disruptions:
                        seen_disruptions.add(stop_alert_key)
                        all_disruptions.append({
                            "route": route_name,
                            "level": "Pysa",
                            "location": stop['name'][:15],
                            "severity": alert.get('alertSeverityLevel', 'INFO')[:4],
                            "header": alert.get('alertHeaderText', 'Hairio'),
                            "description": alert.get('alertDescriptionText', '')
                        })

# Functie om disruption text te verdelen over regels
def get_disruption_lines(disruption, max_width=40):
    lines = []
    
    # Header regel
    header_text = f"{disruption['route'][:2]} {disruption['level'][:5]} {disruption['location'][:10]}"
    lines.append(("yellow", header_text))
    
    # Volledige disruption text
    full_text = disruption['header']
    if disruption.get('description'):
        full_text += " - " + disruption['description']
    
    # Verdeel tekst over meerdere regels
    words = full_text.split()
    current_line_text = ""
    
    for word in words:
        if len(current_line_text) + len(word) + 1 <= max_width:
            if current_line_text:
                current_line_text += " " + word
            else:
                current_line_text = word
        else:
            if current_line_text:
                lines.append(("white", current_line_text))
            current_line_text = word
    
    if current_line_text:
        lines.append(("white", current_line_text))
    
    return lines

# Bereken hoeveel regels elke disruption nodig heeft (inclusief lege regel)
disruption_line_counts = []
for disruption in all_disruptions:
    lines = get_disruption_lines(disruption)
    disruption_line_counts.append(len(lines) + 1)  # +1 voor lege regel

# Verdeel disruptions over subpagina's
max_lines_per_page = 17  # regel 6 t/m 22
subpages_data = []
current_subpage_disruptions = []
current_subpage_lines = 0

for i, disruption in enumerate(all_disruptions):
    lines_needed = disruption_line_counts[i]
    
    if current_subpage_lines + lines_needed > max_lines_per_page:
        # Start nieuwe subpagina
        if current_subpage_disruptions:
            subpages_data.append(current_subpage_disruptions)
        current_subpage_disruptions = [disruption]
        current_subpage_lines = lines_needed
    else:
        current_subpage_disruptions.append(disruption)
        current_subpage_lines += lines_needed

# Voeg laatste subpagina toe
if current_subpage_disruptions:
    subpages_data.append(current_subpage_disruptions)

# Maak teletext pagina met subpagina's
if all_disruptions:
    teletextPage402 = {
        "number": 456,
        "control": {"cycleTime": "5,T"} if len(subpages_data) > 1 else {},
        "subpages": []
    }
    
    for subpage_disruptions in subpages_data:
        subpage = {
            "packets": json.loads(json.dumps(template_402["subpages"][0]["packets"]))
        }
        
        line = 6
        for disruption in subpage_disruptions:
            lines = get_disruption_lines(disruption)
            
            for color, text in lines:
                row = tableRow(
                    [{"width": 40, "data": "text", "colour": color}],
                    {"text": text}
                )
                if row is not None:
                    subpage["packets"] += [{"number": line, "text": row}]
                    line += 1
                    if line > 22:
                        break
            
            # Lege regel tussen disruptions
            if line <= 22:
                line += 1
            
            if line > 22:
                break
        
        teletextPage402["subpages"].append(subpage)
else:
    # Geen disruptions - enkele subpagina
    teletextPage402 = {
        "number": 456,
        "subpages": [{
            "packets": json.loads(json.dumps(template_402["subpages"][0]["packets"]))
        }]
    }
    
    no_disruption_text = "Ei aktiivisia hairioita"
    row = tableRow(
        [{"width": 40, "data": "message", "colour": "green"}],
        {"message": no_disruption_text}
    )
    
    if row is not None:
        teletextPage402["subpages"][0]["packets"] += [{"number": 6, "text": row}]

exportTTI(pageLegaliser(teletextPage402))
num_subpages_402 = len(teletextPage402["subpages"])
print(f"HSL Disruptions Teletextpagina 402 gegenereerd ({num_subpages_402} subpagina{'s' if num_subpages_402 > 1 else ''}).")

print(f"\nKlaar! Pagina 455 (4 subpagina's) en 456 ({num_subpages_402} subpagina{'s' if num_subpages_402 > 1 else ''}) gegenereerd.")