import streamlit as st
import pandas as pd
from supabase import create_client, Client


# --- SUPABASE CLIENT SETUP ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


supabase = init_supabase()

st.title("🏒 EHL Squad Manager")

# Sidebar Navigation
menu = st.sidebar.selectbox("Navigation",
                            ["View Squads & Stats", "Add Player", "Update Player Stats & Odds", "Manage Fixtures",
                             "🔍 DB Debug View"])

# Fetch teams from Supabase
teams_res = supabase.table("teams").select("team_id, name").order("name").execute()
teams_data = teams_res.data
team_dict = {t["name"]: t["team_id"] for t in teams_data} if teams_data else {}

# If teams table is empty on first run, seed initial teams
if not team_dict:
    default_teams = [
        {"name": "Frisk Asker", "city": "Asker"},
        {"name": "Lillehammer", "city": "Lillehammer"},
        {"name": "Narvik", "city": "Narvik"},
        {"name": "Nidaros", "city": "Trondheim"},
        {"name": "Ringerike", "city": "Hønefoss"},
        {"name": "Stavanger Oilers", "city": "Stavanger"},
        {"name": "Stjernen", "city": "Fredrikstad"},
        {"name": "Storhamar", "city": "Hamar"},
        {"name": "Vålerenga", "city": "Oslo"}
    ]
    supabase.table("teams").upsert(default_teams).execute()
    teams_res = supabase.table("teams").select("team_id, name").order("name").execute()
    team_dict = {t["name"]: t["team_id"] for t in teams_res.data}

# --- PAGE 1: VIEW SQUADS, ODDS & FIXTURES ---
if menu == "View Squads & Stats":
    st.header("Team Rosters")

    if not team_dict:
        st.warning("No teams found. Please check your Supabase connection.")
    else:
        selected_team = st.selectbox("Select a Team", list(team_dict.keys()))
        t_id = team_dict[selected_team]

        # Fetch fixtures for this team
        fix_res = supabase.table("fixtures").select("opponent, location, match_order").eq("team_id", t_id).order(
            "match_order").execute()
        fixtures_df = pd.DataFrame(fix_res.data)

        # Fetch players for this team
        p_res = supabase.table("players").select("player_id, name, position, jersey_number, goals, assists, odds").eq(
            "team_id", t_id).execute()
        players_df = pd.DataFrame(p_res.data)

        if players_df.empty:
            st.info(f"No players registered for {selected_team} yet.")
        else:
            # Rename columns to match display format
            players_df = players_df.rename(columns={
                "name": "Player Name",
                "position": "Position",
                "jersey_number": "Jersey #",
                "goals": "Goals",
                "assists": "Assists",
                "odds": "Odds to Score"
            })

            players_df["Odds to Score"] = players_df["Odds to Score"].apply(lambda x: f"{x:.2f}" if x and x > 0 else "")

            # Append 6 match columns
            for i in range(1, 7):
                col_label = f"Match {i}"
                if not fixtures_df.empty and i in fixtures_df['match_order'].values:
                    match_row = fixtures_df[fixtures_df['match_order'] == i].iloc[0]
                    players_df[col_label] = f"{match_row['opponent']} ({match_row['location']})"
                else:
                    players_df[col_label] = "-"

            # Drop internal ID column if present
            if "player_id" in players_df.columns:
                players_df = players_df.drop(columns=["player_id"])

            st.dataframe(players_df, use_container_width=True, hide_index=True)

# --- PAGE 2: ADD PLAYER ---
elif menu == "Add Player":
    st.header("Add a New Player")

    with st.form("add_player_form", clear_on_submit=True):
        selected_team = st.selectbox("Select Team", list(team_dict.keys()))
        player_name = st.text_input("Player Full Name")
        position = st.selectbox("Position", ["Center", "Left Wing", "Right Wing", "Defense", "Goalie"])
        jersey_number = st.number_input("Jersey Number", min_value=1, max_value=99, value=10)
        initial_odds = st.number_input("Odds to Score Goal (Optional)", min_value=0.00, value=0.00, step=0.05,
                                       format="%.2f")

        submitted = st.form_submit_button("Add Player")

        if submitted:
            if not player_name.strip():
                st.error("Please type a player name before submitting!")
            else:
                t_id = team_dict[selected_team]
                supabase.table("players").insert({
                    "team_id": t_id,
                    "name": player_name,
                    "position": position,
                    "jersey_number": int(jersey_number),
                    "goals": 0,
                    "assists": 0,
                    "odds": float(initial_odds)
                }).execute()
                st.success(f"Successfully added {player_name} to {selected_team}!")

# --- PAGE 3: UPDATE STATS & ODDS ---
elif menu == "Update Player Stats & Odds":
    st.header("Update Goals, Assists & Odds")

    selected_team = st.selectbox("Select Team", list(team_dict.keys()))
    t_id = team_dict[selected_team]

    p_res = supabase.table("players").select("player_id, name, goals, assists, odds").eq("team_id", t_id).execute()
    players_df = pd.DataFrame(p_res.data)

    if players_df.empty:
        st.warning("No players found in this team to update.")
    else:
        player_dict = dict(zip(players_df["name"], players_df["player_id"]))
        selected_player = st.selectbox("Select Player", list(player_dict.keys()))
        p_id = player_dict[selected_player]

        current_row = players_df[players_df["player_id"] == p_id].iloc[0]

        with st.form("update_stats_form"):
            new_goals = st.number_input("Total Goals", min_value=0, value=int(current_row["goals"]))
            new_assists = st.number_input("Total Assists", min_value=0, value=int(current_row["assists"]))
            new_odds = st.number_input("Goalscorer Odds (e.g. 2.50)", min_value=0.00, value=float(current_row["odds"]),
                                       step=0.05, format="%.2f")

            update_submitted = st.form_submit_button("Save Changes")

            if update_submitted:
                supabase.table("players").update({
                    "goals": int(new_goals),
                    "assists": int(new_assists),
                    "odds": float(new_odds)
                }).eq("player_id", p_id).execute()
                st.success(f"Updated stats and odds for {selected_player}!")

# --- PAGE 4: MANAGE FIXTURES ---
elif menu == "Manage Fixtures":
    st.header("Manage Next 6 Team Fixtures")

    selected_team = st.selectbox("Select Team", list(team_dict.keys()))
    t_id = team_dict[selected_team]
    other_teams = [t for t in team_dict.keys() if t != selected_team]

    with st.form("add_fixture_form", clear_on_submit=True):
        opponent = st.selectbox("Opponent", other_teams)
        location = st.radio("Location", ["Home (H)", "Away (A)"])
        match_order = st.number_input("Match Order Number (1 to 6)", min_value=1, max_value=6, value=1)

        add_fixture = st.form_submit_button("Save Fixture")

        if add_fixture:
            loc_code = "H" if "Home" in location else "A"
            # Remove existing fixture for this slot if it exists
            supabase.table("fixtures").delete().eq("team_id", t_id).eq("match_order", int(match_order)).execute()
            # Insert new fixture
            supabase.table("fixtures").insert({
                "team_id": t_id,
                "opponent": opponent,
                "location": loc_code,
                "match_order": int(match_order)
            }).execute()
            st.success(f"Set Match #{match_order} for {selected_team} vs {opponent} ({loc_code})!")

# --- PAGE 5: DEBUG VIEW ---
elif menu == "🔍 DB Debug View":
    st.header("Raw Supabase Contents")
    p_res = supabase.table("players").select("*, teams(name)").execute()
    debug_df = pd.DataFrame(p_res.data)
    if debug_df.empty:
        st.warning("The players table is currently empty.")
    else:
        st.dataframe(debug_df, use_container_width=True, hide_index=True)