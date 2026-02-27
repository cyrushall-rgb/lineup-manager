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
    cols = ["name", "jersey", "b_t", "age", "positions"]
    if os.path.exists(ROSTER_FILE):
        roster = pd.read_excel(ROSTER_FILE)
        for old in ["player_id", "dob", "Player ID", "Date of Birth", "league_age", "preferred_pos"]:
            if old in roster.columns:
                roster = roster.drop(columns=[old])
        for col in cols:
            if col not in roster.columns:
                roster[col] = ""
        roster = roster[cols]
        roster['jersey'] = roster['jersey'].fillna("")  # No #nan
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

def can_play(positions, position):
    if not positions or pd.isna(positions):
        return False
    prefs = [p.strip().upper() for p in str(positions).split(',')]
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
    st.caption("Click a player's name to edit or delete. Use the button below to add a new player.")

    # Sort alphabetically
    roster = roster.sort_values(by="name").reset_index(drop=True)

    # Display clean list/table
    for idx, row in roster.iterrows():
        col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 2])
        with col1:
            if st.button(row['name'], key=f"edit_btn_{idx}", use_container_width=True):
                st.session_state.edit_idx = idx
                st.rerun()
        with col2:
            st.write(row['jersey'])
        with col3:
            st.write(row['b_t'])
        with col4:
            st.write(row['age'])
        with col5:
            st.write(row['positions'])

    # Add New Player button
    if st.button("➕ Add New Player"):
        st.session_state.show_add_dialog = True
        st.rerun()

    # ====================== ADD DIALOG ======================
    @st.dialog("Add New Player")
    def add_player_dialog():
        name = st.text_input("Player Name")
        jersey = st.text_input("Jersey Number")
        b_t = st.text_input("B/T (e.g. R/R, L/L)")
        age = st.text_input("Age")
        
        st.subheader("Positions")
        positions_list = ["P", "C", "1B", "2B", "3B", "SS", "OF"]
        selected_pos = []
        cols = st.columns(4)
        for i, pos in enumerate(positions_list):
            with cols[i % 4]:
                if st.checkbox(pos, key=f"add_pos_{pos}"):
                    selected_pos.append(pos)
        
        if st.button("Add Player", type="primary"):
            if name:
                new_row = pd.DataFrame([{
                    "name": name,
                    "jersey": jersey,
                    "b_t": b_t,
                    "age": age,
                    "positions": ", ".join(selected_pos)
                }])
                st.session_state.roster_df = pd.concat([st.session_state.roster_df, new_row], ignore_index=True)
                st.success("Player added!")
                st.rerun()
            else:
                st.error("Player name is required.")

    if 'show_add_dialog' in st.session_state and st.session_state.show_add_dialog:
        add_player_dialog()
        st.session_state.show_add_dialog = False

    # ====================== EDIT DIALOG ======================
    @st.dialog("Edit Player")
    def edit_player_dialog(idx):
        row = st.session_state.roster_df.iloc[idx]
        
        name = st.text_input("Player Name", value=row['name'])
        jersey = st.text_input("Jersey Number", value=row['jersey'])
        b_t = st.text_input("B/T", value=row['b_t'])
        age = st.text_input("Age", value=row['age'])
        
        st.subheader("Positions")
        positions_list = ["P", "C", "1B", "2B", "3B", "SS", "OF"]
        current = str(row['positions']).split(', ') if pd.notna(row['positions']) else []
        selected_pos = []
        cols = st.columns(4)
        for i, pos in enumerate(positions_list):
            with cols[i % 4]:
                if st.checkbox(pos, value=pos in current, key=f"edit_pos_{pos}"):
                    selected_pos.append(pos)
        
        col_save, col_delete = st.columns(2)
        with col_save:
            if st.button("Save Changes", type="primary"):
                st.session_state.roster_df.at[idx, 'name'] = name
                st.session_state.roster_df.at[idx, 'jersey'] = jersey
                st.session_state.roster_df.at[idx, 'b_t'] = b_t
                st.session_state.roster_df.at[idx, 'age'] = age
                st.session_state.roster_df.at[idx, 'positions'] = ", ".join(selected_pos)
                st.success("Changes saved!")
                st.rerun()
        
        with col_delete:
            if st.button("Delete Player", type="secondary"):
                if st.button("Confirm Delete"):
                    st.session_state.roster_df = st.session_state.roster_df.drop(idx).reset_index(drop=True)
                    st.success("Player deleted!")
                    st.rerun()

    if 'edit_idx' in st.session_state:
        edit_player_dialog(st.session_state.edit_idx)
        del st.session_state.edit_idx

    # Save button
    if st.button("💾 Save Roster"):
        st.session_state.roster_df.to_excel(ROSTER_FILE, index=False)
        st.success("Roster saved!")

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
    st.caption("Check which players are available for today's game. This controls Defense Rotation Planner and Create Lineup.")

    all_players = sorted(roster['name'].tolist()) if not roster.empty else []

    if 'available_df' not in st.session_state or len(st.session_state.available_df) != len(all_players):
        current_available = st.session_state.get('available_today', all_players)
        df = pd.DataFrame({
            "Player": all_players,
            "Available Today": [player in current_available for player in all_players]
        })
        st.session_state.available_df = df

    edited_df = st.data_editor(
        st.session_state.available_df,
        column_config={
            "Player": st.column_config.TextColumn("Player", disabled=True),
            "Available Today": st.column_config.CheckboxColumn("Available Today", default=False)
        },
        hide_index=True,
        use_container_width=True
    )

    if st.button("💾 Save Available Players"):
        selected = edited_df[edited_df["Available Today"] == True]["Player"].tolist()
        st.session_state.available_today = selected
        with open(AVAILABLE_FILE, "w") as f:
            json.dump(selected, f)
        st.session_state.available_df = edited_df
        st.success("✅ Available players saved!")

# ====================== DEFENSE ROTATION PLANNER ======================
if page == "Defense Rotation Planner":
    st.header("Defense Rotation Planner")
    st.caption("Fully manual • Bench dropdown only shows eligible players • Strict rules enforced • Orioles ⚾")

    available_today = st.session_state.get('available_today', roster['name'].tolist())

    num_innings = st.number_input("Number of Innings", min_value=4, max_value=9, value=6)
    num_team = st.number_input("Number of Team Players Available Today (min 8)", min_value=8, max_value=30, value=len(available_today))

    team_players = st.multiselect("Team Players", available_today, default=available_today[:num_team])

    required_bench = max(0, num_team - 9)
    pool_needed = max(0, 9 - len(team_players))

    if pool_needed > 0:
        st.info(f"✅ Using {pool_needed} Pool Player(s)")

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

                bench_history = {p: 0 for p in team_players}
                for prev_inning in range(1, inning_num):
                    prev_bench = st.session_state.get(f"bench_{prev_inning}", [])
                    for p in prev_bench:
                        if p in bench_history:
                            bench_history[p] += 1

                all_have_sat_once = all(count >= 1 for count in bench_history.values())

                eligible_bench = []
                for p in team_players:
                    was_benched_last = (inning_num > 1 and p in st.session_state.get(f"bench_{inning_num-1}", []))
                    if not was_benched_last and (bench_history[p] == 0 or all_have_sat_once):
                        eligible_bench.append(p)

                st.subheader(f"Bench (select exactly {required_bench} players)")
                bench = st.multiselect("Select players to bench", 
                                       eligible_bench, 
                                       default=st.session_state.get(f"bench_{inning_num}", []), 
                                       key=f"bench_{inning_num}")

                available = [p for p in base_on_field if p not in bench]

                st.subheader("Pitcher & Catcher")
                pitcher_options = [p for p in available if p == "Pool Player" or can_play(roster.loc[roster['name']==p, 'positions'].iloc[0] if len(roster.loc[roster['name']==p]) > 0 else "", "P")]
                pitcher = st.selectbox("Pitcher", pitcher_options or ["No eligible players"], key=f"pitcher_{inning_num}")

                catcher_options = [p for p in available if p != pitcher and (p == "Pool Player" or can_play(roster.loc[roster['name']==p, 'positions'].iloc[0] if len(roster.loc[roster['name']==p]) > 0 else "", "C"))]
                catcher = st.selectbox("Catcher", catcher_options or ["No eligible players"], key=f"catcher_{inning_num}")

                st.subheader("Remaining Defense")
                assigned = {pitcher, catcher}
                for pos in other_positions:
                    pos_options = [p for p in available if p not in assigned and (p == "Pool Player" or can_play(roster.loc[roster['name']==p, 'positions'].iloc[0] if len(roster.loc[roster['name']==p]) > 0 else "", pos))]
                    selected = st.selectbox(f"{pos}", pos_options or ["No eligible players"], key=f"pos_{inning_num}_{pos}")
                    assigned.add(selected)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Current Rotation"):
                full_plan_rows = []
                valid = True
                bench_history = {p: [] for p in team_players}

                for idx in range(num_innings):
                    inning_num = idx + 1
                    bench = st.session_state.get(f"bench_{inning_num}", [])

                    if len(bench) != required_bench:
                        st.error(f"❌ You must select exactly {required_bench} players for bench in Inning {inning_num}")
                        valid = False

                    for p in bench:
                        bench_history[p].append(inning_num)

                    for p in bench:
                        if idx > 0 and (inning_num - 1) in bench_history[p]:
                            st.error(f"❌ {p} cannot be benched in two consecutive innings")
                            valid = False
                    if any(len(b) >= 2 for b in bench_history.values()) and any(len(b) == 0 for b in bench_history.values()):
                        st.error("❌ No player can be benched a second time until every player has been benched at least once")
                        valid = False

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
                    with open(ROTATION_FILE, "w") as f:
                        json.dump(full_plan_rows, f)
                    st.success("✅ Current rotation saved!")

        with col2:
            if st.button("✅ Validate All Innings & Download Full Plan"):
                valid = True
                full_plan_rows = []
                bench_history = {p: [] for p in team_players}

                for idx in range(num_innings):
                    inning_num = idx + 1
                    bench = st.session_state.get(f"bench_{inning_num}", [])

                    if len(bench) != required_bench:
                        st.error(f"❌ You must select exactly {required_bench} players for bench in Inning {inning_num}")
                        valid = False

                    for p in bench:
                        bench_history[p].append(inning_num)

                    for p in bench:
                        if idx > 0 and (inning_num - 1) in bench_history[p]:
                            st.error(f"❌ {p} cannot be benched in two consecutive innings")
                            valid = False
                    if any(len(b) >= 2 for b in bench_history.values()) and any(len(b) == 0 for b in bench_history.values()):
                        st.error("❌ No player can be benched a second time until everyone has sat once")
                        valid = False

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
                                     f"rotation_{num_innings}innings.csv",
                                     "text/csv")
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

    # ====================== FIXED DROPDOWN LINEUP ======================
    n = len(available_today)
    if 'batting_order' not in st.session_state or len(st.session_state.batting_order) != n:
        st.session_state.batting_order = [""] * n

    new_order = st.session_state.batting_order.copy()

    for i in range(n):
        spot = i + 1
        current = new_order[i]
        used = [p for p in new_order if p != "" and p != current]
        options = [""] + [p for p in available_today if p not in used]
        
        selected = st.selectbox(
            f"Batting Spot {spot}",
            options=options,
            index=options.index(current) if current in options else 0,
            key=f"batting_spot_{i}"
        )
        new_order[i] = selected

    st.session_state.batting_order = new_order

    if any(new_order):
        df = pd.DataFrame({"Batting Spot": range(1, n+1), "Player": new_order})
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ====================== CLEAR BUTTON ======================
    if st.button("🗑️ Clear Lineup Selections"):
        st.session_state.batting_order = [""] * n
        for i in range(n):
            key = f"batting_spot_{i}"
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    if st.button("📥 Download Batting Order CSV"):
        csv = pd.DataFrame({"Batting Spot": range(1, n+1), "Player": new_order}).to_csv(index=False)
        st.download_button("Download for GameChanger", csv, f"batting_order_{game_date}.csv", "text/csv")

    if st.button("🖨️ Printable Game Day Card"):
        position_fills = {}
        if os.path.exists(ROTATION_FILE):
            try:
                with open(ROTATION_FILE, "r") as f:
                    saved = json.load(f)
                for row in saved:
                    inning = row["Inning"] - 1
                    for key, value in row.items():
                        if key not in ["Inning", "Bench"] and value and value not in ["— No bench —"]:
                            player = value
                            pos = key
                            if player not in position_fills:
                                position_fills[player] = [""] * 6
                            if inning < 6:
                                position_fills[player][inning] = pos
                        elif key == "Bench" and value and value not in ["— No bench —"]:
                            bench_players = [p.strip() for p in str(value).split(',') if p.strip()]
                            for player in bench_players:
                                if player not in position_fills:
                                    position_fills[player] = [""] * 6
                                if inning < 6:
                                    position_fills[player][inning] = "BN"
            except:
                pass

        if not position_fills:
            st.warning("⚠️ No rotation data found.")

        batting_html = """
        <h2>Batting Order</h2>
        <table border="1" cellpadding="8" cellspacing="0" style="width:75%; border-collapse:collapse; font-size:15px; margin-left:0;">
        <tr>
            <th style="width:6%; text-align:center;">#</th>
            <th style="width:6%; text-align:center;">#</th>
            <th style="width:28%;">Player</th>
            <th style="width:8%; text-align:center;">1</th>
            <th style="width:8%; text-align:center;">2</th>
            <th style="width:8%; text-align:center;">3</th>
            <th style="width:8%; text-align:center;">4</th>
            <th style="width:8%; text-align:center;">5</th>
            <th style="width:8%; text-align:center;">6</th>
        </tr>
        """
        for i, player in enumerate(new_order):
            jersey = roster.loc[roster['name'] == player, 'jersey'].iloc[0] if not roster[roster['name'] == player].empty else "—"
            jersey = str(jersey) if pd.notna(jersey) else "—"
            pos1 = position_fills.get(player, [""]*6)[0]
            pos2 = position_fills.get(player, [""]*6)[1]
            pos3 = position_fills.get(player, [""]*6)[2]
            pos4 = position_fills.get(player, [""]*6)[3]
            pos5 = position_fills.get(player, [""]*6)[4]
            pos6 = position_fills.get(player, [""]*6)[5]
            batting_html += f"""
            <tr>
                <td style="text-align:center; font-weight:bold;">{i+1}</td>
                <td style="text-align:center;">{jersey}</td>
                <td>{player}</td>
                <td style="text-align:center;">{pos1}</td>
                <td style="text-align:center;">{pos2}</td>
                <td style="text-align:center;">{pos3}</td>
                <td style="text-align:center;">{pos4}</td>
                <td style="text-align:center;">{pos5}</td>
                <td style="text-align:center;">{pos6}</td>
            </tr>
            """
        batting_html += "</table>"

        season_html = """
        <br><br><br>
        <h2>Season Stats</h2>
        <table border="1" cellpadding="5" cellspacing="0" style="width:100%; border-collapse:collapse; font-size:6.8px;">
        <tr>
            <th>Player</th>
            <th>OBP</th>
            <th>OPS</th>
            <th>BABIP</th>
            <th>C</th>
            <th>1B</th>
            <th>2B</th>
            <th>3B</th>
            <th>SS</th>
            <th>LF</th>
            <th>CF</th>
            <th>RF</th>
            <th>IP</th>
            <th>FIP</th>
        </tr>
        """
        for _, row in roster.iterrows():
            name = row['name']
            stat_row = season_stats[season_stats['name'] == name] if not season_stats.empty and 'name' in season_stats.columns else pd.DataFrame()
            obp = round(stat_row['OBP'].iloc[0], 3) if not stat_row.empty and 'OBP' in stat_row.columns else "—"
            ops = round(stat_row['OPS'].iloc[0], 3) if not stat_row.empty and 'OPS' in stat_row.columns else "—"
            babip = "—"
            c_inn = "—"
            ip = round(stat_row['IP'].iloc[0], 1) if not stat_row.empty and 'IP' in stat_row.columns else "—"
            fip = "—"
            season_html += f"""
            <tr>
                <td>{name}</td>
                <td>{obp}</td>
                <td>{ops}</td>
                <td>{babip}</td>
                <td>{c_inn}</td>
                <td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td>
                <td>{ip}</td>
                <td>{fip}</td>
            </tr>
            """
        season_html += "</table>"

        full_html = f"""
        <html><head><title>Lineup Card - {game_date}</title>
        <style>
            body {{font-family: Arial, sans-serif; margin: 25px; color: #000; background: white;}}
            h1 {{text-align: center; color: #fc4c02; font-size: 32px; margin-bottom: 8px;}}
            h2 {{color: #000; border-bottom: 3px solid #fc4c02; padding-bottom: 6px; font-size: 18px;}}
            table {{width: 100%; border-collapse: collapse; margin: 15px 0;}}
            th, td {{border: 1px solid #333; padding: 8px; text-align: left;}}
            th {{background: #fc4c02; color: white;}}
            @page {{ margin: 15mm; }}
        </style></head><body>
        <h1>Lineup Card</h1>
        <p style="text-align:center; font-size:18px;"><strong>Date:</strong> {game_date.strftime('%B %d, %Y')} &nbsp;&nbsp;&nbsp; <strong>Opponent:</strong> ________________________</p>
        
        <div>
        {batting_html}
        </div>
        
        <div style="margin-top:25px;">
        {season_html}
        </div>
        </body></html>
        """

        st.download_button(
            "📥 Download HTML (open & print)",
            full_html,
            f"lineup_card_{game_date}.html",
            "text/html"
        )
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

st.sidebar.caption("v1.0 • Lineup Manager • Pop-up Forms for Roster • Orioles ⚾")
