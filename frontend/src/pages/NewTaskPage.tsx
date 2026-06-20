import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Sparkles, Send, Loader } from 'lucide-react'

const EXAMPLE_PROMPTS = [
  '帮我做一个 Todo 待办事项应用，支持添加、删除、标记完成',
  '创建一个博客系统，支持文章发布、评论和标签分类',
  '开发一个用户管理系统，包含注册、登录、角色和权限管理',
  '做一个项目任务管理看板，支持任务拖拽、状态流转',
]

export default function NewTaskPage() {
  const navigate = useNavigate()
  const [requirement, setRequirement] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!requirement.trim()) {
      setError('请描述你的需求')
      return
    }

    setSubmitting(true)
    setError('')

    try {
      const res = await fetch('/api/v1/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ requirement: requirement.trim() }),
      })

      if (!res.ok) {
        throw new Error('创建任务失败')
      }

      const data = await res.json()
      navigate(`/session?id=${data.data.id}`)
    } catch (e) {
      console.error(e)
      setError('创建任务失败，请检查后端服务是否正常运行')
    } finally {
      setSubmitting(false)
    }
  }

  function useExample(prompt: string) {
    setRequirement(prompt)
  }

  return (
    <div className="max-w-4xl mx-auto py-10 px-6">
      <Link to="/" className="text-sm text-blue-600 hover:text-blue-700 inline-block mb-6">
        ← 返回首页
      </Link>

      <div className="text-center mb-10">
        <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg">
          <Sparkles className="w-8 h-8 text-white" />
        </div>
        <h1 className="text-3xl font-bold text-gray-800 dark:text-white mb-2">创建新任务</h1>
        <p className="text-gray-500 dark:text-gray-400">
          用自然语言描述你想要的应用，多个 Agent 将协同为你生成完整的代码
        </p>
      </div>

      {/* Requirement input */}
      <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 shadow-sm mb-6">
        <label htmlFor="requirement" className="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">
          需求描述
        </label>
        <textarea
          id="requirement"
          rows={6}
          value={requirement}
          onChange={(e) => setRequirement(e.target.value)}
          placeholder="例如：帮我做一个 Todo 待办事项应用，支持添加、删除、标记完成..."
          className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-800 dark:text-gray-100 bg-white dark:bg-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
        />

        {error && (
          <div className="mt-3 text-sm text-red-600 bg-red-50 dark:bg-red-900/20 p-3 rounded-lg border border-red-100 dark:border-red-800">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3 mt-6">
          <button
            type="submit"
            disabled={submitting || !requirement.trim()}
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-3 rounded-lg shadow disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? (
              <>
                <Loader className="w-4 h-4 animate-spin" />
                正在创建...
              </>
            ) : (
              <>
                <Send className="w-4 h-4" />
                开始执行
              </>
            )}
          </button>
        </div>
      </form>

      {/* Example prompts */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-4">示例需求</h3>
        <div className="space-y-2">
          {EXAMPLE_PROMPTS.map((prompt, idx) => (
            <button
              key={idx}
              onClick={() => useExample(prompt)}
              className="block w-full text-left p-4 text-sm text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-700 transition-all"
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>

      {/* Tips */}
      <div className="mt-8 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-6">
        <h3 className="text-sm font-semibold text-blue-800 dark:text-blue-200 mb-3">💡 提示</h3>
        <ul className="text-sm text-blue-700 dark:text-blue-300 space-y-1">
          <li>• 尽量清晰地描述你的需求，包括功能、交互、数据等</li>
          <li>• 系统会自动分析并生成架构设计、前端、后端代码</li>
          <li>• 生成的代码会保留版本记录，可以随时回溯</li>
          <li>• 遇到错误会自动积累经验，下次同类问题更快解决</li>
        </ul>
      </div>
    </div>
  )
}
