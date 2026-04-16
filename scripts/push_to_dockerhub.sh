#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# push_to_dockerhub.sh
#
# Build the image locally and push it to Docker Hub.
# Run this on your local machine BEFORE deploying to EC2.
#
# Usage:
#   chmod +x scripts/push_to_dockerhub.sh
#   ./scripts/push_to_dockerhub.sh yourdockerhubname
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

DOCKERHUB_USER="${1:?Usage: $0 <dockerhub-username>}"
IMAGE_NAME="wiki-qa"
TAG="latest"
FULL_IMAGE="${DOCKERHUB_USER}/${IMAGE_NAME}:${TAG}"

echo "==> Building image: ${FULL_IMAGE}"
docker build -t "${FULL_IMAGE}" .

echo "==> Logging in to Docker Hub (enter your password when prompted)"
docker login --username "${DOCKERHUB_USER}"

echo "==> Pushing image to Docker Hub..."
docker push "${FULL_IMAGE}"

echo ""
echo "✅ Done! Image available at: https://hub.docker.com/r/${DOCKERHUB_USER}/${IMAGE_NAME}"
echo ""
echo "Next steps on EC2:"
echo "  1. SSH into your EC2 instance"
echo "  2. Run:  ./scripts/ec2_deploy.sh ${FULL_IMAGE} <EC2_PUBLIC_IP>"
