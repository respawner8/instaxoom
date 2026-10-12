# Azure Cloud Deployment Guide: Backend & Neon Database

This guide explains how to deploy the **instaXoom** FastAPI backend to **Azure Container Apps (ACA)** via **Azure Cloud Shell**, connect it to **Neon Serverless PostgreSQL**, and configure the **Next.js** frontend on **Vercel**.

---

## 1. Architecture Summary

- **Backend Gateway:** FastAPI containerized service hosted on **Azure Container Apps** (Consumption tier) with **Scale to Zero** (`--min-replicas 0`). Idle infrastructure cost is **$0.00/month**.
- **AI Inference Engine:** `gpt-image-2.5-flare` hosted on **Microsoft Azure AI Foundry** (East US 2).
- **Database:** **Neon Serverless PostgreSQL** handling user persistence, credits, pending invitations, and audit logs.
- **Authentication:** **Google Identity Services (OAuth 2.0)** with JWT access token generation and role authorization.
- **Frontend:** Next.js 15 hosted on **Vercel** with `@react-oauth/google`.

---

## 2. One-Command Local Terminal Deployment (`./scripts/deploy-backend.sh`)

You can deploy directly from your local terminal using your local `backend/.env` file. The script automatically parses all variables from `backend/.env`, stamps the Git `COMMIT_SHA` and UTC `BUILD_TIME`, builds the image remotely in Azure Container Registry (`az acr build`), updates the Azure Container App (`instaxoom-backend`), and verifies the live `/health` endpoint.

```bash
# 1. Install Azure CLI (one-time setup on macOS) and log in
brew install azure-cli
az login

# 2. Preview what will be deployed without making changes (Dry Run)
./scripts/deploy-backend.sh --dry-run

# 3. Build, push, update env vars from backend/.env, and verify live status
./scripts/deploy-backend.sh
```

**Useful Script Flags:**
- `./scripts/deploy-backend.sh --skip-build` — Only push updated `backend/.env` variables without rebuilding the Docker image.
- `./scripts/deploy-backend.sh --skip-env` — Build and deploy a new code revision without modifying environment variables.

---

## 3. Manual Azure Cloud Shell Deployment Workflow

Azure Cloud Shell allows you to build container images and manage deployments directly from your browser without requiring a local Docker daemon or Azure CLI installation.

### Step 1: Open Cloud Shell & Pull Latest Repository

In [Azure Cloud Shell](https://shell.azure.com/) (select **Bash**):

```bash
# Clone the repository (or navigate to existing directory)
cd ~/instaxoom || git clone https://github.com/respawner8/instaxoom.git && cd ~/instaxoom

# Fetch and switch to the target branch
git fetch origin
git checkout main
git pull origin main
```

---

### Step 2: Build & Push Image via Azure Container Registry (ACR)

Azure ACR builds the container directly in the cloud using `az acr build`:

```bash
# 1. Create a lightweight ACR (if not already created)
az acr create \
  --resource-group rg-instaxoom-prod \
  --name acrinstaxoom \
  --sku Basic \
  --admin-enabled true

# 2. Build and push the backend container with version metadata
COMMIT_SHA=$(git rev-parse --short HEAD)
BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

az acr build \
  --registry acrinstaxoom \
  --image instaxoom-backend:${COMMIT_SHA} \
  --image instaxoom-backend:latest \
  --build-arg COMMIT_SHA=${COMMIT_SHA} \
  --build-arg BUILD_TIME=${BUILD_TIME} \
  ./backend
```

---

### Step 3: Deploy or Update Azure Container App

#### Option A: Updating an Existing Container App
If `instaxoom-backend` was deployed previously, update the container image and inject the Neon DB + Google Auth + Grafana Cloud OTel environment variables:

```bash
az containerapp update \
  --name instaxoom-backend \
  --resource-group rg-instaxoom-prod \
  --image acrinstaxoom.azurecr.io/instaxoom-backend:${COMMIT_SHA} \
  --set-env-vars \
    ENVIRONMENT="production" \
    COMMIT_SHA="${COMMIT_SHA}" \
    BUILD_TIME="${BUILD_TIME}" \
    DATABASE_URL="postgresql+asyncpg://<username>:<password>@<endpoint-id>.neon.tech/neondb?sslmode=require" \
    GOOGLE_CLIENT_ID="<YOUR_GOOGLE_CLIENT_ID>.apps.googleusercontent.com" \
    ADMIN_EMAILS="<YOUR_ADMIN_EMAIL@gmail.com>" \
    SECRET_KEY="$(openssl rand -hex 32)" \
    JWT_ALGORITHM="HS256" \
    JWT_EXPIRE_MINUTES="10080" \
    ENGINE="azure" \
    AZURE_AI_ENDPOINT="https://imageeastus2-resource.services.ai.azure.com/openai/v1" \
    AZURE_AI_API_KEY="<YOUR_AZURE_AI_FOUNDRY_API_KEY>" \
    AZURE_AI_DEPLOYMENT="gpt-image-2.5-flare" \
    AZURE_RATE_LIMIT_RPM="2" \
    OTEL_EXPORTER_OTLP_ENDPOINT="<YOUR_GRAFANA_OTLP_ENDPOINT>" \
    OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <YOUR_BASE64_TOKEN>" \
    ALLOWED_ORIGINS="http://localhost:3000,https://*.vercel.app,https://your-custom-domain.com"
```

#### Option B: Creating a Fresh Container App

```bash
# 1. Create the Container Apps Managed Environment (if not existing)
az containerapp env create \
  --name instaxoom-env \
  --resource-group rg-instaxoom-prod \
  --location eastus2

# 2. Deploy Container App with scale-to-zero enabled
az containerapp create \
  --name instaxoom-backend \
  --resource-group rg-instaxoom-prod \
  --environment instaxoom-env \
  --image acrinstaxoom.azurecr.io/instaxoom-backend:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 2 \
  --env-vars \
    ENVIRONMENT="production" \
    DATABASE_URL="postgresql+asyncpg://<username>:<password>@<endpoint-id>.neon.tech/neondb?sslmode=require" \
    GOOGLE_CLIENT_ID="<YOUR_GOOGLE_CLIENT_ID>.apps.googleusercontent.com" \
    ADMIN_EMAILS="<YOUR_ADMIN_EMAIL@gmail.com>" \
    SECRET_KEY="$(openssl rand -hex 32)" \
    JWT_ALGORITHM="HS256" \
    JWT_EXPIRE_MINUTES="10080" \
    ENGINE="azure" \
    AZURE_AI_ENDPOINT="https://imageeastus2-resource.services.ai.azure.com/openai/v1" \
    AZURE_AI_API_KEY="<YOUR_AZURE_AI_FOUNDRY_API_KEY>" \
    AZURE_AI_DEPLOYMENT="gpt-image-2.5-flare" \
    AZURE_RATE_LIMIT_RPM="2" \
    OTEL_EXPORTER_OTLP_ENDPOINT="<YOUR_GRAFANA_OTLP_ENDPOINT>" \
    OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <YOUR_BASE64_TOKEN>" \
    ALLOWED_ORIGINS="http://localhost:3000,https://*.vercel.app,https://your-custom-domain.com"
```

---

### Step 4: Verify Deployment, Version & Build Timestamp

1. **Stream Live Container App Logs:**
   ```bash
   az containerapp logs show \
     --name instaxoom-backend \
     --resource-group rg-instaxoom-prod \
     --follow
   ```
   > Look for the following startup confirmation lines:
   > - `Database tables initialized successfully.` *(Neon PostgreSQL tables created)*
   > - `Application startup complete.`
   > - `Uvicorn running on http://0.0.0.0:8000`

2. **Retrieve the Public Ingress FQDN:**
   ```bash
   FQDN=$(az containerapp show \
     --name instaxoom-backend \
     --resource-group rg-instaxoom-prod \
     --query properties.configuration.ingress.fqdn \
     --output tsv)
   echo "https://$FQDN"
   ```
   *Example output: `https://instaxoom-backend.yellowcliff-12345678.eastus2.azurecontainerapps.io`*

3. **Query the Live Status & Version Validation Endpoint (`/health` or `/api/status`):**
   ```bash
   curl -s https://$FQDN/health | python3 -m json.tool
   # Or: curl -s https://$FQDN/api/status | python3 -m json.tool
   ```
   **Expected Response:**
   ```json
   {
     "status": "healthy",
     "service": "instaXoom",
     "environment": "production",
     "version": "1.0.0",
     "commit_sha": "991715c",
     "build_time": "2026-10-12T20:10:55Z",
     "started_at": "2026-10-12T20:11:30.123456+00:00",
     "checked_at": "2026-10-12T20:12:05.654321+00:00",
     "uptime_seconds": 35.53,
     "engine": "azure",
     "telemetry_enabled": true
   }
   ```

---

## 3. Configuring the Frontend (Vercel)

Configure the environment variables in your Vercel Project Settings ($\rightarrow$ **Settings** $\rightarrow$ **Environment Variables**):

| Variable | Recommended Value | Description |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | `https://<YOUR_BACKEND_FQDN>` | Azure Container App backend URL |
| `NEXT_PUBLIC_APP_URL` | `https://your-app.vercel.app` | Public URL of the frontend |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | `xxx.apps.googleusercontent.com` | Google Cloud OAuth 2.0 Web Client ID |
| `NEXT_PUBLIC_ENGINE` | `azure` | Locks UI to Azure Cloud mode |

---

## 4. Google Cloud Console OAuth Setup

To enable Google Sign-In on both local development and production:

1. Open [Google Cloud Console](https://console.cloud.google.com/) $\rightarrow$ **APIs & Services** $\rightarrow$ **Credentials**.
2. Select your **OAuth 2.0 Client ID** (Web application type).
3. Under **Authorized JavaScript origins**, add:
   - `http://localhost:3000`
   - `http://127.0.0.1:3000`
   - `https://<your-project>.vercel.app`
   - `https://your-custom-domain.com` (if applicable)
4. Under **Authorized redirect URIs**, add:
   - `http://localhost:3000`
   - `https://<your-project>.vercel.app`
5. Save changes (takes ~2-5 minutes to propagate across Google's edge CDN).
