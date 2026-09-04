"""
Everything that changes from one season to the next. Edit only this file each August.

The app itself never needs changing unless the format changes.
"""

SEASON = "2026/27"

LEAGUE_ID = 79776

# Group number to FPL Draft entry id. Keyed by id, never by squad name — people rename
# their teams mid-season and a name lookup would silently break.
GROUP_ENTRY_IDS = {
    "G1": 416388,
    "G2": 416391,
    "G3": 417063,
    "G4": 417852,
    "G5": 416395,
    "G6": 417117,
    "G7": 416396,
    "G8": 417582,
    "G9": 416394,
    "G10": 420729,
}

# The person behind each group. The API only carries the name they signed up with,
# which is not always what everyone calls them.
GROUP_MANAGERS = {
    "G1": "Ganapathy",
    "G2": "Pratik",
    "G3": "Nahul",
    "G4": "Smit",
    "G5": "Ayaan",
    "G6": "Jaikishen",
    "G7": "Oluwadunsin",
    "G8": "Joswin",
    "G9": "Janak",
    "G10": "Emrev",
}

# The calendar: which club plays which, and which group owns each club.
# Name it per season and ADD a new one each year — never overwrite the old file.
FIXTURES_FILE = "fixtures_2026_27.csv"
