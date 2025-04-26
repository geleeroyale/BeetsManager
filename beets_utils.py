import os
import logging
import subprocess
import sqlite3
import tempfile
import base64
from pathlib import Path
import json
import paramiko
import requests
from flask import current_app, session

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Global connection settings
# Default to local mode
CONNECTION_MODE = "local"
REMOTE_CONFIG = {
    "host": "",
    "port": 22,
    "username": "",
    "password": "",
    "db_path": "",
    "use_ssh": True,  # If False, use HTTP API
    "api_url": "",    # For HTTP API mode
    "api_key": ""     # For authentication with HTTP API
}

def get_beets_config_path():
    """Get the path to the beets config file."""
    # Beets typically uses ~/.config/beets/config.yaml
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, ".config", "beets", "config.yaml")

def get_beets_db_path():
    """Get the path to the beets database."""
    # Beets typically uses ~/.config/beets/library.db
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, ".config", "beets", "library.db")

def check_beets_config():
    """Check if beets is configured correctly."""
    # If in remote mode, check remote configuration
    if CONNECTION_MODE == "remote":
        return check_remote_beets_config()
    
    # Otherwise, check local configuration
    config_path = get_beets_config_path()
    db_path = get_beets_db_path()
    
    config_exists = os.path.exists(config_path)
    db_exists = os.path.exists(db_path)
    
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
        "config_path": config_path,
        "db_path": db_path,
        "connection_mode": "local"
    }
    
def check_remote_beets_config():
    """Check if a remote beets instance is configured correctly."""
    if not REMOTE_CONFIG["host"]:
        return {
            "config_exists": False,
            "db_exists": False,
            "beets_installed": False,
            "config_path": "Not available in remote mode",
            "db_path": REMOTE_CONFIG["db_path"] or "Not configured",
            "connection_mode": "remote",
            "remote_host": REMOTE_CONFIG["host"] or "Not configured"
        }
    
    # If using SSH, check remote server configuration
    if REMOTE_CONFIG["use_ssh"]:
        try:
            # Set up SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect to the remote server
            ssh.connect(
                REMOTE_CONFIG["host"],
                port=REMOTE_CONFIG["port"],
                username=REMOTE_CONFIG["username"],
                password=REMOTE_CONFIG["password"]
            )
            
            # Check if beets is installed on the remote server
            stdin, stdout, stderr = ssh.exec_command("beet --version")
            exit_code = stdout.channel.recv_exit_status()
            beets_installed = exit_code == 0
            
            # Check if database file exists
            db_path = REMOTE_CONFIG["db_path"]
            if db_path:
                stdin, stdout, stderr = ssh.exec_command(f"test -f {db_path} && echo 'exists'")
                db_output = stdout.read().decode('utf-8').strip()
                db_exists = db_output == 'exists'
            else:
                db_exists = False
            
            # Close connection
            ssh.close()
            
            return {
                "config_exists": True,  # We can't easily check the config file in remote mode
                "db_exists": db_exists,
                "beets_installed": beets_installed,
                "config_path": "Not available in remote mode",
                "db_path": db_path or "Not configured",
                "connection_mode": "remote",
                "remote_host": REMOTE_CONFIG["host"],
                "connection_type": "SSH"
            }
        except Exception as e:
            logger.error(f"Error checking remote beets configuration: {str(e)}")
            return {
                "config_exists": False,
                "db_exists": False,
                "beets_installed": False,
                "config_path": "Not available in remote mode",
                "db_path": REMOTE_CONFIG["db_path"] or "Not configured",
                "connection_mode": "remote",
                "remote_host": REMOTE_CONFIG["host"],
                "connection_type": "SSH",
                "connection_error": str(e)
            }
    else:
        # API-based connection
        return {
            "config_exists": True,  # We assume the config exists in API mode
            "db_exists": True,      # We assume the database exists in API mode
            "beets_installed": True, # We assume beets is installed in API mode
            "config_path": "Not available in API mode",
            "db_path": "Not available in API mode",
            "connection_mode": "remote",
            "remote_host": REMOTE_CONFIG["host"],
            "connection_type": "API",
            "api_url": REMOTE_CONFIG["api_url"]
        }

def connect_db():
    """Connect to the beets database."""
    # If in remote mode, connect to remote database
    if CONNECTION_MODE == "remote":
        return remote_connect_db()
    
    # Otherwise, connect to local database
    db_path = get_beets_db_path()
    if not os.path.exists(db_path):
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
        
        # If in remote mode, use remote method to get album art
        if CONNECTION_MODE == "remote":
            return remote_get_album_art(item)
        
        # Otherwise, get album art locally
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
        
def remote_get_album_art(item):
    """Get album art from a remote beets instance."""
    if not REMOTE_CONFIG["host"] or not REMOTE_CONFIG["use_ssh"]:
        return None
    
    try:
        # Set up SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect to the remote server
        ssh.connect(
            REMOTE_CONFIG["host"],
            port=REMOTE_CONFIG["port"],
            username=REMOTE_CONFIG["username"],
            password=REMOTE_CONFIG["password"]
        )
        
        # Create a temporary file on the remote server to store the album art
        temp_file = f"/tmp/beets_albumart_{item['id']}.jpg"
        
        # Build the command
        beet_cmd = f"beet albumart -o {temp_file}"
        
        # Try to be more specific if we have artist information
        if item.get('albumartist'):
            beet_cmd += f" 'album:{item.get('album')} albumartist:{item.get('albumartist')}'"
        elif item.get('artist'):
            beet_cmd += f" 'album:{item.get('album')} artist:{item.get('artist')}'"
        else:
            beet_cmd += f" '{item.get('album')}'"
        
        # Execute the command
        stdin, stdout, stderr = ssh.exec_command(beet_cmd)
        exit_code = stdout.channel.recv_exit_status()
        
        if exit_code != 0:
            logger.warning(f"Failed to get album art on remote server: {stderr.read().decode('utf-8')}")
            ssh.close()
            return None
        
        # Download the album art file
        sftp = ssh.open_sftp()
        
        try:
            # Create a temporary file locally
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_local:
                try:
                    # Download the file
                    sftp.get(temp_file, temp_local.name)
                    
                    # Read the file and convert to base64
                    with open(temp_local.name, 'rb') as img_file:
                        image_data = base64.b64encode(img_file.read()).decode('utf-8')
                    
                    # Remove temporary files
                    ssh.exec_command(f"rm -f {temp_file}")
                    
                    return image_data
                finally:
                    # Clean up local temp file
                    os.unlink(temp_local.name)
        finally:
            sftp.close()
            ssh.close()
    except Exception as e:
        logger.error(f"Error getting album art from remote server: {str(e)}")
        return None

def execute_beets_command(command):
    """Execute a beets command and return the result."""
    if not command.strip():
        return "No command provided"
    
    # If in remote mode, execute command on remote server
    if CONNECTION_MODE == "remote":
        return remote_execute_command(command)
    
    # Otherwise, execute command locally
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
        
def remote_execute_command(command):
    """Execute a beets command on a remote server."""
    if not REMOTE_CONFIG["host"]:
        return {"success": False, "stderr": "Remote host not configured", "stdout": "", "returncode": 1}
    
    if not REMOTE_CONFIG["use_ssh"]:
        return {"success": False, "stderr": "Remote command execution is only supported via SSH", "stdout": "", "returncode": 1}
    
    try:
        # Set up SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect to the remote server
        ssh.connect(
            REMOTE_CONFIG["host"],
            port=REMOTE_CONFIG["port"],
            username=REMOTE_CONFIG["username"],
            password=REMOTE_CONFIG["password"]
        )
        
        # Execute the command on the remote server
        beet_command = f"beet {command}"
        stdin, stdout, stderr = ssh.exec_command(beet_command)
        
        # Get command output
        stdout_str = stdout.read().decode('utf-8')
        stderr_str = stderr.read().decode('utf-8')
        exit_code = stdout.channel.recv_exit_status()
        
        # Close connection
        ssh.close()
        
        # Build response
        response = {
            "stdout": stdout_str,
            "stderr": stderr_str,
            "returncode": exit_code,
            "success": exit_code == 0
        }
        
        return response
    except Exception as e:
        logger.error(f"Error executing command on remote server: {str(e)}")
        return {"success": False, "stderr": str(e), "stdout": "", "returncode": 1}

def import_music(path):
    """Import music files into the beets library."""
    if CONNECTION_MODE == "remote":
        return remote_import_music(path)
    
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
        
def set_connection_mode(mode):
    """Set the connection mode (local or remote)."""
    global CONNECTION_MODE
    if mode not in ["local", "remote"]:
        raise ValueError("Connection mode must be 'local' or 'remote'")
    
    CONNECTION_MODE = mode
    return {"success": True, "mode": mode}
    
def get_connection_mode():
    """Get the current connection mode."""
    return {"mode": CONNECTION_MODE, "remote_config": REMOTE_CONFIG if CONNECTION_MODE == "remote" else None}
    
def set_remote_config(config):
    """Set the remote connection configuration."""
    global REMOTE_CONFIG
    required_fields = ["host"]
    
    # Validate required fields
    for field in required_fields:
        if not config.get(field):
            return {"success": False, "message": f"Missing required field: {field}"}
    
    # Update config with provided values
    for key, value in config.items():
        if key in REMOTE_CONFIG:
            REMOTE_CONFIG[key] = value
    
    return {"success": True, "config": REMOTE_CONFIG}
    
def remote_connect_db():
    """Connect to a remote beets database via SSH."""
    if not REMOTE_CONFIG["host"]:
        raise ValueError("Remote host not configured")
    
    if REMOTE_CONFIG["use_ssh"]:
        return remote_connect_ssh()
    else:
        return remote_connect_api()
    
def remote_connect_ssh():
    """Connect to a remote beets database via SSH."""
    try:
        # Create a temporary file to store the remote database
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        # Set up SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect to the remote server
        ssh.connect(
            REMOTE_CONFIG["host"],
            port=REMOTE_CONFIG["port"],
            username=REMOTE_CONFIG["username"],
            password=REMOTE_CONFIG["password"]
        )
        
        # Set up SFTP client
        sftp = ssh.open_sftp()
        
        # Download the remote database file
        sftp.get(REMOTE_CONFIG["db_path"], temp_db.name)
        
        # Close connections
        sftp.close()
        ssh.close()
        
        # Connect to the downloaded database
        conn = sqlite3.connect(temp_db.name)
        conn.row_factory = sqlite3.Row
        
        # Store the temp file path to delete it when done
        conn.temp_db_path = temp_db.name
        
        return conn
    except Exception as e:
        logger.error(f"Error connecting to remote database via SSH: {str(e)}")
        raise
    
def remote_connect_api():
    """Connect to a remote beets database via HTTP API."""
    # This is a placeholder for an API-based remote connection
    # In a real implementation, this would use the API to query the database
    raise NotImplementedError("API-based remote connection not implemented yet")
    
def remote_import_music(path):
    """Import music files into a remote beets library."""
    if not REMOTE_CONFIG["host"]:
        return {"success": False, "message": "Remote host not configured"}
    
    if not REMOTE_CONFIG["use_ssh"]:
        return {"success": False, "message": "Remote import is only supported via SSH"}
    
    try:
        # Set up SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect to the remote server
        ssh.connect(
            REMOTE_CONFIG["host"],
            port=REMOTE_CONFIG["port"],
            username=REMOTE_CONFIG["username"],
            password=REMOTE_CONFIG["password"]
        )
        
        # Execute the import command on the remote server
        command = f"beet import {path}"
        stdin, stdout, stderr = ssh.exec_command(command)
        
        # Get command output
        stdout_str = stdout.read().decode('utf-8')
        stderr_str = stderr.read().decode('utf-8')
        exit_code = stdout.channel.recv_exit_status()
        
        # Close connection
        ssh.close()
        
        # Build response
        response = {
            "stdout": stdout_str,
            "stderr": stderr_str,
            "returncode": exit_code,
            "success": exit_code == 0
        }
        
        return response
    except Exception as e:
        logger.error(f"Error importing music on remote server: {str(e)}")
        raise
