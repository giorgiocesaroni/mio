export function formatCompactNumber(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return `${value}`;
}

export function CompactNumber({ value }: { value: number }) {
  return (
    <span title={value.toLocaleString()}>{formatCompactNumber(value)}</span>
  );
}
