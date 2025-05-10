# -*- coding: utf-8 -*-
"""
Dieses Skript ruft Wetterwarnungen des Deutschen Wetterdienstes (DWD) für einen
eingegebenen Ort ab. Es verwendet dazu folgende Schritte:

1.  **Koordinatenermittlung**: Über die Nominatim API von OpenStreetMap werden
    die geografischen Koordinaten (Breitengrad, Längengrad) für den
    eingegebenen Ort ermittelt.
2.  **AGS-Ermittlung**: Mithilfe der Koordinaten und eines GeoJSON-Dienstes des
    DWD wird der Amtliche Gemeindeschlüssel (AGS) und der Gemeindename für den
    Ort bestimmt. Die Geometrien der DWD-Warngemeinden werden geprüft, um die
    passende Gemeinde zu finden.
3.  **Warnungsabruf**: Mit dem ermittelten AGS-Code (genauer: den ersten fünf
    Ziffern für die Kreisebene) werden die aktuellen Wetterwarnungen von der
    JSON-Schnittstelle des DWD abgerufen.
4.  **Anzeige**: Die gefundenen Warnungen werden formatiert und auf der Konsole
    ausgegeben.

Abhängigkeiten:
-   requests: Für HTTP-Anfragen an die APIs.
-   shapely: Zur Verarbeitung von GeoJSON-Geometrien und zur Prüfung, ob ein
    Punkt innerhalb eines Polygons liegt.

APIs:
-   Nominatim (OpenStreetMap): https://nominatim.openstreetmap.org/
-   DWD GeoServer (Warngemeinden): https://maps.dwd.de/geoserver/dwd/ows
-   DWD Warnungs-API: https://www.dwd.de/DWD/warnungen/warnapp/json/warnings.json

Hinweis: Für die Nutzung der Nominatim API ist ein User-Agent erforderlich.
Passen Sie diesen ggf. an.
"""
import requests
import json
from shapely.geometry import shape, Point
import urllib.parse
from datetime import datetime
from typing import Tuple, List, Dict, Any, Optional

# --- Konstanten ---
NOMINATIM_URL_TEMPLATE = "https://nominatim.openstreetmap.org/search?format=json&q={}"
DWD_GEOJSON_URL = "https://maps.dwd.de/geoserver/dwd/ows?service=WFS&version=2.0.0&request=GetFeature&typeName=dwd:Warngebiete_Gemeinden&outputFormat=application/json"
DWD_WARNINGS_URL = "https://www.dwd.de/DWD/warnungen/warnapp/json/warnings.json"

REQUEST_TIMEOUT = 10  # Sekunden
# Passen Sie den User-Agent ggf. mit Ihrer E-Mail-Adresse oder einer Projekt-URL an
USER_AGENT = 'DWD-WarnApp-Improved/1.1 (https://example.com/contact)'


# --- Funktionen ---

def get_coordinates(place: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Ermittelt die geografischen Koordinaten (Latitude, Longitude) eines Ortsnamens
    über OpenStreetMap (Nominatim).

    Args:
        place: Der Name des Ortes.

    Returns:
        Ein Tupel (Latitude, Longitude, Fehlermeldung).
        Latitude und Longitude sind None im Fehlerfall.
        Fehlermeldung ist None im Erfolgsfall.
    """
    url = NOMINATIM_URL_TEMPLATE.format(urllib.parse.quote(place))
    headers = {'User-Agent': USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()  # Löst HTTPError für 4xx/5xx Statuscodes aus

        data = response.json()
        if data and isinstance(data, list) and len(data) > 0:
            # Überprüfen, ob die erwarteten Schlüssel vorhanden sind
            if "lat" in data[0] and "lon" in data[0]:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                return lat, lon, None
            else:
                return None, None, "Fehler: Unerwartetes Datenformat von Nominatim (fehlende lat/lon)."
        else:
            return None, None, f"Keine Koordinaten für '{place}' gefunden."
    except requests.exceptions.Timeout:
        return None, None, "Fehler: Zeitüberschreitung bei der Anfrage an Nominatim."
    except requests.exceptions.HTTPError as e:
        return None, None, f"Fehler: HTTP-Fehler von Nominatim: {e}"
    except requests.exceptions.RequestException as e:
        return None, None, f"Fehler: Netzwerkproblem bei der Anfrage an Nominatim: {e}"
    except json.JSONDecodeError:
        return None, None, "Fehler: Ungültige JSON-Antwort von Nominatim."
    except (ValueError, TypeError) as e:
        return None, None, f"Fehler: Datenverarbeitungsfehler bei Nominatim-Antwort: {e}"


def get_ags_from_coordinates(lat: float, lon: float) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Bestimmt den AGS-Code und Gemeindenamen aus Koordinaten per DWD-GeoJSON.

    Args:
        lat: Breitengrad.
        lon: Längengrad.

    Returns:
        Ein Tupel (AGS-Code, Gemeindename, Fehlermeldung).
        AGS-Code und Gemeindename sind None im Fehlerfall.
        Fehlermeldung ist None im Erfolgsfall.
    """
    try:
        response = requests.get(DWD_GEOJSON_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        point = Point(lon, lat)

        if "features" not in data or not isinstance(data["features"], list):
            return None, None, "Fehler: Unerwartetes Format der GeoJSON-Daten vom DWD (fehlende 'features')."

        for feature in data["features"]:
            if "geometry" not in feature or "properties" not in feature:
                # Geometrie oder Eigenschaften fehlen im Feature, überspringen
                continue

            try:
                geometry = shape(feature["geometry"])
                if geometry.contains(point):
                    properties = feature["properties"]
                    ags = properties.get("AGS")
                    name = properties.get("NAME", "Unbekannt")
                    if ags:  # Sicherstellen, dass AGS vorhanden ist
                        return ags, name, None
            except Exception as e:  # Fängt Fehler von shapely ab (z.B. bei ungültiger Geometrie)
                print(f"Hinweis: Fehler bei der Verarbeitung einer Geometrie: {e}")
                continue  # Mit dem nächsten Feature fortfahren

        return None, None, "Kein passendes Warngebiet (AGS) für die Koordinaten gefunden."
    except requests.exceptions.Timeout:
        return None, None, "Fehler: Zeitüberschreitung bei der Anfrage an den DWD GeoServer."
    except requests.exceptions.HTTPError as e:
        return None, None, f"Fehler: HTTP-Fehler vom DWD GeoServer: {e}"
    except requests.exceptions.RequestException as e:
        return None, None, f"Fehler: Netzwerkproblem bei der Anfrage an den DWD GeoServer: {e}"
    except json.JSONDecodeError:
        return None, None, "Fehler: Ungültige JSON-Antwort vom DWD GeoServer."
    except Exception as e:  # Fängt andere unerwartete Fehler ab
        return None, None, f"Unerwarteter Fehler bei der AGS-Ermittlung: {e}"


def format_timestamp(ms: Optional[int]) -> str:
    """
    Wandelt einen Unix-Zeitstempel (in Millisekunden) in ein deutsches
    Datums-/Zeitformat um.

    Args:
        ms: Zeitstempel in Millisekunden oder None.

    Returns:
        Formatierter Zeitstring oder "N/A" falls ms None ist.
    """
    if ms is None:
        return "N/A"
    try:
        return datetime.fromtimestamp(ms / 1000).strftime("%H:%M Uhr am %d.%m.%Y")
    except (ValueError, TypeError):
        return "Ungültiger Zeitstempel"


def get_warnings_by_ags(ags_code: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Sucht DWD-Warnungen für einen AGS-Code.
    Vergleicht WarnCell-IDs anhand der ersten 5 Ziffern des AGS-Codes (Kreisebene).

    Args:
        ags_code: Der AGS-Code (Amtlicher Gemeindeschlüssel).

    Returns:
        Eine Liste mit Warnmeldungen und eine optionale Fehlermeldung.
        Die Liste ist leer, wenn keine Warnungen gefunden wurden oder ein Fehler auftrat.
    """
    if not ags_code or len(ags_code) < 5:
        return [], "Fehler: Ungültiger oder zu kurzer AGS-Code für die Warnungssuche."

    ags_kreis = ags_code[:5]  # Die ersten 5 Ziffern des AGS repräsentieren i.d.R. den Kreis

    try:
        response = requests.get(DWD_WARNINGS_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        text = response.text

        # JSON-P Wrapper entfernen: DWD gibt JSON in Funktion eingebettet zurück (z.B. warnWetter.loadWarnings(...))
        json_start_index = text.find('(')
        json_end_index = text.rfind(')')

        if json_start_index == -1 or json_end_index == -1 or json_start_index >= json_end_index:
            return [], "Fehler: Unerwartetes JSONP-Format von der DWD Warnungs-API."

        json_str = text[json_start_index + 1:json_end_index]
        data = json.loads(json_str)

        if "warnings" not in data or not isinstance(data["warnings"], dict):
            return [], "Fehler: Unerwartetes Format der Warnungsdaten vom DWD (fehlende 'warnings')."

        all_warnings_raw = data["warnings"]
        matched_warnings: List[Dict[str, Any]] = []

        # Nur Warnzellen vergleichen, deren mittlere 5 Stellen (Index 1-5) mit AGS[:5] übereinstimmen
        # Annahme: WarnCell-ID-Format ist z.B. 'X<Kreis-ID>...'
        for warncell_id_str, warnings_for_cell in all_warnings_raw.items():
            if not isinstance(warncell_id_str, str) or len(warncell_id_str) < 6:
                # Ungültige oder zu kurze WarnCell-ID, überspringen
                continue

            # Die WarnCellID des DWD hat oft die Form <TypZiffer><Kreisदर्शकSchlüssel>...
            # z.B. 803257000 (Typ 8, Kreis 03257 ...)
            # Der Vergleich ist hier warncell_id[1:6] == ags_kreis
            if warncell_id_str[1:6] == ags_kreis:
                if isinstance(warnings_for_cell, list):
                    matched_warnings.extend(warnings_for_cell)

        return matched_warnings, None
    except requests.exceptions.Timeout:
        return [], "Fehler: Zeitüberschreitung bei der Anfrage an die DWD Warnungs-API."
    except requests.exceptions.HTTPError as e:
        return [], f"Fehler: HTTP-Fehler von der DWD Warnungs-API: {e}"
    except requests.exceptions.RequestException as e:
        return [], f"Fehler: Netzwerkproblem bei der Anfrage an die DWD Warnungs-API: {e}"
    except json.JSONDecodeError:
        return [], "Fehler: Ungültige JSON-Antwort von der DWD Warnungs-API."
    except Exception as e:  # Fängt andere unerwartete Fehler ab
        return [], f"Unerwarteter Fehler beim Abrufen der Warnungen: {e}"


# --- Hauptprogrammablauf ---
if __name__ == "__main__":
    ort = input("Ort eingeben (z.B. Köln): ")
    if not ort.strip():
        print("❌ Keine Eingabe. Bitte geben Sie einen Ort ein.")
    else:
        lat, lon, error_coords = get_coordinates(ort)

        if error_coords:
            print(f"❌ {error_coords}")
        elif lat is not None and lon is not None:
            print(f"Koordinaten für {ort}: Breitengrad {lat:.4f}, Längengrad {lon:.4f}")
            ags, gemeindename, error_ags = get_ags_from_coordinates(lat, lon)

            if error_ags:
                print(f"❌ {error_ags}")
            elif ags and gemeindename:
                print(f"✔ Gemeinde gefunden: {gemeindename} (AGS: {ags})")
                warnungen, error_warn = get_warnings_by_ags(ags)

                if error_warn:
                    print(f"❌ {error_warn}")
                elif warnungen:
                    print(f"\n⚠️ {len(warnungen)} Warnung(en) für {gemeindename} (Kreisebene {ags[:5]}):\n")
                    for w in warnungen:
                        print(f"📌 Ereignis: {w.get('event', 'N/A')}")
                        print(f"🏷️ Titel: {w.get('headline', 'N/A')}")
                        level_text = w.get('level_name',
                                           f"Stufe {w.get('level', 'N/A')}")  # Bevorzugt level_name falls vorhanden
                        print(f"🟠 Warnstufe: {level_text} | Typ: {w.get('type', 'N/A')}")
                        print(f"📍 Region: {w.get('regionName', 'N/A')} ({w.get('stateShort', w.get('state', 'N/A'))})")
                        print(f"🕒 Von: {format_timestamp(w.get('start'))}")
                        print(f"🕒 Bis: {format_timestamp(w.get('end'))}")

                        description = w.get('description', '').replace(chr(10), ' ').strip()
                        if not description: description = "Keine Beschreibung vorhanden."
                        print(f"📝 Beschreibung: {description}")

                        instruction = w.get('instruction', '').replace(chr(10), ' ').strip()
                        if instruction:
                            print(f"📋 Verhaltensempfehlung: {instruction}")
                        print("-" * 50)
                else:
                    print(f"✅ Keine aktuellen Warnungen für {gemeindename} (Kreisebene {ags[:5]}).")
            else:
                # Dieser Fall sollte durch error_ags abgedeckt sein, aber als Fallback
                print("❌ Kein AGS-Code für die gefundenen Koordinaten ermittelt.")
        else:
            # Dieser Fall sollte durch error_coords abgedeckt sein
            print("❌ Ort nicht gefunden oder keine Koordinaten ermittelt.")
