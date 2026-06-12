"use client";

import { useActionState } from "react";
import { Logo } from "@/app/components/logo";
import { H1, P } from "@/app/components/typography";
import { Button } from "@/app/components/button";
import { login, type LoginState } from "./actions";

const initialState: LoginState = { error: null };

export default function LoginPage() {
  const [state, formAction, isPending] = useActionState(login, initialState);

  return (
    <div className="mx-auto max-w-5xl font-sans md:p-12 p-6 grid content-center gap-16 min-h-screen">
      <section className="flex flex-col gap-8 items-center text-center">
        <Logo />
        <div className="flex flex-col gap-2 items-center">
          <H1>Welcome back.</H1>
          <P className="text-muted-foreground">Sign in to continue to Mio.</P>
        </div>

        <form
          action={formAction}
          className="flex flex-col gap-4 w-full max-w-sm"
        >
          <div className="flex flex-col gap-1 text-left">
            <label htmlFor="email" className="text-sm font-medium">
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              placeholder="you@example.com"
              className="rounded-xl border border-border bg-background-alt px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-foreground/20 placeholder:text-muted-foreground"
            />
          </div>

          <div className="flex flex-col gap-1 text-left">
            <label htmlFor="password" className="text-sm font-medium">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              placeholder="••••••••"
              className="rounded-xl border border-border bg-background-alt px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-foreground/20 placeholder:text-muted-foreground"
            />
          </div>

          {state.error && (
            <P className="text-sm text-red-500 text-left">{state.error}</P>
          )}

          <Button
            type="submit"
            variant={"default"}
            disabled={isPending}
            className="w-full justify-center mt-2"
          >
            {isPending ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </section>
    </div>
  );
}
