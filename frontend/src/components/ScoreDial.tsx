import { bandColor, bandLabel } from "../format";

// A 300–900 semicircular gauge. Single hero number; the arc fill carries the band
// color and is always paired with the band label (color never alone).

const MIN = 300;
const MAX = 900;

function polar(cx: number, cy: number, r: number, deg: number) {
  const rad = ((deg - 180) * Math.PI) / 180; // 0 at left, sweeps clockwise to right
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arc(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const s = polar(cx, cy, r, startDeg);
  const e = polar(cx, cy, r, endDeg);
  const large = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
}

export function ScoreDial({ score, band }: { score: number; band: string }) {
  const frac = Math.max(0, Math.min(1, (score - MIN) / (MAX - MIN)));
  const cx = 110;
  const cy = 110;
  const r = 92;
  const valueDeg = frac * 180;
  const color = bandColor(band);

  return (
    <div style={{ textAlign: "center" }}>
      <svg viewBox="0 0 220 132" width="100%" style={{ maxWidth: 300 }} role="img"
        aria-label={`SETU score ${score}, band ${bandLabel(band)}`}>
        <path d={arc(cx, cy, r, 0, 180)} fill="none" stroke="var(--gridline)"
          strokeWidth={14} strokeLinecap="round" />
        <path d={arc(cx, cy, r, 0, Math.max(0.5, valueDeg))} fill="none" stroke={color}
          strokeWidth={14} strokeLinecap="round" />
        {/* endpoint scale labels */}
        <text x={14} y={128} fontSize={11} fill="var(--text-muted)">300</text>
        <text x={196} y={128} fontSize={11} fill="var(--text-muted)" textAnchor="end">900</text>
      </svg>
      <div style={{ marginTop: -46 }}>
        <div className="tabular" style={{ fontSize: 46, fontWeight: 700, lineHeight: 1, color }}>
          {score}
        </div>
        <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 2 }}>SETU Score</div>
        <div style={{
          display: "inline-block", marginTop: 10, padding: "3px 12px", borderRadius: 999,
          background: color, color: "#fff", fontWeight: 600, fontSize: 13,
        }}>
          {bandLabel(band)}
        </div>
      </div>
    </div>
  );
}
