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
import shutil

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Find the beet executable to ensure it's accessible
BEET_EXECUTABLE = "beet"
# Try to find the full path to beet
beet_path = shutil.which("beet")
if beet_path:
    BEET_EXECUTABLE = beet_path
    logger.info(f"Found beet executable at: {beet_path}")
else:
    # Look in common locations
    for path in ["/usr/local/bin/beet", "/root/.local/bin/beet", "/usr/bin/beet"]:
        if Path(path).exists():
            BEET_EXECUTABLE = path
            logger.info(f"Found beet executable at: {path}")
            break
    else:
        logger.warning("Could not find beet executable in PATH. Using 'beet' and hoping it works.")

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
        subprocess.run([BEET_EXECUTABLE, "--version"], capture_output=True, text=True, check=True)
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
        cmd = [BEET_EXECUTABLE, "albumart", "-o", "-", item.get('album')]
        
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
    cmd_parts = [BEET_EXECUTABLE] + command.split()
    
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
    cmd = [BEET_EXECUTABLE, "import", path]
    
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
        # Handle raw YAML input if provided
        if 'raw_yaml' in config_updates:
            try:
                # Parse the raw YAML and use it as the entire config
                raw_config = yaml.safe_load(config_updates['raw_yaml'])
                if not isinstance(raw_config, dict):
                    return {"success": False, "error": "Invalid YAML: must produce a dictionary"}
                
                # Make sure parent directories exist
                config_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write the parsed YAML directly to the config file
                with open(config_path, 'w') as f:
                    yaml.dump(raw_config, f, default_flow_style=False, sort_keys=False)
                
                return {"success": True, "message": "Configuration updated successfully from raw YAML"}
            except Exception as e:
                logger.error(f"Error parsing raw YAML config: {str(e)}")
                return {"success": False, "error": f"Invalid YAML format: {str(e)}"}
        
        # Standard config update
        # Read existing config
        current_config = {}
        if config_path.exists():
            with open(config_path, 'r') as f:
                current_config = yaml.safe_load(f) or {}
        
        # Create parent directories if they don't exist
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Ensure paths are expanded and absolute (especially for directory)
        if 'directory' in config_updates:
            # Expand user's home directory if using ~
            directory = os.path.expanduser(config_updates['directory'])
            # Convert to absolute path if it's not already
            if not os.path.isabs(directory):
                directory = os.path.abspath(directory)
            config_updates['directory'] = directory
        
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
        result = subprocess.run([BEET_EXECUTABLE, "pluginlist"], capture_output=True, text=True)
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
        version_result = subprocess.run([BEET_EXECUTABLE, "version"], capture_output=True, text=True)
        config_result = subprocess.run([BEET_EXECUTABLE, "config"], capture_output=True, text=True)
        
        return {
            "success": True,
            "version": version_result.stdout.strip() if version_result.returncode == 0 else "Unknown",
            "config": config_result.stdout if config_result.returncode == 0 else "Error fetching configuration"
        }
    except Exception as e:
        logger.error(f"Error getting beets info: {str(e)}")
        return {"success": False, "error": str(e)}

def reset_database():
    """Reset the beets database by moving it to a backup and letting beets recreate it."""
    db_path = get_beets_db_path()
    
    try:
        # Check if database exists
        if not db_path.exists():
            # Just initialize a new database if none exists
            return initialize_database()
            
        # Create a backup with timestamp
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = db_path.with_name(f"library_backup_{timestamp}.db")
        
        # Move the database file to backup
        shutil.move(str(db_path), str(backup_path))
        
        # Initialize a new database
        init_result = initialize_database()
        
        if init_result["success"]:
            return {
                "success": True,
                "message": f"Database reset successfully. Old database backed up to {backup_path}",
                "backup_path": str(backup_path)
            }
        else:
            # If initialization failed, return the error
            init_result["backup_path"] = str(backup_path)
            return init_result
            
    except Exception as e:
        logger.error(f"Error resetting database: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to reset database."
        }

def initialize_database():
    """Initialize a new Beets database."""
    config_path = get_beets_config_path()
    db_path = get_beets_db_path()
    
    try:
        # Make sure the directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # First, check if the config file exists
        if not config_path.exists():
            # Create a basic config file if it doesn't exist
            basic_config = {
                "directory": os.path.expanduser("~/Music"),
                "library": str(db_path),  # Ensure library is a string
                "import": {
                    "copy": True,
                    "write": True
                }
            }
            
            # Create the directory if it doesn't exist
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write the basic config
            with open(config_path, 'w') as f:
                yaml.dump(basic_config, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Created basic config file at {config_path}")
        else:
            # Check and fix the existing config if necessary
            try:
                with open(config_path, 'r') as f:
                    existing_config = yaml.safe_load(f) or {}
                
                # Check if the library setting is properly formatted
                if "library" in existing_config and not isinstance(existing_config["library"], str):
                    # Fix the library setting to be a string
                    existing_config["library"] = str(db_path)
                    # Write the corrected config back
                    with open(config_path, 'w') as f:
                        yaml.dump(existing_config, f, default_flow_style=False, sort_keys=False)
                    logger.info(f"Fixed library setting in config file at {config_path}")
                
                # Ensure library is defined
                if "library" not in existing_config:
                    existing_config["library"] = str(db_path)
                    # Write the updated config back
                    with open(config_path, 'w') as f:
                        yaml.dump(existing_config, f, default_flow_style=False, sort_keys=False)
                    logger.info(f"Added missing library setting to config file at {config_path}")
            except Exception as e:
                logger.error(f"Error checking/fixing existing config: {str(e)}")
                # If we can't fix the existing config, try to create a backup and create a new one
                try:
                    # Create backup of problematic config
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = config_path.with_name(f"config_backup_{timestamp}.yaml")
                    shutil.copy(str(config_path), str(backup_path))
                    
                    # Create a new basic config
                    basic_config = {
                        "directory": os.path.expanduser("~/Music"),
                        "library": str(db_path),
                        "import": {
                            "copy": True,
                            "write": True
                        }
                    }
                    
                    # Write the new config
                    with open(config_path, 'w') as f:
                        yaml.dump(basic_config, f, default_flow_style=False, sort_keys=False)
                    
                    logger.info(f"Created new config file at {config_path} (backup at {backup_path})")
                except Exception as backup_error:
                    logger.error(f"Error creating backup/new config: {str(backup_error)}")
                    return {
                        "success": False,
                        "message": f"Failed to fix config file. Please check the format manually.",
                        "error": f"Original error: {str(e)}. Backup error: {str(backup_error)}"
                    }
        
        # Run beet command to initialize a new database
        # The 'version' command is lightweight and will create the DB if it doesn't exist
        result = subprocess.run([BEET_EXECUTABLE, "version"], capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Error initializing database with 'version' command: {result.stderr}")
            # If that failed, try a more explicit initialization with the 'init' command if available
            try:
                init_result = subprocess.run([BEET_EXECUTABLE, "init"], capture_output=True, text=True)
                if init_result.returncode != 0:
                    return {
                        "success": False,
                        "message": f"Failed to initialize database. Error: {init_result.stderr}",
                        "error": init_result.stderr
                    }
            except Exception as e:
                return {
                    "success": False,
                    "message": f"Failed to initialize database. Error: {str(e)}",
                    "error": str(e)
                }
        
        # Verify the database was created
        if db_path.exists():
            return {
                "success": True,
                "message": "Database initialized successfully",
                "db_path": str(db_path)
            }
        else:
            # As a last resort, try to manually create the database structure
            try:
                # Run the 'list' command which will definitely create the DB
                list_result = subprocess.run([BEET_EXECUTABLE, "list"], capture_output=True, text=True)
                
                if db_path.exists():
                    return {
                        "success": True,
                        "message": "Database initialized successfully (using list command)",
                        "db_path": str(db_path)
                    }
                else:
                    # Create a minimal empty SQLite database manually
                    conn = sqlite3.connect(db_path)
                    # Create base tables
                    conn.execute('''
                    CREATE TABLE IF NOT EXISTS items (
                        id INTEGER PRIMARY KEY,
                        path TEXT,
                        album_id INTEGER,
                        title TEXT,
                        artist TEXT,
                        album TEXT,
                        year INTEGER,
                        month INTEGER,
                        day INTEGER
                    )
                    ''')
                    conn.execute('''
                    CREATE TABLE IF NOT EXISTS albums (
                        id INTEGER PRIMARY KEY,
                        artpath TEXT,
                        albumartist TEXT,
                        album TEXT,
                        year INTEGER,
                        month INTEGER,
                        day INTEGER
                    )
                    ''')
                    conn.commit()
                    conn.close()
                    
                    return {
                        "success": True,
                        "message": "Database initialized successfully (created manually)",
                        "db_path": str(db_path)
                    }
            except Exception as e:
                logger.error(f"Error manually creating database: {str(e)}")
                return {
                    "success": False,
                    "message": "Failed to initialize database. Database file not created.",
                    "error": f"Database file not created after all initialization attempts. Error: {str(e)}"
                }
    
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to initialize database."
        }

def check_paths():
    """Check if all required paths exist and are accessible."""
    config_status = check_beets_config()
    config_path = Path(config_status["config_path"])
    db_path = Path(config_status["db_path"])
    
    results = {
        "paths_checked": [],
        "all_paths_accessible": True,
        "suggestions": []
    }
    
    # Check config directory
    config_dir = config_path.parent
    config_dir_status = {
        "path": str(config_dir),
        "exists": config_dir.exists(),
        "is_dir": config_dir.is_dir() if config_dir.exists() else False,
        "writable": os.access(config_dir, os.W_OK) if config_dir.exists() else False
    }
    results["paths_checked"].append({"config_dir": config_dir_status})
    
    if not config_dir.exists():
        results["all_paths_accessible"] = False
        results["suggestions"].append(f"Create the config directory: mkdir -p '{config_dir}'")
    elif not config_dir_status["is_dir"]:
        results["all_paths_accessible"] = False
        results["suggestions"].append(f"'{config_dir}' exists but is not a directory. Remove it and create a directory instead.")
    elif not config_dir_status["writable"]:
        results["all_paths_accessible"] = False
        results["suggestions"].append(f"Make the config directory writable: chmod u+w '{config_dir}'")
    
    # Check config file
    config_file_status = {
        "path": str(config_path),
        "exists": config_path.exists(),
        "is_file": config_path.is_file() if config_path.exists() else False,
        "readable": os.access(config_path, os.R_OK) if config_path.exists() else False,
        "writable": os.access(config_path, os.W_OK) if config_path.exists() else False
    }
    results["paths_checked"].append({"config_file": config_file_status})
    
    if config_path.exists() and not config_file_status["is_file"]:
        results["all_paths_accessible"] = False
        results["suggestions"].append(f"'{config_path}' exists but is not a file. Remove it and create a file instead.")
    elif config_path.exists() and not config_file_status["readable"]:
        results["all_paths_accessible"] = False
        results["suggestions"].append(f"Make the config file readable: chmod u+r '{config_path}'")
    elif config_path.exists() and not config_file_status["writable"]:
        results["all_paths_accessible"] = False
        results["suggestions"].append(f"Make the config file writable: chmod u+w '{config_path}'")
    
    # Check database file and directory
    db_dir = db_path.parent
    db_dir_status = {
        "path": str(db_dir),
        "exists": db_dir.exists(),
        "is_dir": db_dir.is_dir() if db_dir.exists() else False,
        "writable": os.access(db_dir, os.W_OK) if db_dir.exists() else False
    }
    results["paths_checked"].append({"db_dir": db_dir_status})
    
    if not db_dir.exists():
        results["all_paths_accessible"] = False
        results["suggestions"].append(f"Create the database directory: mkdir -p '{db_dir}'")
    elif not db_dir_status["is_dir"]:
        results["all_paths_accessible"] = False
        results["suggestions"].append(f"'{db_dir}' exists but is not a directory. Remove it and create a directory instead.")
    elif not db_dir_status["writable"]:
        results["all_paths_accessible"] = False
        results["suggestions"].append(f"Make the database directory writable: chmod u+w '{db_dir}'")
    
    # Check library file if it exists
    if db_path.exists():
        db_file_status = {
            "path": str(db_path),
            "exists": True,
            "is_file": db_path.is_file(),
            "readable": os.access(db_path, os.R_OK),
            "writable": os.access(db_path, os.W_OK)
        }
        results["paths_checked"].append({"db_file": db_file_status})
        
        if not db_file_status["is_file"]:
            results["all_paths_accessible"] = False
            results["suggestions"].append(f"'{db_path}' exists but is not a file. Remove it: rm '{db_path}'")
        elif not db_file_status["readable"]:
            results["all_paths_accessible"] = False
            results["suggestions"].append(f"Make the database file readable: chmod u+r '{db_path}'")
        elif not db_file_status["writable"]:
            results["all_paths_accessible"] = False
            results["suggestions"].append(f"Make the database file writable: chmod u+w '{db_path}'")
    
    # If config exists, check music directories defined in config
    music_dir_path = None
    if config_path.exists():
        try:
            config = read_beets_config()
            if isinstance(config, dict) and "directory" in config:
                # Try to expand the music directory path
                directory_str = config["directory"]
                
                # Expand user directory if it starts with ~
                if isinstance(directory_str, str):
                    directory_str = os.path.expanduser(directory_str)
                    
                    # Convert to absolute path if it's relative
                    if not os.path.isabs(directory_str):
                        directory_str = os.path.abspath(directory_str)
                    
                    music_dir = Path(directory_str)
                    music_dir_path = str(music_dir)  # Store for results
                    
                    music_dir_status = {
                        "path": str(music_dir),
                        "exists": music_dir.exists(),
                        "is_dir": music_dir.is_dir() if music_dir.exists() else False,
                        "readable": os.access(music_dir, os.R_OK) if music_dir.exists() else False,
                        "writable": os.access(music_dir, os.W_OK) if music_dir.exists() else False
                    }
                    results["paths_checked"].append({"music_dir": music_dir_status})
                    
                    if not music_dir.exists():
                        results["all_paths_accessible"] = False
                        results["suggestions"].append(f"Create the music directory: mkdir -p '{music_dir}'")
                    elif not music_dir_status["is_dir"]:
                        results["all_paths_accessible"] = False
                        results["suggestions"].append(f"'{music_dir}' exists but is not a directory. Remove it and create a directory instead.")
                    elif not music_dir_status["readable"]:
                        results["all_paths_accessible"] = False
                        results["suggestions"].append(f"Make the music directory readable: chmod u+r '{music_dir}'")
                    elif not music_dir_status["writable"]:
                        results["all_paths_accessible"] = False
                        results["suggestions"].append(f"Make the music directory writable: chmod u+w '{music_dir}'")
                else:
                    results["all_paths_accessible"] = False
                    results["suggestions"].append("The 'directory' setting in your config is not a string. Edit your config.yaml to set a valid music directory path.")
            else:
                results["all_paths_accessible"] = False
                results["suggestions"].append("No 'directory' setting found in the config. Set a music directory in your configuration.")
        except Exception as e:
            logger.error(f"Error checking music directory: {str(e)}")
            results["music_dir_error"] = str(e)
            results["all_paths_accessible"] = False
            results["suggestions"].append(f"Error checking music directory: {str(e)}")
    
    # Add general suggestions if there are problems
    if not results["all_paths_accessible"]:
        if not config_path.exists():
            results["suggestions"].append("Your beets configuration file doesn't exist. Try using the Settings interface to create a basic configuration.")
        
        if music_dir_path is None and config_path.exists():
            results["suggestions"].append("No music directory is configured. Set one in the Settings interface or edit your config.yaml directly.")
    
    return results
