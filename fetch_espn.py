"""Pull the league from ESPN and save one small JSON file per week.

Runs on GitHub's servers (see .github/workflows/pull.yml). Standard library only.
"""
import json, os, urllib.request

LEAGUE_ID = 1938158271
SEASON = 2026
BASE = (f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/"
        f"{SEASON}/segments/0/leagues/{LEAGUE_ID}")
POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}
SLOT = {0: "QB", 2: "RB", 4: "WR", 6: "TE", 16: "D/ST", 17: "K",
        20: "BE", 21: "IR", 23: "FLEX"}
# ESPN stat ids -> short names (only non-zero values are saved)
STATS = {"passYds": "3", "passTD": "4", "int": "20", "rushYds": "24", "rushTD": "25",
         "rec": "53", "recYds": "42", "recTD": "43", "fumLost": "72"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def get(params, filt=None):
    req = urllib.request.Request(BASE + "?" + params,
                                 headers={"User-Agent": "Mozilla/5.0"})
    if filt:
        req.add_header("x-fantasy-filter", json.dumps(filt))
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def save(name, obj):
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, indent=1)


def main():
    os.makedirs(OUT, exist_ok=True)
    league = get("view=mTeam&view=mSettings&view=mStatus")
    members = {m["id"]: m for m in league.get("members", [])}
    teams = []
    for t in league["teams"]:
        owner = members.get((t.get("owners") or [None])[0], {})
        rec = t.get("record", {}).get("overall", {})
        teams.append({
            "id": t["id"],
            "name": t.get("name") or f'{t.get("location","")} {t.get("nickname","")}'.strip(),
            "owner": f'{owner.get("firstName","")} {owner.get("lastName","")}'.strip(),
            "wins": rec.get("wins"), "losses": rec.get("losses"), "ties": rec.get("ties"),
            "pointsFor": rec.get("pointsFor"), "pointsAgainst": rec.get("pointsAgainst"),
        })
    status = league.get("status", {})
    current = status.get("currentMatchupPeriod") or 1
    save("teams.json", {"season": SEASON, "currentMatchupPeriod": current,
                        "latestScoringPeriod": status.get("latestScoringPeriod"),
                        "teams": teams})

    for week in range(1, current + 1):
        data = get(f"view=mBoxscore&view=mMatchupScore&scoringPeriodId={week}",
                   {"schedule": {"filterMatchupPeriodIds": {"value": [week]}}})
        games, final = [], True
        for g in data.get("schedule", []):
            if g.get("matchupPeriodId") != week:
                continue
            if g.get("winner") in (None, "UNDECIDED"):
                final = False
            game = {"winner": g.get("winner")}
            for side in ("home", "away"):
                s = g.get(side)
                if not s:
                    continue
                roster = (s.get("rosterForCurrentScoringPeriod") or {}).get("entries", [])
                players = []
                for e in roster:
                    p = e.get("playerPoolEntry", {})
                    pl = p.get("player", {})
                    raw = {}
                    for st in pl.get("stats") or []:
                        if (st.get("scoringPeriodId") == week and st.get("statSourceId") == 0
                                and st.get("statSplitTypeId") == 1):
                            raw = st.get("stats") or {}
                            break
                    line = {k: raw[i] for k, i in STATS.items() if raw.get(i)}
                    players.append({
                        "name": pl.get("fullName"),
                        "pos": POS.get(pl.get("defaultPositionId"), str(pl.get("defaultPositionId"))),
                        "slot": SLOT.get(e.get("lineupSlotId"), str(e.get("lineupSlotId"))),
                        "pts": round(p.get("appliedStatTotal") or 0, 2),
                        "injury": pl.get("injuryStatus"),
                        "stats": line,
                    })
                game[side] = {"teamId": s.get("teamId"),
                              "points": s.get("totalPoints"),
                              "players": players}
            games.append(game)
        if games:
            save(f"week-{week}.json", {"week": week, "final": final, "games": games})
            print(f"week {week}: {len(games)} games, final={final}")


if __name__ == "__main__":
    main()
