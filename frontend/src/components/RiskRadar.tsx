import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";
import type { SubScores } from "../api";

// Six-axis radar of the sub-scores — a single series, so one hue (blue, categorical
// slot 1) and no legend needed (the title names it).

const AXES: { key: keyof SubScores; label: string }[] = [
  { key: "growth", label: "Growth" },
  { key: "stability", label: "Stability" },
  { key: "compliance", label: "Compliance" },
  { key: "liquidity", label: "Liquidity" },
  { key: "concentration", label: "Diversification" },
  { key: "leverage", label: "Leverage" },
];

export function RiskRadar({ subScores }: { subScores: SubScores }) {
  const data = AXES.map((a) => ({ axis: a.label, value: subScores[a.key] }));
  return (
    <ResponsiveContainer width="100%" height={280}>
      <RadarChart data={data} outerRadius="72%">
        <PolarGrid stroke="var(--gridline)" />
        <PolarAngleAxis
          dataKey="axis"
          tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
        />
        <PolarRadiusAxis
          domain={[0, 100]}
          tick={{ fill: "var(--text-muted)", fontSize: 10 }}
          tickCount={5}
          angle={90}
        />
        <Radar
          dataKey="value"
          stroke="var(--series-1)"
          fill="var(--series-1)"
          fillOpacity={0.28}
          strokeWidth={2}
          isAnimationActive={false}
          dot
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
