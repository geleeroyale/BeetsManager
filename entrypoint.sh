#!/bin/bash
set -e

# Add common Python binary locations to PATH
export PATH="/usr/local/bin:/root/.local/bin:$PATH"

# Print environment information for debugging
echo "=== Environment Information ==="
echo "PATH: $PATH"
echo "Python version: $(python --version 2>&1)"
echo "Working directory: $(pwd)"

# Check if beet is in PATH
if command -v beet >/dev/null 2>&1; then
    echo "Beet found at: $(which beet)"
    echo "Beet version: $(beet --version 2>&1)"
else
    echo "WARNING: beet command not found in PATH!"
    # Try to find it
    find / -name beet -type f 2>/dev/null || echo "Could not find beet executable"
fi

# Execute the main command
echo "Starting application: $@"
exec "$@" 