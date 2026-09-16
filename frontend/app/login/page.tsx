"use client";

import { useActionState } from "react";
import { Logo } from "@/app/components/logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { login, type LoginState } from "./actions";

const initialState: LoginState = { error: null };

export default function LoginPage() {
  const [state, formAction, isPending] = useActionState(login, initialState);

  return (
    <div className="mx-auto grid min-h-screen max-w-5xl content-center gap-16 p-6 font-sans md:p-12">
      <section className="flex flex-col items-center gap-8 text-center">
        <Logo />
        <div className="flex flex-col items-center gap-2">
          <h1 className="font-sans text-4xl font-medium tracking-tight md:text-6xl">
            Welcome back.
          </h1>
          <p className="font-sans text-muted-foreground">
            Sign in to continue to Mio.
          </p>
        </div>

        <Card className="w-full max-w-sm text-left">
          <CardHeader>
            <CardTitle>Sign in</CardTitle>
            <CardDescription>
              Enter your credentials to access your account.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form action={formAction} className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  placeholder="you@example.com"
                />
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  placeholder="••••••••"
                />
              </div>

              {state.error && (
                <p className="text-left text-sm text-destructive">
                  {state.error}
                </p>
              )}

              <Button type="submit" disabled={isPending} className="w-full">
                {isPending ? "Signing in…" : "Sign in"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
