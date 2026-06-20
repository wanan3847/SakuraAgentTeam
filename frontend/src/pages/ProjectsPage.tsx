import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  listProjects,
  createProject,
  getProjectCommits,
  rollbackProject,
  type ProjectCommit,
} from '../services/api'

export default function ProjectsPage() {
  const [projects, setProjects] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [commits, setCommits] = useState<ProjectCommit[]>([])

  const load = async () => {
    setLoading(true)
    try {
      const res = await listProjects()
      setProjects(res.data || [])
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    if (!selected) {
      setCommits([])
      return
    }
    getProjectCommits(selected, 50)
      .then((r) => setCommits(r.data || []))
      .catch((e) => setError(String(e)))
  }, [selected])

  const onCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newName.trim()) return
    setCreating(true)
    setError(null)
    try {
      const id = newName
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')
      await createProject(id, newName.trim())
      setNewName('')
      await load()
      setSelected(id)
    } catch (e) {
      setError(String(e))
    } finally {
      setCreating(false)
    }
  }

  const onRollback = async (hash: string) => {
    if (!selected) return
    if (!confirm(`Rollback project "${selected}" to commit ${hash.slice(0, 7)}?`)) return
    try {
      await rollbackProject(selected, hash)
      const r = await getProjectCommits(selected, 50)
      setCommits(r.data || [])
    } catch (e) {
      setError(String(e))
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100">
      <header className="border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Projects</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Git-versioned history of every generated project
          </p>
        </div>
        <Link
          to="/"
          className="text-sm text-sky-600 dark:text-sky-400 hover:underline"
        >
          ← Back home
        </Link>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 grid grid-cols-1 md:grid-cols-3 gap-6">
        <section className="md:col-span-1 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
          <h2 className="text-lg font-medium mb-3">All projects</h2>

          <form onSubmit={onCreate} className="mb-4 space-y-2">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Project name"
              className="w-full px-3 py-2 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700"
            />
            <button
              type="submit"
              disabled={creating || !newName.trim()}
              className="w-full bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white rounded px-3 py-2 text-sm"
            >
              {creating ? 'Creating…' : '+ New project'}
            </button>
          </form>

          {error && (
            <div className="mb-3 text-xs text-red-600 dark:text-red-400 break-words">
              {error}
            </div>
          )}

          {loading ? (
            <div className="text-sm text-slate-500">Loading…</div>
          ) : projects.length === 0 ? (
            <div className="text-sm text-slate-500">No projects yet.</div>
          ) : (
            <ul className="space-y-2">
              {projects.map((p) => (
                <li key={p.id}>
                  <button
                    onClick={() => setSelected(p.id)}
                    className={`w-full text-left px-3 py-2 rounded border ${
                      selected === p.id
                        ? 'border-sky-500 bg-sky-50 dark:bg-sky-900/20'
                        : 'border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/50'
                    }`}
                  >
                    <div className="font-medium text-sm">{p.id}</div>
                    <div className="text-xs text-slate-500 truncate">
                      {p.last_commit || '—'}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="md:col-span-2 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
          <h2 className="text-lg font-medium mb-3">
            {selected ? `History · ${selected}` : 'Select a project'}
          </h2>

          {selected && commits.length === 0 ? (
            <div className="text-sm text-slate-500">No commits yet.</div>
          ) : null}

          <ol className="space-y-2">
            {commits.map((c) => (
              <li
                key={c.hash}
                className="flex items-start justify-between gap-3 px-3 py-2 rounded border border-slate-200 dark:border-slate-700"
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-mono text-sky-600 dark:text-sky-400">
                    {c.hash.slice(0, 7)}
                  </div>
                  <div className="text-sm">{c.message}</div>
                  <div className="text-xs text-slate-500">
                    {c.author} · {new Date(c.time).toLocaleString()}
                  </div>
                </div>
                <button
                  onClick={() => onRollback(c.hash)}
                  className="text-xs px-2 py-1 rounded border border-slate-300 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700"
                  title="Rollback the project to this commit"
                >
                  Rollback
                </button>
              </li>
            ))}
          </ol>
        </section>
      </main>
    </div>
  )
}
