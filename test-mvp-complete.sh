#!/usr/bin/env bash
# test-mvp-complete.sh
# Comprehensive integration test suite for VIB (Stages 0-8)
# Tests MVP (0-4) and advanced features (5-8) with real API calls
#
# This is the main entry point that calls the modular test suite.
# Individual stage tests are located in the tests/ directory.

set -euo pipefail

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Forward all arguments to the stage runner
exec "$SCRIPT_ROOT/tests/stage_runner.sh" "$@"
