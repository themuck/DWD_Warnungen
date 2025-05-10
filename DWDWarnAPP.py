# -*- coding: utf-8 -*-
"""
Dieses Skript ruft aktuelle Wetterwarnungen des Deutschen Wetterdienstes (DWD) ab
und zeigt Warnungen für einen vom Benutzer angegebenen Ort an.

Funktionsweise:
1.  Herunterladen der DWD-Wetterwarndaten:
    - Lädt eine ZIP-Datei von der DWD OpenData-Seite herunter, die aktuelle
      Wetterwarnungen im CAP (Common Alerting Protocol) XML-Format enthält.
    - Entpackt die ZIP-Datei und liest die darin enthaltene XML-Datei.

2.  Verarbeitung der XML-Warndaten:
    - Parst die XML-Datei, um alle einzelnen Warnmeldungen zu extrahieren.
    - Für jede Warnung werden Details wie Ereignistyp, Überschrift, Beschreibung,
      Beginn, Ende, Schweregrad, Nachrichtentyp (z.B. "Alert", "Update"),
      betroffene Region (areaDesc) und der zugehörige Amtliche Gemeindeschlüssel
      (AGS), der aus der WARNCELLID abgeleitet wird, gespeichert.

3.  Standortbestimmung des Benutzers:
    - Fragt den Benutzer nach einem Ortsnamen.
    - `get_coordinates(place)`: Verwendet den Nominatim-Dienst von OpenStreetMap,
      um die geografischen Koordinaten (Breitengrad, Längengrad) des eingegebenen
      Ortsnamens zu ermitteln.
    - `get_ags_from_coordinates(lat, lon)`: Verwendet die ermittelten Koordinaten,
      um über einen DWD Web Feature Service (WFS) den genauen Amtlichen
      Gemeindeschlüssel (AGS) und den offiziellen Namen des Ortes zu bestimmen.
      Dies geschieht durch Überprüfung, in welchem DWD-Warngemeinde-Polygon
      die Koordinaten liegen.

4.  Abgleich und Anzeige von Warnungen:
    - Vergleicht den AGS des vom Benutzer angegebenen Ortes mit den AGS-Codes der
      abgerufenen DWD-Warnungen.
    - Eine Warnung gilt als relevant, wenn der AGS des Ortes mit dem AGS-Code der
      Warnung beginnt (z.B. eine Warnung für einen Landkreis betrifft alle
      Gemeinden in diesem Landkreis).
    - Zeigt alle relevanten Warnungen für den angegebenen Ort mit detaillierten
      Informationen an.

Abhängigkeiten:
- requests: Für HTTP-Anfragen (Download der DWD-Daten, Nominatim, DWD WFS).
- shapely: Für geometrische Operationen (Prüfung, ob ein Punkt in einem Polygon liegt).
- zipfile: Zum Entpacken der DWD-ZIP-Datei.
- xml.etree.ElementTree: Zum Parsen der CAP-XML-Warndaten.
- urllib.parse: Zum Kodieren von URL-Parametern.

Hinweis:
- Die User-Agent-Kennung in `get_coordinates` ist für die Nutzung von Nominatim
  wichtig und sollte an die eigene Anwendung angepasst werden.
- Das Skript geht davon aus, dass die relevante XML-Datei im DWD-ZIP die erste
  XML-Datei ist oder spezifisch nach ".xml" endet.
- Die WARNCELLID des DWD für COMMUNEUNION beginnt oft mit einer '1', gefolgt vom
  AGS. Diese '1' wird entfernt, um den reinen AGS zu erhalten.
"""

import zipfile
import xml.etree.ElementTree as ET
import requests
from shapely.geometry import Point, shape
from io import BytesIO
import urllib.parse

# URL der DWD-Warn-XML-Daten
ZIP_URL = "https://opendata.dwd.de/weather/alerts/cap/COMMUNEUNION_DWD_STAT/Z_CAP_C_EDZW_LATEST_PVW_STATUS_PREMIUMDWD_COMMUNEUNION_DE.zip"

# XML Namespaces
NS = {'cap': 'urn:oasis:names:tc:emergency:cap:1.2'}


# Funktion, um die Koordinaten eines Orts anhand des Namens zu bekommen
def get_coordinates(place):
    """
    Diese Funktion verwendet den Nominatim-Dienst von OpenStreetMap, um die
    geographischen Koordinaten (Breitengrad und Längengrad) eines Ortes zu ermitteln.
    """
    # Ersetze Leerzeichen und Sonderzeichen im Ortsnamen für die URL
    encoded_place = urllib.parse.quote(place)
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={encoded_place}"
    headers = {'User-Agent': 'AGS-WarnApp/1.0 (https://example.com)'} # Wichtig: Eigene User-Agent-Kennung verwenden!
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Löst einen Fehler aus für HTTP-Fehlercodes 4xx/5xx
        data = response.json()
        if data:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            return lat, lon
    except requests.exceptions.RequestException as e:
        print(f"Fehler bei der Abfrage der Koordinaten: {e}")
    except (IndexError, KeyError, ValueError) as e:
        print(f"Fehler beim Parsen der Koordinatendaten: {e}")
    return None, None


# Funktion, um anhand der Koordinaten den AGS-Code und den Ortsnamen zu bestimmen
def get_ags_from_coordinates(lat, lon):
    """
    Diese Funktion holt die AGS-Nummer und den Namen des Ortes anhand der
    geographischen Koordinaten aus dem DWD-Datenbestand (Warngebiete Gemeinden).
    """
    url = "https://maps.dwd.de/geoserver/dwd/ows?service=WFS&version=2.0.0&request=GetFeature&typeName=dwd:Warngebiete_Gemeinden&outputFormat=application/json"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        point = Point(lon, lat)  # Shapely Point: (lon, lat)

        for feature in data["features"]:
            # Überprüfen, ob die Geometrie gültig ist
            if feature["geometry"] is None:
                continue
            try:
                geometry = shape(feature["geometry"])
                if geometry.contains(point):
                    ags = feature["properties"].get("AGS")
                    name = feature["properties"].get("NAME", "Unbekannt")
                    # Sicherstellen, dass der AGS eine Zeichenkette ist
                    return str(ags) if ags is not None else None, name
            except Exception as e:
                # Fehler beim Verarbeiten einer spezifischen Geometrie ignorieren und fortfahren
                # print(f"Hinweis: Fehler beim Verarbeiten einer Geometrie für AGS-Bestimmung: {e}")
                pass

    except requests.exceptions.RequestException as e:
        print(f"Fehler bei der Abfrage der AGS-Daten: {e}")
    except (KeyError, ValueError) as e:
        print(f"Fehler beim Parsen der AGS-Daten: {e}")
    return None, None


# Lade die ZIP-Datei von DWD herunter
print("Lade Wetterwarnungen des DWD herunter...")
try:
    response = requests.get(ZIP_URL, timeout=30)
    response.raise_for_status()
    zip_file_content = BytesIO(response.content)
except requests.exceptions.RequestException as e:
    print(f"Fehler beim Herunterladen der ZIP-Datei: {e}")
    exit()

all_warnings_data = []  # Liste zum Speichern aller extrahierten Warnungen

try:
    with zipfile.ZipFile(zip_file_content) as zip_f:
        zip_file_list = zip_f.namelist()
        if not zip_file_list:
            print("ZIP-Datei ist leer oder enthält keine Dateien.")
        else:
            # Annahme: Die relevante XML-Datei ist die erste in der Liste
            # DWD-ZIPs enthalten oft nur eine CAP-XML-Datei.
            # Falls es mehrere gibt, könnte hier eine spezifischere Auswahl nötig sein.
            xml_file_name = ""
            for name in zip_file_list:
                if name.lower().endswith('.xml'):  # Suche nach der ersten XML-Datei
                    xml_file_name = name
                    break

            if not xml_file_name:
                print("Keine XML-Datei im ZIP-Archiv gefunden.")
            else:
                print(f"Verarbeite Warnungsdatei: {xml_file_name}")
                with zip_f.open(xml_file_name) as xml_file:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()  # Das <alert> Element

                    msg_type_elem = root.find("cap:msgType", NS)
                    msg_type = msg_type_elem.text if msg_type_elem is not None else "Unbekannt"

                    # Iteration über alle "info"-Elemente, die die Warnungen beinhalten
                    for info in root.findall("cap:info", NS):
                        lang_elem = info.find("cap:language", NS)
                        if lang_elem is None or lang_elem.text.strip().lower() != "de-de":
                            continue

                        event_elem = info.find("cap:event", NS)
                        headline_elem = info.find("cap:headline", NS)
                        description_elem = info.find("cap:description", NS)
                        onset_elem = info.find("cap:onset", NS)
                        expires_elem = info.find("cap:expires", NS)
                        severity_elem = info.find("cap:severity", NS)

                        event = event_elem.text if event_elem is not None else "Unbekannt"
                        headline = headline_elem.text if headline_elem is not None else ""
                        description = description_elem.text if description_elem is not None else ""
                        onset = onset_elem.text if onset_elem is not None else "k.A."
                        expires = expires_elem.text if expires_elem is not None else "k.A."
                        severity = severity_elem.text if severity_elem is not None else "Unbekannt"

                        for area in info.findall("cap:area", NS):
                            area_desc_elem = area.find("cap:areaDesc", NS)
                            area_desc = area_desc_elem.text if area_desc_elem is not None else "Unbekannte Region"

                            polygon_elem = area.find("cap:polygon", NS)
                            has_polygon = "ja" if polygon_elem is not None and polygon_elem.text and polygon_elem.text.strip() else "nein"

                            for geocode in area.findall("cap:geocode", NS):
                                value_name_elem = geocode.find("cap:valueName", NS)
                                value_elem = geocode.find("cap:value", NS)
                                if value_name_elem is not None and value_elem is not None and value_name_elem.text == "WARNCELLID":
                                    warncell_id = value_elem.text
                                    # Entferne die führende Ziffer in der Warncell-ID, um den AGS-Code zu erhalten
                                    # DWD WARNCELLIDs für COMMUNEUNION sind oft 1 gefolgt vom AGS des Kreises/Gemeindeverbands
                                    ags_code_from_warncell = warncell_id[1:] if warncell_id.startswith('1') and len(
                                        warncell_id) > 1 else warncell_id

                                    all_warnings_data.append({
                                        "event": event,
                                        "headline": headline,
                                        "description": description,
                                        "onset": onset,
                                        "expires": expires,
                                        "severity": severity,
                                        "msg_type": msg_type,
                                        "area_desc": area_desc,
                                        "has_polygon": has_polygon,
                                        "warncell_id": warncell_id,
                                        "ags_code": ags_code_from_warncell  # AGS der gewarnten Region
                                    })
except zipfile.BadZipFile:
    print("Fehler: Die heruntergeladene Datei ist keine gültige ZIP-Datei.")
    exit()
except ET.ParseError:
    print("Fehler beim Parsen der XML-Warndaten.")
    exit()
except Exception as e:
    print(f"Ein unerwarteter Fehler ist beim Verarbeiten der ZIP/XML-Datei aufgetreten: {e}")
    exit()

# Schritt 1: Eingabe für den Ort
place_name_input = input("Ort eingeben (z.B. Frischborn, Berlin, München): ").strip()
if not place_name_input:
    print("Kein Ort eingegeben. Programm wird beendet.")
    exit()

# Schritt 2: Koordinaten des Ortes holen
print(f"\nSuche Koordinaten für '{place_name_input}'...")
lat, lon = get_coordinates(place_name_input)

if lat is not None and lon is not None:
    print(f"✔ Koordinaten für '{place_name_input}' gefunden: Breitengrad={lat}, Längengrad={lon}")

    # Schritt 3: AGS und offiziellen Namen des Ortes anhand der Koordinaten bestimmen
    print(f"Bestimme Amtlichen Gemeindeschlüssel (AGS) für die Koordinaten...")
    location_ags, location_name = get_ags_from_coordinates(lat, lon)

    if location_ags and location_name:
        print(f"✔ Ort als '{location_name}' mit AGS '{location_ags}' identifiziert.")

        print(f"\n⚠️ Aktuelle Wetterwarnungen für '{location_name}' (AGS: {location_ags}):")

        found_warnings_for_location = False
        if all_warnings_data:
            for details in all_warnings_data:
                # Prüfen, ob der AGS des Ortes mit dem AGS der Warnung übereinstimmt
                # (z.B. Ort-AGS "06digits" startet mit Warnungs-AGS "06digits" (Kreis))
                # oder wenn der Warnungs-AGS spezifischer ist und mit dem Ort-AGS übereinstimmt.
                # Hauptsächlich ist relevant, ob eine Warnung für einen Kreis (details['ags_code'])
                # die Gemeinde (location_ags) beinhaltet.
                if location_ags.startswith(details['ags_code']):
                    found_warnings_for_location = True
                    print("\n--------------------------------------------------")
                    print(f"📢 Ereignis: {details['event']}")
                    print(f"🏷️ Titel: {details['headline']}")
                    print(f"❗ Schweregrad: {details['severity']} ({details['msg_type']})")
                    print(f"📍 Gewarnte Region: {details['area_desc']} (AGS der Warnung: {details['ags_code']})")
                    print(f"🕒 Von: {details['onset']}")
                    print(f"🕒 Bis: {details['expires']}")
                    print(f"📝 Beschreibung: {details['description']}")
                    if details['has_polygon'] == "ja":
                        print(f"🌐 Enthält Polygon-Daten: {details['has_polygon']}")
                    # print(f"🆔 Warncell-ID: {details['warncell_id']}") # Optional für Debugging
                    print("--------------------------------------------------")

            if not found_warnings_for_location:
                print(
                    f"👍 Keine spezifischen Warnungen für '{location_name}' (AGS: {location_ags}) in den aktuellen Daten gefunden.")
        else:
            print("ℹ️ Keine Warnmeldungen in den heruntergeladenen Daten gefunden.")
    else:
        print(
            f"⚠️ Der Ort '{place_name_input}' ({lat}, {lon}) konnte keinem gültigen AGS zugeordnet werden. Überprüfe, ob der Ort in Deutschland liegt und von den DWD-Daten abgedeckt ist.")
else:
    print(
        f"⚠️ Der Ort '{place_name_input}' konnte nicht gefunden werden oder es gab ein Problem bei der Koordinatenabfrage.")

