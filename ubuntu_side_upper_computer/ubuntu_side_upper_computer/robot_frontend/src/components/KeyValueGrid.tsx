interface Item {
  label: string;
  value: string;
  emphasis?: boolean;
}

export function KeyValueGrid({ items }: { items: Item[] }) {
  return (
    <div className="kv-grid">
      {items.map((item) => (
        <div className="kv-item" key={item.label}>
          <span>{item.label}</span>
          <strong className={item.emphasis ? 'accent' : ''}>{item.value}</strong>
        </div>
      ))}
    </div>
  );
}
