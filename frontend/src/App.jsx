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

  const now = () =>
    new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })

  // ================= LIVE (AUTO REFRESH)
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

  const fetchLive = async () => {
    try {
      const res = await fetch(`${API_BASE}/live`)
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
      const res = await fetch(`${API_BASE}/fixtures/today`)
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
      const res = await fetch(`${API_BASE}/standings/${code}`)
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
      const res = await fetch(`${API_BASE}/scorers/${code}`)
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

      const res = await fetch(endpoint)
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
      })

      const data = await res.json()
      setPrediction(data.prediction || "No prediction returned.")
    } catch (e) {
      setPrediction("Backend not reachable.")
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

  const tabs = [
    { id: "live", label: "🔴 Live" },
    { id: "fixtures", label: "📅 Fixtures" },
    { id: "standings", label: "🏆 Standings" },
    { id: "scorers", label: "⚽ Top Scorers" },
    { id: "search", label: "🔍 Search" },
    { id: "predict", label: "🤖 AI Predict" },
  ]

  return (
    <div className="min-h-screen bg-black text-white">

      <nav className="sticky top-0 z-50 flex items-center justify-between px-8 py-4 border-b border-gray-800 bg-black/90 backdrop-blur">
        <h1 className="text-2xl font-bold text-green-400">KickMind AI ⚽</h1>

        <div className="text-sm text-gray-400">
          Updated {lastUpdated}
        </div>
      </nav>

      <div className="px-6 py-10 max-w-7xl mx-auto">

        {/* LIVE */}
        {activeTab === "live" && (
          <div>
            <h2 className="text-3xl font-bold mb-6">Live Matches</h2>

            {liveMatches.length === 0 ? (
              <EmptyState message="No live matches right now." />
            ) : (
              <div className="grid md:grid-cols-2 gap-4">
                {liveMatches.map((m) => (
                  <div key={m.id} className="bg-gray-900 p-5 rounded-2xl border border-gray-800">
                    <div className="flex justify-between">
                      <span className="text-green-400 font-bold">{m.minute}'</span>
                      <span className="text-gray-400 text-sm">{m.league}</span>
                    </div>
                    <div className="text-center text-2xl font-bold mt-4">
                      {m.home_team} {m.home_score} - {m.away_score} {m.away_team}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
