from flask import Flask, request, jsonify, send_file, abort
import os, re, json, urllib.parse, time
import xml.etree.ElementTree as ET
import requests

app = Flask(__name__, static_folder="/app/static", static_url_path="")

@app.route("/")
def index():
    return app.send_static_file("index.html")
GPX_DIR = os.environ.get("GPX_DIR", "/var/www/gpx-manager/gpx")
os.makedirs(GPX_DIR, exist_ok=True)

NOMINATIM = "https://nominatim.openstreetmap.org/search"
OSRM = "https://router.project-osrm.org/route/v1/driving"

def safe_name(name):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)

def geocode(place):
    r = requests.get(NOMINATIM, params={"q": place, "format": "json", "limit": 1},
                     headers={"User-Agent": "GPX-Manager/1.0"}, timeout=10)
    data = r.json()
    if data:
        return float(data[0]["lat"]), float(data[0]["lon"])
    return None

def build_gpx_waypoints(name, waypoints):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<gpx version="1.1" creator="GPX Manager" xmlns="http://www.topografix.com/GPX/1/1">',
             f'  <metadata><name>{name}</name></metadata>']
    for wp in waypoints:
        lines.append(f'  <wpt lat="{wp["lat"]}" lon="{wp["lon"]}"><name>{wp["name"]}</name></wpt>')
    lines.append('</gpx>')
    return "\n".join(lines)

def parse_gmaps_url(url):
    """Extract waypoints from a Google Maps directions URL."""
    # Expand short URL if needed
    if "goo.gl" in url or "maps.app.goo.gl" in url:
        r = requests.get(url, allow_redirects=True, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        url = r.url

    # Try to extract geocode params from URL
    waypoints = []
    # Look for geocode= pattern with semicolon-separated pairs
    gc_match = re.search(r'geocode=([^&]+)', url)
    # Look for daddr= (destinations) and saddr= (source)
    saddr = re.search(r'saddr=([^&]+)', url)
    daddr = re.search(r'daddr=([^&]+)', url)

    if saddr and daddr:
        src = urllib.parse.unquote_plus(saddr.group(1))
        dsts = urllib.parse.unquote_plus(daddr.group(1)).split("+to:")
        all_places = [src] + dsts
        for place in all_places:
            place = place.strip()
            if place:
                coords = geocode(place)
                if coords:
                    waypoints.append({"name": place, "lat": coords[0], "lon": coords[1]})
                time.sleep(0.5)
        return waypoints

    # Fallback: try /dir/ URL format
    # e.g. /maps/dir/PlaceA/PlaceB/PlaceC
    dir_match = re.search(r'/maps/dir/([^?@]+)', url)
    if dir_match:
        parts = dir_match.group(1).split("/")
        for part in parts:
            part = urllib.parse.unquote_plus(part).strip()
            if part and part not in ("", "maps"):
                coords = geocode(part)
                if coords:
                    waypoints.append({"name": part, "lat": coords[0], "lon": coords[1]})
                time.sleep(0.5)
        return waypoints

    return waypoints

# ── API ──────────────────────────────────────────────────────────────────────

@app.route("/api/files")
def list_files():
    files = []
    for f in sorted(os.listdir(GPX_DIR)):
        if f.endswith(".gpx"):
            path = os.path.join(GPX_DIR, f)
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
            files.append({"name": f, "size": size, "mtime": mtime})
    return jsonify(files)

@app.route("/api/files/<filename>")
def get_file(filename):
    path = os.path.join(GPX_DIR, safe_name(filename) + ".gpx" if not filename.endswith(".gpx") else filename)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name=filename)

@app.route("/api/files/<filename>/content")
def get_file_content(filename):
    path = os.path.join(GPX_DIR, filename)
    if not os.path.exists(path):
        abort(404)
    with open(path) as f:
        return f.read(), 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.route("/api/files/<filename>", methods=["PUT"])
def update_file(filename):
    path = os.path.join(GPX_DIR, filename)
    content = request.data.decode("utf-8")
    with open(path, "w") as f:
        f.write(content)
    return jsonify({"ok": True})

@app.route("/api/files/<filename>", methods=["DELETE"])
def delete_file(filename):
    path = os.path.join(GPX_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
    return jsonify({"ok": True})

@app.route("/api/files/<filename>/rename", methods=["POST"])
def rename_file(filename):
    new_name = request.json.get("name", "").strip()
    if not new_name.endswith(".gpx"):
        new_name += ".gpx"
    old_path = os.path.join(GPX_DIR, filename)
    new_path = os.path.join(GPX_DIR, new_name)
    os.rename(old_path, new_path)
    return jsonify({"ok": True, "name": new_name})

@app.route("/api/generate/waypoints", methods=["POST"])
def generate_waypoints():
    data = request.json
    name = data.get("name", "trasa")
    waypoints = data.get("waypoints", [])  # list of strings or {lat,lon,name}
    resolved = []
    for wp in waypoints:
        if isinstance(wp, str):
            coords = geocode(wp)
            if coords:
                resolved.append({"name": wp, "lat": coords[0], "lon": coords[1]})
            time.sleep(0.5)
        else:
            resolved.append(wp)
    gpx = build_gpx_waypoints(name, resolved)
    filename = safe_name(name) + ".gpx"
    with open(os.path.join(GPX_DIR, filename), "w") as f:
        f.write(gpx)
    return jsonify({"ok": True, "name": filename, "waypoints": resolved})

@app.route("/api/generate/gmaps", methods=["POST"])
def generate_from_gmaps():
    data = request.json
    url = data.get("url", "")
    name = data.get("name", "trasa")
    waypoints = parse_gmaps_url(url)
    if not waypoints:
        return jsonify({"error": "Nepodařilo se extrahovat waypoints z odkazu"}), 400
    gpx = build_gpx_waypoints(name, waypoints)
    filename = safe_name(name) + ".gpx"
    with open(os.path.join(GPX_DIR, filename), "w") as f:
        f.write(gpx)
    return jsonify({"ok": True, "name": filename, "waypoints": waypoints})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5055, debug=False)
