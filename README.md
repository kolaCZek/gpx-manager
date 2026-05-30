# GPX Manager

Web appka pro správu GPX tras — Flask backend + Leaflet mapa, Docker.

## Features

- 📂 Seznam GPX souborů
- 🗺 Interaktivní mapa (Leaflet/OpenStreetMap)
- 📍 Přidávání bodů kliknutím na mapu nebo tažením
- ✏️ Editace waypoints a XML
- 🗑 Mazání, přejmenování, stahování tras
- ➕ Generování trasy z názvů míst (geocoding přes Nominatim)
- 📍 Import z Google Maps odkazu
- 📱 Mobilní layout

## Spuštění (Docker)

```bash
docker compose up -d
```

Appka běží na `http://localhost:5055`.

## Vývoj bez Dockeru

```bash
pip install flask requests
python app.py
```

## Struktura

```
app.py              # Flask API
static/index.html   # Frontend (Leaflet)
Dockerfile
docker-compose.yml
```

## API

| Method | Path | Popis |
|--------|------|-------|
| GET | `/api/files` | Seznam souborů |
| GET | `/api/files/<name>` | Stáhnout GPX |
| GET | `/api/files/<name>/content` | Obsah jako text |
| PUT | `/api/files/<name>` | Uložit/přepsat |
| DELETE | `/api/files/<name>` | Smazat |
| POST | `/api/files/<name>/rename` | Přejmenovat |
| POST | `/api/generate/waypoints` | Generovat z názvů míst |
| POST | `/api/generate/gmaps` | Import z Google Maps |
