"""
DWD WarnApp – Regionale Unwetterwarnungen für eingegebene Orte

Dieses Skript:
1. Fragt einen Ortsnamen ab (z. B. „Köln“)
2. Ermittelt über OpenStreetMap die geografischen Koordinaten (Latitude, Longitude)
3. Nutzt die DWD-Geodaten, um den zugehörigen AGS-Code (Gemeindeschlüssel) zu finden
4. Holt die aktuellen Wetterwarnungen vom Deutschen Wetterdienst (DWD)
5. Gibt alle zutreffenden Warnmeldungen für die entsprechende Warnzelle aus

Benötigte Bibliotheken:
- requests (für HTTP-Abfragen)
- shapely (für Geometrieberechnungen)
"""

import requests
import json
from shapely.geometry import shape, Point
import urllib.parse
from datetime import datetime

# Koordinaten eines Ortsnamens über OpenStreetMap (Nominatim) ermitteln
def get_coordinates(place):
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(place)}"
    headers = {'User-Agent': 'AGS-WarnApp/1.0 (https://example.com)'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            return lat, lon
    return None, None

# AGS-Code aus Koordinaten per DWD-GeoJSON bestimmen
def get_ags_from_coordinates(lat, lon):
    url = "https://maps.dwd.de/geoserver/dwd/ows?service=WFS&version=2.0.0&request=GetFeature&typeName=dwd:Warngebiete_Gemeinden&outputFormat=application/json"
    response = requests.get(url)
    data = response.json()
    point = Point(lon, lat)

    for feature in data["features"]:
        geometry = shape(feature["geometry"])
        if geometry.contains(point):
            ags = feature["properties"].get("AGS")
            name = feature["properties"].get("NAME", "Unbekannt")
            return ags, name
    return None, None

# Zeitstempel (in Millisekunden) in deutsche Datums-/Zeitformatierung umwandeln
def format_timestamp(ms):
    return datetime.fromtimestamp(ms / 1000).strftime("%H:%M Uhr am %d.%m.%Y")

# DWD-Warnungen für einen AGS-Code suchen (Vergleich mit WarnCell-IDs anhand der mittleren 5 Ziffern)
def get_warnings_by_ags(ags_code):
    ags_kreis = ags_code[:5]
    url = "https://www.dwd.de/DWD/warnungen/warnapp/json/warnings.json"
    response = requests.get(url)
    text = response.text

    # JSON-P Wrapper entfernen: DWD gibt JSON in Funktion eingebettet zurück
    json_start = text.find('(') + 1
    json_end = text.rfind(')')
    json_str = text[json_start:json_end]
    data = json.loads(json_str)

    all_warnings = data["warnings"]
    matched_warnings = []

    # Nur Warnzellen vergleichen, deren mittlere 5 Stellen mit AGS[:5] übereinstimmen
    for warncell_id, warnings in all_warnings.items():
        if warncell_id[1:6] == ags_kreis:
            matched_warnings.extend(warnings)

    return matched_warnings

# Hauptprogrammablauf
if __name__ == "__main__":
    ort = input("Ort eingeben: ")
    lat, lon = get_coordinates(ort)

    if lat and lon:
        print(f"Koordinaten für {ort}: {lat}, {lon}")
        ags, gemeindename = get_ags_from_coordinates(lat, lon)
        if ags:
            print(f"✔ Gefunden: {gemeindename} (AGS: {ags})")
            warnungen = get_warnings_by_ags(ags)

            if warnungen:
                print(f"\n⚠️ {len(warnungen)} Warnung(en) für {gemeindename}:\n")
                for w in warnungen:
                    print(f"📌 Ereignis: {w.get('event')}")
                    print(f"🏷️ Titel: {w.get('headline')}")
                    print(f"🟠 Warnstufe: {w.get('level')} | Typ: {w.get('type')}")
                    print(f"📍 Region: {w.get('regionName')} ({w.get('state')})")
                    print(f"🕒 Von: {format_timestamp(w.get('start'))}")
                    print(f"🕒 Bis: {format_timestamp(w.get('end'))}")
                    print(f"📝 Beschreibung: {w.get('description', '').replace(chr(10), ' ').strip()}")
                    instruction = w.get('instruction', '')
                    if instruction:
                        print(f"📋 Verhaltensempfehlung: {instruction.replace(chr(10), ' ').strip()}")
                    print("-" * 50)
            else:
                print("✅ Keine aktuellen Warnungen.")
        else:
            print("❌ Kein AGS-Code gefunden.")
    else:
        print("❌ Ort nicht gefunden.")
