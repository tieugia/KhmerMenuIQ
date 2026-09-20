function BudgetPill({ combo }) {
  const incomplete = combo.missing_roles.length > 0
  if (incomplete) {
    return <span className="budget-pill missing">missing {combo.missing_roles.join(', ')}</span>
  }
  if (combo.budget_usd == null) {
    return <span className="budget-pill estimated">no budget set — cheapest full option</span>
  }
  if (combo.within_budget) {
    return (
      <span className="budget-pill in">
        ${(combo.budget_usd - combo.total_usd).toFixed(2)} left of ${combo.budget_usd.toFixed(2)}
      </span>
    )
  }
  return (
    <span className="budget-pill over">
      ${(combo.total_usd - combo.budget_usd).toFixed(2)} over ${combo.budget_usd.toFixed(2)}
    </span>
  )
}

export default function ComboCard({ combo }) {
  return (
    <div className="combo-card">
      <div className="combo-header">
        <div>
          <div className="rest-en">{combo.restaurant_name_en}</div>
          {combo.restaurant_name_kh && (
            <div className="rest-kh khmer">{combo.restaurant_name_kh}</div>
          )}
          {combo.phone && <div className="phone">Tel: {combo.phone}</div>}
        </div>
        <BudgetPill combo={combo} />
      </div>
      <div className="combo-lines">
        {combo.lines.map((line, i) => (
          <div className="combo-line" key={i}>
            <span><span className="qty">{line.quantity}×</span>{line.item_name_en} <span className="khmer">({line.item_name_kh})</span></span>
            <span>${line.line_total_usd.toFixed(2)}</span>
          </div>
        ))}
      </div>
      <div className="combo-total-row">
        <span>Total</span>
        <span>${combo.total_usd.toFixed(2)}</span>
      </div>
    </div>
  )
}
