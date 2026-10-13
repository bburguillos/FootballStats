import io
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="NFL Fantasy Stat Finder", page_icon="🏈", layout="centered")

st.markdown("""
<style>
.stApp {background: #0b1220; color: #f8fafc;}
.block-container {max-width: 780px; padding-top: 1.5rem;}
h1, h2, h3, p, label {color: #f8fafc !important;}
.hero {background: linear-gradient(110deg,#e87722,#f5a623);color:#0b1220;
       border-radius:18px;padding:18px 22px;margin-bottom:14px;}
.hero h1 {font-size:2rem;margin:0;color:#0b1220!important;}
.hero p {margin:3px 0 0;color:#0b1220!important;font-weight:650;}
.stat {border:1px solid #344256;background:#162238;border-radius:14px;
       padding:18px 8px;text-align:center;min-height:110px;}
.stat .number {font-size:2.3rem;font-weight:850;color:#ffffff;line-height:1.2;}
.stat .name {font-size:.93rem;font-weight:700;color:#dce6f3;margin-top:8px;}
.notice {background:#18283a;border-left:5px solid #f59e0b;
         padding:12px 16px;border-radius:9px;margin-top:12px;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>🏈 NFL Fantasy Stat Finder</h1>'
            '<p>SPORTS BY THE NUMBERS • Find the stats. Do the math.</p></div>',
            unsafe_allow_html=True)

POSITIONS = {
    "Quarterback (QB)": "QB", "Running Back (RB)": "RB",
    "Wide Receiver (WR)": "WR", "Tight End (TE)": "TE"
}
STATS = {
    "QB": [("Passing Yards", "passing_yards"), ("Passing TDs", "passing_tds"),
           ("Rushing TDs", "rushing_tds"), ("Interceptions", "interceptions")],
    "RB": [("Rushing Yards", "rushing_yards"), ("Rushing TDs", "rushing_tds"),
           ("Receiving Yards", "receiving_yards"), ("Receiving TDs", "receiving_tds")],
    "WR": [("Receiving Yards", "receiving_yards"), ("Receiving TDs", "receiving_tds"),
           ("Receptions", "receptions")],
    "TE": [("Receiving Yards", "receiving_yards"), ("Receiving TDs", "receiving_tds"),
           ("Receptions", "receptions")],
}

@st.cache_data(ttl=3600, show_spinner=False)
def load_season(season: int) -> pd.DataFrame:
    url = ("https://github.com/nflverse/nflverse-data/releases/download/"
           f"stats_player/stats_player_week_{season}.csv")
    response = requests.get(url, timeout=45, headers={"User-Agent": "SportsByTheNumbers/1.0"})
    response.raise_for_status()
    df = pd.read_csv(io.BytesIO(response.content), low_memory=False)
    if df.empty:
        raise ValueError("No stats were returned for this season.")
    if "season_type" in df.columns:
        df = df[df["season_type"].astype(str).str.upper().isin(["REG", "REGULAR"])].copy()
    # Newer nflverse releases use 'passing_interceptions'; older releases use 'interceptions'.
    if "interceptions" not in df.columns and "passing_interceptions" in df.columns:
        df["interceptions"] = df["passing_interceptions"]
    if "team" not in df.columns and "recent_team" in df.columns:
        df["team"] = df["recent_team"]
    required = ["week", "position", "player_display_name"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError("The NFL data format has changed; missing: " + ", ".join(missing))
    for col in ["passing_yards", "passing_tds", "rushing_tds", "interceptions",
                "rushing_yards", "receiving_yards", "receiving_tds", "receptions"]:
        if col not in df.columns:
            raise ValueError(f"The stats source does not provide '{col}'.")
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["week"] = pd.to_numeric(df["week"], errors="coerce")
    df = df.dropna(subset=["week", "player_display_name"])
    df["week"] = df["week"].astype(int)
    df["position"] = df["position"].astype(str).str.upper().str.strip()
    df["player_display_name"] = df["player_display_name"].astype(str)
    return df


def number_format(value: float) -> str:
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.1f}"

current_season = datetime.now().year if datetime.now().month >= 8 else datetime.now().year - 1
with st.spinner("Loading NFL weekly statistics..."):
    season = st.selectbox("NFL Season", list(range(current_season, 2023, -1)))
    try:
        data = load_season(season)
    except Exception as exc:
        st.error("NFL stats could not be loaded. Check the internet connection or try another season.")
        st.caption(f"Technical details: {exc}")
        st.stop()

weeks = sorted(data.loc[data["position"].isin(POSITIONS.values()), "week"].unique().tolist())
if not weeks:
    st.warning("No completed regular-season weeks are available for this season.")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    week = st.selectbox("NFL Week", weeks, format_func=lambda x: f"Week {x}", index=len(weeks)-1)
with col2:
    position_label = st.selectbox("Position", list(POSITIONS))
position = POSITIONS[position_label]

filtered = data[(data["week"] == week) & (data["position"] == position)].copy()
filtered = filtered.sort_values("player_display_name")
if filtered.empty:
    st.info("No players at this position have reported stats for that week.")
    st.stop()

# Use the NFL's stable ID as the choice key where supplied, to distinguish same-name players.
if "player_id" not in filtered.columns:
    filtered["player_id"] = filtered["player_display_name"]
filtered["player_id"] = filtered["player_id"].fillna(filtered["player_display_name"]).astype(str)
filtered["team"] = filtered["team"].fillna("—") if "team" in filtered.columns else "—"
filtered["selection"] = (filtered["player_display_name"] + " (" + filtered["team"].astype(str) + ")")
filtered = filtered.drop_duplicates(subset=["player_id"], keep="first")

st.write("")
choice = st.selectbox("Player — one at a time", options=[None] + filtered.index.tolist(),
                      format_func=lambda i: "Choose a player..." if i is None else filtered.loc[i, "selection"])
if choice is None:
    st.info("Select one player to see their stats. Then calculate their fantasy points on paper.")
    st.stop()

player = filtered.loc[choice]
st.markdown(f"### {player['player_display_name']} · {player['team']}")
st.caption(f"{season} regular season • Week {week} • {position}")
items = STATS[position]
for start in range(0, len(items), 2):
    columns = st.columns(2)
    for c, (title, key) in zip(columns, items[start:start+2]):
        with c:
            st.markdown(f'<div class="stat"><div class="number">{number_format(player[key])}</div>'
                        f'<div class="name">{title}</div></div>', unsafe_allow_html=True)

st.markdown('<div class="notice"><strong>🧠 Your turn:</strong> Use our classroom scoring '
            'rules to calculate this player’s fantasy points. This app will not '
            'calculate the total for you.</div>', unsafe_allow_html=True)
st.caption("Data: nflverse weekly player statistics. Updates may lag behind the end of games.")

