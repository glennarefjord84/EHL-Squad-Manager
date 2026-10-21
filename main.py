import sqlite3
import streamlit as st
import pandas as pd


# --- DATABASE SETUP (SMART SELF-HEALING SCHEMA) ---
def init_db():
    conn = sqlite3.connect("hockey_squads.db", check_same_thread=False)
    cursor = conn.cursor()

    # Teams table
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS teams
                   (
                       team_id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       name
                       TEXT
                       NOT
                       NULL
                       UNIQUE,
                       city
                       TEXT
                       NOT
                       NULL
                   )
                   """)

    # Check if 'players' table has an old/incompatible schema (like old 'team_name' or missing 'team_id')
    cursor.execute("PRAGMA table_info(players)")
    existing_cols = [col[1] for col in cursor.fetchall()]

    if existing_cols and (
            "team_name" in existing_cols or "team_id" not in existing_cols or "odds" not in existing_cols):
        # Drop and cleanly recreate the players table to match the new schema
        cursor.execute("DROP TABLE IF EXISTS players")

    # Correct Players table structure
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS players
                   (
                       player_id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       team_id
                       INTEGER,
                       name
                       TEXT
                       NOT
                       NULL,
                       position
                       TEXT,
                       jersey_number
                       INTEGER,
                       goals
                       INTEGER
                       DEFAULT
                       0,
                       assists
                       INTEGER
                       DEFAULT
                       0,
                       odds
                       REAL
                       DEFAULT
                       0.00,
                       FOREIGN
                       KEY
                   (
                       team_id
                   ) REFERENCES teams
                   (
                       team_id
                   )
                       )
                   """)

    # Fixtures table
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS fixtures
                   (
                       fixture_id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       team_id
                       INTEGER,
                       opponent
                       TEXT
                       NOT
                       NULL,
                       location
                       TEXT
                       NOT
                       NULL,    -- 'H' for Home, 'A' for Away
                       match_order
                       INTEGER, -- 1 to 6
                       FOREIGN
                       KEY
                   (
                       team_id
                   ) REFERENCES teams
                   (
                       team_id
                   )
                       )
                   """)

    # Pre-populate exact Norwegian EHL teams
    teams_data = [
        ("Frisk Asker", "Asker"),
        ("Lillehammer", "Lillehammer"),
        ("Narvik", "Narvik"),
        ("Nidaros", "Trondheim"),
        ("Ringerike", "Hønefoss"),
        ("Stavanger Oilers", "Stavanger"),
        ("Stjernen", "Fredrikstad"),
        ("Storhamar", "Hamar"),
        ("Vålerenga", "Oslo")
    ]
    cursor.executemany("INSERT OR IGNORE INTO teams (name, city) VALUES (?, ?)", teams_data)
    conn.commit()

    # Pre-populate 6 upcoming sample fixtures for Storhamar
    cursor.execute("SELECT team_id FROM teams WHERE name = 'Storhamar'")
    row = cursor.fetchone()
    if row:
        storhamar_id = row[0]
        sample_fixtures = [
            (storhamar_id, "Nidaros", "A", 1),
            (storhamar_id, "Lillehammer", "H", 2),
            (storhamar_id, "Vålerenga", "A", 3),
            (storhamar_id, "Stavanger Oilers", "H", 4),
            (storhamar_id, "Frisk Asker", "A", 5),
            (storhamar_id, "Stjernen", "H", 6),
        ]
        cursor.execute("DELETE FROM fixtures WHERE team_id = ?", (storhamar_id,))
        cursor.executemany("""
                           INSERT INTO fixtures (team_id, opponent, location, match_order)
                           VALUES (?, ?, ?, ?)
                           """, sample_fixtures)
        conn.commit()

    conn.close()


init_db()


def get_connection():
    return sqlite3.connect("hockey_squads.db", check_same_thread=False)


st.title("🏒 EHL Squad Manager")

# Sidebar Navigation
menu = st.sidebar.selectbox("Navigation",
                            ["View Squads & Stats", "Add Player", "Update Player Stats & Odds", "Manage Fixtures",
                             "🔍 DB Debug View"])

# Fetch team mapping
conn = get_connection()
teams_df = pd.read_sql("SELECT team_id, name FROM teams ORDER BY name ASC", conn)
team_dict = dict(zip(teams_df["name"], teams_df["team_id"]))
conn.close()

# --- PAGE 1: VIEW SQUADS, ODDS & FIXTURES ---
if menu == "View Squads & Stats":
    st.header("Team Rosters")

    selected_team = st.selectbox("Select a Team", list(team_dict.keys()))
    t_id = team_dict[selected_team]

    conn = get_connection()
    # Fetch next 6 fixtures
    fixtures_df = pd.read_sql("""
                              SELECT opponent || ' (' || location || ')' AS fixture, match_order
                              FROM fixtures
                              WHERE team_id = ?
                              ORDER BY match_order ASC LIMIT 6
                              """, conn, params=(t_id,))

    # Fetch players with Odds
    players_df = pd.read_sql("""
                             SELECT player_id,
                                    name          AS "Player Name",
                                    position      AS "Position",
                                    jersey_number AS "Jersey #",
                                    goals         AS "Goals",
                                    assists       AS "Assists",
                                    odds          AS "Odds to Score"
                             FROM players
                             WHERE team_id = ?
                             """, conn, params=(t_id,))
    conn.close()

    if players_df.empty:
        st.info(f"No players registered for {selected_team} yet.")
    else:
        players_df["Odds to Score"] = players_df["Odds to Score"].apply(lambda x: f"{x:.2f}" if x > 0 else "")

        # Append 6 match columns after Odds
        for i in range(1, 7):
            match_row = fixtures_df[fixtures_df['match_order'] == i]
            col_label = f"Match {i}"
            if not match_row.empty:
                players_df[col_label] = match_row.iloc[0]['fixture']
            else:
                players_df[col_label] = "-"

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
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                               INSERT INTO players (team_id, name, position, jersey_number, goals, assists, odds)
                               VALUES (?, ?, ?, ?, 0, 0, ?)
                               """, (t_id, player_name, position, jersey_number, initial_odds))
                conn.commit()
                conn.close()
                st.success(f"Successfully added {player_name} to {selected_team}!")

# --- PAGE 3: UPDATE STATS & ODDS ---
elif menu == "Update Player Stats & Odds":
    st.header("Update Goals, Assists & Odds")

    selected_team = st.selectbox("Select Team", list(team_dict.keys()))
    t_id = team_dict[selected_team]

    conn = get_connection()
    players_df = pd.read_sql("SELECT player_id, name, goals, assists, odds FROM players WHERE team_id = ?", conn,
                             params=(t_id,))
    conn.close()

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
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                               UPDATE players
                               SET goals   = ?,
                                   assists = ?,
                                   odds    = ?
                               WHERE player_id = ?
                               """, (new_goals, new_assists, new_odds, p_id))
                conn.commit()
                conn.close()
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
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM fixtures WHERE team_id = ? AND match_order = ?", (t_id, match_order))
            cursor.execute("""
                           INSERT INTO fixtures (team_id, opponent, location, match_order)
                           VALUES (?, ?, ?, ?)
                           """, (t_id, opponent, loc_code, match_order))
            conn.commit()
            conn.close()
            st.success(f"Set Match #{match_order} for {selected_team} vs {opponent} ({loc_code})!")

# --- PAGE 5: DEBUG VIEW ---
elif menu == "🔍 DB Debug View":
    st.header("Raw Database Contents")

    conn = get_connection()
    raw_df = pd.read_sql("""
                         SELECT P.player_id,
                                T.name AS team_name,
                                P.team_id,
                                P.name AS player_name,
                                P.position,
                                P.jersey_number,
                                P.goals,
                                P.assists,
                                P.odds
                         FROM players P
                                  LEFT JOIN teams T ON P.team_id = T.team_id
                         """, conn)
    conn.close()

    if raw_df.empty:
        st.warning("The players table is currently empty.")
    else:
        st.dataframe(raw_df, use_container_width=True, hide_index=True)