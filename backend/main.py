from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv
import httpx
import os
from datetime import date

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # FIX: allow all origins (covers all Vercel preview URLs)
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")
FOOTBALLDATA_API_KEY = os.getenv("FOOTBALLDATA_API_KEY")

APIFOOTBALL_BASE = "https://v3.football.api-sports.io"
FOOTBALLDATA_BASE = "https://api.football-data.org/v4"
SPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/3"

APIFOOTBALL_HEADERS = {
    "x-apisports-key": FOOTBALL_API_KEY or ""
}

FOOTBALLDATA_HEADERS = {
    "X-Auth-Token": FOOTBALLDATA_API_KEY or ""
}


class MatchRequest(BaseModel):
    team1: str
    team2: str


@app.get("/")
def home():
    return {"message": "KickMind AI Backend Running"}


# ---------------- LIVE ----------------
@app.get("/live")
async def get_live_matches():
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{APIFOOTBALL_BASE}/fixtures",
                headers=APIFOOTBALL_HEADERS,
                params={"live": "all"}
            )

        data = response.json()

        if "response" not in data:
            return {"matches": [], "error": "Invalid API response"}

        matches = []

        for fixture in data.get("response", []):
            matches.append({
                "id": fixture["fixture"]["id"],
                "status": fixture["fixture"]["status"]["long"],
                "minute": fixture["fixture"]["status"].get("elapsed", 0),
                "home_team": fixture["teams"]["home"]["name"],
                "home_logo": fixture["teams"]["home"]["logo"],
                "away_team": fixture["teams"]["away"]["name"],
                "away_logo": fixture["teams"]["away"]["logo"],
                "home_score": fixture["goals"]["home"],
                "away_score": fixture["goals"]["away"],
                "league": fixture["league"]["name"],
                "league_logo": fixture["league"]["logo"],
                "country": fixture["league"]["country"],
            })

        return {"matches": matches}

    except Exception as e:
        return {"matches": [], "error": str(e)}


# ---------------- FIXTURES ----------------
@app.get("/fixtures/today")
async def get_todays_fixtures():
    try:
        today = date.today().isoformat()

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{APIFOOTBALL_BASE}/fixtures",
                headers=APIFOOTBALL_HEADERS,
                params={"date": today}
            )

        data = response.json()

        fixtures = []

        for fixture in data.get("response", []):
            fixtures.append({
                "id": fixture["fixture"]["id"],
                "time": fixture["fixture"]["date"],
                "status": fixture["fixture"]["status"]["short"],
                "minute": fixture["fixture"]["status"].get("elapsed", 0),
                "home_team": fixture["teams"]["home"]["name"],
                "home_logo": fixture["teams"]["home"]["logo"],
                "away_team": fixture["teams"]["away"]["name"],
                "away_logo": fixture["teams"]["away"]["logo"],
                "home_score": fixture["goals"]["home"],
                "away_score": fixture["goals"]["away"],
                "league": fixture["league"]["name"],
                "league_logo": fixture["league"]["logo"],
                "country": fixture["league"]["country"],
            })

        return {"fixtures": fixtures}

    except Exception as e:
        return {"fixtures": [], "error": str(e)}


# ---------------- STANDINGS ----------------
@app.get("/standings/{competition_code}")
async def get_standings(competition_code: str):
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{FOOTBALLDATA_BASE}/competitions/{competition_code}/standings",
                headers=FOOTBALLDATA_HEADERS,
            )

        data = response.json()

        if "standings" not in data:
            return {"standings": [], "error": "No standings data"}

        standings_data = data["standings"][0]["table"]

        result = []

        for team in standings_data:
            result.append({
                "rank": team["position"],
                "team": team["team"]["name"],
                "logo": team["team"]["crest"],
                "played": team["playedGames"],
                "won": team["won"],
                "drawn": team["draw"],
                "lost": team["lost"],
                "goals_for": team["goalsFor"],
                "goals_against": team["goalsAgainst"],
                "goal_difference": team["goalDifference"],
                "points": team["points"],
                "form": team.get("form", ""),
            })

        return {"standings": result}

    except Exception as e:
        return {"standings": [], "error": str(e)}


# ---------------- SCORERS ----------------
@app.get("/scorers/{competition_code}")
async def get_top_scorers(competition_code: str):
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
                "name": scorer["player"]["name"],
                "nationality": scorer["player"]["nationality"],
                "team": scorer["team"]["name"],
                "team_logo": scorer["team"]["crest"],
                "goals": scorer.get("goals", 0),
                "assists": scorer.get("assists", 0),
            })

        return {"scorers": scorers}

    except Exception as e:
        return {"scorers": [], "error": str(e)}


# ---------------- TEAM SEARCH ----------------
@app.get("/team/{team_name}")
async def search_team(team_name: str):
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{SPORTSDB_BASE}/searchteams.php",
                params={"t": team_name}
            )

        data = response.json()
        teams = data.get("teams") or []

        result = []

        for team in teams[:3]:
            result.append({
                "name": team.get("strTeam"),
                "logo": team.get("strTeamBadge"),
                "banner": team.get("strTeamBanner"),
                "country": team.get("strCountry"),
                "league": team.get("strLeague"),
                "founded": team.get("intFormedYear"),
                "stadium": team.get("strStadium"),
                "description": (team.get("strDescriptionEN") or "")[:300],
            })

        return {"teams": result}

    except Exception as e:
        return {"teams": [], "error": str(e)}


# ---------------- PLAYER SEARCH ----------------
@app.get("/player/{player_name}")
async def search_player(player_name: str):
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{SPORTSDB_BASE}/searchplayers.php",
                params={"p": player_name}
            )

        data = response.json()
        players = data.get("player") or []

        result = []

        for player in players[:5]:
            result.append({
                "name": player.get("strPlayer"),
                "photo": player.get("strThumb"),
                "nationality": player.get("strNationality"),
                "team": player.get("strTeam"),
                "position": player.get("strPosition"),
                "date_of_birth": player.get("dateBorn"),
                "height": player.get("strHeight"),
                "weight": player.get("strWeight"),
                "description": (player.get("strDescriptionEN") or "")[:300],
            })

        return {"players": result}

    except Exception as e:
        return {"players": [], "error": str(e)}


# ---------------- PREDICT ----------------
@app.post("/predict")
def predict_match(data: MatchRequest):
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a football analyst."
                },
                {
                    "role": "user",
                    "content": f"Predict {data.team1} vs {data.team2} with score, winner, and analysis."
                }
            ],
            model="llama-3.3-70b-versatile",
        )

        return {"prediction": chat_completion.choices[0].message.content}

    except Exception as e:
        return {"prediction": f"Error: {str(e)}"}
