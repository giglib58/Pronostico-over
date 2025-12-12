import requests
import json
import os
from datetime import datetime

# --- CONFIGURAZIONE ---
API_KEY = os.environ.get("API_FOOTBALL_KEY")
HEADERS = {'x-apisports-key': API_KEY}
DATABASE_FILE = 'database.json'
SEASON = 2023

# SOLO 3 CAMPIONATI PER INIZIARE - FUNZIONERA' CON IL PIANO GRATUITO
LEAGUES_TO_FOLLOW = {
    "Serie A": 135,
    "Premier League": 39,
    "La Liga": 140
}

# --- FUNZIONI ---

def load_database():
    try:
        with open(DATABASE_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_update": None, "teams": {}}

def save_database(data):
    with open(DATABASE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_season_results(league_id):
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season={SEASON}"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        fixtures = response.json()['response']
        
        results = []
        for fixture in fixtures:
            if fixture['fixture']['status']['long'] == "Match Finished":
                results.append({
                    "date": fixture['fixture']['date'],
                    "home": fixture['teams']['home']['name'],
                    "away": fixture['teams']['away']['name'],
                    "home_goals": fixture['goals']['home'],
                    "away_goals": fixture['goals']['away']
                })
        return results
    except requests.exceptions.RequestException as e:
        print(f"Errore nel recupero dati per il campionato {league_id}: {e}")
        return []

def calculate_team_averages(results):
    team_stats = {}
    home_matches = {}
    away_matches = {}

    for res in results:
        home, away = res['home'], res['away']
        hg, ag = res['home_goals'], res['away_goals']

        if home not in home_matches: home_matches[home] = []
        if away not in away_matches: away_matches[away] = []
        
        home_matches[home].append(hg)
        home_matches[home].append(ag)
        away_matches[away].append(ag)
        away_matches[away].append(hg)

    for team, goals in home_matches.items():
        if team not in team_stats: team_stats[team] = {}
        scored_goals = goals[::2][-5:]
        conceded_goals = goals[1::2][-5:]
        if scored_goals and conceded_goals:
            team_stats[team]['avg_scored_home'] = sum(scored_goals) / len(scored_goals)
            team_stats[team]['avg_conceded_home'] = sum(conceded_goals) / len(conceded_goals)

    for team, goals in away_matches.items():
        if team not in team_stats: team_stats[team] = {}
        scored_goals = goals[::2][-5:]
        conceded_goals = goals[1::2][-5:]
        if scored_goals and conceded_goals:
            team_stats[team]['avg_scored_away'] = sum(scored_goals) / len(scored_goals)
            team_stats[team]['avg_conceded_away'] = sum(conceded_goals) / len(conceded_goals)
            
    return team_stats

def predict_upcoming_fixtures(team_stats):
    predictions = []
    for league_name, league_id in LEAGUES_TO_FOLLOW.items():
        url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season={SEASON}&status=NS"
        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            fixtures = response.json()['response']
            
            for fixture in fixtures:
                home = fixture['teams']['home']['name']
                away = fixture['teams']['away']['name']

                if home in team_stats and away in team_stats:
                    home_stats = team_stats[home]
                    away_stats = team_stats[away]

                    expected_home = (home_stats.get('avg_scored_home', 0) + away_stats.get('avg_conceded_away', 0)) / 2
                    expected_away = (away_stats.get('avg_scored_away', 0) + home_stats.get('avg_conceded_home', 0)) / 2
                    total_expected = expected_home + expected_away

                    prediction = "Over 2.5" if total_expected > 2.5 else "Under 2.5"
                    
                    predictions.append({
                        "league": league_name,
                        "match": f"{home} vs {away}",
                        "prediction": prediction,
                        "expected_goals": round(total_expected, 2)
                    })
        except requests.exceptions.RequestException as e:
            print(f"Errore nel recupero partite future per {league_name}: {e}")
    
    return predictions

# --- FLUSSO PRINCIPALE ---
def main():
    print(f"--- Avvio script di aggiornamento per {len(LEAGUES_TO_FOLLOW)} campionati ---")
    
    all_results = []
    for league_name, league_id in LEAGUES_TO_FOLLOW.items():
        print(f"Recupero risultati per: {league_name}...")
        results = get_season_results(league_id)
        if results:
            all_results.extend(results)
    
    if not all_results:
        print("Nessun risultato trovato. Esco.")
        return

    print("Calcolo statistiche squadre...")
    team_stats = calculate_team_averages(all_results)
    print(f"Statistiche calcolate per {len(team_stats)} squadre.")

    print("Generazione pronostici...")
    predictions = predict_upcoming_fixtures(team_stats)
    
    print("\n--- PRONOSTICI DEL GIORNO ---")
    for p in predictions:
        print(f"({p['league']}) {p['match']}: {p['prediction']} (Goal Attesi: {p['expected_goals']})")
    print("---------------------------\n")

    print("Salvataggio database...")
    database_data = {
        "last_update": datetime.now().isoformat(),
        "teams": team_stats
    }
    save_database(database_data)
    print("--- Script completato con successo ---")


if __name__ == '__main__':
    if not API_KEY:
        print("Errore: API_KEY non trovata. Assicurati di aver impostato il secret su GitHub.")
    else:
        main()
