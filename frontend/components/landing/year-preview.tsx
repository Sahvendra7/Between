// A drawn illustration of Money & Time with synthetic data: custody weeks, an expense, and its payment window.
const WEEKS = 5;
const DAYS = ["M", "T", "W", "T", "F", "S", "S"];

export function YearPreview() {
  const cell = 46, gap = 4, top = 34, w = 7 * cell + 6 * gap;
  const owner = (week: number) => (week % 2 === 0 ? "A" : "B");
  return (
    <figure className="m-0 grid gap-3">
      <svg viewBox={`0 0 ${w} ${top + WEEKS * (cell + gap)}`} className="w-full" role="img"
        aria-label="Illustration: a month calendar with alternating weeks for each parent, a $420 orthodontist expense, and the 14-day window to pay the $252 share.">
        {DAYS.map((d, i) => <text key={i} x={i * (cell + gap) + cell / 2} y={18} textAnchor="middle" fontSize="12" fill="var(--ink-2)" fontFamily="var(--font-sans)">{d}</text>)}
        {Array.from({ length: WEEKS }, (_, wk) => (
          <g key={wk}>
            {DAYS.map((_, i) => (
              <rect key={i} x={i * (cell + gap)} y={top + wk * (cell + gap)} width={cell} height={cell} rx="7"
                fill={`var(--${owner(wk) === "A" ? "a" : "b"}-wash)`} />
            ))}
            <text x={4} y={top + wk * (cell + gap) + 14} fontSize="10" fill={`var(--${owner(wk) === "A" ? "a" : "b"})`} fontFamily="var(--font-sans)" fontWeight="600">{owner(wk) === "A" ? "Mother" : "Father"}</text>
          </g>
        ))}
        <rect x={2 * (cell + gap)} y={top + 1 * (cell + gap) + 18} width={5 * (cell + gap) - gap} height={18} rx="5" fill="var(--act)" opacity="0.92" />
        <rect x={0} y={top + 2 * (cell + gap) + 18} width={3 * (cell + gap) - gap} height={18} rx="5" fill="var(--act)" opacity="0.92" />
        <text x={2 * (cell + gap) + 8} y={top + 1 * (cell + gap) + 31} fontSize="11" fill="var(--act-ink)" fontFamily="var(--font-sans)" fontWeight="600">Father → Mother $252 · due in 14 days</text>
        <circle cx={2 * (cell + gap) + cell / 2} cy={top + (cell + gap) + 9} r="5" fill="var(--b)" />
        <rect x={3 * (cell + gap) + 4} y={top + 3 * (cell + gap) + 6} width={cell * 2} height={16} rx="4" fill="var(--good-wash)" />
        <text x={3 * (cell + gap) + 10} y={top + 3 * (cell + gap) + 18} fontSize="10" fill="var(--good)" fontFamily="var(--font-sans)" fontWeight="600">Swap agreed</text>
      </svg>
      <figcaption className="text-sm text-ink-2">Illustration with synthetic data. In the app, this is Bryntum Calendar, and the report beside it is AG Studio.</figcaption>
    </figure>
  );
}
