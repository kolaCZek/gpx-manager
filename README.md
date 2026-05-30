# GPX Manager

A web app for managing GPX routes — Flask backend + Leaflet map, Docker.

## Features

- 📂 GPX file list with rename, download, delete
- 🗺 Interactive map (Leaflet / OpenStreetMap)
- 📍 Add waypoints by clicking on the map or dragging markers
- ✏️ Edit waypoints list and raw XML
- ➕ Generate route from place names (geocoding via Nominatim)
- 📍 Import from Google Maps link
- 📱 Mobile-friendly layout

## Quick Start (Docker)

```bash
docker compose up -d
```

App runs at `http://localhost:5055`.

## Development (without Docker)

```bash
pip install flask requests
python app.py
```

## Project Structure

```
app.py              # Flask API
static/index.html   # Frontend (Leaflet)
Dockerfile
docker-compose.yml
```

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/files` | List all files |
| GET | `/api/files/<name>` | Download GPX file |
| GET | `/api/files/<name>/content` | Get file content as text |
| PUT | `/api/files/<name>` | Save / overwrite file |
| DELETE | `/api/files/<name>` | Delete file |
| POST | `/api/files/<name>/rename` | Rename file |
| POST | `/api/generate/waypoints` | Generate GPX from place names |
| POST | `/api/generate/gmaps` | Import from Google Maps link |
