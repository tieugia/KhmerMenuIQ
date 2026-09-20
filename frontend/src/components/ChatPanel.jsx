import { useRef, useState } from 'react'
import { sendChatMessage } from '../api'
import ComboCard from './ComboCard'

const STARTERS = [
  "I have $10, want chicken, some vegetables, and a couple of beers — what should I order?",
  'What vegetarian dishes are under $2?',
  'Where can I get grilled chicken feet?',
]

export default function ChatPanel() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: "Sok sabay! Tell me your budget and what you're craving, and I'll find the best combo across these 30 menus.",
      combos: [],
    },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const logRef = useRef(null)

  async function submit(text) {
    const trimmed = text.trim()
    if (!trimmed || busy) return
    setMessages((m) => [...m, { role: 'user', text: trimmed }])
    setInput('')
    setBusy(true)
    try {
      const data = await sendChatMessage(trimmed)
      setMessages((m) => [...m, { role: 'assistant', text: data.reply, combos: data.combos || [] }])
    } catch {
      setMessages((m) => [
        ...m,
        { role: 'assistant', text: "Sorry, I couldn't reach the kitchen (server error). Please try again.", combos: [] },
      ])
    } finally {
      setBusy(false)
      setTimeout(() => logRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }), 50)
    }
  }

  return (
    <div className="chat-shell">
      {messages.length <= 1 && (
        <div className="suggestions">
          {STARTERS.map((s) => (
            <button key={s} className="suggestion-chip" onClick={() => submit(s)}>{s}</button>
          ))}
        </div>
      )}

      <div className="chat-log">
        {messages.map((m, i) => (
          <div className={`bubble-row ${m.role}`} key={i}>
            <div>
              <div className="bubble">{m.text}</div>
              {m.combos?.map((c) => <ComboCard combo={c} key={c.restaurant_id} />)}
            </div>
          </div>
        ))}
        {busy && (
          <div className="bubble-row assistant">
            <div className="bubble">
              <span className="typing-dots"><span></span><span></span><span></span></span>
            </div>
          </div>
        )}
        <div ref={logRef} />
      </div>

      <div className="chat-input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit(input)}
          placeholder="e.g. I have $10, want chicken, veggies, and a couple beers…"
          disabled={busy}
        />
        <button onClick={() => submit(input)} disabled={busy || !input.trim()}>Ask</button>
      </div>
    </div>
  )
}
