import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type Macros = {
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
};

export function MacroBadge({
  letter,
  color,
  value,
}: {
  letter: string;
  color: string;
  value: string;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm leading-none">
      <Badge className={cn(color, "size-5 p-0 text-white")}>{letter}</Badge>
      {value} g
    </span>
  );
}

export function FoodBadges({
  amount,
  macros,
}: {
  amount?: string;
  macros: Macros;
}) {
  return (
    <div className="grid grid-cols-4 items-center gap-4 whitespace-nowrap text-muted-foreground md:grid-cols-5">
      {amount !== undefined && (
        <span className="hidden whitespace-nowrap md:inline">{amount}</span>
      )}
      <span>{macros.calories.toFixed()} Kcal</span>
      <MacroBadge
        letter="P"
        color="bg-red-500"
        value={macros.protein.toFixed()}
      />
      <MacroBadge
        letter="C"
        color="bg-yellow-500"
        value={macros.carbs.toFixed()}
      />
      <MacroBadge letter="F" color="bg-blue-500" value={macros.fat.toFixed()} />
    </div>
  );
}
