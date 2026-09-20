import { useEffect, useState } from 'react'
import { fetchRestaurants } from './api'
import RestaurantList from './components/RestaurantList'
import ChatPanel from './components/ChatPanel'

export default function App() {
  const [tab, setTab] = useState('chat')
  const [restaurants, setRestaurants] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchRestaurants()
      .then(setRestaurants)
      .catch(() => setError('Could not load menu data. Is the backend running on :8000?'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      <header className="site-header">
        <div className="brand-row">
          <div className="brand-mark">ម</div>
          <h1>KhmerMenuIQ</h1>
          <span className="khmer-title khmer">ម៉ឺនុយឆ្លាត</span>
        </div>
        <p className="tagline">
          30 real Cambodian street-food menus, transcribed bilingually from photos. Browse dishes
          in English &amp; Khmer, or ask the assistant what to order on a budget.
        </p>
      </header>

      <nav className="tabs">
        <button className={`tab-btn ${tab === 'chat' ? 'active' : ''}`} onClick={() => setTab('chat')}>
          Ask KhmerMenuIQ
        </button>
        <button className={`tab-btn ${tab === 'menus' ? 'active' : ''}`} onClick={() => setTab('menus')}>
          Browse Menus
        </button>
      </nav>

      {tab === 'menus' ? (
        <RestaurantList restaurants={restaurants} loading={loading} error={error} />
      ) : (
        <ChatPanel />
      )}

      <footer className="app-footer">
        Menu data extracted from photographed restaurant boards · prices approximate, converted from Riel at a fixed rate
      </footer>
    </>
  )
}
