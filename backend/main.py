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
   allow_origins=[
    "http://localhost:5173",
    "http://localhost:5174",
    "https://https://kick-mind-ai.vercel.app/",
],
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

APIFOOTBALL_HEADERS = {"x-apisports-key": FOOTBALL_API_KEY}
FOOTBALLDATA_HEADERS = {"X-Auth-Token": FOOTBALLDATA_API_KEY}


class MatchRequest(BaseModel):
    team1: str
    team2: str


@app.get("/")
def home():
    return {"message": "KickMind AI Backend Running"}


@app.get("/live")
async def get_live_matches():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{APIFOOTBALL_BASE}/fixtures",
            headers=APIFOOTBALL_HEADERS,
            params={"live": "all"}
        )

    data = response.json()

    matches = []

    for fixture in data.get("response", []):
        matches.append({
            "id": fixture["fixture"]["id"],
            "status": fixture["fixture"]["status"]["long"],
            "minute": fixture["fixture"]["status"]["elapsed"],
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


@app.get("/fixtures/today")
async def get_todays_fixtures():
    today = date.today().isoformat()

    async with httpx.AsyncClient() as client:
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
            "status_long": fixture["fixture"]["status"]["long"],
            "minute": fixture["fixture"]["status"]["elapsed"],
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


@app.get("/standings/{competition_code}")
async def get_standings(competition_code: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{FOOTBALLDATA_BASE}/competitions/{competition_code}/standings",
            headers=FOOTBALLDATA_HEADERS,
        )

    data = response.json()

    try:
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

        return {
            "standings": result,
            "competition": data["competition"]["name"],
            "season": data["season"]["startDate"][:4],
        }

    except Exception as e:
        return {"standings": [], "error": str(e)}


@app.get("/scorers/{competition_code}")
async def get_top_scorers(competition_code: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{FOOTBALLDATA_BASE}/competitions/{competition_code}/scorers",
            headers=FOOTBALLDATA_HEADERS,
        )

    data = response.json()

    try:
        scorers = []

        for scorer in data.get("scorers", []):
            scorers.append({
                "name": scorer["player"]["name"],
                "nationality": scorer["player"]["nationality"],
                "team": scorer["team"]["name"],
                "team_logo": scorer["team"]["crest"],
                "goals": scorer.get("goals", 0),
                "assists": scorer.get("assists", 0),
                "penalties": scorer.get("penalties", 0),
            })

        return {"scorers": scorers}

    except Exception as e:
        return {"scorers": [], "error": str(e)}


@app.get("/team/{team_name}")
async def search_team(team_name: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SPORTSDB_BASE}/searchteams.php",
            params={"t": team_name}
        )

    data = response.json()

    try:
        teams = data.get("teams", []) or []

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
                "stadium_image": team.get("strStadiumThumb"),
                "description": team.get("strDescriptionEN", "")[:300] if team.get("strDescriptionEN") else "",
                "website": team.get("strWebsite"),
            })

        return {"teams": result}

    except Exception as e:
        return {"teams": [], "error": str(e)}


@app.get("/player/{player_name}")
async def search_player(player_name: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SPORTSDB_BASE}/searchplayers.php",
            params={"p": player_name}
        )

    data = response.json()

    try:
        players = data.get("player", []) or []

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
                "description": player.get("strDescriptionEN", "")[:300] if player.get("strDescriptionEN") else "",
                "instagram": player.get("strInstagram"),
            })

        return {"players": result}

    except Exception as e:
        return {"players": [], "error": str(e)}


@app.get("/transfers/{team_name}")
async def get_transfers(team_name: str):
    async with httpx.AsyncClient() as client:
        team_response = await client.get(
            f"{SPORTSDB_BASE}/searchteams.php",
            params={"t": team_name}
        )

    team_data = team_response.json()

    try:
        team = team_data["teams"][0]
        team_id = team["idTeam"]

        async with httpx.AsyncClient() as client:
            transfers_response = await client.get(
                f"{SPORTSDB_BASE}/lookup_transfers.php",
                params={"id": team_id}
            )

        transfers_data = transfers_response.json()
        transfers = transfers_data.get("transfers", []) or []

        result = []

        for t in transfers[:10]:
            result.append({
                "player": t.get("strPlayer"),
                "from_team": t.get("strFromTeam"),
                "to_team": t.get("strToTeam"),
                "season": t.get("strSeason"),
                "transfer_type": t.get("strTransferType"),
            })

        return {
            "transfers": result,
            "team": team.get("strTeam"),
            "logo": team.get("strTeamBadge")
        }

    except Exception as e:
        return {"transfers": [], "error": str(e)}


@app.post("/predict")
def predict_match(data: MatchRequest):
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional football analyst who gives exciting, concise match predictions."
                },
                {
                    "role": "user",
                    "content": f"""
Predict the football match between {data.team1} and {data.team2}.

Include:
- Likely winner with confidence percentage
- Predicted score
- Key players to watch
- Tactical insight
- Brief match analysis

Keep it concise and exciting.
"""
                }
            ],
            model="llama-3.3-70b-versatile",
        )

        return {
            "prediction": chat_completion.choices[0].message.content
        }

    except Exception as e:
        return {
            "prediction": f"Error generating prediction: {str(e)}"
        }
