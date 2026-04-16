#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# ec2_setup.sh
#
# Run this ONCE on a fresh EC2 t2.micro (Ubuntu 22.04) to:
#   1. Add 2 GB swap (critical for t2.micro — only 1 GB RAM)
#   2. Install Docker + Docker Compose
#   3. Clone the repo (or pull the pre-built image)
#   4. Start the application
#
# Usage (on EC2 after SSH):
#   chmod +x scripts/ec2_setup.sh
#   ./scripts/ec2_setup.sh <DOCKERHUB_IMAGE> <EC2_PUBLIC_IP>
#
# Example:
#   ./scripts/ec2_setup.sh johndoe/wiki-qa:latest 54.123.45.67
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

DOCKER_IMAGE="${1:?Arg 1 required: Docker Hub image (e.g. johndoe/wiki-qa:latest)}"
EC2_PUBLIC_IP="${2:?Arg 2 required: EC2 public IP address}"

echo "========================================================"
echo " Wikipedia Smart QA — EC2 Setup"
echo " Image : ${DOCKER_IMAGE}"
echo " IP    : ${EC2_PUBLIC_IP}"
echo "========================================================"

# ── 1. Swap file ─────────────────────────────────────────────────────────────
echo ""
echo "==> [1/4] Setting up 2 GB swap file..."
if swapon --show | grep -q /swapfile; then
    echo "    Swap already active — skipping."
else
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    # Persist across reboots
    grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "    Swap active: $(free -h | grep Swap)"
fi

# ── 2. Docker ─────────────────────────────────────────────────────────────────
echo ""
echo "==> [2/4] Installing Docker..."
if command -v docker &>/dev/null; then
    echo "    Docker already installed: $(docker --version)"
else
    sudo apt-get update -qq
    sudo apt-get install -y --no-install-recommends docker.io docker-compose-plugin curl
    sudo usermod -aG docker "${USER}"
    sudo systemctl enable --now docker
    echo "    Docker installed: $(docker --version)"
fi

# ── 3. Pull image ─────────────────────────────────────────────────────────────
echo ""
echo "==> [3/4] Pulling Docker image: ${DOCKER_IMAGE}..."
sudo docker pull "${DOCKER_IMAGE}"

# ── 4. Write .env and start ───────────────────────────────────────────────────
echo ""
echo "==> [4/4] Writing .env and starting services..."

cat > .env <<EOF
DOCKER_IMAGE=${DOCKER_IMAGE}
BACKEND_URL=http://${EC2_PUBLIC_IP}:8000
EOF

# Use sudo because the current shell may not have picked up the docker group yet
sudo docker compose up -d

echo ""
echo "========================================================"
echo " ✅ Deployment complete!"
echo ""
echo "  Streamlit UI  →  http://${EC2_PUBLIC_IP}:8501"
echo "  API docs      →  http://${EC2_PUBLIC_IP}:8000/docs"
echo "  Health check  →  http://${EC2_PUBLIC_IP}:8000/health"
echo ""
echo "  View logs:  sudo docker compose logs -f"
echo "========================================================"
