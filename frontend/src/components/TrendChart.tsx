import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TrendPoint } from "../api";
import { inr } from "../format";

// Declared GST turnover vs observed bank credits over time. Two series → legend is
// always present (identity never by color alone). For honest firms the lines track
// each other; for the fraud persona the GST line rides far above bank credits.

const SERIES = [
  { key: "gst_declared", name: "GST declared", color: "var(--series-1)" },
  { key: "bank_credit", name: "Bank credits", color: "var(--series-2)" },
] as const;

function shortMonth(m: string): string {
  // "2024-07" → "Jul '24"
  const [y, mm] = m.split("-");
  const names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${names[Number(mm) - 1]} '${y.slice(2)}`;
}

export function TrendChart({ data }: { data: TrendPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
        <CartesianGrid stroke="var(--gridline)" vertical={false} />
        <XAxis
          dataKey="month"
          tickFormatter={shortMonth}
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          interval="preserveStartEnd"
          minTickGap={28}
        />
        <YAxis
          tickFormatter={(v) => inr(v)}
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          width={58}
        />
        <Tooltip
          formatter={(v: number, name) => [inr(v), name]}
          labelFormatter={shortMonth}
          contentStyle={{
            background: "var(--surface-1)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            color: "var(--text-primary)",
            fontSize: 12,
          }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {SERIES.map((s) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.name}
            stroke={s.color}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
