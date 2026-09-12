// [Windows] GraphSentinel — Susheep
// ui/CopyableHash — truncated hash with click-to-copy + confirmation
// (Error.md #38: users could see a truncated tx hash but never reliably
// copy or inspect the full value)
import { useState } from 'react'
import { Copy, Check } from 'lucide-react'

export default function CopyableHash({ value, prefixLen = 14, suffixLen = 0, style = {}, iconSize = 10 }) {
  const [copied, setCopied] = useState(false)

  if (!value) return <span style={{ color: '#9aa1ad' }}>—</span>

  const display = suffixLen > 0
    ? `${value.slice(0, prefixLen)}…${value.slice(-suffixLen)}`
    : `${value.slice(0, prefixLen)}…`

  const handleCopy = async (e) => {
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard API unavailable (e.g. insecure context) — nothing to fall back to silently
      console.warn('[CopyableHash] Clipboard write failed')
    }
  }

  return (
    <button
      onClick={handleCopy}
      title={copied ? 'Copied!' : `Click to copy: ${value}`}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 5,
        background: 'none', border: 'none', padding: 0, cursor: 'pointer',
        font: 'inherit', color: 'inherit', ...style,
      }}
    >
      <span>{display}</span>
      {copied ? (
        <Check size={iconSize} style={{ color: '#12a672', flexShrink: 0 }} />
      ) : (
        <Copy size={iconSize} style={{ opacity: 0.5, flexShrink: 0 }} />
      )}
    </button>
  )
}
