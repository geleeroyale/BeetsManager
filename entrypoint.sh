#!/bin/bash
set -e

# Add common Python binary locations to PATH
export PATH="/usr/local/bin:/root/.local/bin:$PATH"

# Handle user/group permissions for mounted volumes
# Default to root (1000:1000) if not specified
PUID=${PUID:-1000}
PGID=${PGID:-1000}
USER=${USER:-beets}

# Define the container config path
CONTAINER_CONFIG_DIR="/config"

echo "=== User/Group Information ==="
echo "User ID (PUID): $PUID"
echo "Group ID (PGID): $PGID"

# Create the user/group if they don't exist
if ! getent group $PGID >/dev/null; then
    groupadd -g $PGID $USER
    echo "Created group $USER with GID $PGID"
fi

if ! getent passwd $PUID >/dev/null; then
    useradd -u $PUID -g $PGID -d /home/$USER -s /bin/bash -m $USER
    echo "Created user $USER with UID $PUID"
else
    # User exists, make sure it's in the correct group
    usermod -g $PGID $(getent passwd $PUID | cut -d: -f1)
    echo "Updated user $(getent passwd $PUID | cut -d: -f1) to group $PGID"
fi

# List the user/group for verification
id $(getent passwd $PUID | cut -d: -f1)

# Create or update ownership of key directories
# Only do this if we're running as root
if [ "$(id -u)" = "0" ]; then
    # Create the config directory if it doesn't exist
    mkdir -p $CONTAINER_CONFIG_DIR
    chown $PUID:$PGID $CONTAINER_CONFIG_DIR
    echo "Ensured config directory $CONTAINER_CONFIG_DIR exists and is owned by $PUID:$PGID"
    
    # Music directory - check if it's mounted
    if [ -d "/music" ]; then
        chown -R $PUID:$PGID /music
        echo "Updated ownership of music directory /music to $PUID:$PGID"
    fi
    
    # Downloads directory - check if it's mounted
    if [ -d "/downloads" ]; then
        chown -R $PUID:$PGID /downloads
        echo "Updated ownership of downloads directory /downloads to $PUID:$PGID"
    fi
fi

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

# If PUID/PGID is set and we're running as root, switch to the created user
if [ "$(id -u)" = "0" ] && [ "$PUID" != "0" ]; then
    echo "Switching to user $(getent passwd $PUID | cut -d: -f1) (UID: $PUID, GID: $PGID)"
    exec gosu $PUID:$PGID "$@"
else
    # Execute the main command as the current user
    echo "Starting application: $@"
    exec "$@" 
fi 