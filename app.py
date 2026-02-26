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

# ====================== DEFENSE ROTATION PLANNER (Live connected tabs) ======================
if page == "Defense Rotation Planner":
    st.header("Defense Rotation Planner")
    st.caption("Bench selections are connected across innings • No player benches twice until everyone has sat once • Orioles ⚾")

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
                    all_sat_once = all(s >= 1 for s in sit_count.values())
                    sorted_players = sorted(team_players, key=lambda p: sit_count[p])
                    bench = []
                    for p in sorted_players:
                        if len(bench) >= bench_size: break
                        if not all_sat_once or sit_count[p] < 2:   # Strict: no second bench until everyone has sat once
                            bench.append(p)
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
            other_positions = ["1B", "SS", "2B", "CF", "3B", "LF", "RF"]

            for idx, tab in enumerate(tabs):
                inning_num = idx + 1
                with tab:
                    if st.session_state.pool_needed > 0:
                        on_field = st.session_state.team_players + ["Pool Player"] * st.session_state.pool_needed
                        bench = []
                    else:
                        suggested_bench = st.session_state.rotation_plan[idx]["Bench"]
                        bench = st.multiselect("Bench this inning", 
                                               st.session_state.team_players, 
                                               default=suggested_bench, 
                                               key=f"bench_{inning_num}")
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
    st.header("Create Today’s Batting Order")
    game_date = st.date_input("Game Date", datetime.today())
    all_players = roster['name'].tolist() if not roster.empty else []
    
    st.subheader("Step 1: Who is Available Today?")
    available_today = st.multiselect("Available Players (ALL will bat)", all_players, default=st.session_state.available_today)
    
    if st.button("💾 Save Available Players"):
        st.session_state.available_today = available_today
        with open(AVAILABLE_FILE, "w") as f:
            json.dump(available_today, f)
        st.success("✅ Available players saved!")

    st.subheader("Step 2: Batting Order")
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
            st.success("✅ Auto-filled!")
    
    batting_order = st.session_state.get('batting_order', available_today)
    batting_df = pd.DataFrame({"Batting Spot": range(1, len(batting_order) + 1), "Player": batting_order})
    edited_batting = st.data_editor(batting_df, use_container_width=True)
    
    if st.button("📥 Download Batting Order CSV"):
        csv = edited_batting.to_csv(index=False)
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
        for i, player in enumerate(edited_batting["Player"]):
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

st.sidebar.caption("v1.0 • Lineup Manager • Connected Bench Logic • One-Page Card • Orioles ⚾")
