# fpl-draft-h2h

Weekly head-to-head table for the WhatsApp FPL Draft league, as one link the group opens.
Nothing to run or send each week.

## The rule this app exists to enforce

Each group owns Premier League clubs. The real fixture list is used **only as a calendar**:
when two clubs meet, the match is decided by the two groups' **draft points** that gameweek.
**Real Premier League results never count.**

The head-to-head starts at GW2 — there are no GW1 fixtures.

## How it works

| Step | What happens |
|---|---|
| Fetch | `draft.premierleague.com/api/league/<id>/details` for squad names, then one `/entry/<entry_id>/history` call per group for per-gameweek points |
| Compute | join to the season's fixtures file, 3/1/0, points for and against, difference |
| Display | one tab by group, one by club |

Groups are keyed by **entry id, never squad name** — people rename teams mid-season and a name
lookup would silently break. Names are re-read on each load so renames still display correctly.

Unplayed gameweeks are excluded, so a future fixture never shows as a 0–0 draw.

## Each new season

1. Add the new calendar as `fixtures_<season>.csv` — **add, never overwrite**, so old seasons stay
   in the repo.
2. Update `SEASON`, `LEAGUE_ID`, `GROUP_ENTRY_IDS` and `FIXTURES_FILE` in `season.py`.

The app itself does not change unless the format changes.

Nothing is stored while the season runs — the table is computed live on every load. Use the
**download button** under either table to keep a copy, and commit the final one at GW38.

### GW1 and GW31 are skipped on purpose

10 groups make 45 unique pairings. 36 gameweeks x 10 fixtures = 360 matches, which is exactly
**8 meetings per pair**. 37 gameweeks would not divide evenly, so one gameweek beyond GW1 had to
go, and GW31 was chosen.

### Choosing the number of groups

20 clubs have to divide evenly, or someone gets more fixtures than someone else.

| Groups | Clubs each | Owned by AVERAGE | Matches against AVERAGE |
|---|---|---|---|
| **10** | 2 | 0 | none |
| 9 | 2 | 2 | ~10% |
| 13 | 1 | 7 | ~35% |
| 12 | 1 | 8 | ~40% |

**10 groups is the right number** — every group owns exactly 2 clubs and no filler is needed.

For any other count, give every group the *same* number of clubs and hand the leftovers to an
**AVERAGE** entry that scores the gameweek mean. This mirrors the official FPL rule, where an
average team joins an odd-numbered head-to-head league so nobody has a bye. It keeps things fair,
but at 12 groups you would play the filler two weeks in five. Workable, not good.

## Run it locally

    pip install -r requirements.txt
    streamlit run streamlit_app.py

## Deploy

GitHub repo → share.streamlit.io → post the link in the group once.
