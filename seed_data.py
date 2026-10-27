import streamlit as st
from supabase import create_client

# Initialize Supabase client using your secrets
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# 1. Fetch team IDs mapping
teams_res = supabase.table("teams").select("team_id, name").execute()
team_dict = {t["name"]: t["team_id"] for t in teams_res.data}

# 2. Define your bulk players list
# Format: (Team Name, Player Full Name, Position, Jersey Number, Goals, Assists, Odds)
players_to_add = [
    ("Frisk Asker", "Tobias Fladeby", "Left Wing", 40, 0, 0, 2.50),
    ("Frisk Asker", "Magnus Geheb", "Center", 28, 0, 1, 5.00),
    ("Frisk Asker", "Felix Granath", "Center", 91, 4, 9, 2.35),
    ("Frisk Asker", "Viktor Granholm","Right Wing", 59, 5, 2, 2.00),
    ("Frisk Asker", "Hampus Gustafsson", "Left Wing", 24, 1, 5, 3.00),
    ("Frisk Asker", "Michael Haga", "Center", 85, 2, 11, 2.50),
    ("Frisk Asker", "Thomas Valkvæ Olsen", "Right Wing", 93, 3, 3, 4.50),
    ("Frisk Asker", "Tobias Skuterud", "Left Wing", 31, 2, 2, 5.00),
    ("Frisk Asker", "Eskil Wold", "Left Wing", 34, 6, 4, 2.25),
    ("Frisk Asker", "Sander Wold", "Center", 88, 3, 6, 2.45),
    ("Frisk Asker", "Alexander Anderberg", "Defense", 57, 2, 3, 6.00),
    ("Frisk Asker", "Charlie Callaghan", "Defense", 27, 1, 7, 7.00),
    # Add as many players as you want here across any team!
]

# 3. Format and insert into Supabase
formatted_players = []
for team_name, name, pos, jersey, goals, assists, odds in players_to_add:
    if team_name in team_dict:
        formatted_players.append({
            "team_id": team_dict[team_name],
            "name": name,
            "position": pos,
            "jersey_number": jersey,
            "goals": goals,
            "assists": assists,
            "odds": odds
        })

if formatted_players:
    response = supabase.table("players").insert(formatted_players).execute()
    print("Successfully seeded players into Supabase!")
else:
    print("No players matched the teams.")