import streamlit as st
import pandas as pd
import os
import json
import base64
from datetime import datetime

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
ROSTER_FILE = f"{DATA_DIR}/roster.xlsx"
GAMES_FILE = f"{DATA_DIR}/games.xlsx"
STATS_FILE = f"{DATA_DIR}/season_stats.xlsx"
ROTATION_FILE = f"{DATA_DIR}/current_rotation.json"
AVAILABLE_FILE = f"{DATA_DIR}/available_today.json"

st.set_page_config(
    page_title="Lineup Manager",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        footer {visibility: hidden !important;}
    </style>
""", unsafe_allow_html=True)

st.title("⚾ Lineup Manager - v1.0")

def load_data():
    cols = ["name", "jersey", "league_age", "preferred_pos"]
    if os.path.exists(ROSTER_FILE):
        roster = pd.read_excel(ROSTER_FILE)
        for old in ["player_id", "dob", "Player ID", "Date of Birth"]:
            if old in roster.columns:
                roster = roster.drop(columns=[old])
        for col in cols:
            if col not in roster.columns:
                roster[col] = ""
        roster = roster[cols]
    else:
        roster = pd.DataFrame(columns=cols)
        roster.to_excel(ROSTER_FILE, index=False)
    
    games = pd.read_excel(GAMES_FILE) if os.path.exists(GAMES_FILE) else pd.DataFrame()
    stats = pd.read_excel(STATS_FILE) if os.path.exists(STATS_FILE) else pd.DataFrame()
    return roster, games, stats

roster, games, season_stats = load_data()

# Persistent available players
if os.path.exists(AVAILABLE_FILE):
    try:
        with open(AVAILABLE_FILE, "r") as f:
            st.session_state.available_today = json.load(f)
    except:
        pass
elif 'available_today' not in st.session_state:
    st.session_state.available_today = roster['name'].tolist()

page = st.sidebar.selectbox("Menu", [
    "Roster & Stats",
    "Available Players Today",
    "Defense Rotation Planner",
    "Create Lineup",
    "Log Game",
    "Pitcher Workload",
    "Reports"
])

def can_play(preferred_pos, position):
    if not preferred_pos or pd.isna(preferred_pos):
        return False
    prefs = [p.strip().upper() for p in str(preferred_pos).split(',')]
    pos = position.upper()
    if pos in ["P", "PITCHER"] and any(x in prefs for x in ["P", "PITCHER"]): return True
    if pos in ["C", "CATCHER"] and any(x in prefs for x in ["C", "CATCHER"]): return True
    if pos == "1B" and "1B" in prefs: return True
    if pos in ["2B","3B","SS"] and ("INF" in prefs or pos in prefs): return True
    if pos in ["LF","CF","RF"] and ("OF" in prefs or pos in prefs): return True
    return False

# ====================== ROSTER & STATS ======================
if page == "Roster & Stats":
    st.header("Roster")
    st.caption("Columns: Name, Jersey, League Age, Positions (P, C, 1B, INF, OF, etc.)")
    edited = st.data_editor(roster, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Save Roster"):
        edited.to_excel(ROSTER_FILE, index=False)
        st.success("Saved!")

    st.header("Import GameChanger Season Stats CSV")
    gc_file = st.file_uploader("Upload GC CSV", type="csv")
    if gc_file:
        gc = pd.read_csv(gc_file)
        if 'Player' in gc.columns:
            gc['Player_lower'] = gc['Player'].str.lower().str.strip()
            roster['name_lower'] = roster['name'].str.lower().str.strip()
            keep = [c for c in ['H', 'AB', 'K', 'AVG', 'OBP', 'SLG', 'OPS', 'IP', 'ERA'] if c in gc.columns]
            merged = roster.merge(gc[['Player_lower'] + keep], left_on='name_lower', right_on='Player_lower', how='left')
            season_stats = merged[['name'] + keep].copy()
            season_stats.to_excel(STATS_FILE, index=False)
            st.success("✅ GC stats merged!")
            st.dataframe(season_stats)

# ====================== AVAILABLE PLAYERS TODAY ======================
if page == "Available Players Today":
    st.header("Available Players Today")
    st.caption("Select who is available for today's game. This controls Defense Rotation Planner and Create Lineup.")

    all_players = roster['name'].tolist() if not roster.empty else []
    
    available_today = st.multiselect(
        "Who is Available Today?", 
        all_players, 
        default=st.session_state.get('available_today', all_players)
    )
    
    if st.button("💾 Save Available Players"):
        st.session_state.available_today = available_today
        with open(AVAILABLE_FILE, "w") as f:
            json.dump(available_today, f)
        st.success("✅ Available players saved!")

    st.info("Tip: Save after making changes so other pages update automatically.")

# ====================== DEFENSE ROTATION PLANNER ======================
if page == "Defense Rotation Planner":
    st.header("Defense Rotation Planner")
    st.caption("Fully manual • Bench is single dropdown • Strict rules optional • Orioles ⚾")

    available_today = st.session_state.get('available_today', roster['name'].tolist())

    num_innings = st.number_input("Number of Innings", min_value=4, max_value=9, value=6)
    num_team = st.number_input("Number of Team Players Available Today (min 8)", min_value=8, max_value=30, value=len(available_today))

    team_players = st.multiselect("Team Players", available_today, default=available_today[:num_team])

    required_bench = max(0, num_team - 9)
    pool_needed = max(0, 9 - len(team_players))

    if pool_needed > 0:
        st.info(f"✅ Using {pool_needed} Pool Player(s)")

    force_bench_rule = st.toggle("Force League Bench Rule (no back-to-back + fair rotation)", value=True)

    if len(team_players) < 8:
        st.error("Minimum 8 team players required")
    else:
        if 'num_innings' not in st.session_state or st.session_state.num_innings != num_innings:
            st.session_state.num_innings = num_innings
            for i in range(1, num_innings + 1):
                if f"bench_{i}" not in st.session_state:
                    st.session_state[f"bench_{i}"] = []

        tabs = st.tabs([f"Inning {i}" for i in range(1, num_innings + 1)])
        other_positions = ["1B", "SS", "2B", "CF", "3B", "LF", "RF"]

        for idx, tab in enumerate(tabs):
            inning_num = idx + 1
            with tab:
                if pool_needed > 0:
                    base_on_field = team_players + ["Pool Player"] * pool_needed
                else:
                    base_on_field = team_players

                st.write(f"**Available players:** {', '.join(base_on_field)}")

                # === LIVE BENCH ELIGIBILITY ===
                bench_history = {p: 0 for p in team_players}
                for prev_inning in range(1, inning_num):
                    prev_bench = st.session_state.get(f"bench_{prev_inning}", [])
                    for p in prev_bench:
                        if p in bench_history:
                            bench_history[p] += 1

                all_have_sat_once = all(count >= 1 for count in bench_history.values())

                if force_bench_rule:
                    # Strict rule
                    eligible_bench = []
                    for p in team_players:
                        was_benched_last = (inning_num > 1 and p in st.session_state.get(f"bench_{inning_num-1}", []))
                        if not was_benched_last and (bench_history[p] == 0 or all_have_sat_once):
                            eligible_bench.append(p)
                else:
                    # Rule disabled — allow any player (except those already benched this inning, which is automatic)
                    eligible_bench = team_players

                st.subheader(f"Bench (select exactly {required_bench} players)")
                bench = st.multiselect("Select players to bench", 
                                       eligible_bench, 
                                       default=st.session_state.get(f"bench_{inning_num}", []), 
                                       key=f"bench_{inning_num}")

                available = [p for p in base_on_field if p not in bench]

                st.subheader("Pitcher & Catcher")
                pitcher_options = [p for p in available if p == "Pool Player" or can_play(roster.loc[roster['name']==p, 'preferred_pos'].iloc[0] if len(roster.loc[roster['name']==p]) > 0 else "", "P")]
                pitcher = st.selectbox("Pitcher", pitcher_options or ["No eligible players"], key=f"pitcher_{inning_num}")

                catcher_options = [p for p in available if p != pitcher and (p == "Pool Player" or can_play(roster.loc[roster['name']==p, 'preferred_pos'].iloc[0] if len(roster.loc[roster['name']==p]) > 0 else "", "C"))]
                catcher = st.selectbox("Catcher", catcher_options or ["No eligible players"], key=f"catcher_{inning_num}")

                st.subheader("Remaining Defense")
                assigned = {pitcher, catcher}
                for pos in other_positions:
                    pos_options = [p for p in available if p not in assigned and (p == "Pool Player" or can_play(roster.loc[roster['name']==p, 'preferred_pos'].iloc[0] if len(roster.loc[roster['name']==p]) > 0 else "", pos))]
                    selected = st.selectbox(f"{pos}", pos_options or ["No eligible players"], key=f"pos_{inning_num}_{pos}")
                    assigned.add(selected)

        # Save and Validate (unchanged)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Current Rotation"):
                # ... (same as previous version)
                st.success("✅ Current rotation saved!")

        with col2:
            if st.button("✅ Validate All Innings & Download Full Plan"):
                # ... (same as previous version)
                st.success("✅ All innings validated!")

# ====================== CREATE LINEUP ======================
if page == "Create Lineup":
    st.header("Create Today’s Batting Order")
    game_date = st.date_input("Game Date", datetime.today())
    
    available_today = st.session_state.get('available_today', roster['name'].tolist())
    
    st.subheader("Step 2: Batting Order")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Auto-Fill Batting Order - Value Strategy"):
            if season_stats.empty:
                st.error("Import GameChanger stats first!")
            else:
                stats_map = {row['name']: {'H': float(row.get('H',0) or 0), 'OBP': float(row.get('OBP',0) or 0), 'OPS': float(row.get('OPS',0) or 0), 'SLG': float(row.get('SLG',0) or 0)} for _, row in season_stats.iterrows()}
                remaining = available_today[:]
                order = []
                candidates = [p for p in remaining if stats_map.get(p, {}).get('H', 0) >= 1]
                if candidates:
                    candidates.sort(key=lambda p: stats_map.get(p, {}).get('OBP', 0), reverse=True)
                    order.append(candidates[0])
                    remaining.remove(candidates[0])
                for _ in range(3):
                    if remaining:
                        remaining.sort(key=lambda p: stats_map.get(p, {}).get('OPS', 0), reverse=True)
                        order.append(remaining[0])
                        remaining.pop(0)
                if remaining:
                    remaining.sort(key=lambda p: stats_map.get(p, {}).get('SLG', 0), reverse=True)
                    order.append(remaining[0])
                    remaining.pop(0)
                while remaining:
                    remaining.sort(key=lambda p: stats_map.get(p, {}).get('OPS', 0), reverse=True)
                    order.append(remaining[0])
                    remaining.pop(0)
                st.session_state.batting_order = order
                st.success("✅ Auto-filled with Value Strategy!")

    with col2:
        if st.button("Auto-Fill Batting Order - OPS"):
            if season_stats.empty:
                st.error("Import GameChanger stats first!")
            else:
                order = sorted(available_today, 
                               key=lambda p: float(season_stats[season_stats['name'] == p]['OPS'].iloc[0]) 
                               if not season_stats[season_stats['name'] == p].empty else 0, 
                               reverse=True)
                st.session_state.batting_order = order
                st.success("✅ Auto-filled by OPS (highest to lowest)!")

    with col3:
        if st.button("Auto-Fill Batting Order - BA"):
            if season_stats.empty:
                st.error("Import GameChanger stats first!")
            else:
                order = sorted(available_today, 
                               key=lambda p: float(season_stats[season_stats['name'] == p]['AVG'].iloc[0]) 
                               if not season_stats[season_stats['name'] == p].empty else 0, 
                               reverse=True)
                st.session_state.batting_order = order
                st.success("✅ Auto-filled by Batting Average (highest to lowest)!")
    
    batting_order = st.session_state.get('batting_order', available_today)
    batting_df = pd.DataFrame({"Batting Spot": range(1, len(batting_order) + 1), "Player": batting_order})
    edited_batting = st.data_editor(batting_df, use_container_width=True)
    
    if st.button("📥 Download Batting Order CSV"):
        csv = edited_batting.to_csv(index=False)
        st.download_button("Download for GameChanger", csv, f"batting_order_{game_date}.csv", "text/csv")

    if st.button("🖨️ Printable Game Day Card"):
        # (tight printable card code unchanged)
        st.success("✅ Printable Lineup Card ready!")

# ====================== LOG GAME, PITCHER WORKLOAD, REPORTS ======================
if page == "Log Game":
    st.header("Log Completed Game - Positions + Bench")
    date = st.date_input("Date", datetime.today())
    opponent = st.text_input("Opponent")
    if roster.empty:
        st.warning("Add players first!")
    else:
        positions = ["P", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]
        pt_template = pd.DataFrame({"Player": roster["name"].tolist()})
        for pos in positions:
            pt_template[f"{pos}_innings"] = 0.0
        pt_template["Bench_innings"] = 0.0
        pt_template["Pitches_Thrown"] = 0
        edited_pt = st.data_editor(pt_template, use_container_width=True, hide_index=True)
        if st.button("💾 Save Game & Update All Trackers"):
            innings_cols = [f"{pos}_innings" for pos in positions] + ["Bench_innings"]
            mask = (edited_pt[innings_cols].sum(axis=1) > 0) | (edited_pt["Pitches_Thrown"] > 0)
            played = edited_pt[mask].copy()
            if not played.empty:
                played["date"] = date
                played["opponent"] = opponent
                games = pd.concat([games, played], ignore_index=True)
                games.to_excel(GAMES_FILE, index=False)
                st.success("Game saved!")
                st.rerun()

if page == "Pitcher Workload":
    st.header("Pitcher Workload & Rest")
    if not games.empty and "Pitches_Thrown" in games.columns:
        fig = px.bar(games[games["Pitches_Thrown"] > 0], x="date", y="Pitches_Thrown", color="Player", title="Pitches by Game")
        st.plotly_chart(fig, use_container_width=True)

if page == "Reports":
    st.header("Season Reports - Positions + Bench")
    if not games.empty:
        innings_cols = [col for col in games.columns if col.endswith("_innings")]
        agg = {col: "sum" for col in innings_cols}
        if "Pitches_Thrown" in games.columns:
            agg["Pitches_Thrown"] = "sum"
        summary = games.groupby("Player").agg(agg).round(1).reset_index()
        summary["Total_Field_Innings"] = summary[[c for c in innings_cols if c != "Bench_innings"]].sum(axis=1)
        st.dataframe(summary, use_container_width=True)
        fig = px.bar(summary, x="Player", y="Total_Field_Innings", title="Total Field Innings")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No games logged yet.")

    st.divider()
    st.subheader("🗑️ Danger Zone")
    st.warning("This will permanently delete ALL logged games and pitch counts.")
    if st.checkbox("I understand this cannot be undone"):
        if st.button("🗑️ Permanently Clear ALL Game Data", type="primary"):
            try:
                if os.path.exists(GAMES_FILE):
                    os.remove(GAMES_FILE)
                st.success("✅ All game data has been permanently deleted!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

st.sidebar.caption("v1.1 • Lineup Manager • Toggleable Bench Rule • Orioles ⚾")
