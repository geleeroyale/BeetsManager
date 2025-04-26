import os
import logging
import subprocess
import sqlite3
import tempfile
import base64
from pathlib import Path
import json
import yaml
from flask import current_app, session

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define default paths relative to home if env vars are not set
DEFAULT_BEETS_CONFIG_DIR = Path(os.path.expanduser("~")) / ".config" / "beets"
DEFAULT_CONFIG_PATH = DEFAULT_BEETS_CONFIG_DIR / "config.yaml"
DEFAULT_DB_PATH = DEFAULT_BEETS_CONFIG_DIR / "library.db"

def get_beets_config_path():
    """Get the path to the beets config file, prioritizing ENV."""
    return Path(os.environ.get("BEETS_CONFIG_PATH", DEFAULT_CONFIG_PATH))

def get_beets_db_path():
    """Get the path to the beets database, derived from config path or ENV."""
    # If BEETS_CONFIG_PATH is set, assume db is in the same directory
    config_path_str = os.environ.get("BEETS_CONFIG_PATH")
    if config_path_str:
        config_path = Path(config_path_str)
        # Assume library.db is in the same directory as config.yaml
        # This might need adjustment if user has a non-standard setup
        return config_path.parent / "library.db" 
    else:
        # Fallback to default if env var is not set
        return DEFAULT_DB_PATH

def check_beets_config():
    """Check if beets is configured correctly."""
    # Check local configuration
    config_path = get_beets_config_path()
    db_path = get_beets_db_path()
    
    config_exists = config_path.exists()
    db_exists = db_path.exists()
    
    # Check if beets command is available
    try:
        subprocess.run(["beet", "--version"], capture_output=True, text=True, check=True)
        beets_installed = True
    except (subprocess.SubprocessError, FileNotFoundError):
        beets_installed = False
    
    return {
        "config_exists": config_exists,
        "db_exists": db_exists,
        "beets_installed": beets_installed,
        "config_path": str(config_path), # Return as string
        "db_path": str(db_path),     # Return as string
    }

def connect_db():
    """Connect to the beets database."""
    # Connect to local database
    db_path = get_beets_db_path()
    if not db_path.exists():
        raise FileNotFoundError(f"Beets database not found at {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_item_count():
    """Get the total number of items in the library."""
    conn = connect_db()
    try:
        cursor = conn.cursor()
        count = cursor.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        return count
    except Exception as e:
        logger.error(f"Error counting items: {str(e)}")
        raise
    finally:
        conn.close()

def get_library_items(page=1, limit=50, sort='artist'):
    """Get a paginated list of library items."""
    conn = connect_db()
    try:
        cursor = conn.cursor()
        offset = (page - 1) * limit
        
        valid_sorts = {
            'artist': 'artist',
            'album': 'album',
            'title': 'title',
            'year': 'year',
            'added': 'added'
        }
        
        sort_field = valid_sorts.get(sort, 'artist')
        
        query = f"""
            SELECT id, title, artist, album, year, length, format, bitrate, albumartist
            FROM items
            ORDER BY {sort_field}
            LIMIT ? OFFSET ?
        """
        
        rows = cursor.execute(query, (limit, offset)).fetchall()
        
        items = []
        for row in rows:
            item = dict(row)
            # Format length in minutes:seconds
            if 'length' in item and item['length']:
                minutes, seconds = divmod(int(item['length']), 60)
                item['length_formatted'] = f"{minutes}:{seconds:02d}"
            items.append(item)
        
        return items
    except Exception as e:
        logger.error(f"Error fetching library items: {str(e)}")
        raise
    finally:
        conn.close()

def search_library(query):
    """Search the library with a query string."""
    if not query:
        return []
    
    conn = connect_db()
    try:
        cursor = conn.cursor()
        # Build search query
        search_query = """
            SELECT id, title, artist, album, year, length, format, bitrate, albumartist
            FROM items
            WHERE title LIKE ? OR artist LIKE ? OR album LIKE ? OR albumartist LIKE ?
            ORDER BY artist, album, track
            LIMIT 100
        """
        
        pattern = f"%{query}%"
        rows = cursor.execute(search_query, (pattern, pattern, pattern, pattern)).fetchall()
        
        results = []
        for row in rows:
            item = dict(row)
            # Format length in minutes:seconds
            if 'length' in item and item['length']:
                minutes, seconds = divmod(int(item['length']), 60)
                item['length_formatted'] = f"{minutes}:{seconds:02d}"
            results.append(item)
        
        return results
    except Exception as e:
        logger.error(f"Error searching library: {str(e)}")
        raise
    finally:
        conn.close()

def get_artists():
    """Get a list of all artists in the library."""
    conn = connect_db()
    try:
        cursor = conn.cursor()
        query = """
            SELECT DISTINCT artist
            FROM items
            ORDER BY artist
        """
        
        rows = cursor.execute(query).fetchall()
        artists = [row[0] for row in rows if row[0]]
        
        return artists
    except Exception as e:
        logger.error(f"Error fetching artists: {str(e)}")
        raise
    finally:
        conn.close()

def get_albums(artist=None):
    """Get a list of albums, optionally filtered by artist."""
    conn = connect_db()
    try:
        cursor = conn.cursor()
        
        if artist:
            query = """
                SELECT DISTINCT album, artist, albumartist, year
                FROM items
                WHERE artist = ? OR albumartist = ?
                ORDER BY year DESC, album
            """
            rows = cursor.execute(query, (artist, artist)).fetchall()
        else:
            query = """
                SELECT DISTINCT album, artist, albumartist, year
                FROM items
                ORDER BY year DESC, album
            """
            rows = cursor.execute(query).fetchall()
        
        albums = [dict(row) for row in rows if row['album']]
        
        return albums
    except Exception as e:
        logger.error(f"Error fetching albums: {str(e)}")
        raise
    finally:
        conn.close()

def get_item_details(item_id):
    """Get detailed information for a specific item."""
    conn = connect_db()
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM items WHERE id = ?"
        row = cursor.execute(query, (item_id,)).fetchone()
        
        if not row:
            return None
        
        # Convert row to dictionary
        item = dict(row)
        
        # Format length in minutes:seconds
        if 'length' in item and item['length']:
            minutes, seconds = divmod(int(item['length']), 60)
            item['length_formatted'] = f"{minutes}:{seconds:02d}"
        
        return item
    except Exception as e:
        logger.error(f"Error fetching item details: {str(e)}")
        raise
    finally:
        conn.close()

def get_album_art(item_id):
    """Get album art for a specific item using beets command."""
    try:
        # Get item details to get the album
        item = get_item_details(item_id)
        if not item or not item.get('album'):
            return None
        
        # Get album art locally
        cmd = ["beet", "albumart", "-o", "-", item.get('album')]
        
        # Try to be more specific if we have artist information
        if item.get('albumartist'):
            cmd[-1] = f"album:{item.get('album')} albumartist:{item.get('albumartist')}"
        elif item.get('artist'):
            cmd[-1] = f"album:{item.get('album')} artist:{item.get('artist')}"
        
        try:
            result = subprocess.run(cmd, capture_output=True, check=True)
            # Convert binary image data to base64 for embedding in HTML
            image_data = base64.b64encode(result.stdout).decode('utf-8')
            return image_data
        except subprocess.CalledProcessError:
            logger.warning(f"Failed to get album art for item {item_id}")
            return None
    except Exception as e:
        logger.error(f"Error getting album art: {str(e)}")
        return None

def execute_beets_command(command):
    """Execute a beets command and return the result."""
    if not command.strip():
        return "No command provided"
    
    # Execute command locally
    cmd_parts = ["beet"] + command.split()
    
    try:
        # Run the command
        result = subprocess.run(cmd_parts, capture_output=True, text=True)
        
        # Build response
        response = {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "success": result.returncode == 0
        }
        
        return response
    except Exception as e:
        logger.error(f"Error executing beets command: {str(e)}")
        raise

def import_music(path):
    """Import music files into the beets library."""
    if not path or not os.path.exists(path):
        return {"success": False, "message": f"Path does not exist: {path}"}
    
    # Prepare the import command
    cmd = ["beet", "import", path]
    
    try:
        # Run the command - note that this might require user interaction
        # which won't work well in a web interface
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Build response
        response = {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "success": result.returncode == 0
        }
        
        return response
    except Exception as e:
        logger.error(f"Error importing music: {str(e)}")
        raise

# New functions for configuration management

def read_beets_config():
    """Read and parse the beets config file."""
    config_path = get_beets_config_path()
    if not config_path.exists():
        return {"error": f"Config file not found at {config_path}"}
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config or {}
    except Exception as e:
        logger.error(f"Error reading beets config: {str(e)}")
        return {"error": str(e)}

def update_beets_config(config_updates):
    """Update the beets configuration file with new settings."""
    config_path = get_beets_config_path()
    
    try:
        # Read existing config
        current_config = {}
        if config_path.exists():
            with open(config_path, 'r') as f:
                current_config = yaml.safe_load(f) or {}
        
        # Create parent directories if they don't exist
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Update config with new values (deep merge)
        updated_config = deep_update(current_config, config_updates)
        
        # Write updated config back to file
        with open(config_path, 'w') as f:
            yaml.dump(updated_config, f, default_flow_style=False, sort_keys=False)
        
        return {"success": True, "message": "Configuration updated successfully"}
    except Exception as e:
        logger.error(f"Error updating beets config: {str(e)}")
        return {"success": False, "error": str(e)}

def deep_update(source, overrides):
    """Deep update of nested dictionaries."""
    for key, value in overrides.items():
        if isinstance(value, dict) and key in source and isinstance(source[key], dict):
            source[key] = deep_update(source[key], value)
        else:
            source[key] = value
    return source

def get_beets_plugins():
    """Get a list of available beets plugins."""
    try:
        result = subprocess.run(["beet", "pluginlist"], capture_output=True, text=True)
        if result.returncode != 0:
            return {"success": False, "error": result.stderr}
        
        # Parse the output to get plugin list
        lines = result.stdout.strip().split('\n')
        plugins = []
        
        for line in lines:
            if ':' in line:
                name, description = line.split(':', 1)
                plugins.append({
                    "name": name.strip(),
                    "description": description.strip()
                })
        
        return {"success": True, "plugins": plugins}
    except Exception as e:
        logger.error(f"Error getting beets plugins: {str(e)}")
        return {"success": False, "error": str(e)}

def get_beets_info():
    """Get information about the beets installation."""
    try:
        version_result = subprocess.run(["beet", "version"], capture_output=True, text=True)
        config_result = subprocess.run(["beet", "config"], capture_output=True, text=True)
        
        return {
            "success": True,
            "version": version_result.stdout.strip() if version_result.returncode == 0 else "Unknown",
            "config": config_result.stdout if config_result.returncode == 0 else "Error fetching configuration"
        }
    except Exception as e:
        logger.error(f"Error getting beets info: {str(e)}")
        return {"success": False, "error": str(e)}
