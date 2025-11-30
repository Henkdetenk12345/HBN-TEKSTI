import requests
import json
import csv
from typing import Dict, List, Optional


class HSLRouteScraper:
    """Scraper voor HSL route informatie via de Digitransit API"""
    
    def __init__(self, api_key: str = None):
        """
        Initialiseer de scraper
        
        Args:
            api_key: Digitransit API key (vereist voor v2 API)
        """
        self.api_url = "https://api.digitransit.fi/routing/v2/hsl/gtfs/v1"
        self.api_key = api_key
    
    def extract_route_id(self, url: str) -> Optional[str]:
        """Haalt de route ID uit een HSL URL"""
        import re
        match = re.search(r'HSL:([^/]+)', url)
        return match.group(1) if match else None
    
    def scrape_route(self, route_url: str) -> Optional[Dict]:
        """
        Haalt route data op voor een gegeven HSL route URL
        
        Args:
            route_url: URL van de HSL route pagina
            
        Returns:
            Dictionary met route informatie, of None bij fout
        """
        route_id = self.extract_route_id(route_url)
        
        if not route_id:
            print(f"Fout: Kon geen route ID vinden in URL: {route_url}")
            return None
        
        # GraphQL query voor route informatie inclusief alerts
        query = """
        {
          route(id: "HSL:%s") {
            shortName
            longName
            mode
            alerts {
              alertHeaderText
              alertDescriptionText
              alertUrl
              effectiveStartDate
              effectiveEndDate
              alertSeverityLevel
              alertEffect
              alertCause
            }
            patterns {
              code
              directionId
              headsign
              alerts {
                alertHeaderText
                alertDescriptionText
                effectiveStartDate
                effectiveEndDate
                alertSeverityLevel
              }
              stops {
                name
                lat
                lon
                code
                gtfsId
                platformCode
                alerts {
                  alertHeaderText
                  alertDescriptionText
                  alertSeverityLevel
                }
              }
            }
          }
        }
        """ % route_id
        
        # Setup headers
        headers = {
            'Content-Type': 'application/json'
        }
        
        # Voeg API key toe als deze beschikbaar is
        if self.api_key:
            headers['digitransit-subscription-key'] = self.api_key
        
        try:
            print(f"Bezig met ophalen van route {route_id}...")
            
            response = requests.post(
                self.api_url,
                json={'query': query},
                headers=headers,
                timeout=10
            )
            
            print(f"Status code: {response.status_code}")
            
            response.raise_for_status()
            
            data = response.json()
            
            if 'errors' in data:
                print(f"API fout: {data['errors'][0]['message']}")
                return None
            
            if not data.get('data') or not data['data'].get('route'):
                print("Geen route data gevonden in response")
                return None
            
            return data['data']['route']
            
        except requests.exceptions.RequestException as e:
            print(f"Fout bij ophalen data: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return None
    
    def get_stop_times_for_route(self, stop_gtfs_id: str, route_short_name: str) -> Optional[List[str]]:
        """
        Haalt de eerstvolgende vertrektijden op voor een halte en route
        
        Args:
            stop_gtfs_id: GTFS ID van de halte
            route_short_name: Route korte naam (bijv. M1, M2)
            
        Returns:
            List van tijden in HH:MM formaat
        """
        query = """
        {
          stop(id: "%s") {
            stoptimesWithoutPatterns(numberOfDepartures: 10) {
              scheduledDeparture
              realtimeDeparture
              realtime
              trip {
                route {
                  shortName
                }
              }
            }
          }
        }
        """ % stop_gtfs_id
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        if self.api_key:
            headers['digitransit-subscription-key'] = self.api_key
        
        try:
            response = requests.post(
                self.api_url,
                json={'query': query},
                headers=headers,
                timeout=10
            )
            
            if not response.ok:
                return None
            
            data = response.json()
            
            if 'errors' in data or not data.get('data'):
                return None
            
            times = []
            for stoptime in data['data']['stop'].get('stoptimesWithoutPatterns', []):
                # Filter op route
                trip_route = stoptime.get('trip', {}).get('route', {}).get('shortName')
                if trip_route != route_short_name:
                    continue
                
                # Gebruik realtime als beschikbaar, anders scheduled
                seconds = stoptime.get('realtimeDeparture') or stoptime.get('scheduledDeparture')
                if seconds:
                    hours = (seconds // 3600) % 24
                    minutes = (seconds % 3600) // 60
                    times.append(f"{hours:02d}:{minutes:02d}")
                    
                    if len(times) >= 2:
                        break
            
            return times if times else None
            
        except Exception as e:
            print(f"Error getting times: {e}")
            return None
    
    def save_to_json(self, route_data: Dict, filename: str = None):
        """Slaat route data op als JSON bestand"""
        if not route_data:
            print("Geen data om op te slaan")
            return
        
        if filename is None:
            filename = f"hsl_route_{route_data['shortName']}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(route_data, f, ensure_ascii=False, indent=2)
        
        print(f"Data opgeslagen in: {filename}")
    
    def save_to_csv(self, route_data: Dict, filename: str = None):
        """Slaat halte informatie op als CSV bestand"""
        if not route_data or not route_data.get('patterns'):
            print("Geen data om op te slaan")
            return
        
        if filename is None:
            filename = f"hsl_route_{route_data['shortName']}_stops.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Route', 'Direction', 'Stop Name', 'Stop Code', 
                           'Platform', 'Latitude', 'Longitude', 'GTFS ID', 'Has Alert'])
            
            for pattern in route_data['patterns']:
                for stop in pattern['stops']:
                    has_alert = 'Yes' if stop.get('alerts') else 'No'
                    writer.writerow([
                        route_data['shortName'],
                        pattern['headsign'],
                        stop['name'],
                        stop['code'],
                        stop.get('platformCode', ''),
                        stop['lat'],
                        stop['lon'],
                        stop['gtfsId'],
                        has_alert
                    ])
        
        print(f"CSV opgeslagen in: {filename}")
    
    def save_disruptions_to_csv(self, route_data: Dict, filename: str = None):
        """Slaat verstoringen op in een apart CSV bestand"""
        if not route_data:
            print("Geen data om op te slaan")
            return
        
        if filename is None:
            filename = f"hsl_route_{route_data['shortName']}_disruptions.csv"
        
        disruptions = []
        
        # Route-level alerts
        if route_data.get('alerts'):
            for alert in route_data['alerts']:
                disruptions.append({
                    'Level': 'Route',
                    'Location': route_data['shortName'],
                    'Direction': 'All',
                    'Severity': alert.get('alertSeverityLevel', 'UNKNOWN'),
                    'Header': alert.get('alertHeaderText', ''),
                    'Description': alert.get('alertDescriptionText', ''),
                    'Effect': alert.get('alertEffect', ''),
                    'Cause': alert.get('alertCause', ''),
                    'URL': alert.get('alertUrl', ''),
                    'Start': alert.get('effectiveStartDate', ''),
                    'End': alert.get('effectiveEndDate', '')
                })
        
        # Pattern-level alerts
        for pattern in route_data.get('patterns', []):
            if pattern.get('alerts'):
                for alert in pattern['alerts']:
                    disruptions.append({
                        'Level': 'Pattern',
                        'Location': pattern['headsign'],
                        'Direction': pattern['headsign'],
                        'Severity': alert.get('alertSeverityLevel', 'UNKNOWN'),
                        'Header': alert.get('alertHeaderText', ''),
                        'Description': alert.get('alertDescriptionText', ''),
                        'Effect': '',
                        'Cause': '',
                        'URL': '',
                        'Start': alert.get('effectiveStartDate', ''),
                        'End': alert.get('effectiveEndDate', '')
                    })
            
            # Stop-level alerts
            for stop in pattern['stops']:
                if stop.get('alerts'):
                    for alert in stop['alerts']:
                        disruptions.append({
                            'Level': 'Stop',
                            'Location': stop['name'],
                            'Direction': pattern['headsign'],
                            'Severity': alert.get('alertSeverityLevel', 'UNKNOWN'),
                            'Header': alert.get('alertHeaderText', ''),
                            'Description': alert.get('alertDescriptionText', ''),
                            'Effect': '',
                            'Cause': '',
                            'URL': '',
                            'Start': '',
                            'End': ''
                        })
        
        if not disruptions:
            print(f"Geen verstoringen gevonden voor route {route_data['shortName']}")
            return
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['Level', 'Location', 'Direction', 'Severity', 
                                                   'Header', 'Description', 'Effect', 'Cause', 
                                                   'URL', 'Start', 'End'])
            writer.writeheader()
            writer.writerows(disruptions)
        
        print(f"Verstoringen opgeslagen in: {filename}")
    
    def print_route_info(self, route_data: Dict):
        """Print route informatie naar console"""
        if not route_data:
            return
        
        print(f"\n{'='*60}")
        print(f"Route: {route_data['shortName']} - {route_data['longName']}")
        print(f"Type: {route_data['mode']}")
        print(f"{'='*60}\n")
        
        # Count alerts
        route_alerts = len(route_data.get('alerts', []))
        pattern_alerts = sum(len(p.get('alerts', [])) for p in route_data.get('patterns', []))
        stop_alerts = sum(
            len(s.get('alerts', []))
            for p in route_data.get('patterns', [])
            for s in p.get('stops', [])
        )
        total_alerts = route_alerts + pattern_alerts + stop_alerts
        
        if total_alerts > 0:
            print(f"VERSTORINGEN: {total_alerts} actief")
            print(f"  - Route niveau: {route_alerts}")
            print(f"  - Pattern niveau: {pattern_alerts}")
            print(f"  - Stop niveau: {stop_alerts}")
            print(f"  (Zie {route_data['shortName']}_disruptions.csv voor details)")
            print()
        else:
            print("Geen actieve verstoringen\n")
        
        for pattern in route_data.get('patterns', []):
            print(f"Richting: {pattern['headsign']}")
            print(f"Pattern code: {pattern['code']}")
            print(f"Aantal haltes: {len(pattern['stops'])}")
            print(f"\nHaltes:")
            
            for idx, stop in enumerate(pattern['stops'], 1):
                platform = f" (Platform {stop['platformCode']})" if stop.get('platformCode') else ""
                alert_marker = " [ALERT]" if stop.get('alerts') else ""
                print(f"  {idx}. {stop['name']}{platform}{alert_marker}")
                print(f"     Code: {stop['code']} | Locatie: {stop['lat']:.6f}, {stop['lon']:.6f}")
            
            print(f"\n{'-'*60}\n")


def main():
    """Voorbeeld gebruik van de scraper"""
    
    # API KEY
    API_KEY = "e9561c686c054ff99c03b9b117cce72a"
    
    # Of lees van environment variable
    import os
    API_KEY = os.getenv('DIGITRANSIT_API_KEY', API_KEY)
    
    # Maak scraper instance
    scraper = HSLRouteScraper(api_key=API_KEY)
    
    # HSL route URLs - M1 en M2
    routes = [
        "https://reittiopas.hsl.fi/linjat/HSL:31M1/pysakit/HSL:31M1:0:01",
        "https://reittiopas.hsl.fi/linjat/HSL:31M2/pysakit/HSL:31M2:0:01"
    ]
    
    print(f"Bezig met ophalen van route data voor M1 en M2...")
    if API_KEY:
        print(f"API key: {API_KEY[:10]}...")
    else:
        print("Geen API key geconfigureerd (probeer zonder)")
    
    # Loop door alle routes
    for route_url in routes:
        print(f"\n{'='*70}")
        print(f"Route URL: {route_url}")
        print(f"{'='*70}\n")
        
        # Haal route data op
        route_data = scraper.scrape_route(route_url)
        
        if route_data:
            # Print informatie
            scraper.print_route_info(route_data)
            
            # Sla op als JSON
            scraper.save_to_json(route_data)
            
            # Sla op als CSV
            scraper.save_to_csv(route_data)
            
            # Sla verstoringen op in apart bestand
            scraper.save_disruptions_to_csv(route_data)
        else:
            print(f"\n❌ Kon geen route data ophalen voor {route_url}")
    
    print(f"\n{'='*70}")
    print("Alle routes verwerkt!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()