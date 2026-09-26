"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  getCurrentGoal,
  getDailyMacrosView,
} from "@/repository/supabase/queries";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

function MacroCard({
  label,
  unit,
  current,
  target,
  showDifference,
  onClick,
}: {
  label: string;
  unit: string;
  current: number;
  target: number | undefined;
  showDifference: boolean;
  onClick: () => void;
}) {
  const remaining = target !== undefined ? target - current : undefined;

  const value = showDifference ? remaining : current;
  const displayValue = value !== undefined ? Math.abs(value).toFixed() : "0";

  let suffix: string | undefined;
  if (showDifference && remaining !== undefined) {
    suffix = remaining >= 0 ? "left" : "over";
  }

  return (
    <Card
      onClick={target === undefined ? undefined : onClick}
      className={
        target === undefined ? undefined : "cursor-pointer hover:bg-muted/50"
      }
    >
      <CardHeader className="gap-0">
        <CardDescription>
          {label} {suffix && ` ${suffix}`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <CardTitle>
          {displayValue} {unit}
        </CardTitle>
      </CardContent>
    </Card>
  );
}

/** The day's calories and macros against the current goal. */
export function DailyMacros({ day }: { day: string }) {
  const [showDifference, setShowDifference] = useState(false);

  const { data: macros } = useQuery({
    queryKey: ["getDailyMacrosView", day],
    queryFn: () => getDailyMacrosView(day),
  });

  const { data: goal } = useQuery({
    queryKey: ["getCurrentGoal"],
    queryFn: getCurrentGoal,
  });

  return (
    <div className="grid grid-cols-2 items-center gap-3 md:grid-cols-4">
      <MacroCard
        label="Calories"
        unit="Kcal"
        current={macros?.total_calories_kcal ?? 0}
        target={goal?.calories_kcal}
        showDifference={showDifference}
        onClick={() => setShowDifference((v) => !v)}
      />
      <MacroCard
        label="Protein"
        unit="g"
        current={macros?.total_protein_g ?? 0}
        target={goal?.protein_g}
        showDifference={showDifference}
        onClick={() => setShowDifference((v) => !v)}
      />
      <MacroCard
        label="Carbs"
        unit="g"
        current={macros?.total_carbs_g ?? 0}
        target={goal?.carbs_g}
        showDifference={showDifference}
        onClick={() => setShowDifference((v) => !v)}
      />
      <MacroCard
        label="Fat"
        unit="g"
        current={macros?.total_fat_g ?? 0}
        target={goal?.fat_g}
        showDifference={showDifference}
        onClick={() => setShowDifference((v) => !v)}
      />
    </div>
  );
}
