// Who is using the dashboard: the public demo school, or a signed-in principal (Cognito).
//
// Deployed: Cognito user pool via Amplify Auth. The ID token goes to /me/* routes, where API Gateway's JWT
// authorizer verifies it before any Lambda runs.
// Local dev (no pool configured): a stand-in "dev user" sent as x-dev-user, which only the local dev server
// accepts. It is never honoured by the deployed API.
import { Amplify } from "aws-amplify";
import {
  confirmSignUp as amplifyConfirm,
  fetchAuthSession,
  signIn as amplifySignIn,
  signOut as amplifySignOut,
  signUp as amplifySignUp,
} from "aws-amplify/auth";

const POOL_ID = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || "";
const CLIENT_ID = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID || "";
export const COGNITO_ENABLED = Boolean(POOL_ID && CLIENT_ID);

const DEV_USER_KEY = "airday-dev-user";
const EVENT = "airday-auth-changed";
let configured = false;

function configure(): void {
  if (COGNITO_ENABLED && !configured) {
    Amplify.configure({ Auth: { Cognito: { userPoolId: POOL_ID, userPoolClientId: CLIENT_ID, loginWith: { email: true } } } });
    configured = true;
  }
}

export interface Session {
  signedIn: boolean;
  label: string; // email, dev user name, or "Demo school"
}

function changed(): void {
  window.dispatchEvent(new Event(EVENT));
}

export function onSessionChange(fn: () => void): () => void {
  window.addEventListener(EVENT, fn);
  return () => window.removeEventListener(EVENT, fn);
}

export async function authHeaders(): Promise<Record<string, string> | null> {
  if (typeof window === "undefined") return null;
  if (COGNITO_ENABLED) {
    configure();
    try {
      const s = await fetchAuthSession();
      const token = s.tokens?.idToken?.toString();
      return token ? { authorization: `Bearer ${token}` } : null;
    } catch {
      return null;
    }
  }
  const dev = window.sessionStorage.getItem(DEV_USER_KEY);
  return dev ? { "x-dev-user": dev } : null;
}

export async function currentSession(): Promise<Session> {
  if (typeof window === "undefined") return { signedIn: false, label: "Demo school" };
  if (COGNITO_ENABLED) {
    configure();
    try {
      const s = await fetchAuthSession();
      const email = s.tokens?.idToken?.payload?.email;
      if (s.tokens?.idToken) return { signedIn: true, label: typeof email === "string" ? email : "Signed in" };
    } catch {
      /* not signed in */
    }
    return { signedIn: false, label: "Demo school" };
  }
  const dev = window.sessionStorage.getItem(DEV_USER_KEY);
  return dev ? { signedIn: true, label: `${dev} (local dev)` } : { signedIn: false, label: "Demo school" };
}

export async function signIn(email: string, password: string): Promise<"done" | "confirm"> {
  configure();
  const r = await amplifySignIn({ username: email, password });
  if (r.nextStep.signInStep === "CONFIRM_SIGN_UP") return "confirm";
  changed();
  return "done";
}

export async function signUp(email: string, password: string): Promise<void> {
  configure();
  await amplifySignUp({ username: email, password, options: { userAttributes: { email } } });
}

export async function confirmSignUp(email: string, code: string): Promise<void> {
  configure();
  await amplifyConfirm({ username: email, confirmationCode: code });
}

export function devSignIn(name: string): void {
  window.sessionStorage.setItem(DEV_USER_KEY, name.trim().toLowerCase().replace(/[^a-z0-9-]/g, "-"));
  changed();
}

export async function signOut(): Promise<void> {
  if (COGNITO_ENABLED) {
    configure();
    await amplifySignOut();
  } else {
    window.sessionStorage.removeItem(DEV_USER_KEY);
  }
  changed();
}
