# Deploying AirDay

Region: `ap-south-1` (Mumbai). Stage: `prod`. Nothing here runs automatically until step 5.

## 1. Secrets (once)

```bash
aws ssm put-parameter --name /airday/prod/admin-key --type SecureString --value "$(openssl rand -hex 32)"
```

Optional, for live official AQI and station readings:

```bash
aws ssm put-parameter --name /airday/prod/data-gov-key --type SecureString --value "<data.gov.in key>"
aws ssm put-parameter --name /airday/prod/openaq-key --type SecureString --value "<OpenAQ key>"
```

## 2. SES

Verify the sender address (or domain) and, while the account is in the SES sandbox, each principal's address:

```bash
aws sesv2 create-email-identity --email-identity airday@yourdomain.com
```

## 3. Bedrock

Confirm Nova Lite is invokable through the APAC inference profile:

```bash
aws bedrock-runtime converse --model-id apac.amazon.nova-lite-v1:0 --messages '[{"role":"user","content":[{"text":"hi"}]}]'
```

## 4. First deploy (from a laptop)

Needs the SAM CLI and Python 3.12.

```bash
sam build
sam deploy --guided --stack-name airday-prod --capabilities CAPABILITY_IAM
```

Note the outputs: `ApiUrl`, `UserPoolId`, `UserPoolClientId`.

## 5. Continuous deploy from GitHub (OIDC, no stored keys)

1. In IAM, add GitHub as an OIDC identity provider (`token.actions.githubusercontent.com`, audience `sts.amazonaws.com`).
2. Create a role that trusts it, limited to this repo's `main` branch:

   ```json
   {
     "Effect": "Allow",
     "Principal": {"Federated": "arn:aws:iam::<account>:oidc-provider/token.actions.githubusercontent.com"},
     "Action": "sts:AssumeRoleWithWebIdentity",
     "Condition": {
       "StringEquals": {"token.actions.githubusercontent.com:aud": "sts.amazonaws.com"},
       "StringLike": {"token.actions.githubusercontent.com:sub": "repo:Rohit-998/Environmental-Hacks:environment:prod"}
     }
   }
   ```

   Give it permissions to deploy the stack (CloudFormation, Lambda, IAM role creation for the stack, DynamoDB, SQS,
   SNS, Cognito, API Gateway, Scheduler, CloudWatch, S3 for the SAM artifact bucket).
3. In the GitHub repo, create an environment named `prod` and set these repository variables:
   `AWS_DEPLOY_ROLE_ARN`, `SES_SENDER`, `DASHBOARD_URL`, `CORS_ORIGINS`, `ALARM_EMAIL`.

From then on, every push to `main` that passes CI deploys. Without `AWS_DEPLOY_ROLE_ARN` the deploy job is skipped.

## 6. Dashboard (Amplify Hosting)

Connect the repo in Amplify Hosting. It reads `amplify.yml`. Set environment variables:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `ApiUrl` output |
| `NEXT_PUBLIC_COGNITO_USER_POOL_ID` | `UserPoolId` output |
| `NEXT_PUBLIC_COGNITO_CLIENT_ID` | `UserPoolClientId` output |

Then set the stack's `DashboardUrl` and add the Amplify domain to `CorsOrigins`, and redeploy.

## 7. Check it worked

- Invoke the planner once: `aws lambda invoke --function-name <PlannerFunction> --payload '{}' out.json`
- CloudWatch dashboard `airday-prod`: `SchoolsQueued` and `BriefBuilt` should match.
- Logs Insights on the worker log group: `filter message like /daily_brief/`.

## Before the demo

Set `DemoAdmin=false` once the video is recorded, so the public demo school is read-only.
