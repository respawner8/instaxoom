# Azure Cloud Deployment Guide: GPT-Image-2.5 Flare

This guide explains how to deploy the **instaXoom** backend to **Azure Container Apps** using the **Microsoft Azure AI Foundry** `gpt-image-2.5-flare` model.

---

## 1. Architecture Summary

- **Model:** `gpt-image-2.5-flare` hosted on Microsoft Azure AI Foundry.
- **Constraints Handled:**
  - **Single Photo:** The cloud engine accepts 1 portrait photo (auto-framed and cropped to 4:5 headshot).
  - **2 RPM Rate Limit:** The backend enforces a sliding-window rate limiter (max 2 images/min), and the UI runs an automatic 30-second cooldown timer between requests to prevent HTTP 429s.
- **Compute:** Azure Container Apps (Consumption Plan) with **Scale to Zero** (`--min-replicas 0`). Idle cost is **$0.00/month**.

---

## 2. Azure Deployment Steps

### Step 1: Login & Prepare Resource Group
```bash
# 1. Login to Azure
az login

# 2. Set your default subscription (if multiple)
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"

# 3. Create Resource Group in East US 2 (same region as Foundry deployment)
az group create --name rg-instaxoom-prod --location eastus2
```

### Step 2: Create Azure Container Registry (ACR) & Build Image
```bash
# 1. Create a lightweight ACR
az acr create \
  --resource-group rg-instaxoom-prod \
  --name acrinstaxoom \
  --sku Basic \
  --admin-enabled true

# 2. Build and push the backend container directly in Azure (no local Docker daemon required)
az acr build \
  --registry acrinstaxoom \
  --image instaxoom-backend:latest \
  ./backend
```

### Step 3: Deploy to Azure Container Apps
```bash
# 1. Create the Container Apps Managed Environment
az containerapp env create \
  --name instaxoom-env \
  --resource-group rg-instaxoom-prod \
  --location eastus2

# 2. Deploy the backend with environment variables
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
    ENGINE="azure" \
    AZURE_AI_ENDPOINT="https://imageeastus2-resource.services.ai.azure.com/api/projects/imageeastus2" \
    AZURE_AI_API_KEY="<YOUR_AZURE_AI_FOUNDRY_API_KEY>" \
    AZURE_AI_DEPLOYMENT="gpt-image-2.5-flare" \
    AZURE_RATE_LIMIT_RPM="2" \
    ALLOWED_ORIGINS="http://localhost:3000,https://*.vercel.app"
```

Once created, note down your Container App URL (FQDN):
```
https://instaxoom-backend.<region>.azurecontainerapps.io
```

---

## 3. Configuring the Frontend (Vercel)

You control whether the frontend runs in **Azure Cloud Mode** or **Local Flux GPU Mode** using environment variables in your Vercel deployment:

### For Azure Cloud Deployment (GPT-Image 2.5 Flare):
In Vercel Project Settings $\rightarrow$ Environment Variables:
```env
NEXT_PUBLIC_ENGINE=azure
NEXT_PUBLIC_API_URL=https://instaxoom-backend.<region>.azurecontainerapps.io
```
- **UI Behavior:**
  - Header displays: `☁️ Azure Cloud • GPT-Image-2.5 Flare`
  - Upload allows: `1 photo max`
  - Cooldown: `30 seconds between generations (2 RPM)`

### For Local GPU Deployment (FLUX.1 + PuLID):
```env
NEXT_PUBLIC_ENGINE=flux
NEXT_PUBLIC_API_URL=https://<your-cloudflare-tunnel>.trycloudflare.com
```
- **UI Behavior:**
  - Header displays: `⚡ Local GPU • FLUX.1 + PuLID`
  - Upload allows: `1 to 5 photos`
  - Cooldown: `None (unlimited)`
