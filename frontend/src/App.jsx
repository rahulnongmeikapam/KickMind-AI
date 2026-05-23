import { useState, useEffect } from "react"

const API_BASE = "https://kickmind-ai-4opi.onrender.com"

const LEAGUES = [
  { code: "PL", name: "Premier League", country: "🏴" },
  { code: "PD", name: "La Liga", country: "🇪🇸" },
  { code: "SA", name: "Serie A", country: "🇮🇹" },
  { code: "BL1", name: "Bundesliga", country: "🇩🇪" },
  { code: "FL1", name: "Ligue 1", country: "🇫🇷" },
  { code: "CL", name: "Champions League", country: "🇪🇺" },
]

const FORM_COLORS = {
  W: "bg-green-500",
  D: "bg-yellow-500",
  L: "bg-red-500",
}

export default function App() {
  const [activeTab, setActiveTab] = useState("live")
  const [selectedLeague, setSelectedLeague] = useState("PL")

  const [liveMatches, setLiveMatches] = useState([])
  const [fixtures, setFixtures] = useState([])
  const [standings, setStandings] = useState([])
  const [scorers, setScorers] = useState([])

  const [searchQuery, setSearchQuery] = useState("")
  const [searchType, setSearchType] = useState("team")
  const [searchResults, setSearchResults] = useState(null)

  const [team1, setTeam1] = useState("")
  const [team2, setTeam2] = useState("")
  const [prediction, setPrediction] = useState("")

  const [loading, setLoading] = useState(false)
  const [dataLoading, setDataLoading] = useState(false)
  const [lastUpdated, setLastUpdated] = useState("")
  // FIX: track backend wake-up state for Render free tier cold starts
  const [backendWaking, setBackendWaking] = useState(false)

  const now = () =>
    new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })

  // FIX: wake backend on mount before any real fetch
  useEffect(() => {
    wakeBackend()
  }, [])

  useEffect(() => {
    fetchLive()
    const interval = setInterval(fetchLive, 30000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    fetchFixtures()
  }, [])

  useEffect(() => {
    if (activeTab === "standings") fetchStandings(selectedLeague)
    if (activeTab === "scorers") fetchScorers(selectedLeague)
  }, [activeTab, selectedLeague])

  // ================= FETCH FUNCTIONS

  // FIX: ping backend root to wake Render dyno before data fetches
  const wakeBackend = async () => {
    try {
      setBackendWaking(true)
      await fetch(`${API_BASE}/`, { signal: AbortSignal.timeout(60000) })
    } catch (e) {
      console.warn("Backend wake ping failed:", e.message)
    } finally {
      setBackendWaking(false)
    }
  }

  const fetchLive = async () => {
    try {
      const res = await fetch(`${API_BASE}/live`, {
        signal: AbortSignal.timeout(30000),
      })
      const data = await res.json()
      setLiveMatches(data.matches || [])
      setLastUpdated(now())
    } catch (e) {
      console.error("LIVE API ERROR:", e.message)
    }
  }

  const fetchFixtures = async () => {
    setDataLoading(true)
    try {
      const res = await fetch(`${API_BASE}/fixtures/today`, {
        signal: AbortSignal.timeout(30000),
      })
      const data = await res.json()
      setFixtures(data.fixtures || [])
    } catch (e) {
      console.error("FIXTURES ERROR:", e.message)
    } finally {
      setDataLoading(false)
    }
  }

  const fetchStandings = async (code) => {
    setDataLoading(true)
    setStandings([])
    try {
      const res = await fetch(`${API_BASE}/standings/${code}`, {
        signal: AbortSignal.timeout(30000),
      })
      const data = await res.json()
      setStandings(data.standings || [])
    } catch (e) {
      console.error("STANDINGS ERROR:", e.message)
    } finally {
      setDataLoading(false)
    }
  }

  const fetchScorers = async (code) => {
    setDataLoading(true)
    setScorers([])
    try {
      const res = await fetch(`${API_BASE}/scorers/${code}`, {
        signal: AbortSignal.timeout(30000),
      })
      const data = await res.json()
      setScorers(data.scorers || [])
    } catch (e) {
      console.error("SCORERS ERROR:", e.message)
    } finally {
      setDataLoading(false)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setDataLoading(true)
    setSearchResults(null)
    try {
      const endpoint =
        searchType === "team"
          ? `${API_BASE}/team/${encodeURIComponent(searchQuery)}`
          : `${API_BASE}/player/${encodeURIComponent(searchQuery)}`
      const res = await fetch(endpoint, { signal: AbortSignal.timeout(30000) })
      const data = await res.json()
      setSearchResults(data)
    } catch (e) {
      console.error("SEARCH ERROR:", e.message)
    } finally {
      setDataLoading(false)
    }
  }

  const generatePrediction = async () => {
    if (!team1 || !team2) {
      setPrediction("Please enter both team names.")
      return
    }
    setLoading(true)
    setPrediction("")
    try {
      const res = await fetch(`${API_BASE}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ team1, team2 }),
        signal: AbortSignal.timeout(30000),
      })
      const data = await res.json()
      setPrediction(data.prediction || "No prediction returned.")
    } catch (e) {
      setPrediction("Backend not reachable. It may still be waking up — try again in 30 seconds.")
    } finally {
      setLoading(false)
    }
  }

  const formatTime = (dateStr) => {
    if (!dateStr) return ""
    return new Date(dateStr).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  const Spinner = () => (
    <div className="flex justify-center py-20">
      <div className="w-12 h-12 border-4 border-gray-700 border-t-green-400 rounded-full animate-spin"></div>
    </div>
  )

  const EmptyState = ({ message }) => (
    <div className="bg-gray-900 border border-gray-800 rounded-3xl p-12 text-center">
      <p className="text-gray-400 text-xl">{message}</p>
    </div>
  )

  // FIX: league selector shown on relevant tabs
  const LeagueSelector = () => (
    <div className="flex flex-wrap gap-2 mb-6">
      {LEAGUES.map((l) => (
        <button
          key={l.code}
          onClick={() => setSelectedLeague(l.code)}
          className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
            selectedLeague === l.code
              ? "bg-green-500 text-black"
              : "bg-gray-800 text-gray-300 hover:bg-gray-700"
          }`}
        >
          {l.country} {l.name}
        </button>
      ))}
    </div>
  )

  // FIX: tab definitions with proper labels matching original design
  const tabs = [
    { id: "live", icon: "🔴", label: "Live" },
    { id: "fixtures", icon: "📅", label: "Fixtures" },
    { id: "standings", icon: "🏆", label: "Standings" },
    { id: "scorers", icon: "⚽", label: "Top Scorers" },
    { id: "search", icon: "🔍", label: "Search" },
    { id: "predict", icon: "🤖", label: "AI Predict" },
  ]

  return (
    <div className="min-h-screen bg-black text-white">

      {/* NAVBAR */}
      <nav className="sticky top-0 z-50 flex items-center justify-between px-8 py-4 border-b border-gray-800 bg-black/90 backdrop-blur">
        <h1 className="text-2xl font-bold text-green-400">KickMind AI ⚽</h1>
        <div className="text-sm text-gray-400">
          {backendWaking
            ? "⏳ Waking backend..."
            : lastUpdated
            ? `Updated ${lastUpdated}`
            : ""}
        </div>
        <button
          onClick={fetchLive}
          className="px-4 py-2 border border-green-500 text-green-400 rounded-lg text-sm hover:bg-green-500 hover:text-black transition-all"
        >
          Refresh
        </button>
      </nav>

      {/* HERO */}
      <div className="text-center py-16 px-4">
        <p className="text-green-400 text-sm font-semibold tracking-widest uppercase mb-4">
          Real-Time AI Football Intelligence
        </p>
        <h2 className="text-5xl font-extrabold mb-4">
          Your Ultimate Football <span className="text-green-400">Hub</span>
        </h2>
        <p className="text-gray-400 max-w-xl mx-auto">
          Live scores, fixtures, standings, top scorers, player &amp; team search — all powered by real data and AI.
        </p>
      </div>

      {/* FIX: TAB BAR — actually rendered so users can switch tabs */}
      <div className="sticky top-[72px] z-40 bg-black/90 backdrop-blur border-b border-gray-800 px-6">
        <div className="max-w-7xl mx-auto flex gap-1 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-5 py-3 text-sm font-medium whitespace-nowrap transition-all border-b-2 ${
                activeTab === tab.id
                  ? "border-green-400 text-green-400"
                  : "border-transparent text-gray-400 hover:text-white"
              }`}
            >
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* CONTENT */}
      <div className="px-6 py-10 max-w-7xl mx-auto">

        {/* LIVE */}
        {activeTab === "live" && (
          <div>
            <h2 className="text-3xl font-bold mb-2">Live Matches</h2>
            <p className="text-gray-500 text-sm mb-6">Auto-refreshes every 30 seconds</p>
            {liveMatches.length === 0 ? (
              <EmptyState message="No live matches right now. Check back during match hours!" />
            ) : (
              <div className="grid md:grid-cols-2 gap-4">
                {liveMatches.map((m) => (
                  <div key={m.id} className="bg-gray-900 p-5 rounded-2xl border border-gray-800">
                    <div className="flex justify-between items-center mb-3">
                      <span className="text-green-400 font-bold text-sm">
                        🔴 {m.minute}'
                      </span>
                      <span className="text-gray-400 text-xs">{m.league} · {m.country}</span>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-2 flex-1">
                        {m.home_logo && (
                          <img src={m.home_logo} alt="" className="w-8 h-8 object-contain" />
                        )}
                        <span className="font-semibold text-sm">{m.home_team}</span>
                      </div>
                      <div className="text-2xl font-extrabold text-green-400 px-4">
                        {m.home_score ?? 0} - {m.away_score ?? 0}
                      </div>
                      <div className="flex items-center gap-2 flex-1 justify-end">
                        <span className="font-semibold text-sm text-right">{m.away_team}</span>
                        {m.away_logo && (
                          <img src={m.away_logo} alt="" className="w-8 h-8 object-contain" />
                        )}
                      </div>
                    </div>
                    <div className="mt-2 text-center text-xs text-gray-500">{m.status}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* FIXTURES */}
        {activeTab === "fixtures" && (
          <div>
            <h2 className="text-3xl font-bold mb-6">Today's Fixtures</h2>
            {dataLoading ? (
              <Spinner />
            ) : fixtures.length === 0 ? (
              <EmptyState message="No fixtures found for today." />
            ) : (
              <div className="grid md:grid-cols-2 gap-4">
                {fixtures.map((m) => (
                  <div key={m.id} className="bg-gray-900 p-5 rounded-2xl border border-gray-800">
                    <div className="flex justify-between items-center mb-3">
                      <span className="text-gray-400 text-xs">{formatTime(m.time)}</span>
                      <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                        m.status === "FT" ? "bg-gray-700 text-gray-300" :
                        ["1H","2H","HT"].includes(m.status) ? "bg-green-900 text-green-400" :
                        "bg-gray-800 text-gray-400"
                      }`}>
                        {m.status === "NS" ? "Upcoming" : m.status}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-2 flex-1">
                        {m.home_logo && (
                          <img src={m.home_logo} alt="" className="w-8 h-8 object-contain" />
                        )}
                        <span className="font-semibold text-sm">{m.home_team}</span>
                      </div>
                      <div className="text-xl font-extrabold text-white px-4">
                        {m.home_score !== null ? `${m.home_score} - ${m.away_score}` : "vs"}
                      </div>
                      <div className="flex items-center gap-2 flex-1 justify-end">
                        <span className="font-semibold text-sm text-right">{m.away_team}</span>
                        {m.away_logo && (
                          <img src={m.away_logo} alt="" className="w-8 h-8 object-contain" />
                        )}
                      </div>
                    </div>
                    <div className="mt-2 text-center text-xs text-gray-500">{m.league} · {m.country}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* STANDINGS */}
        {activeTab === "standings" && (
          <div>
            <h2 className="text-3xl font-bold mb-6">Standings</h2>
            <LeagueSelector />
            {dataLoading ? (
              <Spinner />
            ) : standings.length === 0 ? (
              <EmptyState message="No standings data available." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-400 border-b border-gray-800">
                      <th className="text-left py-3 px-2">#</th>
                      <th className="text-left py-3 px-2">Team</th>
                      <th className="py-3 px-2">P</th>
                      <th className="py-3 px-2">W</th>
                      <th className="py-3 px-2">D</th>
                      <th className="py-3 px-2">L</th>
                      <th className="py-3 px-2">GD</th>
                      <th className="py-3 px-2 text-green-400">Pts</th>
                      <th className="py-3 px-2">Form</th>
                    </tr>
                  </thead>
                  <tbody>
                    {standings.map((team) => (
                      <tr key={team.rank} className="border-b border-gray-800 hover:bg-gray-900 transition-colors">
                        <td className="py-3 px-2 text-gray-400">{team.rank}</td>
                        <td className="py-3 px-2">
                          <div className="flex items-center gap-2">
                            {team.logo && (
                              <img src={team.logo} alt="" className="w-6 h-6 object-contain" />
                            )}
                            <span className="font-medium">{team.team}</span>
                          </div>
                        </td>
                        <td className="py-3 px-2 text-center text-gray-300">{team.played}</td>
                        <td className="py-3 px-2 text-center text-green-400">{team.won}</td>
                        <td className="py-3 px-2 text-center text-yellow-400">{team.drawn}</td>
                        <td className="py-3 px-2 text-center text-red-400">{team.lost}</td>
                        <td className="py-3 px-2 text-center text-gray-300">
                          {team.goal_difference > 0 ? `+${team.goal_difference}` : team.goal_difference}
                        </td>
                        <td className="py-3 px-2 text-center font-bold text-green-400">{team.points}</td>
                        <td className="py-3 px-2">
                          <div className="flex gap-1">
                            {team.form?.split("").map((r, i) => (
                              <span key={i} className={`w-5 h-5 rounded-full text-xs flex items-center justify-center font-bold text-black ${FORM_COLORS[r] || "bg-gray-700 text-white"}`}>
                                {r}
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* SCORERS */}
        {activeTab === "scorers" && (
          <div>
            <h2 className="text-3xl font-bold mb-6">Top Scorers</h2>
            <LeagueSelector />
            {dataLoading ? (
              <Spinner />
            ) : scorers.length === 0 ? (
              <EmptyState message="No scorers data available." />
            ) : (
              <div className="space-y-3">
                {scorers.map((s, i) => (
                  <div key={i} className="bg-gray-900 p-4 rounded-2xl border border-gray-800 flex items-center gap-4">
                    <span className="text-2xl font-extrabold text-gray-700 w-8 text-center">{i + 1}</span>
                    {s.team_logo && (
                      <img src={s.team_logo} alt="" className="w-10 h-10 object-contain" />
                    )}
                    <div className="flex-1">
                      <p className="font-bold">{s.name}</p>
                      <p className="text-gray-400 text-sm">{s.team} · {s.nationality}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-2xl font-extrabold text-green-400">{s.goals}</p>
                      <p className="text-xs text-gray-500">{s.assists} assists</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* SEARCH */}
        {activeTab === "search" && (
          <div>
            <h2 className="text-3xl font-bold mb-6">Search</h2>
            <div className="flex gap-3 mb-6 flex-wrap">
              <div className="flex rounded-xl overflow-hidden border border-gray-700">
                <button
                  onClick={() => setSearchType("team")}
                  className={`px-5 py-2 text-sm font-medium transition-all ${searchType === "team" ? "bg-green-500 text-black" : "bg-gray-900 text-gray-300"}`}
                >
                  Team
                </button>
                <button
                  onClick={() => setSearchType("player")}
                  className={`px-5 py-2 text-sm font-medium transition-all ${searchType === "player" ? "bg-green-500 text-black" : "bg-gray-900 text-gray-300"}`}
                >
                  Player
                </button>
              </div>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder={`Search for a ${searchType}...`}
                className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-2 text-white placeholder-gray-500 outline-none focus:border-green-500 min-w-[200px]"
              />
              <button
                onClick={handleSearch}
                className="px-6 py-2 bg-green-500 text-black font-bold rounded-xl hover:bg-green-400 transition-all"
              >
                Search
              </button>
            </div>
            {dataLoading && <Spinner />}
            {searchResults && (
              <div className="space-y-4">
                {searchType === "team" && (searchResults.teams || []).map((t, i) => (
                  <div key={i} className="bg-gray-900 p-5 rounded-2xl border border-gray-800 flex gap-4 items-start">
                    {t.logo && <img src={t.logo} alt="" className="w-16 h-16 object-contain" />}
                    <div>
                      <p className="text-xl font-bold">{t.name}</p>
                      <p className="text-gray-400 text-sm">{t.league} · {t.country} · Founded {t.founded}</p>
                      <p className="text-gray-400 text-sm mt-1">🏟 {t.stadium}</p>
                      {t.description && <p className="text-gray-500 text-sm mt-2">{t.description}</p>}
                    </div>
                  </div>
                ))}
                {searchType === "player" && (searchResults.players || []).map((p, i) => (
                  <div key={i} className="bg-gray-900 p-5 rounded-2xl border border-gray-800 flex gap-4 items-start">
                    {p.photo && <img src={p.photo} alt="" className="w-16 h-16 object-contain rounded-full" />}
                    <div>
                      <p className="text-xl font-bold">{p.name}</p>
                      <p className="text-gray-400 text-sm">{p.team} · {p.position} · {p.nationality}</p>
                      <p className="text-gray-500 text-sm mt-1">Born: {p.date_of_birth} · {p.height} · {p.weight}</p>
                      {p.description && <p className="text-gray-500 text-sm mt-2">{p.description}</p>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* AI PREDICT */}
        {activeTab === "predict" && (
          <div>
            <h2 className="text-3xl font-bold mb-2">AI Match Prediction</h2>
            <p className="text-gray-400 mb-6">Enter two team names and let AI predict the outcome.</p>
            <div className="flex gap-3 flex-wrap mb-4">
              <input
                type="text"
                value={team1}
                onChange={(e) => setTeam1(e.target.value)}
                placeholder="Home team (e.g. Arsenal)"
                className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 outline-none focus:border-green-500 min-w-[180px]"
              />
              <span className="flex items-center font-bold text-gray-400">vs</span>
              <input
                type="text"
                value={team2}
                onChange={(e) => setTeam2(e.target.value)}
                placeholder="Away team (e.g. Chelsea)"
                className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 outline-none focus:border-green-500 min-w-[180px]"
              />
              <button
                onClick={generatePrediction}
                disabled={loading}
                className="px-6 py-3 bg-green-500 text-black font-bold rounded-xl hover:bg-green-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Predicting..." : "🤖 Predict"}
              </button>
            </div>
            {loading && <Spinner />}
            {prediction && (
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 mt-4 whitespace-pre-wrap text-gray-200 leading-relaxed">
                {prediction}
              </div>
            )}
          </div>
        )}

      </div>

      {/* FOOTER */}
      <footer className="border-t border-gray-800 mt-16 py-8 text-center">
        <p className="text-gray-500 text-sm">
          Designed by{" "}
          <span className="text-green-400 font-semibold">Rahul Nongmeikapam</span>
        </p>
        <p className="text-gray-700 text-xs mt-1">
          KickMind AI · Real-Time Football Intelligence
        </p>
      </footer>

    </div>
  )
}
