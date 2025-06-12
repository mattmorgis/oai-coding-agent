#!/usr/bin/env bash
# Bootstraps the CloudNativePG operator into the current kube-context.
set -euo pipefail

NAMESPACE="cnpg-system"
CHART_VERSION="0.24.0"

helm repo add cloudnative-pg https://cloudnative-pg.github.io/charts
helm repo update

helm upgrade --install cloudnativepg-operator cloudnative-pg/cloudnative-pg \
  --namespace "$NAMESPACE" --create-namespace \
  --version "$CHART_VERSION" \
  -f $(dirname "$0")/../charts/cloudnativepg-values.yaml \
  --wait --timeout 5m

echo "✅ CloudNativePG operator installed (or already present)."
