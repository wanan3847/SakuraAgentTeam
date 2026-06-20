import { useState, useMemo } from 'react'
import { Copy, Check, FileCode, Download } from 'lucide-react'

interface CodeBlockProps {
  code: string
  language?: string
  filename?: string
  showLineNumbers?: boolean
  maxHeight?: string
}

// 极简语言检测 - 通过文件扩展名或 language 字段
function detectLanguage(language?: string, filename?: string): string {
  const fromName = (filename || '').split('.').pop()?.toLowerCase() || ''
  const lang = (language || fromName).toLowerCase()
  if (['ts', 'tsx'].includes(lang)) return 'tsx'
  if (['js', 'jsx'].includes(lang)) return 'jsx'
  if (['py', 'python'].includes(lang)) return 'python'
  if (['md', 'markdown'].includes(lang)) return 'markdown'
  if (['json'].includes(lang)) return 'json'
  if (['yml', 'yaml'].includes(lang)) return 'yaml'
  if (['html'].includes(lang)) return 'html'
  if (['css', 'scss'].includes(lang)) return 'css'
  if (['sh', 'bash', 'shell'].includes(lang)) return 'bash'
  if (['dockerfile'].includes(lang)) return 'dockerfile'
  if (['sql'].includes(lang)) return 'sql'
  if (['env'].includes(lang)) return 'plaintext'
  return 'plaintext'
}

// 极简语法高亮 - 基于正则的轻量 token 高亮
// 不用 prism / shiki，避免引入大依赖
function tokenize(code: string, language: string): Array<{ type: string; text: string }> {
  const lines: Array<{ type: string; text: string }> = []

  if (language === 'python' || language === 'python3') {
    // Python: comments, strings, keywords, numbers
    return tokenizeGeneric(code, [
      { type: 'comment', pattern: /#.*$/gm },
      { type: 'string', pattern: /"""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g },
      {
        type: 'keyword',
        pattern:
          /\b(def|class|import|from|as|return|if|elif|else|for|while|try|except|finally|with|lambda|pass|break|continue|in|is|not|and|or|None|True|False|async|await|raise|yield|self)\b/g,
      },
      { type: 'number', pattern: /\b\d+\.?\d*\b/g },
      { type: 'function', pattern: /\b([a-z_][a-z0-9_]*)\s*\(/g },
    ])
  }

  if (language === 'tsx' || language === 'jsx' || language === 'typescript' || language === 'javascript') {
    return tokenizeGeneric(code, [
      { type: 'comment', pattern: /\/\/.*$|\/\*[\s\S]*?\*\//gm },
      { type: 'string', pattern: /`(?:[^`\\]|\\.)*`|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g },
      {
        type: 'keyword',
        pattern:
          /\b(const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|class|extends|new|this|super|import|export|from|as|default|async|await|try|catch|finally|throw|typeof|instanceof|in|of|null|undefined|true|false|interface|type|enum|public|private|protected|static|readonly)\b/g,
      },
      { type: 'number', pattern: /\b\d+\.?\d*\b/g },
      { type: 'function', pattern: /\b([a-zA-Z_$][\w$]*)\s*\(/g },
    ])
  }

  if (language === 'json') {
    return tokenizeGeneric(code, [
      { type: 'string', pattern: /"(?:[^"\\]|\\.)*"(?=\s*:)/g },
      { type: 'string', pattern: /"(?:[^"\\]|\\.)*"/g },
      { type: 'number', pattern: /-?\b\d+\.?\d*([eE][+-]?\d+)?\b/g },
      { type: 'keyword', pattern: /\b(true|false|null)\b/g },
    ])
  }

  if (language === 'yaml' || language === 'yml') {
    return tokenizeGeneric(code, [
      { type: 'comment', pattern: /#.*$/gm },
      { type: 'keyword', pattern: /^[a-zA-Z_][\w-]*:/gm },
      { type: 'string', pattern: /"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g },
    ])
  }

  if (language === 'bash' || language === 'sh' || language === 'shell') {
    return tokenizeGeneric(code, [
      { type: 'comment', pattern: /#.*$/gm },
      { type: 'string', pattern: /"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g },
      { type: 'keyword', pattern: /\b(if|then|else|elif|fi|for|in|do|done|while|case|esac|function|return|export|source|cd|echo|export)\b/g },
    ])
  }

  if (language === 'dockerfile') {
    return tokenizeGeneric(code, [
      { type: 'comment', pattern: /#.*$/gm },
      { type: 'keyword', pattern: /^(FROM|RUN|COPY|ADD|ENV|EXPOSE|CMD|ENTRYPOINT|WORKDIR|USER|VOLUME|ARG|LABEL)\b/gm },
      { type: 'string', pattern: /"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g },
    ])
  }

  if (language === 'markdown' || language === 'md') {
    return tokenizeGeneric(code, [
      { type: 'keyword', pattern: /^#{1,6}\s+.*$/gm },
      { type: 'string', pattern: /`[^`]+`/g },
    ])
  }

  // default: just code
  return [{ type: 'plain', text: code }]
}

function tokenizeGeneric(
  code: string,
  rules: Array<{ type: string; pattern: RegExp }>
): Array<{ type: string; text: string }> {
  // Find all matches with positions
  type Match = { start: number; end: number; type: string; text: string }
  const matches: Match[] = []

  for (const rule of rules) {
    rule.pattern.lastIndex = 0
    let m: RegExpExecArray | null
    while ((m = rule.pattern.exec(code)) !== null) {
      matches.push({
        start: m.index,
        end: m.index + m[0].length,
        type: rule.type,
        text: m[0],
      })
      if (m.index === rule.pattern.lastIndex) rule.pattern.lastIndex++
    }
  }

  // Sort by start position; when tied, longer match wins
  matches.sort((a, b) => a.start - b.start || b.end - a.end)

  // Remove overlapping (first one wins)
  const filtered: Match[] = []
  let lastEnd = 0
  for (const m of matches) {
    if (m.start >= lastEnd) {
      filtered.push(m)
      lastEnd = m.end
    }
  }

  // Build tokens
  const tokens: Array<{ type: string; text: string }> = []
  let cursor = 0
  for (const m of filtered) {
    if (m.start > cursor) {
      tokens.push({ type: 'plain', text: code.slice(cursor, m.start) })
    }
    tokens.push({ type: m.type, text: m.text })
    cursor = m.end
  }
  if (cursor < code.length) {
    tokens.push({ type: 'plain', text: code.slice(cursor) })
  }
  return tokens
}

// 把 token 流按行切分，方便加行号
function tokensToLines(tokens: Array<{ type: string; text: string }>): Array<Array<{ type: string; text: string }>> {
  const allText = tokens.map((t) => t.text).join('')
  const rawLines = allText.split('\n')

  // Walk tokens and split each token's text by newline boundaries
  const result: Array<Array<{ type: string; text: string }>> = []
  let pos = 0
  for (const rawLine of rawLines) {
    const lineTokens: Array<{ type: string; text: string }> = []
    let cursor = 0
    const target = pos + rawLine.length
    while (cursor < tokens.length) {
      const tk = tokens[cursor]
      const tkStart = pos
      const tkEnd = pos + tk.text.length
      if (tkEnd <= target) {
        lineTokens.push(tk)
        pos = tkEnd
        cursor++
      } else {
        // split token
        const cut = target - tkStart
        if (cut > 0) {
          lineTokens.push({ type: tk.type, text: tk.text.slice(0, cut) })
          tokens[cursor] = { type: tk.type, text: tk.text.slice(cut) }
          pos = target
        }
        break
      }
    }
    result.push(lineTokens)
  }
  return result
}

const TYPE_CLASS: Record<string, string> = {
  comment: 'text-slate-500 italic',
  string: 'text-emerald-300',
  keyword: 'text-purple-400 font-semibold',
  number: 'text-amber-300',
  function: 'text-sky-300',
  plain: 'text-slate-100',
}

export default function CodeBlock({
  code,
  language,
  filename,
  showLineNumbers = true,
  maxHeight = '500px',
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false)

  const lang = useMemo(() => detectLanguage(language, filename), [language, filename])
  const lines = useMemo(() => tokensToLines(tokenize(code, lang)), [code, lang])

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // ignore
    }
  }

  const onDownload = () => {
    const blob = new Blob([code], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || 'artifact.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 overflow-hidden">
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-800 border-b border-slate-700">
        <div className="flex items-center gap-2 min-w-0">
          <FileCode className="w-4 h-4 text-slate-400 flex-shrink-0" />
          <span className="text-xs font-mono text-slate-300 truncate">
            {filename || 'artifact'}
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-400 font-mono">
            {lang}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onCopy}
            className="flex items-center gap-1 px-2 py-1 text-xs text-slate-300 hover:text-white hover:bg-slate-700 rounded"
            title="Copy code"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
          {filename && (
            <button
              onClick={onDownload}
              className="flex items-center gap-1 px-2 py-1 text-xs text-slate-300 hover:text-white hover:bg-slate-700 rounded"
              title="Download file"
            >
              <Download className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Code body */}
      <div
        className="overflow-auto font-mono text-sm leading-relaxed"
        style={{ maxHeight }}
      >
        <table className="w-full border-collapse">
          <tbody>
            {lines.map((line, idx) => (
              <tr key={idx} className="hover:bg-slate-800/50">
                {showLineNumbers && (
                  <td className="select-none text-right pr-3 pl-3 text-slate-500 text-xs w-12 align-top border-r border-slate-800">
                    {idx + 1}
                  </td>
                )}
                <td className="pl-3 pr-4 align-top whitespace-pre">
                  {line.length === 0 ? (
                    <span>&nbsp;</span>
                  ) : (
                    line.map((tok, i) => (
                      <span key={i} className={TYPE_CLASS[tok.type] || TYPE_CLASS.plain}>
                        {tok.text}
                      </span>
                    ))
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
