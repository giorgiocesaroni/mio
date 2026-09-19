import { cn } from "@/lib/utils";

type Model = {
  id: string;
  name: string;
};

function abbreviatedModelName(name: string): string {
  return name.trim().split(/\s+/)[0] ?? name;
}

export function ModelSelector({
  models,
  value,
  onChange,
}: {
  models: Model[];
  value?: string;
  onChange: (value: string) => void;
}) {
  const selectedName = models.find((model) => model.id === value)?.name ?? "";
  const abbreviatedName = abbreviatedModelName(selectedName);

  return (
    <span className="relative mx-2 inline-block">
      <span className="text-sm whitespace-nowrap text-muted-foreground">
        {abbreviatedName}
      </span>
      <select
        aria-label="Model"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
        className={cn(
          "absolute inset-0 cursor-pointer appearance-none bg-transparent text-sm outline-none",
          "text-transparent",
        )}
      >
        {models.map((model) => (
          <option key={model.id} value={model.id}>
            {model.name}
          </option>
        ))}
      </select>
    </span>
  );
}
