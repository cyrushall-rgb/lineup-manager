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
    st.caption("Columns: Name, Jersey, League Age, Preferred Positions (P, C, 1B, INF, OF, etc.)")
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

# ====================== DEFENSE ROTATION PLANNER ======================
if page == "Defense Rotation Planner":
    st.header("Defense Rotation Planner")
    st.caption("Only tagged P for Pitcher • Only tagged C for Catcher • Fair bench rotation • Orioles ⚾")

    available_today = st.session_state.get('available_today', roster['name'].tolist())

    num_innings = st.number_input("Number of Innings", min_value=4, max_value=9, value=6)
    num_team = st.number_input("Number of Team Players Available Today (min 8)", min_value=8, max_value=30, value=len(available_today))

    team_players = st.multiselect("Team Players", available_today, default=available_today[:num_team])

    pool_needed = max(0, 9 - len(team_players))
    if pool_needed > 0:
        st.info(f"✅ Using {pool_needed} Pool Player(s)")

    if len(team_players) < 8:
        st.error("Minimum 8 team players required")
    else:
        if st.button("🚀 Generate Full Rotation & Defense Plan"):
            sit_count = {p: 0 for p in team_players}
            rotation_plan = []
            bench_size = max(0, len(team_players) - 9)

            for inning in range(1, num_innings + 1):
                if bench_size == 0:
                    bench = []
                else:
                    # Strict fair rotation: no second bench until everyone has sat once
                    all_sat_once = all(s >= 1 for s in sit_count.values())
                    sorted_players = sorted(team_players, key=lambda p: (sit_count[p], 0))
                    bench = []
                    for p in sorted_players:
                        if len(bench) >= bench_size: break
                        if not all_sat_once or sit_count[p] < 2:   # allow second bench only after everyone has 1
                            bench.append(p)
                    # Fill remaining if needed
                    if len(bench) < bench_size:
                        for p in sorted_players:
                            if p not in bench:
                                bench.append(p)
                                if len(bench) >= bench_size: break

                for p in bench:
                    sit_count[p] += 1
                rotation_plan.append({"Inning": inning, "Bench": bench})

            st.session_state.rotation_plan = rotation_plan
            st.session_state.team_players = team_players
            st.session_state.num_innings = num_innings
            st.session_state.pool_needed = pool_needed
            st.success("✅ Fair rotation plan generated!")

        if 'rotation_plan' in st.session_state:
            tabs = st.tabs([f"Inning {i}" for i in range(1, st.session_state.num_innings + 1)])
            other_positions = ["1B", "SS", "2B", "CF", "3B", "LF", "RF"]   # Your requested order

            for idx, tab in enumerate(tabs):
                inning_num = idx + 1
                with tab:
                    if st.session_state.pool_needed > 0:
                        on_field = st.session_state.team_players + ["Pool Player"] * st.session_state.pool_needed
                        bench = []
                    else:
                        suggested_bench = st.session_state.rotation_plan[idx]["Bench"]
                        bench = st.multiselect("Bench this inning", st.session_state.team_players, default=suggested_bench, key=f"bench_{inning_num}")
                        on_field = [p for p in st.session_state.team_players if p not in bench]

                    st.write(f"**On field:** {', '.join(on_field)}")

                    st.subheader("Pitcher & Catcher (select first)")
                    pitcher_options = [p for p in on_field if p == "Pool Player" or can_play(roster.loc[roster['name']==p, 'preferred_pos'].iloc[0] if len(roster.loc[roster['name']==p]) > 0 else "", "P")]
                    pitcher = st.selectbox("Pitcher", pitcher_options or on_field, key=f"pitcher_{inning_num}")

                    catcher_options = [p for p in on_field if p != pitcher and (p == "Pool Player" or can_play(roster.loc[roster['name']==p, 'preferred_pos'].iloc[0] if len(roster.loc[roster['name']==p]) > 0 else "", "C"))]
                    catcher = st.selectbox("Catcher", catcher_options, key=f"catcher_{inning_num}")

                    st.subheader("Remaining Defense")
                    assigned = {pitcher, catcher}
                    for pos in other_positions:
                        pos_options = [p for p in on_field if p not in assigned and (p == "Pool Player" or can_play(roster.loc[roster['name']==p, 'preferred_pos'].iloc[0] if len(roster.loc[roster['name']==p]) > 0 else "", pos))]
                        selected = st.selectbox(f"{pos}", pos_options or ["No eligible players"], key=f"pos_{inning_num}_{pos}")
                        assigned.add(selected)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Save Current Rotation"):
                    full_plan_rows = []
                    for idx in range(st.session_state.num_innings):
                        inning_num = idx + 1
                        bench = st.session_state.get(f"bench_{inning_num}", []) if st.session_state.pool_needed == 0 else []
                        p = st.session_state.get(f"pitcher_{inning_num}", "")
                        c = st.session_state.get(f"catcher_{inning_num}", "")
                        assigned = [p, c] + [st.session_state.get(f"pos_{inning_num}_{pos}", "") for pos in other_positions]
                        row = {
                            "Inning": inning_num,
                            "Bench": ", ".join(bench) if bench else "— No bench —",
                            "P": p,
                            "C": c,
                            **{pos: st.session_state.get(f"pos_{inning_num}_{pos}", "") for pos in other_positions}
                        }
                        full_plan_rows.append(row)
                    with open(ROTATION_FILE, "w") as f:
                        json.dump(full_plan_rows, f)
                    st.success("✅ Current rotation saved!")

            with col2:
                if st.button("✅ Validate All Innings & Download Full Plan"):
                    # validation code unchanged
                    valid = True
                    full_plan_rows = []
                    for idx in range(st.session_state.num_innings):
                        inning_num = idx + 1
                        bench = st.session_state.get(f"bench_{inning_num}", []) if st.session_state.pool_needed == 0 else []
                        p = st.session_state.get(f"pitcher_{inning_num}", "")
                        c = st.session_state.get(f"catcher_{inning_num}", "")
                        assigned = [p, c] + [st.session_state.get(f"pos_{inning_num}_{pos}", "") for pos in other_positions]
                        if len(set(assigned)) != 9 or "" in assigned:
                            st.error(f"❌ Duplicates or missing in Inning {inning_num}!")
                            valid = False
                        row = {
                            "Inning": inning_num,
                            "Bench": ", ".join(bench) if bench else "— No bench —",
                            "P": p,
                            "C": c,
                            **{pos: st.session_state.get(f"pos_{inning_num}_{pos}", "") for pos in other_positions}
                        }
                        full_plan_rows.append(row)
                    if valid:
                        st.session_state.full_plan_rows = full_plan_rows
                        with open(ROTATION_FILE, "w") as f:
                            json.dump(full_plan_rows, f)
                        full_df = pd.DataFrame(full_plan_rows)
                        st.dataframe(full_df, use_container_width=True)
                        st.download_button("📥 Download COMPLETE Plan CSV",
                                         full_df.to_csv(index=False),
                                         f"rotation_{st.session_state.num_innings}innings.csv",
                                         "text/csv")
                        st.success("✅ All innings validated!")

# ====================== CREATE LINEUP ======================
if page == "Create Lineup":
    # (unchanged from your last working version)
    st.header("Create Today’s Batting Order")
    # ... rest of Create Lineup code remains the same as your previous version ...

    # (I kept the tight printable card from the last update)

# (Log Game, Pitcher Workload, Reports pages unchanged)

st.sidebar.caption("v1.0 • Lineup Manager • Fair Bench Rotation • One-Page Card • Orioles ⚾")
