import { useRef, useState } from 'react'
import { sendChatMessage } from '../api'
import ComboCard from './ComboCard'
import MenuItemCard from './MenuItemCard'

const STARTERS = [
  "I have $10, want chicken, some vegetables, and a couple of beers — what should I order?",
  'What vegetarian dishes are under $2?',
  'Where can I get grilled chicken feet?',
]

export default function ChatPanel({ selectedItem, initialDraft, onClearSelectedItem }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: "Sok sabay! Tell me your budget and what you're craving, and I'll find the best combo across these 30 menus.",
      combos: [],
      suggestedItems: [],
    },
  ])
  const [input, setInput] = useState(initialDraft || '')
  const [busy, setBusy] = useState(false)
  const logRef = useRef(null)
  const inputRef = useRef(null)

  async function submit(text) {
    const trimmed = text.trim()
    if (!trimmed || busy) return
    setMessages((m) => [...m, { role: 'user', text: trimmed }])
    setInput('')
    setBusy(true)
    try {
      const data = await sendChatMessage(trimmed, [], selectedItem)
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          text: data.reply,
          combos: data.combos || [],
          suggestedItems: data.suggested_items || [],
        },
      ])
    } catch {
      setMessages((m) => [
        ...m,
        { role: 'assistant', text: "Sorry, I couldn't reach the kitchen (server error). Please try again.", combos: [], suggestedItems: [] },
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

      {selectedItem && (
        <div className="selected-item-context" aria-label="Selected menu item">
          <div className="selected-item-icon" aria-hidden="true">ម</div>
          <div className="selected-item-copy">
            <span className="selected-item-eyebrow">Asking about</span>
            <strong>{selectedItem.item_name_en || selectedItem.item_name_kh}</strong>
            <span>
              {selectedItem.restaurant_name_en}
              {selectedItem.price_usd != null ? ` · $${selectedItem.price_usd.toFixed(2)}` : ''}
            </span>
          </div>
          <button
            className="clear-selected-item"
            type="button"
            onClick={onClearSelectedItem}
            aria-label="Clear selected menu item"
          >
            ×
          </button>
        </div>
      )}

      <div className="chat-log">
        {messages.map((m, i) => (
          <div className={`bubble-row ${m.role}`} key={i}>
            <div>
              <div className="bubble">{m.text}</div>
              {m.combos?.map((c) => <ComboCard combo={c} key={c.restaurant_id} />)}
              {m.suggestedItems?.length > 0 && (
                <section className="menu-suggestions" aria-label="Suggested menu items">
                  <div className="menu-suggestions-title">Items to compare</div>
                  <div className="menu-suggestions-grid">
                    {m.suggestedItems.map((item) => (
                      <MenuItemCard
                        item={item}
                        key={`${item.restaurant_id}-${item.item_en}-${item.item_kh}`}
                      />
                    ))}
                  </div>
                </section>
              )}
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
          ref={inputRef}
          autoFocus={Boolean(selectedItem)}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit(input)}
          placeholder={selectedItem ? 'Ask anything about this item…' : 'e.g. I have $10, want chicken, veggies, and a couple beers…'}
          disabled={busy}
        />
        <button onClick={() => submit(input)} disabled={busy || !input.trim()}>Ask</button>
      </div>
    </div>
  )
}
