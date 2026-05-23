from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv
import httpx
import os
import asyncio
from datetime import date, datetime, timedelta
import time

load_dotenv()

app = FastAPI(title="KickMind AI Backend", version="2.0.1")

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
# CLIENTS
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
# CACHE (safe version)
# ─────────────────────────────────────────────
_cache = {}

def cache_get(key):
    entry = _cache.get(key)
    if not entry:
        return None
    if time.time() > entry["expires"]:
        return None
    return entry["data"]

def cache_set(key, data, ttl):
    _cache[key] = {
        "data": data,
        "expires": time.time() + ttl
    }

def cache_clear_key(prefix):
    keys_to_remove = [k for k in _cache.keys() if k.startswith(prefix)]
    for k in keys_to_remove:
        del _cache[k]

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
# ROOT
# ─────────────────────────────────────────────
@app.get("/")
def home():
    return {
        "message": "KickMind AI Backend Running",
        "status": "healthy",
        "time": datetime.utcnow().isoformat()
    }

# ─────────────────────────────────────────────
# LIVE MATCHES
# ─────────────────────────────────────────────
@app.get("/live")
async def get_live_matches():
    cached = cache_get("live")
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.get(
                f"{APIFOOTBALL_BASE}/fixtures",
                headers=APIFOOTBALL_HEADERS,
                params={"live": "all"},
            )

        data = res.json()
        matches = data.get("response", [])

        result = {"matches": matches}
        cache_set("live", result, 60)
        return result

    except Exception as e:
        return {"matches": [], "error": str(e)}

# ─────────────────────────────────────────────
# TEAM SEARCH (FIXED — MAIN ISSUE)
# ─────────────────────────────────────────────
@app.get("/team/{team_name}")
async def search_team(team_name: str):
    try:
        team_name = team_name.strip()

        # IMPORTANT: DO NOT trust cache for search results
        cache_key = f"team_{team_name.lower()}"
        cached = cache_get(cache_key)

        # Only return cache if it is NOT corrupted
        if cached and isinstance(cached.get("teams"), list):
            return cached

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{SPORTSDB_BASE}/searchteams.php",
                params={"t": team_name},
            )

        data = response.json()
        teams = data.get("teams")

        if not teams:
            return {"teams": []}

        result_teams = []

        for team in teams[:5]:
            result_teams.append({
                "name": team.get("strTeam"),
                "logo": team.get("strTeamBadge"),
                "banner": team.get("strTeamBanner"),
                "country": team.get("strCountry"),
                "league": team.get("strLeague"),
                "founded": team.get("intFormedYear"),
                "stadium": team.get("strStadium"),
                "stadium_capacity": team.get("intStadiumCapacity"),
                "website": team.get("strWebsite"),
                "twitter": team.get("strTwitter"),
                "instagram": team.get("strInstagram"),
                "description": (team.get("strDescriptionEN") or "")[:500],
            })

        result = {"teams": result_teams}

        # cache only CLEAN results
        cache_set(cache_key, result, 600)

        return result

    except Exception as e:
        return {"teams": [], "error": str(e)}

# ─────────────────────────────────────────────
# PLAYER SEARCH
# ─────────────────────────────────────────────
@app.get("/player/{player_name}")
async def search_player(player_name: str):
    try:
        cache_key = f"player_{player_name.lower()}"
        cached = cache_get(cache_key)
        if cached:
            return cached

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{SPORTSDB_BASE}/searchplayers.php",
                params={"p": player_name.strip()},
            )

        data = response.json()
        players = data.get("player") or []

        result_players = []

        for p in players[:5]:
            result_players.append({
                "name": p.get("strPlayer"),
                "photo": p.get("strThumb"),
                "nationality": p.get("strNationality"),
                "team": p.get("strTeam"),
                "position": p.get("strPosition"),
                "date_of_birth": p.get("dateBorn"),
                "height": p.get("strHeight"),
                "weight": p.get("strWeight"),
                "description": (p.get("strDescriptionEN") or "")[:500],
            })

        result = {"players": result_players}
        cache_set(cache_key, result, 600)
        return result

    except Exception as e:
        return {"players": [], "error": str(e)}

# ─────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────
@app.get("/fixtures/today")
async def fixtures_today():
    cached = cache_get("fixtures_today")
    if cached:
        return cached

    try:
        today = date.today().isoformat()

        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.get(
                f"{APIFOOTBALL_BASE}/fixtures",
                headers=APIFOOTBALL_HEADERS,
                params={"date": today},
            )

        data = res.json()
        fixtures = data.get("response", [])

        result = {"fixtures": fixtures}
        cache_set("fixtures_today", result, 300)
        return result

    except Exception as e:
        return {"fixtures": [], "error": str(e)}

# ─────────────────────────────────────────────
# STANDINGS
# ─────────────────────────────────────────────
@app.get("/standings/{code}")
async def standings(code: str):
    cached = cache_get(f"standings_{code}")
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.get(
                f"{FOOTBALLDATA_BASE}/competitions/{code}/standings",
                headers=FOOTBALLDATA_HEADERS,
            )

        data = res.json()

        table = []
        for team in data["standings"][0]["table"]:
            table.append({
                "rank": team["position"],
                "team": team["team"]["name"],
                "logo": team["team"]["crest"],
                "points": team["points"],
                "played": team["playedGames"],
                "won": team["won"],
                "drawn": team["draw"],
                "lost": team["lost"],
            })

        result = {"standings": table}
        cache_set(f"standings_{code}", result, 3600)
        return result

    except Exception as e:
        return {"standings": [], "error": str(e)}

# ─────────────────────────────────────────────
# PREDICT (unchanged but stable)
# ─────────────────────────────────────────────
@app.post("/predict")
def predict(data: MatchRequest):
    try:
        chat = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a football analyst."},
                {"role": "user", "content": f"{data.team1} vs {data.team2}"},
            ],
            model="llama-3.3-70b-versatile",
        )

        return {"prediction": chat.choices[0].message.content}

    except Exception as e:
        return {"prediction": str(e)}

# ─────────────────────────────────────────────
# CACHE CLEAR (DEBUG)
# ─────────────────────────────────────────────
@app.delete("/cache/clear")
def clear_cache():
    _cache.clear()
    return {"message": "cache cleared"}
