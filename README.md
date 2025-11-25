# SpotDL Web

Web interface for SpotDL that automatically downloads Spotify playlists, albums, and songs and creates playlists in Navidrome.

## Features

- 🎵 Download Spotify playlists, albums, and individual songs
- 🎯 Automatic playlist creation in Navidrome
- ⚡ Fast M3U-based playlist generation (no API searching)
- 🌐 Web interface for easy management
- 📊 Real-time download progress logging
- 🔄 Automatic Navidrome library scanning

## How It Works

1. Paste a Spotify URL (playlist, album, or song)
2. Click "Descargar" to start the download
3. SpotDL downloads the audio files
4. App automatically generates an M3U playlist file
5. Navidrome scans and imports the playlist

## Architecture

### M3U Strategy
The application uses M3U playlist files instead of API-based song matching:
- **Previous approach**: Search for each downloaded song via Navidrome API → Unreliable (API limitation)
- **Current approach**: Generate M3U file with song list → Navidrome auto-imports → Reliable and fast

This avoids Navidrome's search API limitations and provides instant playlist creation.

## Requirements

- Docker & Docker Compose
- Navidrome instance accessible on the same Docker network
- Music directory mounted to container
- Spotify (for music availability)

## Installation

1. Place this directory in your music-stack
2. Update `docker-compose.yml` with your music directory path
3. Run:
   ```bash
   docker compose up -d
   ```

4. Access at `http://localhost:5000`

## Configuration

Edit `docker-compose.yml` to set:
- `MUSIC_DIR`: Path where downloaded music is stored
- `NAVIDROME_URL`: Navidrome instance URL
- `NAVIDROME_USER` / `NAVIDROME_PASSWORD`: Navidrome credentials

## Development Notes

### Key Files
- `app.py`: Flask backend with SpotDL integration
- `templates/index.html`: Web UI with real-time status updates
- `Dockerfile`: Container configuration
- `docker-compose.yml`: Service orchestration

### Functions
- `run_spotdl()`: Executes SpotDL download command
- `create_playlist_in_navidrome()`: Generates M3U file for Navidrome
- `find_recently_modified_files()`: Finds newly downloaded songs
- `start_navidrome_scan()`: Triggers Navidrome library scan

### Logging
All operations are logged with prefixes:
- `[SEARCH]`: Song search operations
- `[M3U]`: M3U playlist generation
- `[FILES]`: File detection
- `[SCAN]`: Navidrome scan status

## Troubleshooting

### M3U file not creating
- Check `/music/` directory permissions
- Verify Navidrome URL and credentials in `app.py`
- Check container logs: `docker logs spotdl-web`

### Playlist not appearing in Navidrome
- Ensure M3U file was created in `/music/` directory
- Check that Navidrome scan completed successfully
- Verify file paths in M3U are correct

### Download fails
- Check SpotDL logs in web interface
- Ensure internet connection for Spotify access
- Verify FFmpeg is installed (included in Dockerfile)

## Performance

- Download time: Depends on song count and internet speed
- Playlist creation: ~2-3 seconds
- Navidrome scan: Runs in background after playlist is ready

## Future Improvements

- User authentication for web interface
- Download history and management
- Playlist editing in Navidrome
- Support for liked songs, saved playlists from Spotify account
