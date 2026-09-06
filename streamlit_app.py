"""
Weekly head-to-head table for the WhatsApp FPL Draft league.

Each group owns two Premier League clubs. The real fixture list is used only as a calendar:
when two clubs meet, the match is decided by the two groups' DRAFT points that gameweek.
Real Premier League results never count.

Open the link, see the current table. Nothing to run or send each week.
"""

from html import escape

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
    """Return the fixed GW2-GW38 calendar, dropping matches a group plays against itself."""
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


def build_matches(fixtures: pd.DataFrame, points: dict[str, dict[int, int]]) -> pd.DataFrame:
    """Return one row per played match, both sides on the same row.

    `build_results` splits each match into two rows, one per club, because a league table adds
    up what each club did. A results list is the other shape: the two sides belong together so
    a scoreline can be read across. Same source numbers, so the two views cannot disagree.
    """
    finished = played_gameweeks(points)
    rows = []
    for fixture in fixtures.itertuples():
        if fixture.gw not in finished:
            continue
        rows.append(
            {
                "gw": fixture.gw,
                "home_group": fixture.home_group,
                "home_club": fixture.home_club,
                "home_points": points[fixture.home_group].get(fixture.gw, 0),
                "away_group": fixture.away_group,
                "away_club": fixture.away_club,
                "away_points": points[fixture.away_group].get(fixture.gw, 0),
            }
        )
    return pd.DataFrame(rows)


ALL_TEAMS = "All teams"


def team_label(group: str, names: dict[str, str]) -> str:
    """Return the manager and their current squad name, which is how people refer to a side."""
    return f"{GROUP_MANAGERS[group]} — {names.get(group, group)}"


def gameweek_label(gameweek: int, latest: int) -> str:
    """Return the gameweek name, marking the most recent one so the default reads as current."""
    return f"Gameweek {gameweek} — current" if gameweek == latest else f"Gameweek {gameweek}"


# One ceiling for the whole page, so the three tabs share a left edge and an outer limit
# instead of each sprawling to the width of the browser. The widest thing on the page is the
# group table's fifteen columns, and this is set just above it so that table still never
# scrolls sideways. Narrower tabs simply end sooner, which reads as deliberate; stretching
# them to match would put a gap between a manager's name and their score.
PAGE_MAX_WIDTH = 1100

# The results list sits inside that ceiling rather than filling it. A scoreline is read
# across, so the two sides have to stay close enough to take in at a glance.
MATCH_LIST_MAX_WIDTH = 900

PAGE_STYLE = f"""
<style>
.block-container, .stMainBlockContainer {{ max-width: {PAGE_MAX_WIDTH}px; }}
</style>
"""

# The results list is drawn as one HTML block rather than a set of st.columns per match. A
# Streamlit column carries its own block padding, so ten matches meant ten stacked containers
# and a page far taller and wider than the two tables beside it. One grid, one render.
MATCH_LIST_STYLE = f"""
<style>
.match-list {{ max-width: {MATCH_LIST_MAX_WIDTH}px; }}
.match-row {{
  display: grid;
  grid-template-columns: 42px 1fr 74px 1fr;
  align-items: center;
  gap: 6px;
  padding: 7px 0;
  border-bottom: 1px solid rgba(128, 128, 128, 0.18);
}}
.match-gw {{ opacity: 0.45; font-size: 0.78em; }}
.match-team-cell {{ display: flex; align-items: center; gap: 8px; }}
.match-crest {{ width: 22px; height: 22px; object-fit: contain; flex: 0 0 auto; }}
.match-side {{ line-height: 1.2; }}
.match-manager {{ font-weight: 600; font-size: 0.92em; }}
.match-team {{ opacity: 0.55; font-size: 0.76em; }}
.match-score {{ text-align: center; font-size: 0.95em; }}
.match-score .sep {{ opacity: 0.3; padding: 0 5px; }}
</style>
"""


def side_html(
    group: str, club: str, names: dict[str, str], badges: dict[str, str], align: str
) -> str:
    """Return one half of a scoreline: crest on the outside, manager and squad beside it.

    The crest sits on the outer edge of each side so the two of them frame the score, which is
    how a results list is read -- eye to the middle first, then out to whoever played.
    """
    crest = (
        f"<img class='match-crest' src='{badges.get(club, '')}' alt='{escape(club)}'>"
        if badges.get(club)
        else ""
    )
    text = (
        f"<div class='match-side' style='text-align:{align}'>"
        f"<div class='match-manager'>{escape(GROUP_MANAGERS[group])}</div>"
        f"<div class='match-team'>{escape(names.get(group, group))} · {escape(club)}</div>"
        f"</div>"
    )
    ordered = (text, crest) if align == "right" else (crest, text)
    justify = "flex-end" if align == "right" else "flex-start"
    return f"<div class='match-team-cell' style='justify-content:{justify}'>{''.join(ordered)}</div>"


def match_row_html(match, names: dict[str, str], badges: dict[str, str]) -> str:
    """Return one scoreline row, the winning side's total in bold."""
    home_weight = "700" if match.home_points > match.away_points else "400"
    away_weight = "700" if match.away_points > match.home_points else "400"
    return (
        "<div class='match-row'>"
        f"<div class='match-gw'>GW{match.gw}</div>"
        f"{side_html(match.home_group, match.home_club, names, badges, 'right')}"
        "<div class='match-score'>"
        f"<span style='font-weight:{home_weight}'>{match.home_points}</span>"
        "<span class='sep'>|</span>"
        f"<span style='font-weight:{away_weight}'>{match.away_points}</span>"
        "</div>"
        f"{side_html(match.away_group, match.away_club, names, badges, 'left')}"
        "</div>"
    )


def render_matches(matches: pd.DataFrame, names: dict[str, str], latest: int) -> None:
    """Draw the results list, filtered by gameweek and by team, newest gameweek first."""
    groups = sorted(GROUP_ENTRY_IDS, key=lambda g: int(g[1:]))
    team_options = [ALL_TEAMS] + [team_label(group, names) for group in groups]
    gameweeks = sorted(matches["gw"].unique(), reverse=True)
    gameweek_options = [gameweek_label(gameweek, latest) for gameweek in gameweeks]

    st.session_state.setdefault("match_team", ALL_TEAMS)
    st.session_state.setdefault("match_gw", gameweek_label(latest, latest))

    def reset_filters() -> None:
        st.session_state["match_team"] = ALL_TEAMS
        st.session_state["match_gw"] = gameweek_label(latest, latest)

    team_column, gameweek_column, reset_column, _ = st.columns([4, 4, 2, 5])
    chosen_team = team_column.selectbox("Team", team_options, key="match_team")
    chosen_gameweek = gameweek_column.selectbox("Gameweek", gameweek_options, key="match_gw")
    reset_column.markdown("<div style='height:1.9em'></div>", unsafe_allow_html=True)
    reset_column.button("Reset ↺", on_click=reset_filters)

    shown = matches[matches["gw"] == gameweeks[gameweek_options.index(chosen_gameweek)]]
    if chosen_team != ALL_TEAMS:
        chosen_group = groups[team_options.index(chosen_team) - 1]
        shown = shown[(shown["home_group"] == chosen_group) | (shown["away_group"] == chosen_group)]

    if shown.empty:
        st.info("No matches for that combination.")
        return

    badges = fetch_club_badges()
    rows = "".join(match_row_html(match, names, badges) for match in shown.itertuples())
    st.markdown(
        f"{MATCH_LIST_STYLE}<div class='match-list'>{rows}</div>", unsafe_allow_html=True
    )


ROW_HEIGHT = 35
HEADER_HEIGHT = 38

# Exact pixel widths, so all fifteen group columns fit a laptop window and the table never
# scrolls sideways. Streamlit's named sizes (small/medium/large) pushed the last three columns
# off-screen behind a scrollbar, which hid Pts -- the column the table is sorted on, and the
# one number that says who is winning.
#
# Each width is set by the longest real value, not by the header: "Group 7 (MARIOSUPER)" sizes
# the team name and "Oluwadunsin" the manager. Both tables read from this one map so the same
# column is never a different width on the two tabs.
COLUMN_WIDTHS = {
    "pos": 42,
    "group": 48,
    "manager": 100,
    "team name": 150,
    "clubs": 82,
    "badge": 44,
    "club": 56,
    "P": 38,
    "W": 38,
    "D": 38,
    "L": 38,
    "F": 48,
    "A": 48,
    "PD": 46,
    "Pts": 46,
    "form": 92,
    "next": 66,
}

NUMERIC_COLUMNS = ("pos", "P", "W", "D", "L", "F", "A", "PD", "Pts")

# Form as colour, because WWLLW has to be read letter by letter while a run of colour is taken
# in at a glance. Squares rather than coloured letters: a Streamlit table cell holds one string
# and cannot style parts of it, so per-letter colour would mean giving up the sortable table.
# The CSV download keeps the letters -- see below, the export is built from the uncoloured
# frame so a spreadsheet gets W/D/L rather than characters it cannot filter on.
FORM_SQUARES = {"W": "🟩", "D": "🟨", "L": "🟥"}


def with_form_colours(table: pd.DataFrame) -> pd.DataFrame:
    """Return a display copy whose form column is coloured squares instead of letters."""
    shown = table.copy()
    shown["form"] = shown["form"].map(
        lambda run: "".join(FORM_SQUARES.get(result, result) for result in run)
    )
    return shown


def column_settings(table: pd.DataFrame, key: str) -> dict:
    """Return how each column is drawn: fixed width, and crests as images on the club table."""
    settings = {}
    for column in table.columns:
        width = COLUMN_WIDTHS[column]
        if column == "badge":
            settings[column] = st.column_config.ImageColumn("", width=width)
        elif column == "next" and key == "club":
            settings[column] = st.column_config.ImageColumn("next", width=width)
        elif column in NUMERIC_COLUMNS:
            settings[column] = st.column_config.NumberColumn(column, width=width)
        else:
            settings[column] = st.column_config.TextColumn(column, width=width)
    return settings


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
    if key == "club":
        table["next"] = table["next"].map(fetch_club_badges())
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
st.markdown(PAGE_STYLE, unsafe_allow_html=True)
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
    group_tab, club_tab, matches_tab = st.tabs(["Groups", "Clubs", "Matches"])
    with matches_tab:
        render_matches(build_matches(fixtures, points), names, latest)
    for tab, key in ((group_tab, "group"), (club_tab, "club")):
        with tab:
            table = summarise(results, key, names, fixtures, played)
            st.dataframe(
                with_form_colours(table),
                hide_index=True,
                width="content",
                height=full_height(len(table)),
                column_config=column_settings(table, key),
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
