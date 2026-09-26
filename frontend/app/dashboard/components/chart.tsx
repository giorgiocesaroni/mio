"use client";

const defaultFormatValue = (value: number) =>
  Math.round(value).toLocaleString();

type ChartTooltipProps = {
  active?: boolean;
  payload?: Array<{
    value?: number;
    name?: string;
    color?: string;
    dataKey?: string;
    payload?: { key?: string };
  }>;
  unit?: string;
  formatValue?: (value: number) => string;
  showBreakdown?: boolean;
};

export function ChartTooltip({
  active,
  payload,
  unit,
  formatValue = defaultFormatValue,
  showBreakdown = false,
}: ChartTooltipProps) {
  if (!active || !payload?.length) return null;

  const point = payload[0].payload;
  const date = point?.key ? new Date(`${point.key}T12:00:00`) : undefined;
  const value = Number(payload[0].value ?? 0);
  const segments = showBreakdown
    ? payload.filter(
        (entry) =>
          entry.dataKey !== "total" && Number(entry.value ?? 0) > 0,
      )
    : [];
  const total = segments.reduce(
    (sum, entry) => sum + Number(entry.value ?? 0),
    0,
  );

  return (
    <div className="max-w-[18rem] rounded-lg border bg-background px-3 py-2 text-sm shadow-lg">
      <p className="font-medium text-foreground">
        {date?.toLocaleDateString(undefined, {
          weekday: "long",
          month: "short",
          day: "numeric",
        })}
      </p>
      {segments.length > 0 ? (
        <div className="mt-1 grid gap-0.5">
          {segments.map((entry) => (
            <p
              key={entry.name ?? entry.color}
              className="flex items-center gap-2 text-muted-foreground"
            >
              <span
                className="size-2 shrink-0 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              <span className="min-w-0 max-w-[11rem] truncate">{entry.name}</span>
              <span className="ml-auto pl-3 tabular-nums text-foreground">
                {formatValue(Number(entry.value ?? 0))}
              </span>
            </p>
          ))}
          <p className="mt-1 flex items-center border-t pt-1 font-medium text-foreground">
            <span>Total</span>
            <span className="ml-auto pl-3 tabular-nums">
              {formatValue(total)}
            </span>
          </p>
        </div>
      ) : (
        <p className="text-muted-foreground">
          {formatValue(value)}
          {unit ? ` ${unit}` : ""}
        </p>
      )}
    </div>
  );
}

type ChartLineLabelProps = {
  viewBox?: { x?: number; y?: number };
  value: number;
  chartMax: number;
  unit?: string;
  formatValue?: (value: number) => string;
};

export function ChartLineLabel({
  viewBox,
  value,
  chartMax,
  unit,
  formatValue = defaultFormatValue,
}: ChartLineLabelProps) {
  // When the line is at the top of the chart, the label would be clipped if
  // drawn above it, so draw it below.
  const atTop = value >= chartMax;

  return (
    <text
      x={viewBox?.x ?? 0}
      y={(viewBox?.y ?? 0) + (atTop ? 14 : -6)}
      fill="#ef4444"
      fontFamily="var(--font-sans)"
      fontSize={12}
      fontWeight={600}
      textAnchor="start"
    >
      {formatValue(value)}
      {unit ? ` ${unit}` : ""}
    </text>
  );
}
