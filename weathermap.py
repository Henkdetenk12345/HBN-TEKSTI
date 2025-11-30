"""
Fixed Weather Map Colorizer - Correcte kleuren voor Finland kaart
"""

import requests
import os
import re
from datetime import datetime, timedelta
import copy
from page import exportTTI, loadTTI
from legaliser import pageLegaliser
import ttxcolour
from collections import defaultdict

TEMPERATUUR_LOCATIES = {
    "10": {"locatie": "Helsinki"},
    "20": {"locatie": "Tampere"},
    "30": {"locatie": "Kuopio"},
    "40": {"locatie": "Puolanka"},
    "50": {"locatie": "Sodankylä"},
}

DAGDELEN_FIN = {
    "aamu": "AAMUUN ASTI:",
    "iltapäivä": "ILTAPÄIVÄÄN ASTI:",
    "ilta": "ILTAAN ASTI:",
    "yö": "YÖHÖN ASTI:"
}

DAGDELEN_FIN_MORGEN = {
    "aamu": "HUOMISAAMUUN ASTI:",
    "iltapäivä": "HUOMISILTAPÄIVÄÄN:",
    "ilta": "HUOMISILTAAN ASTI:",
    "yö": "HUOMISYÖHÖN ASTI:"
}

for key in DAGDELEN_FIN:
    DAGDELEN_FIN[key] = DAGDELEN_FIN[key].ljust(19)
for key in DAGDELEN_FIN_MORGEN:
    DAGDELEN_FIN_MORGEN[key] = DAGDELEN_FIN_MORGEN[key].ljust(19)

GEBIED_REGELS = {
    "Lapland": (1, 10),
    "Noord-Pohjanmaa": (8, 12),
    "Kainuu": (10, 14),
    "Pohjanmaa": (11, 14),
    "Noord-Savo": (12, 15),
    "Noord-Karelia": (13, 16),
    "Centraal-Finland": (13, 15),
    "Zuid-Savo": (14, 17),
    "Pirkanmaa": (14, 16),
    "Satakunta": (15, 18),
    "Kanta-Häme": (16, 18),
    "Zuidwest": (17, 20),
    "Zuid-Karelia": (17, 20),
    "Zuid-Uusimaa": (18, 22),
}

FINLAND_STEDEN = {
    "Zuid-Uusimaa": "Helsinki",
    "Zuidwest": "Turku",
    "Satakunta": "Pori",
    "Kanta-Häme": "Hämeenlinna",
    "Pirkanmaa": "Tampere",
    "Zuid-Karelia": "Lappeenranta",
    "Zuid-Savo": "Mikkeli",
    "Pohjanmaa": "Vaasa",
    "Noord-Savo": "Kuopio",
    "Noord-Karelia": "Joensuu",
    "Centraal-Finland": "Jyväskylä",
    "Kainuu": "Kajaani",
    "Noord-Pohjanmaa": "Oulu",
    "Lapland": "Rovaniemi",
}

WEER_KLEUREN = {
    "2": ttxcolour.MOSAICMAGENTA,
    "3": ttxcolour.MOSAICCYAN,
    "5": ttxcolour.MOSAICBLUE,
    "6": ttxcolour.MOSAICRED,
    "7": ttxcolour.MOSAICRED,
    "800": ttxcolour.MOSAICYELLOW,
    "8": ttxcolour.MOSAICGREEN,
}

WEER_BESCHRIJVINGEN_FI = {
    "200": "Ukkosta, sadetta",
    "201": "Ukkosta ja sadetta",
    "202": "Ukkos-rankkasade",
    "210": "Kevyt ukkonen",
    "211": "Ukkosta",
    "212": "Voimakas ukkonen",
    "221": "Hajaukkosta",
    "230": "Ukkos-tihkusade",
    "231": "Ukkosta, sadetta",
    "232": "Ukkos-rankkasade",
    "300": "Kevyt tihkusade",
    "301": "Tihkusadetta",
    "302": "Voimakas tihku",
    "310": "Kevyttä sadetta",
    "311": "Tihkusadetta",
    "312": "Voimakas tihku",
    "313": "Sadekuuroja",
    "314": "Voimak. kuurot",
    "321": "Sadekuuroja",
    "500": "Kevyt vesisade",
    "501": "Vesisadetta",
    "502": "Voimakas sade",
    "503": "Rankkasadetta",
    "504": "Rankkasadetta",
    "511": "Jäätävä sade",
    "520": "Kevyet kuurot",
    "521": "Sadekuuroja",
    "522": "Voimak. kuurot",
    "531": "Hajasadetta",
    "600": "Kevyt lumisade",
    "601": "Lumisadetta",
    "602": "Voimakas lumi",
    "611": "Räntäsadetta",
    "612": "Kevyttä räntää",
    "613": "Räntäsadetta",
    "615": "Lumi-räntää",
    "616": "Lumi-räntää",
    "620": "Kevyet lumikuur.",
    "621": "Lumikuuroja",
    "622": "Voimak. lumikuur",
    "701": "Usvaa",
    "711": "Savua",
    "721": "Auerta",
    "731": "Pölymyrsky",
    "741": "Sumua",
    "751": "Hiekkaa",
    "761": "Pölyä",
    "762": "Vulk. tuhkaa",
    "771": "Puuskia",
    "781": "Tornado",
    "800": "Selkeää",
    "801": "Vähän pilviä",
    "802": "Hajapilviä",
    "803": "Puolipilvistä",
    "804": "Pilvistä",
}

def get_weer_kleur(weer_code):
    code_str = str(weer_code)
    if code_str in WEER_KLEUREN:
        return WEER_KLEUREN[code_str]
    eerste_cijfer = code_str[0]
    if eerste_cijfer in WEER_KLEUREN:
        return WEER_KLEUREN[eerste_cijfer]
    return ttxcolour.MOSAICWHITE

def get_dagdeel(uur):
    if 6 <= uur < 12:
        return "aamu"
    elif 12 <= uur < 18:
        return "iltapäivä"
    elif 18 <= uur < 24:
        return "ilta"
    else:
        return "yö"

def get_volgend_dagdeel(huidig_dagdeel, huidig_uur):
    volgorde = ["yö", "aamu", "iltapäivä", "ilta"]
    huidige_index = volgorde.index(huidig_dagdeel)
    volgende_index = (huidige_index + 1) % 4
    volgend_dagdeel = volgorde[volgende_index]
    daaropvolgende_index = (huidige_index + 2) % 4
    daaropvolgend_dagdeel = volgorde[daaropvolgende_index]
    is_morgen = (huidig_dagdeel == "ilta" and volgend_dagdeel == "yö")
    is_overmorgen = (huidig_dagdeel == "ilta" and daaropvolgend_dagdeel == "aamu") or (is_morgen and daaropvolgend_dagdeel == "aamu")
    return volgend_dagdeel, is_morgen, daaropvolgend_dagdeel, is_overmorgen

def round_tijd_op_15_min():
    nu = datetime.now()
    minuten = round(nu.minute / 15) * 15
    if minuten == 60:
        nu = nu + timedelta(hours=1)
        minuten = 0
    afgeronde_tijd = nu.replace(minute=minuten, second=0, microsecond=0)
    return f"Klo {afgeronde_tijd.strftime('%H.%M')}"

def get_finnish_datum():
    nu = datetime.now()
    return f"{nu.day:02d}.{nu.month:02d}.{nu.year}"

def get_weer_forecast(locatie, api_key, uren_vooruit=0):
    if uren_vooruit > 0:
        url = f"http://api.openweathermap.org/data/2.5/forecast?q={locatie},FI&appid={api_key}&units=metric&lang=fi"
    else:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={locatie},FI&appid={api_key}&units=metric&lang=fi"
    try:
        response = requests.get(url, timeout=10)
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
                        "beschrijving": closest_forecast["weather"][0]["description"],
                        "wind_speed": closest_forecast.get("wind", {}).get("speed", 0),
                        "wind_deg": closest_forecast.get("wind", {}).get("deg", 0),
                    }
            else:
                return {
                    "temp": round(data["main"]["temp"]),
                    "weer_id": str(data["weather"][0]["id"]),
                    "beschrijving": data["weather"][0]["description"],
                    "wind_speed": data.get("wind", {}).get("speed", 0),
                    "wind_deg": data.get("wind", {}).get("deg", 0),
                }
        return None
    except Exception as e:
        print(f"Virhe säädatan haussa paikalle {locatie}: {e}")
        return None

def bepaal_regel_kleuren(api_key, uren_vooruit=0):
    gebied_weer = {}
    gebied_weer_data = {}
    for gebied, stad in FINLAND_STEDEN.items():
        weer_data = get_weer_forecast(stad, api_key, uren_vooruit)
        if weer_data:
            gebied_weer[gebied] = int(weer_data["weer_id"])
            gebied_weer_data[stad] = weer_data
    regel_kleuren_votes = defaultdict(lambda: defaultdict(int))
    for gebied, weer_code in gebied_weer.items():
        if gebied in GEBIED_REGELS:
            start_regel, eind_regel = GEBIED_REGELS[gebied]
            kleur = get_weer_kleur(weer_code)
            for regel_nr in range(start_regel, eind_regel + 1):
                regel_kleuren_votes[regel_nr][kleur] += 1
    regel_kleuren = {}
    for regel_nr, kleuren_count in regel_kleuren_votes.items():
        beste_kleur = max(kleuren_count.items(), key=lambda x: x[1])[0]
        regel_kleuren[regel_nr] = beste_kleur
    return regel_kleuren, gebied_weer_data

def genereer_kleur_beschrijvingen(regel_kleuren, gebied_weer_data, api_key, uren_vooruit=0):
    unieke_kleuren = set(regel_kleuren.values())
    kleur_naar_gebieden = {}
    for gebied, (start, eind) in GEBIED_REGELS.items():
        gebied_kleuren = [regel_kleuren.get(r) for r in range(start, eind + 1) if r in regel_kleuren]
        if gebied_kleuren:
            meest_voorkomend = max(set(gebied_kleuren), key=gebied_kleuren.count)
            if meest_voorkomend not in kleur_naar_gebieden:
                kleur_naar_gebieden[meest_voorkomend] = []
            kleur_naar_gebieden[meest_voorkomend].append(gebied)
    for kleur in unieke_kleuren:
        if kleur not in kleur_naar_gebieden:
            for regel_nr, regel_kleur in regel_kleuren.items():
                if regel_kleur == kleur:
                    for gebied, (start, eind) in GEBIED_REGELS.items():
                        if start <= regel_nr <= eind:
                            if kleur not in kleur_naar_gebieden:
                                kleur_naar_gebieden[kleur] = []
                            kleur_naar_gebieden[kleur].append(gebied)
                            break
                    break
    beschrijvingen = {}
    kleur_display = {
        ttxcolour.MOSAICYELLOW: ttxcolour.ALPHAYELLOW,
        ttxcolour.MOSAICGREEN: ttxcolour.ALPHAGREEN,
        ttxcolour.MOSAICBLUE: ttxcolour.ALPHABLUE,
        ttxcolour.MOSAICRED: ttxcolour.ALPHARED,
        ttxcolour.MOSAICCYAN: ttxcolour.ALPHACYAN,
        ttxcolour.MOSAICMAGENTA: ttxcolour.ALPHAMAGENTA,
    }
    for kleur, gebieden in kleur_naar_gebieden.items():
        if gebieden and gebieden[0] in FINLAND_STEDEN:
            stad = FINLAND_STEDEN[gebieden[0]]
            if stad in gebied_weer_data:
                weer_info = gebied_weer_data[stad]
                tekst_delen = []
                weer_code = str(weer_info.get("weer_id", ""))
                prefix = ""
                if kleur == ttxcolour.MOSAICRED:
                    if weer_code.startswith("6"):
                        prefix = "LUMI: "
                    elif weer_code.startswith("7"):
                        prefix = "SUMU: "
                elif kleur == ttxcolour.MOSAICBLUE:
                    prefix = "SADE: "
                elif kleur == ttxcolour.MOSAICCYAN:
                    prefix = "TIHKU: "
                elif kleur == ttxcolour.MOSAICMAGENTA:
                    prefix = "UKKO: "
                elif kleur == ttxcolour.MOSAICYELLOW:
                    prefix = "SELKEÄ: "
                elif kleur == ttxcolour.MOSAICGREEN:
                    prefix = "PILVET: "
                if weer_code in WEER_BESCHRIJVINGEN_FI:
                    tekst = WEER_BESCHRIJVINGEN_FI[weer_code]
                elif weer_info.get("beschrijving"):
                    tekst = weer_info["beschrijving"].capitalize()
                else:
                    tekst = ""
                if tekst:
                    max_lengte = 22  # 23 - 1 voor de punt
                    eerste_regel = prefix + tekst
                    if len(eerste_regel) > max_lengte:
                        max_beschrijving = max_lengte - len(prefix)
                        tekst = tekst[:max_beschrijving]
                        eerste_regel = prefix + tekst
                    tekst_delen.append(eerste_regel)
                if "wind_speed" in weer_info and "wind_deg" in weer_info:
                    wind_speed = weer_info["wind_speed"]
                    wind_deg = weer_info["wind_deg"]
                    richtingen = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
                    idx = round(wind_deg / 45) % 8
                    richting = richtingen[idx]
                    wind_tekst = f"{richting} {wind_speed:.0f}m/s"
                    if len(wind_tekst) > 23:
                        wind_tekst = wind_tekst[:23]
                    tekst_delen.append(wind_tekst)
                if tekst_delen:
                    beschrijving = ". ".join(tekst_delen) + "."
                    beschrijvingen[kleur] = (beschrijving, kleur_display.get(kleur, ttxcolour.ALPHAWHITE))
    return beschrijvingen

def inject_kleuren_in_packets(packets, regel_kleuren):
    for packet in packets:
        if "text" not in packet or "number" not in packet:
            continue
        regel_nr = packet["number"]
        if regel_nr >= 22:
            continue
        if regel_nr not in regel_kleuren:
            continue
        text = packet["text"]
        kleur_code_raw = regel_kleuren[regel_nr]
        mosaic_kleur = chr(kleur_code_raw)
        nieuwe_text = ""
        for char in text:
            char_code = ord(char)
            if 0x10 <= char_code <= 0x17:
                if char_code == 0x16 or char_code == 0x13:
                    nieuwe_text += char
                else:
                    nieuwe_text += mosaic_kleur
            else:
                nieuwe_text += char
        packet["text"] = nieuwe_text
    return packets

def inject_beschrijvingen_in_packets(packets, beschrijvingen, regel_kleuren):
    if not beschrijvingen:
        return packets
    start_regel = 6
    gesorteerde_beschrijvingen = sorted(beschrijvingen.items(), key=lambda x: x[0])
    regel_nr = start_regel
    for kleur, (tekst, display_kleur) in gesorteerde_beschrijvingen:
        delen = tekst.rstrip('.').split('. ')
        originele_packet = None
        for packet in packets:
            if packet.get("number") == regel_nr:
                originele_packet = packet
                break
        if delen and originele_packet:
            originele_text = originele_packet["text"]
            text_lijst = list(originele_text)
            tekst_met_kleur = chr(display_kleur) + delen[0] + "."
            start_pos = 1
            for i, char in enumerate(tekst_met_kleur):
                if start_pos + i < len(text_lijst):
                    text_lijst[start_pos + i] = char
            originele_packet["text"] = ''.join(text_lijst)
            regel_nr += 1
        for deel in delen[1:]:
            originele_packet = None
            for packet in packets:
                if packet.get("number") == regel_nr:
                    originele_packet = packet
                    break
            if originele_packet:
                originele_text = originele_packet["text"]
                text_lijst = list(originele_text)
                tekst_met_kleur = chr(display_kleur) + deel + "."
                start_pos = 3
                for i, char in enumerate(tekst_met_kleur):
                    if start_pos + i < len(text_lijst):
                        text_lijst[start_pos + i] = char
                originele_packet["text"] = ''.join(text_lijst)
                regel_nr += 1
        regel_nr += 1
        if regel_nr > 20:
            break
    return packets

def vervang_placeholders(packet_text, temperaturen, datum, tijd, dagdeel_tekst):
    text = packet_text
    text = text.replace("DAGDELEN HIER AUBB:", dagdeel_tekst)
    for placeholder, temp in temperaturen.items():
        temp_str = f"{int(temp):02d}"
        pattern = rf'(?<!Klo )(?<!\d)(?<!\.){re.escape(placeholder)}(?!\d)(?!\.)'
        text = re.sub(pattern, temp_str, text)
    text = re.sub(r'11\.01\.1988', datum, text)
    text = re.sub(r'Klo 19\.00', tijd, text)
    return text

def get_weather_subpages(input_bestand="weathermap.tti"):
    api_key = "bfb1f2b8ee2cc2051070561815d83445"
    if not os.path.exists(input_bestand):
        print(f"VIRHE: Mallia '{input_bestand}' ei löydy.")
        return []
    try:
        template = loadTTI(input_bestand)
        nu = datetime.now()
        datum = get_finnish_datum()
        tijd = round_tijd_op_15_min()
        huidig_dagdeel = get_dagdeel(nu.hour)
        volgend_dagdeel, is_morgen, daaropvolgend_dagdeel, is_overmorgen = get_volgend_dagdeel(huidig_dagdeel, nu.hour)
        subpages = []
        regel_kleuren_nu, gebied_weer_data_nu = bepaal_regel_kleuren(api_key, 0)
        beschrijvingen_nu = genereer_kleur_beschrijvingen(regel_kleuren_nu, gebied_weer_data_nu, api_key, 0)
        subpage1 = {"packets": copy.deepcopy(template["subpages"][0]["packets"])}
        inject_kleuren_in_packets(subpage1["packets"], regel_kleuren_nu)
        inject_beschrijvingen_in_packets(subpage1["packets"], beschrijvingen_nu, regel_kleuren_nu)
        temperaturen_nu = {}
        for placeholder, info in TEMPERATUUR_LOCATIES.items():
            weer_data = get_weer_forecast(info["locatie"], api_key, 0)
            if weer_data:
                temperaturen_nu[placeholder] = weer_data["temp"]
        for packet in subpage1["packets"]:
            if "text" in packet:
                packet["text"] = vervang_placeholders(packet["text"], temperaturen_nu, datum, tijd, DAGDELEN_FIN[huidig_dagdeel])
        subpages.append(subpage1)
        regel_kleuren_volgend, gebied_weer_data_volgend = bepaal_regel_kleuren(api_key, 6)
        beschrijvingen_volgend = genereer_kleur_beschrijvingen(regel_kleuren_volgend, gebied_weer_data_volgend, api_key, 6)
        geldig_volgend = DAGDELEN_FIN_MORGEN[volgend_dagdeel] if is_morgen else DAGDELEN_FIN[volgend_dagdeel]
        subpage2 = {"packets": copy.deepcopy(template["subpages"][0]["packets"])}
        inject_kleuren_in_packets(subpage2["packets"], regel_kleuren_volgend)
        inject_beschrijvingen_in_packets(subpage2["packets"], beschrijvingen_volgend, regel_kleuren_volgend)
        temperaturen_volgend = {}
        for placeholder, info in TEMPERATUUR_LOCATIES.items():
            weer_data = get_weer_forecast(info["locatie"], api_key, 6)
            if weer_data:
                temperaturen_volgend[placeholder] = weer_data["temp"]
        for packet in subpage2["packets"]:
            if "text" in packet:
                packet["text"] = vervang_placeholders(packet["text"], temperaturen_volgend, datum, tijd, geldig_volgend)
        subpages.append(subpage2)
        regel_kleuren_daarna, gebied_weer_data_daarna = bepaal_regel_kleuren(api_key, 12)
        beschrijvingen_daarna = genereer_kleur_beschrijvingen(regel_kleuren_daarna, gebied_weer_data_daarna, api_key, 12)
        geldig_daarna = DAGDELEN_FIN_MORGEN[daaropvolgend_dagdeel] if is_overmorgen else DAGDELEN_FIN[daaropvolgend_dagdeel]
        subpage3 = {"packets": copy.deepcopy(template["subpages"][0]["packets"])}
        inject_kleuren_in_packets(subpage3["packets"], regel_kleuren_daarna)
        inject_beschrijvingen_in_packets(subpage3["packets"], beschrijvingen_daarna, regel_kleuren_daarna)
        temperaturen_daarna = {}
        for placeholder, info in TEMPERATUUR_LOCATIES.items():
            weer_data = get_weer_forecast(info["locatie"], api_key, 12)
            if weer_data:
                temperaturen_daarna[placeholder] = weer_data["temp"]
        for packet in subpage3["packets"]:
            if "text" in packet:
                packet["text"] = vervang_placeholders(packet["text"], temperaturen_daarna, datum, tijd, geldig_daarna)
        subpages.append(subpage3)
        return subpages
    except Exception as e:
        print(f"Virhe: {e}")
        import traceback
        traceback.print_exc()
        return []

def maak_weer_kaart(input_bestand="weathermap.tti"):
    subpages = get_weather_subpages(input_bestand)
    if not subpages:
        print("Säädataa ei saatavilla")
        return
    page = {
        "number": "166",
        "subpages": subpages,
        "control": {"cycleTime": "5,T"}
    }
    exportTTI(pageLegaliser(page))
    print(f"Värillinen sääkartta tallennettu: teletext/P166.tti")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        maak_weer_kaart(sys.argv[1])
    else:
        maak_weer_kaart()