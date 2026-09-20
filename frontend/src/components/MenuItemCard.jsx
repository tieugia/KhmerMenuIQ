const RELATION_LABELS = {
  'selected item': 'Selected',
  cheaper: 'Cheaper',
  'same price': 'Same price',
  'more expensive': 'Pricier',
  unknown: 'Compare',
}

export default function MenuItemCard({ item }) {
  const relationClass = item.price_vs_selected.replaceAll(' ', '-')

  return (
    <article className={`menu-suggestion-card ${relationClass}`}>
      <div className="menu-suggestion-topline">
        <span className="menu-suggestion-category">{item.category.replace('_', ' ')}</span>
        <span className={`comparison-badge ${relationClass}`}>
          {RELATION_LABELS[item.price_vs_selected] || item.price_vs_selected}
        </span>
      </div>
      <h3>{item.item_en || item.item_kh}</h3>
      {item.item_kh && <div className="menu-suggestion-kh khmer">{item.item_kh}</div>}
      <div className="menu-suggestion-footer">
        <span>{item.restaurant}</span>
        <strong>{item.price_usd == null ? 'Ask for price' : `$${item.price_usd.toFixed(2)}`}</strong>
      </div>
    </article>
  )
}
