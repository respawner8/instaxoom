#!/usr/bin/env bash
# ==============================================================================
# instaXoom Backend Deployment Script (Azure Container Apps)
#
# Usage:
#   ./scripts/deploy-backend.sh [OPTIONS]
#
# Options:
#   --env-file <path>    Path to .env file (default: backend/.env)
#   --resource-group <rg> Resource group (default: rg-instaxoom-prod)
#   --acr-name <name>    ACR name (default: acrinstaxoom)
#   --app-name <name>    Container App name (default: instaxoom-backend)
#   --dry-run            Parse .env and show commands without executing
#   --skip-build         Skip image build and only update environment variables
#   --skip-env           Deploy new image without modifying environment variables
#   -h, --help           Show this help message
# ==============================================================================

set -eo pipefail

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default Configuration
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_ROOT}/backend/.env"
RESOURCE_GROUP="rg-instaxoom-prod"
ACR_NAME="acrinstaxoom"
APP_NAME="instaxoom-backend"
DRY_RUN=false
SKIP_BUILD=false
SKIP_ENV=false

# Parse command line flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --resource-group)
      RESOURCE_GROUP="$2"
      shift 2
      ;;
    --acr-name)
      ACR_NAME="$2"
      shift 2
      ;;
    --app-name)
      APP_NAME="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --skip-build)
      SKIP_BUILD=true
      shift
      ;;
    --skip-env)
      SKIP_ENV=true
      shift
      ;;
    -h|--help)
      echo -e "${BOLD}instaXoom Backend Deployment Tool${NC}"
      echo ""
      echo "Usage: ./scripts/deploy-backend.sh [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --env-file <path>      Path to local .env file (default: backend/.env)"
      echo "  --resource-group <rg>  Azure Resource Group (default: rg-instaxoom-prod)"
      echo "  --acr-name <name>      Azure Container Registry name (default: acrinstaxoom)"
      echo "  --app-name <name>      Azure Container App name (default: instaxoom-backend)"
      echo "  --dry-run              Inspect variables and commands without running"
      echo "  --skip-build           Deploy existing image; update config & env vars only"
      echo "  --skip-env             Deploy image without pushing new env vars"
      echo "  -h, --help             Show this help message"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      echo "Run './scripts/deploy-backend.sh --help' for usage."
      exit 1
      ;;
  esac
done

echo -e "${CYAN}${BOLD}======================================================${NC}"
echo -e "${CYAN}${BOLD}       instaXoom Backend Deployment to Azure          ${NC}"
echo -e "${CYAN}${BOLD}======================================================${NC}"

# Check dependencies
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}[ERROR] 'python3' is required to parse .env safely.${NC}"
  exit 1
fi

if ! command -v curl &>/dev/null; then
  echo -e "${RED}[ERROR] 'curl' is required for health check verification.${NC}"
  exit 1
fi

if [ "$DRY_RUN" = false ]; then
  if ! command -v az &>/dev/null; then
    echo -e "${RED}[ERROR] Azure CLI ('az') is not installed.${NC}"
    echo "Install it on macOS via: brew install azure-cli"
    echo "Then authenticate via:   az login"
    exit 1
  fi

  # Verify Azure Login
  if ! az account show &>/dev/null; then
    echo -e "${YELLOW}[WARNING] Not logged into Azure CLI. Running 'az login'...${NC}"
    az login --output table
  fi

  CURRENT_SUB=$(az account show --query name -o tsv 2>/dev/null || echo "Unknown")
else
  CURRENT_SUB="(Dry Run - Skipped Azure Check)"
fi

echo -e "${BLUE}[Azure Subscription]${NC} ${CURRENT_SUB}"
echo -e "${BLUE}[Resource Group]${NC}    ${RESOURCE_GROUP}"
echo -e "${BLUE}[Container Registry]${NC} ${ACR_NAME}"
echo -e "${BLUE}[Container App]${NC}     ${APP_NAME}"
echo -e "${BLUE}[Environment File]${NC}  ${ENV_FILE}"

# Verify .env file exists
if [ ! -f "$ENV_FILE" ]; then
  echo -e "${RED}[ERROR] Environment file not found at: ${ENV_FILE}${NC}"
  echo "Please create backend/.env or specify --env-file <path>"
  exit 1
fi

# Extract Git Commit & Build Timestamp
COMMIT_SHA=$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo "manual")
BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
IMAGE_TAG="${COMMIT_SHA}-$(date -u +%Y%m%d%H%M%S)"
FULL_IMAGE="${ACR_NAME}.azurecr.io/${APP_NAME}:${IMAGE_TAG}"

echo -e "${BLUE}[Git Commit SHA]${NC}    ${COMMIT_SHA}"
echo -e "${BLUE}[Build Timestamp]${NC}   ${BUILD_TIME}"
echo -e "${BLUE}[New Image Tag]${NC}     ${IMAGE_TAG}"
echo "------------------------------------------------------"

# Parse .env into arguments array safely using Python
# Strips whitespace, quotes, comments, handles spaces/equals in values, and sets production environment
ENV_PAIRS=()
while IFS= read -r -d '' item; do
  ENV_PAIRS+=("$item")
done < <(python3 -c '
import sys

env_file = sys.argv[1]
commit_sha = sys.argv[2]
build_time = sys.argv[3]

env_dict = {}
with open(env_file, "r") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            # Strip matching surrounding double or single quotes
            if (v.startswith("\"") and v.endswith("\"")) or (v.startswith("\x27") and v.endswith("\x27")):
                v = v[1:-1]
            env_dict[k] = v

# Ensure deployment metadata and production environment
env_dict["ENVIRONMENT"] = "production"
env_dict["COMMIT_SHA"] = commit_sha
env_dict["BUILD_TIME"] = build_time

# Output null-delimited key=value pairs for safe bash reading
for k, v in env_dict.items():
    sys.stdout.buffer.write(f"{k}={v}\0".encode("utf-8"))
' "$ENV_FILE" "$COMMIT_SHA" "$BUILD_TIME")

echo -e "${GREEN}[OK] Successfully parsed ${#ENV_PAIRS[@]} environment variables from ${ENV_FILE}${NC}"

if [ "$DRY_RUN" = true ]; then
  echo ""
  echo -e "${YELLOW}${BOLD}[DRY RUN] Summary of planned actions:${NC}"
  echo "1. Build and push image in Azure Container Registry:"
  echo "   az acr build --registry ${ACR_NAME} \\"
  echo "     --image ${APP_NAME}:${IMAGE_TAG} \\"
  echo "     --image ${APP_NAME}:latest \\"
  echo "     --build-arg COMMIT_SHA=${COMMIT_SHA} \\"
  echo "     --build-arg BUILD_TIME=${BUILD_TIME} \\"
  echo "     ${REPO_ROOT}/backend"
  echo ""
  echo "2. Update Azure Container App revision & environment variables:"
  echo "   az containerapp update --name ${APP_NAME} --resource-group ${RESOURCE_GROUP} \\"
  echo "     --image ${FULL_IMAGE} \\"
  echo "     --set-env-vars <${#ENV_PAIRS[@]} parsed variables>"
  echo ""
  echo "Variables to be deployed:"
  for pair in "${ENV_PAIRS[@]}"; do
    key="${pair%%=*}"
    # Mask sensitive keys
    if [[ "$key" =~ (KEY|SECRET|PASSWORD|HEADERS|DATABASE_URL|CONNECTION_STRING) ]]; then
      echo "   $key=******** [PROTECTED]"
    else
      echo "   $pair"
    fi
  done
  echo ""
  echo -e "${GREEN}[DRY RUN] Completed without making any changes.${NC}"
  exit 0
fi

# Step 1: Cloud Build via ACR
if [ "$SKIP_BUILD" = false ]; then
  echo ""
  echo -e "${BOLD}${BLUE}==> [1/3] Building & pushing container in ACR (${ACR_NAME})...${NC}"
  az acr build \
    --registry "${ACR_NAME}" \
    --image "${APP_NAME}:${IMAGE_TAG}" \
    --image "${APP_NAME}:latest" \
    --build-arg COMMIT_SHA="${COMMIT_SHA}" \
    --build-arg BUILD_TIME="${BUILD_TIME}" \
    "${REPO_ROOT}/backend"
  echo -e "${GREEN}[OK] Image built and pushed successfully: ${FULL_IMAGE}${NC}"
else
  echo -e "${YELLOW}[SKIP] Skipping container build as requested (--skip-build).${NC}"
  FULL_IMAGE="${ACR_NAME}.azurecr.io/${APP_NAME}:latest"
fi

# Step 2: Deploy to Azure Container App
echo ""
echo -e "${BOLD}${BLUE}==> [2/3] Updating Azure Container App (${APP_NAME})...${NC}"

UPDATE_ARGS=(
  --name "${APP_NAME}"
  --resource-group "${RESOURCE_GROUP}"
)

if [ "$SKIP_BUILD" = false ]; then
  UPDATE_ARGS+=(--image "${FULL_IMAGE}")
fi

if [ "$SKIP_ENV" = false ]; then
  UPDATE_ARGS+=(--set-env-vars "${ENV_PAIRS[@]}")
fi

az containerapp update "${UPDATE_ARGS[@]}"

echo -e "${GREEN}[OK] Azure Container App revision created.${NC}"

# Step 3: Health & Version Verification
echo ""
echo -e "${BOLD}${BLUE}==> [3/3] Validating deployment & querying health status...${NC}"

INGRESS_FQDN=$(az containerapp show \
  --name "${APP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query "properties.configuration.ingress.fqdn" \
  -o tsv 2>/dev/null || echo "")

if [ -z "$INGRESS_FQDN" ]; then
  echo -e "${RED}[WARNING] Could not retrieve ingress FQDN for ${APP_NAME}.${NC}"
  exit 0
fi

HEALTH_URL="https://${INGRESS_FQDN}/health"
echo -e "${BLUE}Target Health Endpoint:${NC} ${HEALTH_URL}"
echo "Waiting for new revision to become ready..."

MAX_RETRIES=15
RETRY_COUNT=0
SUCCESS=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  RETRY_COUNT=$((RETRY_COUNT + 1))
  sleep 4

  RESPONSE=$(curl -s -m 10 "$HEALTH_URL" 2>/dev/null || echo "")
  if [ -n "$RESPONSE" ] && echo "$RESPONSE" | grep -q '"status": "healthy"'; then
    SUCCESS=true
    break
  fi
  echo "  Attempt $RETRY_COUNT/$MAX_RETRIES: revision warming up..."
done

echo ""
if [ "$SUCCESS" = true ]; then
  echo -e "${GREEN}${BOLD}======================================================${NC}"
  echo -e "${GREEN}${BOLD}         DEPLOYMENT SUCCESSFUL & VERIFIED!            ${NC}"
  echo -e "${GREEN}${BOLD}======================================================${NC}"
  echo -e "${CYAN}Live Endpoint Response (${HEALTH_URL}):${NC}"
  echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
  echo ""
  echo -e "${BOLD}Backend Ingress:${NC}  https://${INGRESS_FQDN}"
  echo -e "${BOLD}Health Query:${NC}     curl https://${INGRESS_FQDN}/health"
  echo -e "${BOLD}Status Query:${NC}     curl https://${INGRESS_FQDN}/api/status"
else
  echo -e "${YELLOW}[NOTICE] Endpoint did not respond within timeout, but deployment was triggered.${NC}"
  echo "You can check status at: curl -s ${HEALTH_URL}"
fi
