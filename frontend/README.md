# AirDay — dashboard

The Next.js dashboard for AirDay (App Router, TypeScript, static export for AWS Amplify Hosting).

See the [root README](../README.md) for what AirDay is, the live demo, the full AWS architecture, and how it all
fits together. This file covers just the frontend.

## Develop

```bash
npm install
npm run dev
```

Open http://localhost:3000. By default the dev site talks to a local backend at `http://localhost:8000`
(run `uv run python -m airday.devserver` in [`../backend`](../backend)); copy `.env.example` to
`.env.development.local` to change that or to point at a deployed API.

## Environment

Public config (baked into the static build at build time):

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL of the HTTP API (the SAM `ApiUrl` output). |
| `NEXT_PUBLIC_COGNITO_USER_POOL_ID` | Cognito user pool; leave empty to use the local stand-in sign-in. |
| `NEXT_PUBLIC_COGNITO_CLIENT_ID` | Cognito app client ID. |

In Amplify these are set in the console; local values go in `.env.development.local` (gitignored).

## Build

```bash
npm run build
```

Produces a static export in `out/`, which Amplify serves (see [`../amplify.yml`](../amplify.yml)).

## Scripts

- `npm run dev` — dev server
- `npm run build` — static production export
- `npm run lint` — ESLint
