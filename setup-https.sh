#!/usr/bin/env bash
set -euo pipefail

CERT_DIR="${HOME}/.config/lumbergh"
CERT_FILE="${CERT_DIR}/tls.crt"
KEY_FILE="${CERT_DIR}/tls.key"

# Check tailscale is installed
if ! command -v tailscale &>/dev/null; then
  echo "Error: tailscale is not installed."
  echo "Install it from https://tailscale.com/download"
  exit 1
fi

# Check tailscale is connected
if ! tailscale status &>/dev/null; then
  echo "Error: tailscale is not connected. Run 'tailscale up' first."
  exit 1
fi

# Get FQDN
FQDN=$(tailscale status --self --json | python3 -c "import sys,json; print(json.load(sys.stdin)['Self']['DNSName'].rstrip('.'))")

if [ -z "$FQDN" ]; then
  echo "Error: could not determine Tailscale FQDN."
  exit 1
fi

echo "Tailscale FQDN: ${FQDN}"

mkdir -p "$CERT_DIR"

# Generate certs
echo "Generating TLS certs (may require sudo)..."
sudo tailscale cert \
  --cert-file "$CERT_FILE" \
  --key-file "$KEY_FILE" \
  "$FQDN"

sudo chown "$USER" "$CERT_FILE" "$KEY_FILE"

echo ""
echo "Done! Certs written to ${CERT_DIR}/"
echo "Restart the dev server and open:"
echo ""
echo "  https://${FQDN}:5420"
echo ""
