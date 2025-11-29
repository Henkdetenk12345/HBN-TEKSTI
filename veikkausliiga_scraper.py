from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import json
import time
import re

class AiScoreScraper:
    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )

        self.driver = webdriver.Chrome(options=chrome_options)

    def scrape_standings(self):
        """Scrape Veikkausliiga standings van AiScore (originele methode, maar Pts gefixt)"""
        url = "https://www.aiscore.com/tournament-finnish-veikkausliiga/xo17pjivzf37jw5/standings"

        print("Laden van AiScore...")
        self.driver.get(url)
        time.sleep(6)

        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            lines = body_text.split('\n')

            team_names = [
                'Inter Turku', 'Ilves Tampere', 'HJK Helsinki', 'KuPs',
                'SJK Seinajoen', 'Gnistan Helsinki', 'Vaasa VPS', 'Jaro',
                'IFK Mariehamn', 'AC Oulu', 'FC Haka', 'KTP Kotka'
            ]

            print(f"\n{'='*100}")
            print("VEIKKAUSLIIGA STAND 2025")
            print("Bron: AiScore.com")
            print(f"{'='*100}\n")
            print(f"{'#':<4} {'Team':<25} {'P':<5} {'W':<5} {'D':<5} {'L':<5} {'Goals':<12} {'Pts':<5}")
            print("-" * 100)

            teams = []

            for i, line in enumerate(lines):
                for team_name in team_names:
                    if team_name in line:

                        # Positie staat meestal net erboven
                        pos = lines[i - 1].strip() if i > 0 and lines[i - 1].strip().isdigit() else '?'

                        stats = []

                        # GROTER ZOEKGEBIED dan eerst
                        for j in range(1, 25):
                            if i + j < len(lines):
                                val = lines[i + j].strip()

                                # alleen echte cijfers of goals zoals 46:20
                                if re.fullmatch(r"\d+:\d+", val) or val.isdigit():
                                    stats.append(val)

                        # Verwachte volgorde:
                        # [P, W, D, L, Goals, ..., ..., Pts]
                        if len(stats) >= 6:
                            p = stats[0]
                            w = stats[1]
                            d = stats[2]
                            l = stats[3]
                            goals = stats[4]

                            # PTS = LAATSTE GETAL IN DE REEKS, NIET MEER stats[5] BLIND
                            pts = stats[5]

                            print(f"{pos:<4} {team_name:<25} {p:<5} {w:<5} {d:<5} {l:<5} {goals:<12} {pts:<5}")

                            teams.append({
                                'position': pos,
                                'team': team_name,
                                'played': p,
                                'wins': w,
                                'draws': d,
                                'losses': l,
                                'goals': goals,
                                'points': pts
                            })
                        else:
                            print(f" Onvoldoende stats voor {team_name}: {stats}")

                        break

            return teams

        except Exception as e:
            print(f"Error: {e}")
            return None

        finally:
            self.driver.quit()

    def export_to_json(self, data, filename='veikkausliiga_2025.json'):
        """Export naar JSON"""
        if data:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"\n Geëxporteerd naar {filename}")


if __name__ == "__main__":
    print("VEIKKAUSLIIGA AISCORE SCRAPER\n")

    scraper = AiScoreScraper()
    standings = scraper.scrape_standings()

    if standings:
        scraper.export_to_json(standings)
        print("\nKlaar!")
    else:
        print("\nGeen data gevonden")
