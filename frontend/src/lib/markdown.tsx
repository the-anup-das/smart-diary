import * as React from "react"

/**
 * A small markdown renderer for chat replies: paragraphs, headings, bullet and numbered
 * lists, bold, italic, inline code and links. Deliberately tiny and dependency-free; the
 * model writes light markdown and this covers it. Date citations like [2026-09-16] are
 * styled as small chips because the answer refers to entries by date.
 */

const INLINE = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\[(\d{4}-\d{2}-\d{2})\]|\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)|(?<![\w*])\*[^*\n]+\*(?![\w*])|(?<!\w)_[^_\n]+_(?!\w))/g

export function renderInline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = []
  let last = 0
  let key = 0
  for (const match of text.matchAll(INLINE)) {
    const index = match.index ?? 0
    if (index > last) nodes.push(text.slice(last, index))
    const token = match[0]
    if (token.startsWith("**")) {
      nodes.push(<strong key={key++} className="font-semibold">{token.slice(2, -2)}</strong>)
    } else if (token.startsWith("`")) {
      nodes.push(<code key={key++} className="px-1 py-0.5 rounded bg-black/5 dark:bg-white/10 font-mono text-[0.85em]">{token.slice(1, -1)}</code>)
    } else if (match[2]) {
      nodes.push(<span key={key++} className="inline-block align-baseline px-1.5 rounded bg-primary/10 text-primary font-mono text-[0.75em]">{match[2]}</span>)
    } else if (match[3] && match[4]) {
      nodes.push(<a key={key++} href={match[4]} target="_blank" rel="noopener noreferrer" className="underline decoration-primary/50 hover:decoration-primary">{match[3]}</a>)
    } else {
      nodes.push(<em key={key++}>{token.slice(1, -1)}</em>)
    }
    last = index + token.length
  }
  if (last < text.length) nodes.push(text.slice(last))
  return nodes
}

const BULLET = /^\s*[-*•]\s+(.*)$/
const NUMBERED = /^\s*(\d+)[.)]\s+(.*)$/
const HEADING = /^(#{1,3})\s+(.*)$/

export function renderMarkdown(text: string): React.ReactNode {
  const lines = text.replace(/\r\n/g, "\n").split("\n")
  const blocks: React.ReactNode[] = []
  let paragraph: string[] = []
  let key = 0

  const flush = () => {
    if (!paragraph.length) return
    blocks.push(
      <p key={key++} className="mb-2 last:mb-0">
        {paragraph.map((line, j) => (
          <React.Fragment key={j}>
            {j > 0 && <br />}
            {renderInline(line)}
          </React.Fragment>
        ))}
      </p>
    )
    paragraph = []
  }

  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) { flush(); i++; continue }

    const heading = HEADING.exec(line)
    if (heading) {
      flush()
      blocks.push(<p key={key++} className="font-semibold mt-3 mb-1 first:mt-0">{renderInline(heading[2])}</p>)
      i++
      continue
    }

    if (BULLET.test(line)) {
      flush()
      const items: string[] = []
      while (i < lines.length && BULLET.test(lines[i])) { items.push(BULLET.exec(lines[i])![1]); i++ }
      blocks.push(<ul key={key++} className="list-disc pl-5 mb-2 space-y-1">{items.map((item, j) => <li key={j}>{renderInline(item)}</li>)}</ul>)
      continue
    }

    const numbered = NUMBERED.exec(line)
    if (numbered) {
      flush()
      const start = Number(numbered[1])
      const items: string[] = []
      while (i < lines.length && NUMBERED.test(lines[i])) { items.push(NUMBERED.exec(lines[i])![2]); i++ }
      // Lists the model separates with blank lines become several <ol>s; keeping each one's own start number keeps the numbering honest.
      blocks.push(<ol key={key++} start={start} className="list-decimal pl-5 mb-2 space-y-1">{items.map((item, j) => <li key={j}>{renderInline(item)}</li>)}</ol>)
      continue
    }

    paragraph.push(line)
    i++
  }
  flush()
  return <>{blocks}</>
}
