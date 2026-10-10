"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { COGNITO_ENABLED, confirmSignUp, devSignIn, signIn, signUp } from "@/lib/session";

type Step = "signin" | "signup" | "confirm";

export default function SignInPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const field = "mt-1 block w-full rounded border border-line px-3 py-2";

  if (!COGNITO_ENABLED) {
    return (
      <div className="mx-auto max-w-md space-y-4">
        <h1 className="text-[clamp(28px,3.4vw,42px)] font-bold leading-tight tracking-tight">Sign in (local dev)</h1>
        <p className="text-sm text-muted">
          Cognito isn&apos;t configured here, so you can sign in as a stand-in user. Each name is its own school. The
          deployed app uses real Cognito accounts.
        </p>
        <form
          className="space-y-3 card"
          onSubmit={(e) => {
            e.preventDefault();
            devSignIn(email || "principal");
            router.push("/setup/");
          }}
        >
          <label className="block text-sm">
            Name
            <input className={field} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="principal" />
          </label>
          <button type="submit" className="rounded bg-brand px-4 py-2 font-semibold text-white">
            Continue
          </button>
        </form>
        <Link href="/" className="text-sm underline">
          Back to the demo school
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md space-y-4">
      <h1 className="text-[clamp(28px,3.4vw,42px)] font-bold leading-tight tracking-tight">{step === "signup" ? "Create an account" : step === "confirm" ? "Check your email" : "Sign in"}</h1>

      <form
        className="space-y-3 card"
        onSubmit={(e) => {
          e.preventDefault();
          if (step === "signin")
            run(async () => {
              const r = await signIn(email, password);
              if (r === "confirm") setStep("confirm");
              else router.push("/setup/");
            });
          else if (step === "signup")
            run(async () => {
              await signUp(email, password);
              setStep("confirm");
            });
          else
            run(async () => {
              await confirmSignUp(email, code);
              await signIn(email, password);
              router.push("/setup/");
            });
        }}
      >
        {step !== "confirm" && (
          <>
            <label className="block text-sm">
              School email
              <input type="email" autoComplete="email" required className={field} value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label className="block text-sm">
              Password
              <input
                type="password"
                autoComplete={step === "signup" ? "new-password" : "current-password"}
                required
                minLength={10}
                className={field}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              {step === "signup" && <span className="text-xs text-muted">At least 10 characters, with a number and a lowercase letter.</span>}
            </label>
          </>
        )}
        {step === "confirm" && (
          <label className="block text-sm">
            We sent a code to {email}
            <input inputMode="numeric" autoComplete="one-time-code" required className={field} value={code} onChange={(e) => setCode(e.target.value)} />
          </label>
        )}
        {error && (
          <p role="alert" className="text-sm text-red-800">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy} className="btn btn-primary">
          {busy ? "Please wait…" : step === "signup" ? "Create account" : step === "confirm" ? "Confirm" : "Sign in"}
        </button>
      </form>

      {step === "signin" && (
        <p className="text-sm">
          New school?{" "}
          <button type="button" className="underline" onClick={() => setStep("signup")}>
            Create an account
          </button>
        </p>
      )}
      {step === "signup" && (
        <p className="text-sm">
          Have an account?{" "}
          <button type="button" className="underline" onClick={() => setStep("signin")}>
            Sign in
          </button>
        </p>
      )}
      <Link href="/" className="text-sm underline">
        Back to the demo school
      </Link>
    </div>
  );
}
