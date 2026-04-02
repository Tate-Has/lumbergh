#!/bin/bash
# Check Node.js version meets minimum requirements (>=20.19.0)
# Sourced by bootstrap.sh and frontend/start.sh

REQUIRED_MAJOR=20
REQUIRED_MINOR=19
REQUIRED_PATCH=0

if ! command -v node &>/dev/null; then
    echo "Error: Node.js is not installed."
    echo "  Recommended: install via nvm (Node Version Manager)"
    echo "  Install nvm: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash"
    echo "  Then: nvm install --lts"
    exit 1
fi

NODE_VERSION=$(node --version | sed 's/^v//')
IFS='.' read -r MAJOR MINOR PATCH <<< "$NODE_VERSION"

if [ "$MAJOR" -lt "$REQUIRED_MAJOR" ] || \
   { [ "$MAJOR" -eq "$REQUIRED_MAJOR" ] && [ "$MINOR" -lt "$REQUIRED_MINOR" ]; } || \
   { [ "$MAJOR" -eq "$REQUIRED_MAJOR" ] && [ "$MINOR" -eq "$REQUIRED_MINOR" ] && [ "$PATCH" -lt "$REQUIRED_PATCH" ]; }; then
    echo "Error: Node.js v${NODE_VERSION} is too old. Lumbergh requires Node.js >= ${REQUIRED_MAJOR}.${REQUIRED_MINOR}.${REQUIRED_PATCH}"
    echo "  Your version: v${NODE_VERSION}"
    if command -v nvm &>/dev/null; then
        echo "  Fix: nvm install --lts && nvm use --lts"
    else
        echo "  Recommended: install nvm, then: nvm install --lts"
        echo "  Install nvm: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash"
    fi
    exit 1
fi
