"""
Weekly head-to-head table for the WhatsApp FPL Draft league.

Each group owns two Premier League clubs. The real fixture list is used only as a calendar:
when two clubs meet, the match is decided by the two groups' DRAFT points that gameweek.
Real Premier League results never count.

Open the link, see the current table. Nothing to run or send each week.
"""

import pandas as pd
import requests
import streamlit as st

from season import FIXTURES_FILE, GROUP_ENTRY_IDS, GROUP_MANAGERS, LEAGUE_ID, SEASON

DETAILS_URL = f"https://draft.premierleague.com/api/league/{LEAGUE_ID}/details"
HISTORY_URL = "https://draft.premierleague.com/api/entry/{entry_id}/history"
BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
BADGE_URL = "https://resources.premierleague.com/premierleague/badges/70/t{code}.png"
HEADERS = {"User-Agent": "Mozilla/5.0"}
CACHE_SECONDS = 900


@st.cache_data(ttl=CACHE_SECONDS)
def fetch_entry_names() -> dict[str, str]:
    """Return group number to current team name, read fresh so renames show up."""
    entries = requests.get(DETAILS_URL, headers=HEADERS, timeout=20).json()["league_entries"]
    by_entry_id = {e["entry_id"]: e["entry_name"] for e in entries}
    return {group: by_entry_id.get(entry_id, group) for group, entry_id in GROUP_ENTRY_IDS.items()}


@st.cache_data(ttl=CACHE_SECONDS)
def fetch_gameweek_points() -> dict[str, dict[int, int]]:
    """Return group number to {gameweek: draft points scored that gameweek}."""
    points = {}
    for group, entry_id in GROUP_ENTRY_IDS.items():
        history = requests.get(
            HISTORY_URL.format(entry_id=entry_id), headers=HEADERS, timeout=20
        ).json()["history"]
        points[group] = {row["event"]: row["points"] for row in history}
    return points


@st.cache_data(ttl=CACHE_SECONDS)
def fetch_club_badges() -> dict[str, str]:
    """Return club short name to its badge image, so the table shows crests not codes."""
    teams = requests.get(BOOTSTRAP_URL, headers=HEADERS, timeout=20).json()["teams"]
    return {t["short_name"]: BADGE_URL.format(code=t["code"]) for t in teams}


def load_fixtures() -> pd.DataFrame:
    """Return the fixed GW2-GW14 calendar, dropping matches a group plays against itself."""
    fixtures = pd.read_csv(FIXTURES_FILE)
    return fixtures[~fixtures["self"]].copy()


def clubs_by_group(fixtures: pd.DataFrame) -> dict[str, str]:
    """Return group number to the clubs it owns, so the table says who is playing for whom."""
    owned: dict[str, set[str]] = {}
    for fixture in fixtures.itertuples():
        owned.setdefault(fixture.home_group, set()).add(fixture.home_club)
        owned.setdefault(fixture.away_group, set()).add(fixture.away_club)
    return {group: " · ".join(sorted(clubs)) for group, clubs in owned.items()}


def played_gameweeks(points: dict[str, dict[int, int]]) -> set[int]:
    """Return gameweeks where at least one group has scored, so unplayed weeks are excluded."""
    return {gw for scores in points.values() for gw, scored in scores.items() if scored > 0}


def build_results(fixtures: pd.DataFrame, points: dict[str, dict[int, int]]) -> pd.DataFrame:
    """Return one row per club per played match, with points for, against and the result."""
    finished = played_gameweeks(points)
    rows = []
    for fixture in fixtures.itertuples():
        if fixture.gw not in finished:
            continue
        home_points = points[fixture.home_group].get(fixture.gw, 0)
        away_points = points[fixture.away_group].get(fixture.gw, 0)
        for club, group, scored, conceded in (
            (fixture.home_club, fixture.home_group, home_points, away_points),
            (fixture.away_club, fixture.away_group, away_points, home_points),
        ):
            rows.append(
                {
                    "gw": fixture.gw,
                    "club": club,
                    "group": group,
                    "F": scored,
                    "A": conceded,
                    "W": int(scored > conceded),
                    "D": int(scored == conceded),
                    "L": int(scored < conceded),
                    "Pts": 3 if scored > conceded else 1 if scored == conceded else 0,
                }
            )
    return pd.DataFrame(rows)


ROW_HEIGHT = 35
HEADER_HEIGHT = 38


def full_height(row_count: int) -> int:
    """Return the exact pixel height of the table, so it neither scrolls nor leaves gaps."""
    return ROW_HEIGHT * row_count + HEADER_HEIGHT


def recent_form(results: pd.DataFrame, key: str, entity: str, matches: int = 5) -> str:
    """Return the last few results for one club or group, most recent last."""
    rows = results[results[key] == entity].sort_values("gw").tail(matches)
    return "".join("W" if r.W else "D" if r.D else "L" for r in rows.itertuples())


def next_opponents(fixtures: pd.DataFrame, played: set[int], key: str, entity: str) -> str:
    """Return who this club or group meets in the next gameweek that has not been played."""
    upcoming = fixtures[~fixtures["gw"].isin(played)]
    if upcoming.empty:
        return ""
    gameweek = upcoming["gw"].min()
    side = "club" if key == "club" else "group"
    opponents = [
        getattr(f, f"away_{side}") if getattr(f, f"home_{side}") == entity else getattr(f, f"home_{side}")
        for f in upcoming[upcoming["gw"] == gameweek].itertuples()
        if entity in (getattr(f, f"home_{side}"), getattr(f, f"away_{side}"))
    ]
    return " · ".join(opponents)


def summarise(
    results: pd.DataFrame, key: str, names: dict[str, str], fixtures: pd.DataFrame, played: set[int]
) -> pd.DataFrame:
    """Return a league table grouped by club or by group, sorted on points then difference."""
    if results.empty:
        return pd.DataFrame()
    table = (
        results.groupby(key)
        .agg(P=("gw", "count"), W=("W", "sum"), D=("D", "sum"), L=("L", "sum"),
             F=("F", "sum"), A=("A", "sum"), Pts=("Pts", "sum"))
        .reset_index()
    )
    table["PD"] = table["F"] - table["A"]
    table["form"] = table[key].map(lambda e: recent_form(results, key, e))
    table["next"] = table[key].map(lambda e: next_opponents(fixtures, played, key, e))
    if key == "group":
        table.insert(1, "team name", table["group"].map(names))
        table.insert(1, "manager", table["group"].map(GROUP_MANAGERS))
        table.insert(3, "clubs", table["group"].map(clubs_by_group(load_fixtures())))
    table = table.sort_values(["Pts", "PD", "F"], ascending=False).reset_index(drop=True)
    table.insert(0, "pos", range(1, len(table) + 1))
    if key == "club":
        table.insert(1, "badge", table["club"].map(fetch_club_badges()))
    ordered = [c for c in ("group", "manager", "team name", "clubs", "badge", "club") if c in table]
    return table[["pos", *ordered, "P", "W", "D", "L", "F", "A", "PD", "Pts", "form", "next"]]


st.set_page_config(page_title="Draft League H2H", page_icon="⚽", layout="wide")
st.title("⚽ Draft League — head to head")
st.caption(f"Season {SEASON} · league {LEAGUE_ID}")

names = fetch_entry_names()
points = fetch_gameweek_points()
fixtures = load_fixtures()
played = played_gameweeks(points)
results = build_results(fixtures, points)

if results.empty:
    st.info("No gameweeks played yet. The head-to-head starts at GW2.")
else:
    latest = max(results["gw"])
    st.caption(f"Through gameweek {latest}. Refreshes every 15 minutes.")
    group_tab, club_tab = st.tabs(["Groups", "Clubs"])
    for tab, key in ((group_tab, "group"), (club_tab, "club")):
        with tab:
            table = summarise(results, key, names, fixtures, played)
            st.dataframe(
                table,
                hide_index=True,
                use_container_width=False,
                height=full_height(len(table)),
                column_config={
                    "badge": st.column_config.ImageColumn("", width="small"),
                    **{
                        column: st.column_config.NumberColumn(column, width="small")
                        for column in ("pos", "P", "W", "D", "L", "F", "A", "PD", "Pts")
                    },
                },
            )
            st.download_button(
                f"Download the {key} table",
                table.to_csv(index=False).encode("utf-8"),
                file_name=f"draft_h2h_{key}_gw{latest}.csv",
                mime="text/csv",
            )

st.divider()
st.caption(
    "Every match is decided by DRAFT points. Real Premier League results do not count — "
    "the fixture list is only a calendar. Each group owns two clubs, so two matches a "
    "gameweek and a maximum of six points."
)
