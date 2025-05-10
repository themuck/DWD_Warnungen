# -*- coding: utf-8 -*-
"""
Dieses Skript lädt GeoJSON-Daten der DWD-Warngemeinden von einem öffentlichen
WFS-Dienst des Deutschen Wetterdienstes (DWD).
Anschließend visualisiert es diese Daten als Karte mithilfe von GeoPandas und
Matplotlib und speichert die resultierende Karte als PNG-Datei.

Abhängigkeiten:
- geopandas
- matplotlib
- requests

Verwendete Datenquelle:
DWD GeoServer - Warngebiete_Gemeinden
URL: https://maps.dwd.de/geoserver/dwd/ows?service=WFS&version=2.0.0&request=GetFeature&typeName=dwd:Warngebiete_Gemeinden&outputFormat=application/json
"""

import geopandas as gpd
import matplotlib.pyplot as plt
import requests
from io import BytesIO
import logging
import sys

# Konfiguration für Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Konstanten
GEOJSON_URL = "https://maps.dwd.de/geoserver/dwd/ows?service=WFS&version=2.0.0&request=GetFeature&typeName=dwd:Warngebiete_Gemeinden&outputFormat=application/json"
OUTPUT_FILENAME = "dwd_warngebiete_gemeinden.png"
PLOT_TITLE = "DWD Warngebiete (Gemeinden)"
REQUEST_TIMEOUT = 30  # Sekunden

def fetch_geojson_data(url: str) -> bytes:
    """
    Lädt GeoJSON-Daten von der angegebenen URL.

    Args:
        url (str): Die URL zur GeoJSON-Datei.

    Returns:
        bytes: Der Inhalt der GeoJSON-Datei als Bytes.

    Raises:
        requests.exceptions.RequestException: Wenn ein Fehler beim Abrufen der Daten auftritt.
    """
    logging.info(f"Lade GeoJSON-Daten von: {url}")
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()  # Löst eine HTTPError für schlechte Antworten (4xx oder 5xx) aus
        logging.info("Daten erfolgreich heruntergeladen.")
        return response.content
    except requests.exceptions.RequestException as e:
        logging.error(f"Fehler beim Abrufen der Daten: {e}")
        raise

def load_geodata(geojson_content: bytes) -> gpd.GeoDataFrame:
    """
    Lädt GeoJSON-Inhalt in ein GeoDataFrame.

    Args:
        geojson_content (bytes): Der GeoJSON-Inhalt als Bytes.

    Returns:
        gpd.GeoDataFrame: Das geladene GeoDataFrame.

    Raises:
        Exception: Wenn ein Fehler beim Parsen des GeoJSON auftritt.
    """
    logging.info("Verarbeite GeoJSON zu GeoDataFrame...")
    try:
        gdf = gpd.read_file(BytesIO(geojson_content))
        if gdf.empty:
            logging.warning("Das geladene GeoDataFrame ist leer. Überprüfen Sie die Datenquelle oder den Inhalt.")
        else:
            logging.info(f"GeoDataFrame erfolgreich geladen mit {len(gdf)} Einträgen.")
        return gdf
    except Exception as e:
        logging.error(f"Fehler beim Laden des GeoJSON in GeoDataFrame: {e}")
        raise

def plot_and_save_map(gdf: gpd.GeoDataFrame, title: str, filename: str):
    """
    Erstellt einen Plot des GeoDataFrames und speichert ihn als PNG-Datei.

    Args:
        gdf (gpd.GeoDataFrame): Das zu plottende GeoDataFrame.
        title (str): Der Titel des Plots.
        filename (str): Der Dateiname für die zu speichernde PNG-Datei.
    """
    logging.info("Erstelle Plot...")
    fig, ax = plt.subplots(figsize=(10, 12)) # Figurengröße für bessere Lesbarkeit bei vielen Gemeinden

    if not gdf.empty:
        gdf.plot(
            ax=ax,
            edgecolor='black',
            facecolor='lightblue',
            linewidth=0.2,
            legend=False # Legende ist hier nicht relevant
        )
    else:
        logging.warning("GeoDataFrame ist leer, Plot wird möglicherweise leer sein.")
        # Optional: Text auf leeren Plot schreiben
        ax.text(0.5, 0.5, "Keine Daten zum Anzeigen", horizontalalignment='center', verticalalignment='center', transform=ax.transAxes)


    ax.axis('off')  # Achsen entfernen für eine saubere Kartenansicht
    ax.set_title(title, fontsize=15, pad=10) # Etwas Abstand für den Titel

    try:
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        logging.info(f"Karte erfolgreich gespeichert als: {filename}")
    except Exception as e:
        logging.error(f"Fehler beim Speichern der Karte: {e}")
        # Nicht erneut raisen, damit plt.show() noch aufgerufen werden kann, falls gewünscht.
        # Besser wäre es, die main-Funktion hier zu beenden.

    plt.show()

def main():
    """
    Hauptfunktion des Skripts.
    Führt das Laden, Verarbeiten und Plotten der DWD-Warngemeinden durch.
    """
    try:
        geojson_content = fetch_geojson_data(GEOJSON_URL)
        gdf = load_geodata(geojson_content)
        plot_and_save_map(gdf, PLOT_TITLE, OUTPUT_FILENAME)
        logging.info("Skript erfolgreich abgeschlossen.")
    except requests.exceptions.RequestException:
        # Fehler wurde bereits in fetch_geojson_data geloggt
        logging.error("Abbruch des Skripts aufgrund eines Netzwerkfehlers.")
        sys.exit(1) # Beendet das Skript mit einem Fehlercode
    except Exception as e:
        # Allgemeine Fehlerbehandlung für andere Ausnahmen
        logging.error(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
        sys.exit(1) # Beendet das Skript mit einem Fehlercode

if __name__ == "__main__":
    main()
