#!/bin/bash
# Boot a disposable QEMU VM running Lumbergh for interactive E2E testing.
# Same VM as e2e-vm.sh but stays running so you can run tests repeatedly.
#
# Usage:
#   ./test/start-test-server.sh              # build wheel from source
#   INSTALL_FROM_PYPI=1 ./test/start-test-server.sh  # install from PyPI
#
# Then in another terminal:
#   pytest test/e2e/ --base-url=http://localhost:18420 -v
#   pytest test/e2e-ui/ --base-url=http://localhost:18420 -v
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run the VM script but override to stop after service is up
# by setting a marker env var that we check
export E2E_SERVER_MODE=1
exec "$SCRIPT_DIR/e2e-vm.sh"
