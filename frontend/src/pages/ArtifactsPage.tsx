import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  listProjectFiles,
  readProjectFile,
  listSessions,
  type ProjectFile,
  type Session,
} from '../services/api'
import { FolderTree, FileText, ChevronRight, Folder, AlertCircle } from 'lucide-react'
import CodeBlock from '../components/CodeBlock'

export default function ArtifactsPage() {
  const { sessionId: urlSessionId } = useParams<{ sessionId: string }>()
  const [sessions, setSessions] = useState<Session[]>([])
  const [selectedSession, setSelectedSession] = useState<string>(urlSessionId || '')
  const [files, setFiles] = useState<ProjectFile[]>([])
  const [selectedFile, setSelectedFile] = useState<string>('')
  const [fileContent, setFileContent] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [fileLoading, setFileLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load sessions list
  useEffect(() => {
    listSessions()
      .then((r) => {
        const arr = (r.data as Session[]) || []
        setSessions(arr)
        if (!selectedSession && arr.length > 0) {
          const first = arr[0]
          setSelectedSession(first.id)
        }
      })
      .catch((e) => setError(String(e)))
  }, [])

  // Load files for selected session
  useEffect(() => {
    if (!selectedSession) {
      setFiles([])
      setSelectedFile('')
      return
    }
    setLoading(true)
    setError(null)
    listProjectFiles(selectedSession, '')
      .then((r) => {
        const arr = (r.data as ProjectFile[]) || []
        setFiles(arr)
        // auto-select: prefer URL ?file=, then first file
        const params = new URLSearchParams(window.location.search)
        const urlFile = params.get('file') || ''
        if (urlFile && arr.some((f) => f.path === urlFile)) {
          setSelectedFile(urlFile)
        } else {
          const firstFile = arr.find((f) => f.type === 'file')
          if (firstFile) setSelectedFile(firstFile.path)
          else setSelectedFile('')
        }
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [selectedSession])

  // Load file content
  useEffect(() => {
    if (!selectedSession || !selectedFile) {
      setFileContent('')
      return
    }
    setFileLoading(true)
    readProjectFile(selectedSession, selectedFile)
      .then((r) => {
        setFileContent(r.data?.content || '')
      })
      .catch((e) => {
        setFileContent('')
        setError(String(e))
      })
      .finally(() => setFileLoading(false))
  }, [selectedSession, selectedFile])

  const dirs = files.filter((f) => f.type === 'directory')
  const regularFiles = files.filter((f) => f.type === 'file')

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100">
      <header className="border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <FolderTree className="w-6 h-6" />
            产物浏览器
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            浏览每个 Session 生成的完整文件树与代码
          </p>
        </div>
        <Link to="/" className="text-sm text-sky-600 dark:text-sky-400 hover:underline">
          ← 返回首页
        </Link>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {error && (
          <div className="mb-4 flex items-start gap-2 p-3 rounded border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 text-sm text-red-700 dark:text-red-300">
            <AlertCircle className="w-4 h-4 mt-0.5" />
            <div className="break-words">{error}</div>
          </div>
        )}

        {/* Session selector */}
        <div className="mb-4 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
          <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">
            选择 Session
          </label>
          <select
            value={selectedSession}
            onChange={(e) => setSelectedSession(e.target.value)}
            className="w-full px-3 py-2 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm"
          >
            <option value="">— 请选择 —</option>
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.id} · {s.status} · {s.requirement.slice(0, 60)}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* File tree */}
          <div className="md:col-span-1 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
            <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3 flex items-center gap-2">
              <FolderTree className="w-4 h-4" />
              文件树
            </h2>

            {!selectedSession ? (
              <div className="text-xs text-slate-500">请先选择一个 Session</div>
            ) : loading ? (
              <div className="text-xs text-slate-500">加载中…</div>
            ) : files.length === 0 ? (
              <div className="text-xs text-slate-500">该 Session 没有文件</div>
            ) : (
              <div className="space-y-1">
                {dirs.map((d) => (
                  <div
                    key={d.path}
                    className="flex items-center gap-1 text-xs text-slate-500 px-2 py-1"
                  >
                    <Folder className="w-3.5 h-3.5" />
                    <span className="font-mono truncate">{d.name}</span>
                  </div>
                ))}
                {regularFiles.map((f) => (
                  <button
                    key={f.path}
                    onClick={() => setSelectedFile(f.path)}
                    className={`w-full text-left flex items-center gap-2 px-2 py-1.5 rounded text-xs ${
                      selectedFile === f.path
                        ? 'bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300'
                        : 'hover:bg-slate-100 dark:hover:bg-slate-700/50 text-slate-700 dark:text-slate-300'
                    }`}
                  >
                    <FileText className="w-3.5 h-3.5 flex-shrink-0" />
                    <span className="font-mono truncate flex-1">{f.name}</span>
                    {selectedFile === f.path && (
                      <ChevronRight className="w-3 h-3 flex-shrink-0" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Code viewer */}
          <div className="md:col-span-3">
            {!selectedFile ? (
              <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-12 text-center text-slate-500">
                <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                从左侧选择一个文件查看内容
              </div>
            ) : fileLoading ? (
              <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-12 text-center text-slate-500">
                加载中…
              </div>
            ) : (
              <CodeBlock code={fileContent} filename={selectedFile} maxHeight="70vh" />
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
