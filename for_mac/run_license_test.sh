#!/bin/bash
# =============================================================================
# EyesRhythm — rehearse first-run activation against Dodo Payments TEST mode
# =============================================================================
#
# Why this exists: the license gate only switches itself on in a packaged
# build (sys.frozen), and live activation costs real money and burns one of
# the key's activation slots. This script forces the gate on from source and
# points it at test.dodopayments.com instead.
#
# Test mode and live mode are separate environments in Dodo, so a test
# product has a DIFFERENT product id than the live one. That id must be
# passed in, otherwise the app compares the test key against the live id and
# rejects it with a misleading "this key is for the other OS" message.
#
# Usage:
#   ./for_mac/run_license_test.sh pdt_TEST_ID_FOR_MAC
#   ./for_mac/run_license_test.sh pdt_TEST_ID_FOR_MAC --reset
#
# --reset forgets the previous test activation so the gate appears again.
# Note that each activation consumes one slot on the key in Dodo.
#
# Getting the key: test-mode purchases do NOT send email. Read the key from
# Dashboard (test mode) -> License Keys, or append a redirect_url to the
# checkout link so the key comes back as a query parameter.
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

TEST_PRODUCT="${1:-$EYERHYTHM_TEST_PRODUCT_MAC}"
if [ -z "$TEST_PRODUCT" ]; then
    echo "Missing test-mode product id."
    echo
    echo "  ./for_mac/run_license_test.sh pdt_YOUR_TEST_PRODUCT_ID"
    echo
    echo "Find it in the Dodo dashboard with the test-mode toggle ON."
    echo "The live id in app/license.py will NOT work against test mode."
    exit 1
fi

# Keep the rehearsal away from the real activation record.
TEST_LICENSE_FILE="$HOME/.eyerhythm_blinkcounter/license.test.json"

if [ "$2" = "--reset" ] || [ "$1" = "--reset" ]; then
    rm -f "$TEST_LICENSE_FILE"
    echo "Cleared previous test activation."
fi

if [ -d "$ROOT/EyeRhythm" ]; then
    # shellcheck disable=SC1091
    source "$ROOT/EyeRhythm/bin/activate"
elif [ -d "$ROOT/.venv" ]; then
    # shellcheck disable=SC1091
    source "$ROOT/.venv/bin/activate"
else
    echo "No virtual environment found. Run ./for_mac/setup.sh first."
    exit 1
fi

export EYERHYTHM_DODO_TEST=1
export EYERHYTHM_DODO_PRODUCT_MAC="$TEST_PRODUCT"
export EYERHYTHM_LICENSE_FILE="$TEST_LICENSE_FILE"

echo "=============================================="
echo "  Dodo TEST mode activation rehearsal"
echo "  API         : https://test.dodopayments.com"
echo "  Product id  : $TEST_PRODUCT"
echo "  License file: $TEST_LICENSE_FILE"
echo "=============================================="
echo "No real money moves. Live keys will NOT work here."
echo

exec python -m app.main --require-license "${@:2}"
