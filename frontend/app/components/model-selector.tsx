type Model = {
  id: string;
  name: string;
};

const MODEL_ABBREVIATIONS: Record<string, string> = {
  "GPT-5.6 Luna": "GPT",
  "Gemini 3.8 Flash": "Gemini",
  "DeepSeek V4.1 Flash": "DeepSeek",
  "GLM 5.3 Flash": "GLM",
  "MiMo-V2.6-Pro": "MiMo Pro",
  "MiMo-V2.6-Flash": "MiMo Flash",
};

function abbreviatedModelName(name: string): string {
  return MODEL_ABBREVIATIONS[name] ?? name;
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
        className="absolute inset-0 cursor-pointer appearance-none bg-transparent text-sm text-transparent outline-none"
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
