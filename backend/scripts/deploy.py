"""Deploy AirDay from backend/.env.

    uv run python scripts/deploy.py              # secrets -> SSM, build, sam deploy, write frontend/.env.local
    uv run python scripts/deploy.py --no-deploy  # only push secrets and refresh frontend/.env.local

Secrets never leave this machine except to SSM Parameter Store as SecureString. Nothing secret is printed.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets as pysecrets
import shutil
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
ROOT = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)

from airday import envfile  # noqa: E402

ENV_PATH = os.path.join(BACKEND, ".env")
FRONTEND_ENV = os.path.join(ROOT, "frontend", ".env.local")
SECRETS = {"ADMIN_KEY": "admin-key", "DATA_GOV_API_KEY": "data-gov-key", "OPENAQ_API_KEY": "openaq-key"}


def tool(name: str) -> str:
    """Resolve via PATH. On Windows, CreateProcess would otherwise try System32 first (e.g. WSL's bash.exe)."""
    path = shutil.which(name)
    if not path:
        sys.exit(f"{name} not found on PATH")
    return path


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("$", os.path.basename(cmd[0]), *cmd[1:3], "…" if len(cmd) > 3 else "", flush=True)
    return subprocess.run(cmd, check=True, **kw)


def aws(*args: str, region: str) -> dict:
    out = subprocess.run([tool("aws"), *args, "--region", region, "--output", "json"], check=True,
                         capture_output=True, text=True).stdout
    return json.loads(out) if out.strip() else {}


def push_secrets(env: dict[str, str], stage: str, region: str) -> None:
    for var, name in SECRETS.items():
        value = env.get(var, "")
        path = f"/airday/{stage}/{name}"
        if not value:
            print(f"  skip {path} ({var} is empty)")
            continue
        subprocess.run([tool("aws"), "ssm", "put-parameter", "--name", path, "--type", "SecureString",
                        "--value", value, "--overwrite", "--region", region],
                       check=True, capture_output=True, text=True)
        print(f"  set  {path}")


def deploy(env: dict[str, str], stack: str, stage: str, region: str) -> None:
    run([tool("bash"), os.path.join(HERE, "build_lambda.sh")])
    params = {
        "Stage": stage,
        "SesSender": env.get("SES_SENDER", ""),
        "AlarmEmail": env.get("ALARM_EMAIL", ""),
        "DemoAdmin": env.get("DEMO_ADMIN", "true"),
        "DashboardUrl": env.get("DASHBOARD_URL", ""),
        "CorsOrigins": env.get("CORS_ORIGINS", "http://localhost:3000"),
    }
    overrides = [f"{k}={v}" for k, v in params.items() if v]
    if not params["SesSender"]:
        sys.exit("SES_SENDER is required in backend/.env")
    run([tool("sam"), "deploy", "--template-file", os.path.join(ROOT, "template.yaml"), "--stack-name", stack,
         "--region", region, "--resolve-s3", "--capabilities", "CAPABILITY_IAM",
         "--no-confirm-changeset", "--no-fail-on-empty-changeset",
         "--parameter-overrides", *overrides], cwd=ROOT, env=os.environ | {"SAM_CLI_TELEMETRY": "0"})


def outputs(stack: str, region: str) -> dict[str, str]:
    d = aws("cloudformation", "describe-stacks", "--stack-name", stack, region=region)
    return {o["OutputKey"]: o["OutputValue"] for o in d["Stacks"][0].get("Outputs", [])}


def write_frontend_env(out: dict[str, str]) -> None:
    for key, value in (("NEXT_PUBLIC_API_URL", out["ApiUrl"]),
                       ("NEXT_PUBLIC_COGNITO_USER_POOL_ID", out["UserPoolId"]),
                       ("NEXT_PUBLIC_COGNITO_CLIENT_ID", out["UserPoolClientId"])):
        envfile.set_value(FRONTEND_ENV, key, value)
    print(f"  wrote {os.path.relpath(FRONTEND_ENV, ROOT)}")


def seed_demo(api_url: str, admin_key: str, principal: str) -> None:
    """Point the demo school at the principal email so the 06:00 run has someone to email."""
    if not principal:
        print("  skip demo school email (PRINCIPAL_EMAIL is empty)")
        return
    req = urllib.request.Request(f"{api_url}/school", method="PUT",
                                 data=json.dumps({"principalEmail": principal}).encode(),
                                 headers={"content-type": "application/json", "x-admin-key": admin_key})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read())
    print(f"  demo school: {body.get('name')} (principal email set: {body.get('hasEmail')})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-deploy", action="store_true")
    args = ap.parse_args()

    env = envfile.parse(ENV_PATH)
    if not env:
        sys.exit("backend/.env not found: copy backend/.env.example to backend/.env and fill it in")
    if not env.get("ADMIN_KEY"):
        env["ADMIN_KEY"] = pysecrets.token_hex(32)
        envfile.set_value(ENV_PATH, "ADMIN_KEY", env["ADMIN_KEY"])
        print("  generated ADMIN_KEY in backend/.env")
    region, stage = env.get("AWS_REGION", "ap-south-1"), env.get("STAGE", "prod")
    stack = env.get("STACK_NAME", f"airday-{stage}")

    print("1. secrets -> SSM")
    push_secrets(env, stage, region)
    if not args.no_deploy:
        print("2. build and deploy")
        deploy(env, stack, stage, region)
    print("3. stack outputs -> frontend/.env.local")
    out = outputs(stack, region)
    write_frontend_env(out)
    print("4. demo school")
    seed_demo(out["ApiUrl"], env["ADMIN_KEY"], env.get("PRINCIPAL_EMAIL", ""))
    print(f"\nAPI: {out['ApiUrl']}\nDashboard (CloudWatch): {out.get('DashboardName')}")


if __name__ == "__main__":
    main()
