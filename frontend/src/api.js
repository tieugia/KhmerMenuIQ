const BASE = `${import.meta.env.VITE_API_BASE_URL || ''}/api`

export async function fetchRestaurants() {
  const res = await fetch(`${BASE}/restaurants`)
  if (!res.ok) throw new Error('Failed to load restaurants')
  return res.json()
}

export async function sendChatMessage(message, history = [], selectedItem = null) {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history, selected_item: selectedItem }),
  })
  if (!res.ok) throw new Error('Chat request failed')
  return res.json()
}
