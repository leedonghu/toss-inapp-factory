const colors = ['#d5e8ff', '#c9f0e5', '#ffe9b5', '#ffdbd3', '#dfdcff', '#cdeff6', '#f9dcec', '#e3edc8', '#d7ddfa', '#fbe0b8', '#d1e8db', '#eadcf5'];
const point = (angle: number, radius = 142) => {
  const radians = (angle - 90) * Math.PI / 180;
  return [160 + Math.cos(radians) * radius, 160 + Math.sin(radians) * radius];
};
export function Wheel({ items, angle, duration }: { items: string[]; angle: number; duration: number }) {
  const width = 360 / Math.max(1, items.length);
  return <div className="wheel-wrap">
    <span className="pointer" aria-hidden="true" />
    <svg className="wheel" viewBox="0 0 320 320" role="img" aria-label={`메뉴 룰렛: ${items.join(', ') || '메뉴 없음'}`}>
      <g style={{ transform: `rotate(${angle}deg)`, transformOrigin: '160px 160px', transition: `transform ${duration}ms cubic-bezier(.2,.05,.15,1)` }}>
        <circle cx="160" cy="160" r="146" fill="#f2f4f6" />
        {items.map((item, i) => {
          const a = point(i * width); const b = point((i + 1) * width);
          const center = (i + 0.5) * width;
          return <g key={item}>
            {items.length === 1 ? <circle cx="160" cy="160" r="142" fill={colors[0]} /> : <path d={`M160 160 L${a.join(' ')} A142 142 0 ${width > 180 ? 1 : 0} 1 ${b.join(' ')} Z`} fill={colors[i]} stroke="white" strokeWidth="2" />}
            <text x="160" y="67" transform={`rotate(${center} 160 160)`} textAnchor="middle" fill="#25364a" fontSize={items.length > 9 ? 12 : 14} fontWeight="700">
              <title>{item}</title>{Array.from(item).length > 6 ? `${Array.from(item).slice(0, 5).join('')}…` : item}
            </text>
          </g>;
        })}
      </g>
      <circle cx="160" cy="160" r="25" fill="white" />
      <circle cx="160" cy="160" r="16" fill="#3182f6" />
      <path d="M154 160l4 4 8-9" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  </div>;
}
