import { useState } from 'react'

const CATEGORY_ORDER = [
  'chicken', 'beef', 'pork', 'fish', 'seafood', 'egg', 'tofu',
  'vegetable', 'soup', 'rice', 'noodle', 'salad', 'dessert',
  'beer', 'soft_drink', 'other',
]

const CATEGORY_LABELS = {
  chicken: 'Chicken · មាន់',
  beef: 'Beef · គោ',
  pork: 'Pork · ជ្រូក',
  fish: 'Fish · ត្រី',
  seafood: 'Seafood · អាហារសមុទ្រ',
  egg: 'Egg · ពងទា',
  tofu: 'Tofu · តៅហ៊ូ',
  vegetable: 'Vegetable · បន្លែ',
  soup: 'Soup · ស៊ុប',
  rice: 'Rice · បាយ',
  noodle: 'Noodle · មី/គុយទាវ',
  salad: 'Salad · បុកល្ហុង',
  dessert: 'Dessert · បង្អែម',
  beer: 'Beer · ស្រាបៀរ',
  soft_drink: 'Drinks · ភេសជ្ជៈ',
  other: 'Other · ផ្សេងៗ',
}

function formatPrice(item) {
  if (item.min_price_usd == null) return <span className="price unknown">call to ask</span>
  const variants = item.prices.length > 1
  return (
    <span className="price">
      {variants ? 'from ' : ''}${item.min_price_usd.toFixed(2)}
    </span>
  )
}

function RestaurantDetail({ restaurant, onBack }) {
  const grouped = {}
  for (const item of restaurant.items) {
    grouped[item.category] = grouped[item.category] || []
    grouped[item.category].push(item)
  }

  return (
    <div className="detail-panel">
      <button className="back-link" onClick={onBack}>&larr; Back to all restaurants</button>
      <h2 className="display">{restaurant.restaurant_name_en}</h2>
      {restaurant.restaurant_name_kh && (
        <div className="name-kh khmer">{restaurant.restaurant_name_kh}</div>
      )}
      {restaurant.phone && <div className="tagline">Tel: {restaurant.phone}</div>}

      {CATEGORY_ORDER.filter((c) => grouped[c]?.length).map((cat) => (
        <div className="category-group" key={cat}>
          <div className="category-label">{CATEGORY_LABELS[cat] || cat}</div>
          {grouped[cat].map((item, i) => (
            <div className="menu-item-row" key={i}>
              <div className="names">
                <div className="en">{item.name_en}</div>
                <div className="kh khmer">{item.name_kh}</div>
              </div>
              {formatPrice(item)}
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

export default function RestaurantList({ restaurants, loading, error }) {
  const [selectedId, setSelectedId] = useState(null)

  if (loading) return <div className="loading-state">Loading menus…</div>
  if (error) return <div className="error-state">{error}</div>
  if (!restaurants.length) return <div className="empty-state">No menu data yet.</div>

  if (selectedId) {
    const restaurant = restaurants.find((r) => r.id === selectedId)
    if (restaurant) {
      return <RestaurantDetail restaurant={restaurant} onBack={() => setSelectedId(null)} />
    }
  }

  return (
    <div className="restaurant-grid">
      {restaurants.map((r) => (
        <div className="restaurant-card" key={r.id} onClick={() => setSelectedId(r.id)}>
          <div className="name-en">{r.restaurant_name_en}</div>
          {r.restaurant_name_kh && <div className="name-kh khmer">{r.restaurant_name_kh}</div>}
          <div className="meta-row">
            <span>{r.phone || 'no phone listed'}</span>
            <span className="item-count-badge">{r.items.length} items</span>
          </div>
        </div>
      ))}
    </div>
  )
}
