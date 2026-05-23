from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv
import httpx
import os
import asyncio
from datetime import date, datetime, timedelta
from typing import Optional
import time

load_dotenv()

app = FastAPI(title="KickMind AI Backend", version="2.0.0")

# ─────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# CLIENTS & KEYS
# ─────────────────────────────────────────────
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

FOOTBALL_API_KEY     = os.getenv("FOOTBALL_API_KEY", "")
FOOTBALLDATA_API_KEY = os.getenv("FOOTBALLDATA_API_KEY", "")

APIFOOTBALL_BASE  = "https://v3.football.api-sports.io"
FOOTBALLDATA_BASE = "https://api.football-data.org/v4"
SPORTSDB_BASE     = "https://www.thesportsdb.com/api/v1/json/3"

APIFOOTBALL_HEADERS  = {"x-apisports-key": FOOTBALL_API_KEY}
FOOTBALLDATA_HEADERS = {"X-Auth-Token": FOOTBALLDATA_API_KEY}

# ─────────────────────────────────────────────
# SIMPLE IN-MEMORY CACHE
# Avoids hammering APIs on every frontend poll
# ─────────────────────────────────────────────
_cache: dict = {}

def cache_get(key: str):
    entry = _cache.get(key)
    if entry and time.time() < entry["expires"]:
        return entry["data"]
    return None

def cache_set(key: str, data, ttl_seconds: int):
    _cache[key] = {"data": data, "expires": time.time() + ttl_seconds}


# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────
class MatchRequest(BaseModel):
    team1: str
    team2: str

class HeadToHeadRequest(BaseModel):
    team1: str
    team2: str


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def parse_fixture(fixture: dict) -> dict:
    """Shared fixture parser used across live, fixtures, and match detail."""
    f   = fixture["fixture"]
    t   = fixture["teams"]
    g   = fixture["goals"]
    lg  = fixture["league"]
    sc  = fixture.get("score", {})
    ev  = fixture.get("events", [])
    lin = fixture.get("lineups", [])

    events_parsed = []
    for e in ev:
        events_parsed.append({
            "minute":    e["time"].get("elapsed", 0),
            "extra":     e["time"].get("extra"),
            "team":      e["team"]["name"],
            "player":    e["player"]["name"] if e.get("player") else None,
            "assist":    e["assist"]["name"] if e.get("assist") else None,
            "type":      e["type"],
            "detail":    e["detail"],
        })

    lineups_parsed = []
    for side in lin:
        lineups_parsed.append({
            "team":        side["team"]["name"],
            "formation":   side.get("formation", ""),
            "start_xi":    [p["player"]["name"] for p in side.get("startXI", [])],
            "substitutes": [p["player"]["name"] for p in side.get("substitutes", [])],
        })

    return {
        "id":          f["id"],
        "date":        f["date"],
        "status":      f["status"]["long"],
        "status_short":f["status"]["short"],
        "minute":      f["status"].get("elapsed", 0),
        "home_team":   t["home"]["name"],
        "home_logo":   t["home"]["logo"],
        "home_winner": t["home"].get("winner"),
        "away_team":   t["away"]["name"],
        "away_logo":   t["away"]["logo"],
        "away_winner": t["away"].get("winner"),
        "home_score":  g["home"],
        "away_score":  g["away"],
        "ht_home":     sc.get("halftime", {}).get("home"),
        "ht_away":     sc.get("halftime", {}).get("away"),
        "ft_home":     sc.get("fulltime", {}).get("home"),
        "ft_away":     sc.get("fulltime", {}).get("away"),
        "league":      lg["name"],
        "league_logo": lg["logo"],
        "country":     lg["country"],
        "season":      lg.get("season"),
        "round":       lg.get("round"),
        "venue":       f.get("venue", {}).get("name"),
        "referee":     f.get("referee"),
        "events":      events_parsed,
        "lineups":     lineups_parsed,
    }


# ─────────────────────────────────────────────
# ROOT / HEALTH
# ─────────────────────────────────────────────
@app.get("/")
def home():
    return {
        "message": "KickMind AI Backend Running",
        "version": "2.0.0",
        "status":  "healthy",
        "time":    datetime.utcnow().isoformat(),
    }

@app.get("/health")
def health():
    """UptimeRobot / monitoring ping endpoint."""
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


# ─────────────────────────────────────────────
# LIVE MATCHES  (cache 60 s — refreshes often)
# ─────────────────────────────────────────────
@app.get("/live")
async def get_live_matches():
    cached = cache_get("live")
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{APIFOOTBALL_BASE}/fixtures",
                headers=APIFOOTBALL_HEADERS,
                params={"live": "all"},
            )
        data = response.json()

        if "response" not in data:
            return {"matches": [], "error": "Invalid API response", "cached": False}

        matches = [parse_fixture(f) for f in data.get("response", [])]
        result  = {"matches": matches, "count": len(matches), "cached": False}
        cache_set("live", result, ttl_seconds=60)
        return result

    except Exception as e:
        return {"matches": [], "error": str(e), "cached": False}


# ─────────────────────────────────────────────
# MATCH DETAIL  (events + lineups for one game)
# ─────────────────────────────────────────────
@app.get("/match/{fixture_id}")
async def get_match_detail(fixture_id: int):
    cache_key = f"match_{fixture_id}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # Fetch fixture + events + lineups in parallel
            fix_task = client.get(
                f"{APIFOOTBALL_BASE}/fixtures",
                headers=APIFOOTBALL_HEADERS,
                params={"id": fixture_id},
            )
            ev_task = client.get(
                f"{APIFOOTBALL_BASE}/fixtures/events",
                headers=APIFOOTBALL_HEADERS,
                params={"fixture": fixture_id},
            )
            lin_task = client.get(
                f"{APIFOOTBALL_BASE}/fixtures/lineups",
                headers=APIFOOTBALL_HEADERS,
                params={"fixture": fixture_id},
            )
            stat_task = client.get(
                f"{APIFOOTBALL_BASE}/fixtures/statistics",
                headers=APIFOOTBALL_HEADERS,
                params={"fixture": fixture_id},
            )
            fix_res, ev_res, lin_res, stat_res = await asyncio.gather(
                fix_task, ev_task, lin_task, stat_task
            )

        fix_data  = fix_res.json()
        ev_data   = ev_res.json()
        lin_data  = lin_res.json()
        stat_data = stat_res.json()

        fixtures = fix_data.get("response", [])
        if not fixtures:
            return {"match": None, "error": "Match not found"}

        # Inject events and lineups into fixture blob
        fixture_blob = fixtures[0]
        fixture_blob["events"]  = ev_data.get("response", [])
        fixture_blob["lineups"] = lin_data.get("response", [])

        match = parse_fixture(fixture_blob)

        # Parse team statistics
        statistics = []
        for side in stat_data.get("response", []):
            stats_map = {s["type"]: s["value"] for s in side.get("statistics", [])}
            statistics.append({
                "team":             side["team"]["name"],
                "logo":             side["team"]["logo"],
                "shots_on_goal":    stats_map.get("Shots on Goal", 0),
                "shots_total":      stats_map.get("Total Shots", 0),
                "possession":       stats_map.get("Ball Possession", "0%"),
                "passes":           stats_map.get("Total passes", 0),
                "pass_accuracy":    stats_map.get("Passes accurate", 0),
                "fouls":            stats_map.get("Fouls", 0),
                "yellow_cards":     stats_map.get("Yellow Cards", 0),
                "red_cards":        stats_map.get("Red Cards", 0),
                "offsides":         stats_map.get("Offsides", 0),
                "corners":          stats_map.get("Corner Kicks", 0),
                "saves":            stats_map.get("Goalkeeper Saves", 0),
            })

        match["statistics"] = statistics
        result = {"match": match}
        cache_set(cache_key, result, ttl_seconds=60)
        return result

    except Exception as e:
        return {"match": None, "error": str(e)}


# ─────────────────────────────────────────────
# TODAY'S FIXTURES  (cache 5 min)
# ─────────────────────────────────────────────
@app.get("/fixtures/today")
async def get_todays_fixtures():
    cached = cache_get("fixtures_today")
    if cached:
        return cached

    try:
        today = date.today().isoformat()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{APIFOOTBALL_BASE}/fixtures",
                headers=APIFOOTBALL_HEADERS,
                params={"date": today},
            )
        data = response.json()
        fixtures = [parse_fixture(f) for f in data.get("response", [])]
        result = {"fixtures": fixtures, "count": len(fixtures), "date": today}
        cache_set("fixtures_today", result, ttl_seconds=300)
        return result

    except Exception as e:
        return {"fixtures": [], "error": str(e)}


# ─────────────────────────────────────────────
# FIXTURES BY DATE RANGE  (e.g. next 7 days)
# ─────────────────────────────────────────────
@app.get("/fixtures/range")
async def get_fixtures_range(
    days_ahead: int = Query(default=7, ge=1, le=30)
):
    cache_key = f"fixtures_range_{days_ahead}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    try:
        today    = date.today()
        end_date = today + timedelta(days=days_ahead)

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{APIFOOTBALL_BASE}/fixtures",
                headers=APIFOOTBALL_HEADERS,
                params={"from": today.isoformat(), "to": end_date.isoformat()},
            )
        data = response.json()
        fixtures = [parse_fixture(f) for f in data.get("response", [])]
        result = {
            "fixtures":   fixtures,
            "count":      len(fixtures),
            "from":       today.isoformat(),
            "to":         end_date.isoformat(),
        }
        cache_set(cache_key, result, ttl_seconds=600)
        return result

    except Exception as e:
        return {"fixtures": [], "error": str(e)}


# ─────────────────────────────────────────────
# STANDINGS  (cache 1 hour)
# ─────────────────────────────────────────────
@app.get("/standings/{competition_code}")
async def get_standings(competition_code: str):
    cache_key = f"standings_{competition_code}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{FOOTBALLDATA_BASE}/competitions/{competition_code}/standings",
                headers=FOOTBALLDATA_HEADERS,
            )
        data = response.json()

        if "standings" not in data:
            return {"standings": [], "error": data.get("message", "No standings data")}

        result_rows = []
        for team in data["standings"][0]["table"]:
            result_rows.append({
                "rank":            team["position"],
                "team":            team["team"]["name"],
                "logo":            team["team"]["crest"],
                "played":          team["playedGames"],
                "won":             team["won"],
                "drawn":           team["draw"],
                "lost":            team["lost"],
                "goals_for":       team["goalsFor"],
                "goals_against":   team["goalsAgainst"],
                "goal_difference": team["goalDifference"],
                "points":          team["points"],
                "form":            team.get("form", ""),
            })

        result = {
            "standings":   result_rows,
            "competition": data.get("competition", {}).get("name", competition_code),
            "season":      data.get("season", {}).get("startDate", ""),
        }
        cache_set(cache_key, result, ttl_seconds=3600)
        return result

    except Exception as e:
        return {"standings": [], "error": str(e)}


# ─────────────────────────────────────────────
# TOP SCORERS  (cache 1 hour)
# ─────────────────────────────────────────────
@app.get("/scorers/{competition_code}")
async def get_top_scorers(competition_code: str):
    cache_key = f"scorers_{competition_code}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{FOOTBALLDATA_BASE}/competitions/{competition_code}/scorers",
                headers=FOOTBALLDATA_HEADERS,
            )
        data = response.json()

        scorers = []
        for scorer in data.get("scorers", []):
            scorers.append({
                "name":        scorer["player"]["name"],
                "nationality": scorer["player"]["nationality"],
                "team":        scorer["team"]["name"],
                "team_logo":   scorer["team"]["crest"],
                "goals":       scorer.get("goals", 0),
                "assists":     scorer.get("assists", 0),
                "penalties":   scorer.get("penalties", 0),
            })

        result = {"scorers": scorers, "competition": competition_code}
        cache_set(cache_key, result, ttl_seconds=3600)
        return result

    except Exception as e:
        return {"scorers": [], "error": str(e)}


# ─────────────────────────────────────────────
# TEAM SEARCH  (cache 10 min)
# ─────────────────────────────────────────────
@app.get("/team/{team_name}")
async def search_team(team_name: str):
    cache_key = f"team_{team_name.lower()}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{SPORTSDB_BASE}/searchteams.php",
                params={"t": team_name},
            )
        data  = response.json()
        teams = data.get("teams") or []

        result_teams = []
        for team in teams[:3]:
            result_teams.append({
                "name":        team.get("strTeam"),
                "logo":        team.get("strTeamBadge"),
                "banner":      team.get("strTeamBanner"),
                "country":     team.get("strCountry"),
                "league":      team.get("strLeague"),
                "founded":     team.get("intFormedYear"),
                "stadium":     team.get("strStadium"),
                "stadium_capacity": team.get("intStadiumCapacity"),
                "website":     team.get("strWebsite"),
                "twitter":     team.get("strTwitter"),
                "instagram":   team.get("strInstagram"),
                "description": (team.get("strDescriptionEN") or "")[:500],
            })

        result = {"teams": result_teams}
        cache_set(cache_key, result, ttl_seconds=600)
        return result

    except Exception as e:
        return {"teams": [], "error": str(e)}


# ─────────────────────────────────────────────
# PLAYER SEARCH  (cache 10 min)
# ─────────────────────────────────────────────
@app.get("/player/{player_name}")
async def search_player(player_name: str):
    cache_key = f"player_{player_name.lower()}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{SPORTSDB_BASE}/searchplayers.php",
                params={"p": player_name},
            )
        data    = response.json()
        players = data.get("player") or []

        result_players = []
        for player in players[:5]:
            result_players.append({
                "name":          player.get("strPlayer"),
                "photo":         player.get("strThumb"),
                "nationality":   player.get("strNationality"),
                "team":          player.get("strTeam"),
                "position":      player.get("strPosition"),
                "date_of_birth": player.get("dateBorn"),
                "height":        player.get("strHeight"),
                "weight":        player.get("strWeight"),
                "shirt_number":  player.get("strNumber"),
                "agent":         player.get("strAgent"),
                "description":   (player.get("strDescriptionEN") or "")[:500],
            })

        result = {"players": result_players}
        cache_set(cache_key, result, ttl_seconds=600)
        return result

    except Exception as e:
        return {"players": [], "error": str(e)}


# ─────────────────────────────────────────────
# HEAD-TO-HEAD  (last 10 meetings between 2 teams)
# ─────────────────────────────────────────────
@app.get("/h2h")
async def get_head_to_head(
    team1_id: int = Query(..., description="api-football team ID for team 1"),
    team2_id: int = Query(..., description="api-football team ID for team 2"),
):
    cache_key = f"h2h_{min(team1_id,team2_id)}_{max(team1_id,team2_id)}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{APIFOOTBALL_BASE}/fixtures/headtohead",
                headers=APIFOOTBALL_HEADERS,
                params={"h2h": f"{team1_id}-{team2_id}", "last": 10},
            )
        data     = response.json()
        meetings = [parse_fixture(f) for f in data.get("response", [])]

        # Basic stats summary
        t1_wins = sum(1 for m in meetings if m["home_winner"] and m["home_team"] or m["away_winner"] and m["away_team"])
        draws   = sum(1 for m in meetings if not m["home_winner"] and not m["away_winner"] and m["ft_home"] is not None)
        goals   = sum((m["home_score"] or 0) + (m["away_score"] or 0) for m in meetings)

        result = {
            "meetings": meetings,
            "count":    len(meetings),
            "summary": {
                "total_goals":       goals,
                "avg_goals":         round(goals / len(meetings), 1) if meetings else 0,
                "draws":             draws,
            },
        }
        cache_set(cache_key, result, ttl_seconds=3600)
        return result

    except Exception as e:
        return {"meetings": [], "error": str(e)}


# ─────────────────────────────────────────────
# LEAGUE NEWS SUMMARY  (AI-generated via Groq)
# ─────────────────────────────────────────────
@app.get("/news/{league_name}")
async def get_league_news(league_name: str):
    cache_key = f"news_{league_name.lower()}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a football journalist. Write a short, punchy news bulletin "
                        "of 4-5 bullet points summarising the most interesting recent stories, "
                        "results, transfers, and talking points in the given league. "
                        "Be specific with team and player names. Keep each bullet under 30 words."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Give me a news bulletin for the {league_name} right now.",
                },
            ],
            model="llama-3.3-70b-versatile",
            max_tokens=400,
        )
        summary = chat_completion.choices[0].message.content
        result  = {"league": league_name, "summary": summary, "generated_at": datetime.utcnow().isoformat()}
        cache_set(cache_key, result, ttl_seconds=1800)  # 30 min cache — AI content
        return result

    except Exception as e:
        return {"league": league_name, "summary": "", "error": str(e)}


# ─────────────────────────────────────────────
# AI MATCH PREDICTION  (enhanced prompt)
# ─────────────────────────────────────────────
@app.post("/predict")
def predict_match(data: MatchRequest):
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert football analyst and data scientist. "
                        "When predicting a match, structure your response exactly as:\n"
                        "1. **Predicted Score** — e.g. 2-1\n"
                        "2. **Winner** — team name or Draw\n"
                        "3. **Confidence** — Low / Medium / High\n"
                        "4. **Key Factors** — 3 bullet points on form, injuries, head-to-head\n"
                        "5. **Brief Analysis** — 2-3 sentences\n"
                        "Be specific. Use real football knowledge."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Predict: {data.team1} vs {data.team2}",
                },
            ],
            model="llama-3.3-70b-versatile",
            max_tokens=500,
        )
        return {"prediction": chat_completion.choices[0].message.content}

    except Exception as e:
        return {"prediction": f"Error: {str(e)}"}


# ─────────────────────────────────────────────
# AI HEAD-TO-HEAD PREDICTION  (with H2H context)
# ─────────────────────────────────────────────
@app.post("/predict/h2h")
def predict_with_h2h(data: HeadToHeadRequest):
    """
    Same as /predict but asks AI to factor in head-to-head history explicitly.
    Frontend can call this after fetching /h2h and passing results in body.
    """
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert football analyst. Factor in head-to-head history, "
                        "recent form, home advantage, and key players when making your prediction. "
                        "Structure: Predicted Score | Winner | Confidence | 3 Key Factors | 2-sentence Analysis."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Predict {data.team1} vs {data.team2}. "
                        f"Focus on their head-to-head history and which team has the psychological edge."
                    ),
                },
            ],
            model="llama-3.3-70b-versatile",
            max_tokens=500,
        )
        return {"prediction": chat_completion.choices[0].message.content}

    except Exception as e:
        return {"prediction": f"Error: {str(e)}"}


# ─────────────────────────────────────────────
# PLAYER STATS (from api-football)
# ─────────────────────────────────────────────
@app.get("/player/stats/{player_id}")
async def get_player_stats(player_id: int, season: int = Query(default=2024)):
    cache_key = f"player_stats_{player_id}_{season}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{APIFOOTBALL_BASE}/players",
                headers=APIFOOTBALL_HEADERS,
                params={"id": player_id, "season": season},
            )
        data    = response.json()
        players = data.get("response", [])

        if not players:
            return {"player": None, "error": "Player not found"}

        p     = players[0]["player"]
        stats = players[0].get("statistics", [{}])[0]

        result = {
            "player": {
                "id":          p["id"],
                "name":        p["name"],
                "firstname":   p["firstname"],
                "lastname":    p["lastname"],
                "age":         p["age"],
                "nationality": p["nationality"],
                "height":      p.get("height"),
                "weight":      p.get("weight"),
                "photo":       p["photo"],
            },
            "stats": {
                "team":          stats.get("team", {}).get("name"),
                "team_logo":     stats.get("team", {}).get("logo"),
                "league":        stats.get("league", {}).get("name"),
                "appearances":   stats.get("games", {}).get("appearences", 0),
                "goals":         stats.get("goals", {}).get("total", 0),
                "assists":       stats.get("goals", {}).get("assists", 0),
                "yellow_cards":  stats.get("cards", {}).get("yellow", 0),
                "red_cards":     stats.get("cards", {}).get("red", 0),
                "passes_total":  stats.get("passes", {}).get("total", 0),
                "pass_accuracy": stats.get("passes", {}).get("accuracy"),
                "dribbles":      stats.get("dribbles", {}).get("success", 0),
                "tackles":       stats.get("tackles", {}).get("total", 0),
                "rating":        stats.get("games", {}).get("rating"),
            },
        }
        cache_set(cache_key, result, ttl_seconds=3600)
        return result

    except Exception as e:
        return {"player": None, "error": str(e)}


# ─────────────────────────────────────────────
# CACHE STATUS  (debug endpoint)
# ─────────────────────────────────────────────
@app.get("/cache/status")
def cache_status():
    now  = time.time()
    keys = [
        {
            "key":        k,
            "expires_in": max(0, round(v["expires"] - now)),
        }
        for k, v in _cache.items()
    ]
    return {"cached_keys": len(keys), "keys": keys}


@app.delete("/cache/clear")
def cache_clear():
    _cache.clear()
    return {"message": "Cache cleared"}
