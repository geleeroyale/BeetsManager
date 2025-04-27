import os
import logging
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from beets_utils import (
    get_library_items, get_item_details, execute_beets_command, 
    get_album_art, import_music, get_item_count, search_library,
    get_albums, get_artists, check_beets_config, 
    read_beets_config, update_beets_config, get_beets_plugins, get_beets_info,
    reset_database, check_paths, initialize_database
)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_beets_gui_secret")

# Add configuration route
@app.route('/config')
def config_view():
    """Render the configuration view."""
    # Get beets configuration status and info
    config_status = check_beets_config()
    beets_info = get_beets_info()
    plugins_info = get_beets_plugins()
    
    return render_template('config.html', 
                          config_status=config_status,
                          beets_info=beets_info,
                          plugins_info=plugins_info)

@app.route('/')
def index():
    """Render the main page of the application."""
    config_status = check_beets_config()
    return render_template('index.html', config_status=config_status)

@app.route('/library')
def library():
    """Render the library view."""
    return render_template('library.html')

@app.route('/import')
def import_view():
    """Render the import view."""
    return render_template('import.html')

@app.route('/commands')
def commands_view():
    """Render the commands view."""
    return render_template('commands.html')

@app.route('/api/library')
def api_library():
    """Get library items with pagination."""
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 50, type=int)
    sort = request.args.get('sort', 'artist')
    
    try:
        items = get_library_items(page, limit, sort)
        total = get_item_count()
        return jsonify({
            'items': items,
            'total': total,
            'page': page,
            'limit': limit
        })
    except Exception as e:
        logger.error(f"Error fetching library: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/search')
def api_search():
    """Search the library with a query."""
    query = request.args.get('query', '')
    
    try:
        results = search_library(query)
        return jsonify({'results': results})
    except Exception as e:
        logger.error(f"Error searching library: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/artists')
def api_artists():
    """Get all artists in the library."""
    try:
        artists = get_artists()
        return jsonify({'artists': artists})
    except Exception as e:
        logger.error(f"Error fetching artists: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/albums')
def api_albums():
    """Get all albums in the library."""
    artist = request.args.get('artist', '')
    
    try:
        albums = get_albums(artist)
        return jsonify({'albums': albums})
    except Exception as e:
        logger.error(f"Error fetching albums: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/item/<int:item_id>')
def api_item_details(item_id):
    """Get detailed information for a specific item."""
    try:
        details = get_item_details(item_id)
        return jsonify(details)
    except Exception as e:
        logger.error(f"Error fetching item details: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/albumart/<int:item_id>')
def api_album_art(item_id):
    """Get album art for a specific item."""
    try:
        art_data = get_album_art(item_id)
        return jsonify({'albumArt': art_data})
    except Exception as e:
        logger.error(f"Error fetching album art: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/command', methods=['POST'])
def api_command():
    """Execute a beets command."""
    data = request.get_json()
    command = data.get('command', '')
    
    if not command:
        return jsonify({'error': 'No command provided'}), 400
    
    try:
        result = execute_beets_command(command)
        return jsonify({'result': result})
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/import', methods=['POST'])
def api_import():
    """Import music files."""
    data = request.get_json()
    path = data.get('path', '')
    
    if not path:
        return jsonify({'error': 'No path provided'}), 400
    
    try:
        result = import_music(path)
        return jsonify({'result': result})
    except Exception as e:
        logger.error(f"Error importing music: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Add new endpoints for beets configuration management
@app.route('/api/beets/config', methods=['GET'])
def api_get_beets_config():
    """Get the beets configuration."""
    try:
        config = read_beets_config()
        return jsonify(config)
    except Exception as e:
        logger.error(f"Error getting beets config: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/beets/config', methods=['POST'])
def api_update_beets_config():
    """Update the beets configuration."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No configuration provided'}), 400
    
    try:
        result = update_beets_config(data)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error updating beets config: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/beets/plugins', methods=['GET'])
def api_get_beets_plugins():
    """Get list of available beets plugins."""
    try:
        plugins = get_beets_plugins()
        return jsonify(plugins)
    except Exception as e:
        logger.error(f"Error getting beets plugins: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/beets/info', methods=['GET'])
def api_get_beets_info():
    """Get information about the beets installation."""
    try:
        info = get_beets_info()
        return jsonify(info)
    except Exception as e:
        logger.error(f"Error getting beets info: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Add new endpoints for database reset and path checking
@app.route('/api/beets/reset', methods=['POST'])
def api_reset_database():
    """Reset the beets database."""
    try:
        result = reset_database()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error resetting database: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/beets/check_paths', methods=['GET'])
def api_check_paths():
    """Check if all required paths exist and are accessible."""
    try:
        result = check_paths()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error checking paths: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/beets/initialize', methods=['POST'])
def api_initialize_database():
    """Initialize a new beets database."""
    try:
        result = initialize_database()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
