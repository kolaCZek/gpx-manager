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
        # Google may redirect to consent page — extract real URL from continue= param
        if "consent.google.com" in url:
            m = re.search(r'continue=([^&]+(?:&[^&]*)*?)(?:&gl=|&m=|&pc=|$)', url)
            if m:
                # Double-decode: consent URL double-encodes the maps URL
                url = urllib.parse.unquote(urllib.parse.unquote(m.group(1)))

    waypoints = []

    # Parse path segments from /maps/dir/A/B/C/@...
    dir_match = re.search(r'/maps/dir/([^?]+?)/@', url)
    if not dir_match:
        dir_match = re.search(r'/maps/dir/([^?]+)', url)
    if not dir_match:
        return waypoints

    segments = []
    for part in dir_match.group(1).split("/"):
        part = urllib.parse.unquote_plus(part).strip()
        if part:
            segments.append(part)

    # Extract coords from data= for named places (in order they appear in data=)
    # Pattern: !1d<lon>!2d<lat> or !2d<lon>!2d<lat> — these are place coords
    data_coords = []
    for lon_str, lat_str in re.findall(r'!(?:1|2)d([-\d.]+)!2d([-\d.]+)', url):
        lat, lon = float(lat_str), float(lon_str)
        if 40 < lat < 60 and 5 < lon < 30:  # Europe sanity check
            data_coords.append((lat, lon))

    # Build waypoints: walk segments in order, assign coords
    data_idx = 0
    for i, seg in enumerate(segments):
        # Is it a raw coordinate?
        m = re.match(r'^([-\d.]+),([-\d.]+)$', seg)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            waypoints.append({"name": f"Waypoint {len(waypoints)+1}", "lat": round(lat,7), "lon": round(lon,7)})
        else:
            # Named place — use next data= coord if available
            name = seg.split(",")[0].strip()  # strip address suffix
            if data_idx < len(data_coords):
                lat, lon = data_coords[data_idx]
                data_idx += 1
                waypoints.append({"name": name, "lat": round(lat,7), "lon": round(lon,7)})
            else:
                # Fallback: geocode
                coords = geocode(seg)
                if coords:
                    waypoints.append({"name": name, "lat": coords[0], "lon": coords[1]})
                time.sleep(0.5)

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
