import os
import logging
import subprocess
import sqlite3
import tempfile
import base64
from pathlib import Path
import json
from flask import current_app

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
        "db_path": db_path
    }

def connect_db():
    """Connect to the beets database."""
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
        
        # Get album art using beets commands
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
    
    # Split the command into parts
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
