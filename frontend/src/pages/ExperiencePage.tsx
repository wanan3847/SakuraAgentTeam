import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  listExperiences,
  rateExperience,
  type Experience,
} from '../services/api'

export default function ExperiencePage() {
  const [items, setItems] = useState<Experience[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  const load = async (q?: string) => {
    setLoading(true)
    setError(null)
    try {
      const r = await listExperiences(q, 20)
      setItems(r.data || [])
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const onSearch = (e: React.FormEvent) => {
    e.preventDefault()
    load(search.trim() || undefined)
  }

  const onRate = async (id: string, rating: number) => {
    try {
      await rateExperience(id, rating)
      // optimistic update
      setItems((prev) =>
        prev.map((it) =>
          it.id === id ? { ...it, rating, occurrences: it.occurrences + 1 } : it
        )
      )
    } catch (e) {
      setError(String(e))
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100">
      <header className="border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Experience store</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Accumulated error patterns and solutions, ranked by usefulness
          </p>
        </div>
        <Link
          to="/"
          className="text-sm text-sky-600 dark:text-sky-400 hover:underline"
        >
          ← Back home
        </Link>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8 space-y-4">
        <form onSubmit={onSearch} className="flex gap-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by error message…"
            className="flex-1 px-3 py-2 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700"
          />
          <button
            type="submit"
            className="bg-sky-600 hover:bg-sky-700 text-white rounded px-4 py-2 text-sm"
          >
            Search
          </button>
        </form>

        {error && (
          <div className="text-xs text-red-600 dark:text-red-400 break-words">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-sm text-slate-500">Loading…</div>
        ) : items.length === 0 ? (
          <div className="text-sm text-slate-500">
            No experiences yet. Run a session and rate the outcomes to build
            up knowledge.
          </div>
        ) : (
          <ul className="space-y-3">
            {items.map((it) => (
              <li
                key={it.id}
                className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-mono text-sky-600 dark:text-sky-400">
                        {it.error_type}
                      </span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full ${
                          it.status === 'graduated'
                            ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                            : 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300'
                        }`}
                      >
                        {it.status}
                      </span>
                      <span className="text-[10px] text-slate-500">
                        ×{it.occurrences}
                      </span>
                    </div>
                    <div className="text-sm font-mono break-words">
                      {it.error_message}
                    </div>
                    <div className="text-sm mt-2 text-slate-700 dark:text-slate-300 break-words">
                      <span className="font-medium">Solution:</span> {it.solution}
                    </div>
                  </div>

                  <div className="flex flex-col items-end gap-1">
                    <div className="text-xs text-slate-500">Rate</div>
                    <div className="flex gap-1">
                      {[1, 2, 3, 4, 5].map((n) => (
                        <button
                          key={n}
                          onClick={() => onRate(it.id, n)}
                          className={`w-6 h-6 text-xs rounded ${
                            n <= it.rating
                              ? 'bg-amber-400 text-white'
                              : 'bg-slate-200 dark:bg-slate-700 text-slate-500'
                          }`}
                        >
                          {n}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  )
}
