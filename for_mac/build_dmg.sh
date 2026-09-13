#!/bin/bash
# =============================================================================
# EyesRhythm — one-shot Mac installer: build .app, wrap as .dmg, clean leftovers
# =============================================================================
#
# Output (only shippable file left in dist/ for Mac):
#   dist/EyesRhythm.dmg
#
# Keep the .app as well:
#   KEEP_APP=1 ./for_mac/build_dmg.sh
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

"$SCRIPT_DIR/build_mac.sh"
"$SCRIPT_DIR/make_dmg.sh"
