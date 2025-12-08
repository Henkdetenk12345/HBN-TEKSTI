import copy
from datetime import datetime
from textBlock import toTeletextBlock
from page import exportTTI, loadTTI
from legaliser import pageLegaliser
from FMI import FMITextScraper

FINNISH_DAYS = ["MAANANTAI", "TIISTAI", "KESKIVIIKKO", "TORSTAI", "PERJANTAI", "LAUANTAI", "SUNNUNTAI"]

def get_finnish_date():
    """Geeft volledige datum in het Fins"""
    now = datetime.now()
    day_name = FINNISH_DAYS[now.weekday()]
    return f"{day_name} {now.day}.{now.month}."

def vervang_datum_in_tti(tti_data):
    """Vervangt DATE placeholder in TTI data met Finse datum"""
    datum = get_finnish_date()
    
    for subpage in tti_data.get("subpages", []):
        for packet in subpage.get("packets", []):
            if "text" in packet:
                packet["text"] = packet["text"].replace("DATE", datum)
    
    return tti_data

def calculate_text_lines(text, width=40):
    """Bereken EXACT hoeveel regels een tekst nodig heeft"""
    if not text:
        return 0
    # Tel karakters, deel door 40, rond naar boven
    import math
    return math.ceil(len(text) / width)

def split_area_name(area):
    """Split lange area namen slim over meerdere regels"""
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

def create_land_weather_page():
    """
    P161: Landelijk weerbericht
    """
    print("\n" + "="*70)
    print("LANDELIJK WEERBERICHT - P161")
    print("="*70)
    
    scraper = FMITextScraper()
    forecast_text = scraper.get_land_forecast()
    
    print(f"Forecast tekst ({len(forecast_text)} karakters):")
    print(forecast_text[:200] + "..." if len(forecast_text) > 200 else forecast_text)
    
    # Laad template
    try:
        template = loadTTI("weather_land_template.tti")
    except:
        print("⚠ weather_land_template.tti niet gevonden, maak basis template")
        template = {
            "subpages": [{
                "packets": [
                    {"number": 0, "text": "ÿ^ƒÿCÿ]¾\u001f€€€€€€°°°°°°Pÿ GSÄÄTIEDOT      161    DATE  "},
                    {"number": 24, "text": "£ Meri 168 Alueet 169 TEXT-TV Yle 100"}
                ]
            }]
        }
    
    # Maak pagina
    teletextPage = {
        "number": 161,
        "subpages": [{"packets": copy.deepcopy(template["subpages"][0]["packets"])}]
    }
    
    # Vervang datum
    teletextPage = vervang_datum_in_tti(teletextPage)
    
    # Voeg forecast toe vanaf regel 5
    line = 5
    paraBlock = toTeletextBlock(
        input = {"content":[{"align":"left","content":[{"colour":"white","text":forecast_text}]}]},
        line = line
    )
    
    teletextPage["subpages"][0]["packets"] += paraBlock
    
    # Export
    exportTTI(pageLegaliser(teletextPage))
    print("✓ Pagina 161 (Landelijk weer) aangemaakt")

def create_marine_weather_page():
    """
    P168: Maritiem weerbericht - ULTRA STRIKTE versie
    - Subpage 1: ALLEEN waarschuwingen
    - Subpage 2+: Elk 1 forecast gebied per subpage
    - Laatste subpages: Elk 1 VRK2 gebied per subpage
    """
    print("\n" + "="*70)
    print("MARITIEM WEERBERICHT - P168 (1 gebied per subpage)")
    print("="*70)
    
    scraper = FMITextScraper()
    marine_data = scraper.get_structured_marine_forecast()
    
    if not marine_data:
        print("✗ Geen marine forecast gevonden")
        return
    
    print(f"Marine forecast opgehaald:")
    print(f"  - Waarschuwingen: {len(marine_data['warnings'])}")
    print(f"  - Forecast secties: {len(marine_data['forecast_sections'])}")
    print(f"  - VRK2 secties: {len(marine_data['vrk2_sections'])}")
    
    # Laad template
    try:
        template = loadTTI("weather_marine_template.tti")
    except:
        print("⚠ weather_marine_template.tti niet gevonden, maak basis template")
        template = {
            "subpages": [{
                "packets": [
                    {"number": 0, "text": "ÿ^ƒÿCÿ]¾\u001f€€€€€€°°°°°°Pÿ GMERISÄÄ        168    DATE  "},
                    {"number": 24, "text": "£ Sää 161 Alueet 169 TEXT-TV Yle 100"}
                ]
            }]
        }
    
    # Maak pagina met dynamische subpagina's
    teletextPage = {
        "number": 168,
        "control": {"cycleTime": "8,T"},
        "subpages": []
    }
    
    MAX_LINE = 20  # Stop HARD op regel 20
    
    # ===== WAARSCHUWING SUBPAGES: SLIM VERDELEN =====
    warning_subpages = 0
    if marine_data['warnings']:
        # Groepeer warnings per gebied/sectie
        warning_groups = []
        current_group = []
        
        for item_type, content in marine_data['warnings']:
            if item_type == 'heading':
                # Nieuwe heading = nieuwe groep
                if current_group:
                    warning_groups.append(current_group)
                current_group = [(item_type, content)]
            else:
                current_group.append((item_type, content))
        
        # Laatste groep
        if current_group:
            warning_groups.append(current_group)
        
        # Bereken hoeveel subpages nodig
        current_line = 5 + 2  # Start na header
        
        for group in warning_groups:
            # Bereken grootte van deze groep
            group_size = 0
            for item_type, content in group:
                if item_type == 'heading':
                    group_size += len(split_area_name(content))
                else:
                    group_size += calculate_text_lines(content)
            group_size += 1  # Lege regel na groep
            
            # Check of groep op huidige pagina past
            if current_line + group_size > MAX_LINE:
                # Nieuwe subpage nodig
                warning_subpages += 1
                current_line = 5 + 2 + group_size
            else:
                current_line += group_size
        
        # Tel laatste subpage
        if current_line > 5 + 2:
            warning_subpages += 1
    
    # Bereken totaal aantal subpagina's
    total_subpages = warning_subpages
    total_subpages += len(marine_data['forecast_sections'])
    total_subpages += len(marine_data['vrk2_sections'])
    
    print(f"  Verdeling:")
    print(f"    - Waarschuwing groepen: {len(warning_groups) if marine_data['warnings'] else 0}")
    print(f"    - Waarschuwing subpages: {warning_subpages}")
    print(f"    - Forecast subpages: {len(marine_data['forecast_sections'])}")
    print(f"    - VRK2 subpages: {len(marine_data['vrk2_sections'])}")
    print(f"  Totaal: {total_subpages} subpagina's")
    
    current_page_num = 0
    
    # ===== MAAK WAARSCHUWING SUBPAGES =====
    if warning_subpages > 0:
        current_groups = []
        current_line = 5 + 2
        
        for group in warning_groups:
            # Bereken grootte van deze groep
            group_size = 0
            for item_type, content in group:
                if item_type == 'heading':
                    group_size += len(split_area_name(content))
                else:
                    group_size += calculate_text_lines(content)
            group_size += 1  # Lege regel
            
            # Check of groep past
            if current_line + group_size > MAX_LINE:
                # Maak subpage met huidige groepen
                if current_groups:
                    current_page_num += 1
                    subpage = {"packets": copy.deepcopy(template["subpages"][0]["packets"])}
                    
                    for packet in subpage["packets"]:
                        if "text" in packet:
                            packet["text"] = packet["text"].replace("DATE", get_finnish_date())
                    
                    line = 5
                    
                    # Header
                    warning_header = "Kovan tuulen varoitus:"
                    warning_header_block = toTeletextBlock(
                        input = {"content":[{"align":"left","content":[{"colour":"red","text":warning_header}]}]},
                        line = line
                    )
                    subpage["packets"] += warning_header_block
                    line += 2
                    
                    # Voeg alle groepen toe
                    for grp in current_groups:
                        for itype, icontent in grp:
                            if itype == 'heading':
                                for heading_line in split_area_name(icontent):
                                    block = toTeletextBlock(
                                        input = {"content":[{"align":"left","content":[{"colour":"cyan","text":heading_line}]}]},
                                        line = line
                                    )
                                    subpage["packets"] += block
                                    line += 1
                            else:
                                block = toTeletextBlock(
                                    input = {"content":[{"align":"left","content":[{"colour":"white","text":icontent}]}]},
                                    line = line
                                )
                                subpage["packets"] += block
                                line += calculate_text_lines(icontent)
                        
                        # Lege regel na groep
                        line += 1
                    
                    # Paginering
                    page_indicator = f"{current_page_num}/{total_subpages}"
                    page_block = toTeletextBlock(
                        input = {"content":[{"align":"right","content":[{"colour":"white","text":page_indicator}]}]},
                        line = 21
                    )
                    subpage["packets"] += page_block
                    
                    teletextPage["subpages"].append(subpage)
                    print(f"  ✓ Subpagina {current_page_num}: Waarschuwingen (tot regel {line})")
                
                # Start nieuwe subpage
                current_groups = [group]
                current_line = 5 + 2 + group_size
            else:
                current_groups.append(group)
                current_line += group_size
        
        # Laatste warning subpage
        if current_groups:
            current_page_num += 1
            subpage = {"packets": copy.deepcopy(template["subpages"][0]["packets"])}
            
            for packet in subpage["packets"]:
                if "text" in packet:
                    packet["text"] = packet["text"].replace("DATE", get_finnish_date())
            
            line = 5
            
            warning_header = "Kovan tuulen varoitus:"
            warning_header_block = toTeletextBlock(
                input = {"content":[{"align":"left","content":[{"colour":"red","text":warning_header}]}]},
                line = line
            )
            subpage["packets"] += warning_header_block
            line += 2
            
            for grp in current_groups:
                for itype, icontent in grp:
                    if itype == 'heading':
                        for heading_line in split_area_name(icontent):
                            block = toTeletextBlock(
                                input = {"content":[{"align":"left","content":[{"colour":"cyan","text":heading_line}]}]},
                                line = line
                            )
                            subpage["packets"] += block
                            line += 1
                    else:
                        block = toTeletextBlock(
                            input = {"content":[{"align":"left","content":[{"colour":"white","text":icontent}]}]},
                            line = line
                        )
                        subpage["packets"] += block
                        line += calculate_text_lines(icontent)
                
                # Lege regel na groep
                line += 1
            
            page_indicator = f"{current_page_num}/{total_subpages}"
            page_block = toTeletextBlock(
                input = {"content":[{"align":"right","content":[{"colour":"white","text":page_indicator}]}]},
                line = 21
            )
            subpage["packets"] += page_block
            
            teletextPage["subpages"].append(subpage)
            print(f"  ✓ Subpagina {current_page_num}: Waarschuwingen (tot regel {line})")
    
    # ===== FORECAST SECTIES: 1 GEBIED PER SUBPAGE =====
    for section_idx, section in enumerate(marine_data['forecast_sections']):
        current_page_num += 1
        
        subpage = {"packets": copy.deepcopy(template["subpages"][0]["packets"])}
        
        # Vervang datum
        for packet in subpage["packets"]:
            if "text" in packet:
                packet["text"] = packet["text"].replace("DATE", get_finnish_date())
        
        line = 5
        
        # Header "Odotettavissa huomisiltaan asti:" (geel)
        header = "Odotettavissa huomisiltaan asti:"
        header_block = toTeletextBlock(
            input = {"content":[{"align":"left","content":[{"colour":"yellow","text":header}]}]},
            line = line
        )
        subpage["packets"] += header_block
        line += 2
        
        # Area naam (cyan)
        area_lines = split_area_name(section['area'])
        for area_line in area_lines:
            area_block = toTeletextBlock(
                input = {"content":[{"align":"left","content":[{"colour":"cyan","text":area_line}]}]},
                line = line
            )
            subpage["packets"] += area_block
            line += 1
        
        # Forecast (wit) - VOLLEDIGE tekst
        forecast = section['forecast']
        forecast_lines = calculate_text_lines(forecast)
        
        # STRIKTE CHECK
        if line + forecast_lines > MAX_LINE:
            print(f"  ⚠ WAARSCHUWING: Forecast voor '{section['area'][:30]}' is te lang!")
            print(f"      Nodig: {forecast_lines} regels, beschikbaar: {MAX_LINE - line} regels")
            print(f"      Tekst lengte: {len(forecast)} karakters")
        
        forecast_block = toTeletextBlock(
            input = {"content":[{"align":"left","content":[{"colour":"white","text":forecast}]}]},
            line = line
        )
        subpage["packets"] += forecast_block
        line += forecast_lines
        
        # Paginering
        page_indicator = f"{current_page_num}/{total_subpages}"
        page_block = toTeletextBlock(
            input = {"content":[{"align":"right","content":[{"colour":"white","text":page_indicator}]}]},
            line = 21
        )
        subpage["packets"] += page_block
        
        teletextPage["subpages"].append(subpage)
        print(f"  ✓ Subpagina {current_page_num}: {section['area'][:40]} (tot regel {line})")
    
    # ===== VRK2 SECTIES: 1 GEBIED PER SUBPAGE =====
    for section_idx, section in enumerate(marine_data['vrk2_sections']):
        current_page_num += 1
        
        subpage = {"packets": copy.deepcopy(template["subpages"][0]["packets"])}
        
        # Vervang datum
        for packet in subpage["packets"]:
            if "text" in packet:
                packet["text"] = packet["text"].replace("DATE", get_finnish_date())
        
        # Update header voor VRK2
        for packet in subpage["packets"]:
            if packet.get("number") == 0 and "text" in packet:
                packet["text"] = packet["text"].replace("MERISÄÄ", "MERI 2VRK")
        
        line = 5
        
        # Header "Säätiedotus 2 vrk merenkulkijoille" (geel)
        header = "Säätiedotus 2 vrk merenkulkijoille"
        header_block = toTeletextBlock(
            input = {"content":[{"align":"left","content":[{"colour":"yellow","text":header}]}]},
            line = line
        )
        subpage["packets"] += header_block
        line += 2
        
        # Area naam (cyan)
        area_lines = split_area_name(section['area'])
        for area_line in area_lines:
            area_block = toTeletextBlock(
                input = {"content":[{"align":"left","content":[{"colour":"cyan","text":area_line}]}]},
                line = line
            )
            subpage["packets"] += area_block
            line += 1
        
        # Forecast (wit) - VOLLEDIGE tekst
        forecast = section['forecast']
        forecast_lines = calculate_text_lines(forecast)
        
        # STRIKTE CHECK
        if line + forecast_lines > MAX_LINE:
            print(f"  ⚠ WAARSCHUWING: VRK2 voor '{section['area'][:30]}' is te lang!")
            print(f"      Nodig: {forecast_lines} regels, beschikbaar: {MAX_LINE - line} regels")
        
        forecast_block = toTeletextBlock(
            input = {"content":[{"align":"left","content":[{"colour":"white","text":forecast}]}]},
            line = line
        )
        subpage["packets"] += forecast_block
        line += forecast_lines
        
        # Paginering
        page_indicator = f"{current_page_num}/{total_subpages}"
        page_block = toTeletextBlock(
            input = {"content":[{"align":"right","content":[{"colour":"white","text":page_indicator}]}]},
            line = 21
        )
        subpage["packets"] += page_block
        
        teletextPage["subpages"].append(subpage)
        print(f"  ✓ Subpagina {current_page_num}: {section['area'][:40]} VRK2 (tot regel {line})")
    
    # Export
    exportTTI(pageLegaliser(teletextPage))
    print(f"✓ Pagina 168 aangemaakt met {len(teletextPage['subpages'])} subpagina's")

def create_regional_weather_pages():
    """
    P169: Regionale weerberichten - 1 pagina met subpagina's per regio
    """
    print("\n" + "="*70)
    print("REGIONALE WEERBERICHTEN - P169")
    print("="*70)
    
    scraper = FMITextScraper()
    regions = scraper.get_regional_forecasts()
    
    if not regions:
        print("✗ Geen regionale forecasts gevonden")
        return
    
    print(f"Gevonden {len(regions)} regio's")
    
    # Laad template
    try:
        template = loadTTI("weather_regional_template.tti")
    except:
        print("⚠ weather_regional_template.tti niet gevonden, maak basis template")
        template = {
            "subpages": [{
                "packets": [
                    {"number": 0, "text": "ÿ^ƒÿCÿ]¾\u001f€€€€€€°°°°°°Pÿ GALUEET        169    DATE  "},
                    {"number": 24, "text": "£ Sää 161 Meri 168 TEXT-TV Yle 100"}
                ]
            }]
        }
    
    # Maak pagina met subpagina's
    teletextPage = {
        "number": 169,
        "control": {"cycleTime": "5,T"},
        "subpages": []
    }
    
    MAX_LINE = 20
    
    # Maak een subpagina voor elke regio
    for region_data in regions:
        region_name = region_data['region']
        forecast = region_data['forecast']
        
        subpage = {"packets": copy.deepcopy(template["subpages"][0]["packets"])}
        
        # Vervang datum
        for packet in subpage["packets"]:
            if "text" in packet:
                packet["text"] = packet["text"].replace("DATE", get_finnish_date())
        
        line = 5
        
        # Region naam (geel)
        region_block = toTeletextBlock(
            input = {"content":[{"align":"left","content":[{"colour":"yellow","text":region_name}]}]},
            line = line
        )
        subpage["packets"] += region_block
        line += 2
        
        # Forecast (wit) - VOLLEDIGE tekst
        forecast_lines = calculate_text_lines(forecast)
        
        if line + forecast_lines > MAX_LINE:
            print(f"  ⚠ Forecast voor '{region_name[:30]}' is te lang!")
        
        forecast_block = toTeletextBlock(
            input = {"content":[{"align":"left","content":[{"colour":"white","text":forecast}]}]},
            line = line
        )
        subpage["packets"] += forecast_block
        
        teletextPage["subpages"].append(subpage)
        print(f"  ✓ Subpagina voor: {region_name[:50]}...")
    
    # Export
    exportTTI(pageLegaliser(teletextPage))
    print(f"✓ Pagina 169 aangemaakt met {len(regions)} subpagina's")

def main():
    """Maak alle weer-pagina's"""
    print("="*70)
    print("FMI WEER NAAR TELETEXT")
    print("="*70)
    
    try:
        # P161: Landelijk weer
        create_land_weather_page()
        
        # P168: Maritiem weer (1 gebied per subpage!)
        create_marine_weather_page()
        
        # P169: Regionale subpagina's
        create_regional_weather_pages()
        
        print("\n" + "="*70)
        print("KLAAR! Alle weerpagina's aangemaakt:")
        print("  - P161: Landelijk weerbericht")
        print("  - P168: Maritiem weerbericht (1 gebied per subpage)")
        print("    └─ Subpagina 1: Waarschuwingen")
        print("    └─ Subpagina 2+: Elk forecast gebied apart")
        print("    └─ Laatste: Elk VRK2 gebied apart")
        print("  - P169: Regionale berichten (subpagina's)")
        print("="*70)
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()