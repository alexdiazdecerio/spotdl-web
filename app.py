from flask import Flask, render_template, request, jsonify
import subprocess
import os
import json
from datetime import datetime
import threading
import requests
from urllib.parse import urljoin
import re
import logging

# Configure logging to file
logging.basicConfig(
    filename='/tmp/spotdl-debug.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)
MUSIC_DIR = "/music"
downloads = {}

# Verify that MUSIC_DIR is writable on startup
try:
    if not os.path.exists(MUSIC_DIR):
        print(f"[STARTUP] ERROR: MUSIC_DIR does not exist: {MUSIC_DIR}", flush=True)
    elif not os.access(MUSIC_DIR, os.W_OK):
        print(f"[STARTUP] ERROR: MUSIC_DIR is not writable: {MUSIC_DIR}", flush=True)
        stat = os.stat(MUSIC_DIR)
        print(f"[STARTUP] Directory permissions: {oct(stat.st_mode)}, UID: {stat.st_uid}, GID: {stat.st_gid}", flush=True)
    else:
        print(f"[STARTUP] ✓ MUSIC_DIR is writable: {MUSIC_DIR}", flush=True)
except Exception as e:
    print(f"[STARTUP] ERROR checking MUSIC_DIR: {str(e)}", flush=True)

# Navidrome configuration
NAVIDROME_URL = "http://navidrome:4533"
NAVIDROME_USER = "alex"
NAVIDROME_PASSWORD = "navcube55"

def search_song_in_navidrome(artist, title, retry_count=0):
    """Search for a song by navigating Artist → Album → Song structure"""
    try:
        import time
        import xml.etree.ElementTree as ET

        print(f"[SEARCH] Looking for: artist='{artist}' title='{title}' (attempt {retry_count + 1})", flush=True)

        # Strategy: Navigate directly through Artist → Album → Song without search
        print(f"[SEARCH] Strategy: Direct navigation Artist → Album → Song", flush=True)

        # Step 1: Get music folders first
        print(f"[SEARCH] Step 1: Getting music folders...", flush=True)
        params_folders = {
            'u': NAVIDROME_USER,
            'p': NAVIDROME_PASSWORD,
            'c': 'spotdl',
            'v': '1.16.1'
        }
        response = requests.get(f"{NAVIDROME_URL}/rest/getMusicFolders.view", params=params_folders, timeout=10)
        print(f"[SEARCH]   Raw response: {response.text[:500]}", flush=True)
        root_folders = ET.fromstring(response.text)
        music_folders = root_folders.findall('.//musicFolder')
        print(f"[SEARCH]   Found {len(music_folders)} music folders", flush=True)
        for folder in music_folders:
            print(f"[SEARCH]   - Folder: {folder.get('name', 'unknown')} ID: {folder.get('id', 'unknown')}", flush=True)

        if not music_folders:
            print(f"[SEARCH] ✗ No music folders found, cannot proceed", flush=True)
            return None

        # Use first music folder
        folder_id = music_folders[0].get('id')
        print(f"[SEARCH]   Using folder ID: {folder_id}", flush=True)

        # Step 2: Get all artists from the music folder
        print(f"[SEARCH] Step 2: Getting artists from folder...", flush=True)
        params_root = {
            'u': NAVIDROME_USER,
            'p': NAVIDROME_PASSWORD,
            'c': 'spotdl',
            'v': '1.16.1',
            'id': folder_id
        }
        response = requests.get(f"{NAVIDROME_URL}/rest/getMusicDirectory.view", params=params_root, timeout=10)
        root = ET.fromstring(response.text)
        artists_dirs = root.findall('.//child[@isDir="true"]')
        print(f"[SEARCH]   Found {len(artists_dirs)} artists", flush=True)

        # Step 3: Find matching artist
        print(f"[SEARCH] Step 3: Finding artist '{artist}'...", flush=True)
        for artist_dir in artists_dirs:
            artist_name = artist_dir.get('title', '')
            artist_id = artist_dir.get('id', '')
            artist_lower = artist.lower().strip()
            artist_name_lower = artist_name.lower()

            # Exact or partial match
            if artist_lower == artist_name_lower or artist_lower in artist_name_lower or artist_name_lower in artist_lower:
                print(f"[SEARCH]   ✓ Found artist: '{artist_name}' (ID: {artist_id})", flush=True)

                # Step 4: Get all albums for this artist
                print(f"[SEARCH] Step 4: Getting albums for {artist_name}...", flush=True)
                params_artist = {
                    'u': NAVIDROME_USER,
                    'p': NAVIDROME_PASSWORD,
                    'c': 'spotdl',
                    'v': '1.16.1',
                    'id': artist_id
                }
                resp_artist = requests.get(f"{NAVIDROME_URL}/rest/getMusicDirectory.view", params=params_artist, timeout=10)
                root_artist = ET.fromstring(resp_artist.text)
                albums = root_artist.findall('.//child[@isDir="true"]')
                print(f"[SEARCH]   Found {len(albums)} albums", flush=True)

                # Step 5: For each album, get songs and look for match
                print(f"[SEARCH] Step 5: Searching for song '{title}' in albums...", flush=True)
                for album in albums:
                    album_name = album.get('title', '')
                    album_id = album.get('id', '')

                    # Get songs from this album
                    params_album = {
                        'u': NAVIDROME_USER,
                        'p': NAVIDROME_PASSWORD,
                        'c': 'spotdl',
                        'v': '1.16.1',
                        'id': album_id
                    }
                    resp_album = requests.get(f"{NAVIDROME_URL}/rest/getMusicDirectory.view", params=params_album, timeout=10)
                    root_album = ET.fromstring(resp_album.text)
                    songs = root_album.findall('.//child[@isDir="false"]')

                    # Look for matching song
                    for song in songs:
                        song_title = song.get('title', '').lower()
                        song_name = song.get('name', '').lower()
                        search_title = title.lower().strip()

                        # Try title match first, then name (filename)
                        if search_title == song_title or search_title in song_title or song_title in search_title:
                            song_id = song.get('id')
                            print(f"[SEARCH] ✓✓✓ FOUND! Artist: {artist_name}, Album: {album_name}, Song: {song_title}, ID: {song_id}", flush=True)
                            return song_id
                        elif search_title == song_name or search_title in song_name or song_name in search_title:
                            song_id = song.get('id')
                            print(f"[SEARCH] ✓✓✓ FOUND (by filename)! Artist: {artist_name}, Album: {album_name}, Name: {song_name}, ID: {song_id}", flush=True)
                            return song_id

        print(f"[SEARCH] Song not found in library navigation", flush=True)

        # Retry with wait
        if retry_count < 2:
            print(f"[SEARCH] Retrying in 15 seconds... (attempt {retry_count + 1}/3)", flush=True)
            time.sleep(15)
            return search_song_in_navidrome(artist, title, retry_count + 1)
        else:
            print(f"[SEARCH] ✗ NOT FOUND after {retry_count + 1} attempts", flush=True)

        return None
    except Exception as e:
        print(f"[SEARCH ERROR] Exception: {e}", flush=True)
        import traceback
        print(f"[SEARCH ERROR] Traceback: {traceback.format_exc()}", flush=True)
        return None

def find_all_available_audio_files():
    """Find all audio files currently available in the music directory"""
    all_files = []
    audio_extensions = ('.mp3', '.m4a', '.flac', '.wav', '.ogg')

    try:
        for root, dirs, files in os.walk(MUSIC_DIR):
            for file in files:
                if file.lower().endswith(audio_extensions):
                    all_files.append(file)

        print(f"[M3U] Scanned directory, found {len(all_files)} total audio files", flush=True)
        return all_files
    except Exception as e:
        print(f"[M3U ERROR] Error scanning directory: {e}", flush=True)
        return []

def create_playlist_in_navidrome(playlist_name, downloaded_files, spotdl_output=None):
    """Create M3U playlist file and let Navidrome import it automatically"""
    try:
        import os

        print(f"[M3U] Creating M3U playlist: {playlist_name}", flush=True)
        print(f"[M3U] Newly downloaded files: {len(downloaded_files)} files", flush=True)

        # Use only the files that were downloaded in this session
        # If downloaded_files is empty, fall back to all available files
        if downloaded_files and len(downloaded_files) > 0:
            files_to_include = downloaded_files
            print(f"[M3U] Using {len(files_to_include)} newly downloaded files for playlist", flush=True)
        else:
            # Fallback: if no files detected as downloaded, use all available
            # This handles cases where file timestamps don't match expectations
            all_available_files = find_all_available_audio_files()
            files_to_include = all_available_files
            print(f"[M3U] No recently downloaded files detected, using all {len(files_to_include)} available files", flush=True)

        print(f"[M3U] Total files to include in playlist: {len(files_to_include)}", flush=True)

        # Create M3U content with file paths
        m3u_lines = ['#EXTM3U']

        for filename in files_to_include:
            # Add the filename as a relative path in the M3U
            m3u_lines.append(filename)

        m3u_content = '\n'.join(m3u_lines)
        print(f"[M3U] M3U playlist will contain {len(files_to_include)} songs", flush=True)

        # Define M3U file path and filename
        m3u_filename = f"{playlist_name}.m3u"
        m3u_path = os.path.join(MUSIC_DIR, m3u_filename)

        # Write M3U file to music directory
        print(f"[M3U] Writing M3U file to: {m3u_path}", flush=True)
        with open(m3u_path, 'w', encoding='utf-8') as f:
            f.write(m3u_content)

        print(f"[M3U] ✓ M3U file created successfully with {len(files_to_include)} songs", flush=True)

        # Trigger Navidrome scan to import the M3U (runs in background)
        print(f"[M3U] Triggering Navidrome scan to import M3U...", flush=True)
        start_navidrome_scan()

        print(f"[M3U] ✓✓✓ SUCCESS! Playlist '{playlist_name}' will be created from M3U", flush=True)
        return True, f"Playlist '{playlist_name}' created (M3U file: {m3u_filename}) - {len(files_to_include)} songs"

    except PermissionError as e:
        print(f"[M3U ERROR] Permission Denied: {str(e)}", flush=True)
        print(f"[M3U ERROR] Check MUSIC_DIR permissions: {MUSIC_DIR}", flush=True)
        import os
        try:
            stat = os.stat(MUSIC_DIR)
            print(f"[M3U ERROR] Directory mode: {oct(stat.st_mode)}, UID: {stat.st_uid}, GID: {stat.st_gid}", flush=True)
        except:
            pass
        import traceback
        print(f"[M3U ERROR] Traceback: {traceback.format_exc()}", flush=True)
        return False, f"Permission denied writing to {MUSIC_DIR}: {str(e)}"
    except Exception as e:
        print(f"[M3U ERROR] Exception: {str(e)}", flush=True)
        import traceback
        print(f"[M3U ERROR] Traceback: {traceback.format_exc()}", flush=True)
        return False, f"Error creating M3U playlist: {str(e)}"

def extract_playlist_info(output_lines):
    """Extract playlist name and downloaded songs from spotdl output"""
    playlist_name = None
    downloaded_files = []

    for line in output_lines:
        # Try to detect playlist name - look for patterns like "Found X songs in PlaylistName (Playlist)"
        match = re.search(r'Found\s+\d+\s+songs?\s+in\s+(.+?)\s+\((Playlist|Album)\)', line)
        if match:
            playlist_name = match.group(1).strip()
            print(f"[EXTRACT] Found playlist name: {playlist_name}", flush=True)

        # Try to detect downloaded files from various SpotDL output formats
        # Look for patterns like:
        # - "Downloaded: songname.mp3"
        # - "Saved: songname.flac"
        # - "✓ songname.mp3"
        # - File paths in output

        # Pattern 1: "Downloaded:" or "Saved:" format
        if "Downloaded" in line or "Saved" in line:
            # Try to extract filename with extension
            match = re.search(r'(?:Downloaded|Saved)[\s:]+(.+\.(?:mp3|m4a|flac|wav|ogg))', line, re.IGNORECASE)
            if match:
                filename = match.group(1).strip()
                # Get just the filename, not the full path
                filename = os.path.basename(filename)
                if filename not in downloaded_files:
                    downloaded_files.append(filename)
                    print(f"[EXTRACT] Found downloaded file: {filename}", flush=True)

        # Pattern 2: Lines with checkmark and filename (✓ filename.ext)
        match = re.search(r'✓\s+(.+\.(?:mp3|m4a|flac|wav|ogg))', line, re.IGNORECASE)
        if match:
            filename = match.group(1).strip()
            filename = os.path.basename(filename)
            if filename not in downloaded_files:
                downloaded_files.append(filename)
                print(f"[EXTRACT] Found checked file: {filename}", flush=True)

    return playlist_name, downloaded_files

def find_recently_modified_files(since_time, limit_count=None):
    """Find music files modified after the given time"""
    from pathlib import Path
    import time

    recently_modified = []
    audio_extensions = ('.mp3', '.m4a', '.flac', '.wav', '.ogg')

    try:
        print(f"[FILES] Looking for files modified after {since_time}", flush=True)
        for root, dirs, files in os.walk(MUSIC_DIR):
            for file in files:
                if file.lower().endswith(audio_extensions):
                    filepath = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(filepath)
                        if mtime > since_time:
                            recently_modified.append({
                                'path': filepath,
                                'mtime': mtime,
                                'filename': file
                            })
                            print(f"[FILES]   Found: {file}", flush=True)
                    except:
                        pass

        # Sort by modification time, most recent first
        recently_modified.sort(key=lambda x: x['mtime'], reverse=True)
        print(f"[FILES] Total files found: {len(recently_modified)}", flush=True)
        if limit_count is None:
            return recently_modified
        return recently_modified[:limit_count]
    except Exception as e:
        print(f"[FILES ERROR] {e}", flush=True)
        return []

def match_songs_in_navidrome(filenames):
    """Check if files can be matched in Navidrome (simple validation)"""
    # Just return the filenames list - actual matching happens during playlist creation
    return filenames

def wait_for_navidrome_scan():
    """Wait for Navidrome to finish scanning and indexing the library"""
    import time
    max_wait = 120  # Max 120 seconds (increased from 60)
    start = time.time()

    # First, wait for scanning to complete
    while time.time() - start < max_wait:
        try:
            params = {
                'u': NAVIDROME_USER,
                'p': NAVIDROME_PASSWORD,
                'c': 'spotdl',
                'v': '1.16.1'
            }
            response = requests.get(f"{NAVIDROME_URL}/rest/getScanStatus.view", params=params, timeout=5)
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.text)

            # Check if scanning
            scan_status = root.find('.//scanStatus')
            if scan_status is not None:
                scanning = scan_status.get('scanning') == 'true'
                if not scanning:
                    print(f"[SCAN] Scanning completed, waiting for full indexing...", flush=True)
                    # Wait additional time for indexing to complete (increased from 5 to 15 seconds)
                    time.sleep(15)
                    print(f"[SCAN] Indexing complete, proceeding with search", flush=True)
                    return True

            time.sleep(2)
        except Exception as e:
            logging.warning(f"SCAN: Exception while waiting: {e}")
            time.sleep(2)

    logging.warning("SCAN: Max wait time exceeded")
    return False

def start_navidrome_scan():
    """Tell Navidrome to scan the music library"""
    try:
        params = {
            'u': NAVIDROME_USER,
            'p': NAVIDROME_PASSWORD,
            'c': 'spotdl',
            'v': '1.16.1'
        }
        requests.get(f"{NAVIDROME_URL}/rest/startScan.view", params=params, timeout=10)
    except:
        pass

def run_spotdl(url, download_id):
    try:
        downloads[download_id]["status"] = "downloading"
        downloads[download_id]["started"] = datetime.now().isoformat()

        # Record the time before downloading
        import time
        start_time = time.time()

        cmd = ["spotdl", url, "--output", MUSIC_DIR, "--add-unavailable", "--max-retries", "10", "--threads", "2"]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )

        output = []
        for line in process.stdout:
            output.append(line.strip())
            downloads[download_id]["log"] = "\n".join(output[-50:])  # Keep last 50 lines

        process.wait()

        if process.returncode == 0:
            # Check if it's a playlist or album URL (create playlist for both)
            if "playlist" in url.lower() or "album" in url.lower():
                downloads[download_id]["status"] = "creating_playlist"

                # Extract playlist/album name and downloaded files from SpotDL output
                playlist_name, output_downloaded_files = extract_playlist_info(output)
                if not playlist_name:
                    playlist_name = "Downloaded Content"

                # If extract_playlist_info found files in output, use those
                # Otherwise try to detect from file timestamps
                if output_downloaded_files and len(output_downloaded_files) > 0:
                    downloaded_filenames = output_downloaded_files
                    print(f"[PLAYLIST] Extracted {len(downloaded_filenames)} files from SpotDL output", flush=True)
                else:
                    # Fallback: Find recently modified files
                    recently_modified = find_recently_modified_files(start_time)
                    downloaded_filenames = [item['filename'] for item in recently_modified] if recently_modified else []
                    print(f"[PLAYLIST] Found {len(downloaded_filenames)} recently modified files", flush=True)

                print(f"[PLAYLIST] Creating playlist '{playlist_name}' with {len(downloaded_filenames)} files...", flush=True)

                # Start Navidrome scan and wait for it to complete
                downloads[download_id]["log"] += "\nEscaneando biblioteca de Navidrome..."
                start_navidrome_scan()
                wait_for_navidrome_scan()
                downloads[download_id]["log"] += "\nEscaneo completado. Creando playlist..."

                # Try to create playlist with downloaded files
                success, message = create_playlist_in_navidrome(playlist_name, downloaded_filenames, output)

                if success:
                    downloads[download_id]["status"] = "completed"
                    downloads[download_id]["playlist_created"] = True
                    downloads[download_id]["playlist_name"] = playlist_name
                else:
                    downloads[download_id]["status"] = "completed_no_playlist"
                    downloads[download_id]["playlist_error"] = message
            else:
                downloads[download_id]["status"] = "completed"
        else:
            downloads[download_id]["status"] = "error"

        downloads[download_id]["finished"] = datetime.now().isoformat()

    except Exception as e:
        downloads[download_id]["status"] = "error"
        downloads[download_id]["error"] = str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({"error": "URL is required"}), 400
    
    download_id = str(len(downloads) + 1)
    downloads[download_id] = {
        "url": url,
        "status": "queued",
        "log": ""
    }
    
    thread = threading.Thread(target=run_spotdl, args=(url, download_id))
    thread.start()
    
    return jsonify({"download_id": download_id})

@app.route('/status/<download_id>')
def status(download_id):
    if download_id not in downloads:
        return jsonify({"error": "Download not found"}), 404
    
    return jsonify(downloads[download_id])

@app.route('/list')
def list_downloads():
    return jsonify(downloads)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
