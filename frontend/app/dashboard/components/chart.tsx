"use client";

const defaultFormatValue = (value: number) =>
  Math.round(value).toLocaleString();

type ChartTooltipProps = {
  active?: boolean;
  payload?: Array<{
    value?: number;
    payload?: { key?: string };
  }>;
  unit?: string;
  formatValue?: (value: number) => string;
};

export function ChartTooltip({
  active,
  payload,
  unit,
  formatValue = defaultFormatValue,
}: ChartTooltipProps) {
  if (!active || !payload?.length) return null;

  const point = payload[0].payload;
  const date = point?.key ? new Date(`${point.key}T12:00:00`) : undefined;
  const value = Number(payload[0].value ?? 0);

  return (
    <div className="rounded-lg border bg-background px-3 py-2 text-sm shadow-lg">
      <p className="font-medium text-foreground">
        {date?.toLocaleDateString(undefined, {
          weekday: "long",
          month: "short",
          day: "numeric",
        })}
      </p>
      <p className="text-muted-foreground">
        {formatValue(value)}
        {unit ? ` ${unit}` : ""}
      </p>
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
