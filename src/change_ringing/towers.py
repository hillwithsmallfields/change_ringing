#!/usr/bin/env python3

import collections
import csv
import datetime
import os
import requests

DOVE_FILE = os.path.expanduser("~/Downloads/dove.csv")
DOVE_URL = "https://dove.cccbr.org.uk/towers.csv"

COLUMN_RENAMES = {
    "TowerID": "Tower_ID",
    "RingID": "Ring_ID",
    "RingType": "Ring_Type",
    "Place2": "Place2",
    "PlaceCL": "PlaceCL",
    "Dedicn": "Dedication",
    "TowerStatus": "Tower_Status",
    "StatusFirst": "Status_First",
    "BareDedicn": "Bare_Dedication",
    "AltName": "Alternative_Name",
    "RingName": "Ring_Name",
    "HistRegion": "Historical_Region",
    "ISO3166code": "ISO3166_code",
    "Lat": "Latitude",
    "Long": "Longitude",
    "UR": "UnRingable",
    "Wt": "Weight",
    "App": "App",
    "Hz": "Hertz",
    "Details": "Details",
    "GF": "Ground_Floor",
    "ExtraInfo": "Extra_Info",
    "WebPage": "Web_Page",
    "NG": "National_Grid",
    "Postcode": "Postcode",
    "Practice": "Practice",
    "OvhaulYr": "Overhaul_Date",
    "Contractor": "Contractor",
    "TuneYr": "Tuning_Date",
    "LGrade": "Listing_Grade",
    "BldgID": "Building_ID",
    "ChurchCare": "Church_Care",
    "CHRAssetID": "CHR_Asset_ID",
    "DoveID": "Dove_ID",
    "SNLat": "SatNav_Latitude",
    "SNLong": "SatNav_Longitude",
}

def convert_date(date_string):
    """Try to convert a string to a datetime.date, using the formats in the Dove file."""
    try:
        return datetime.date.strptime(date_string, "%d %b %Y")
    except ValueError:
        try:
            return datetime.date(int(date_string), 1, 1)
        except ValueError:
            return date_string

# Conversion functions to apply, going by the raw column names
COLUMN_CONVERTERS = {
    'TowerID': int,
    'RingID': int,
    'StatusFirst': lambda sf: sf == 'Y',
    'Lat': float,
    'Long': float,
    'Bells': int,
    'UR': lambda ur: ur == 'u/r',
    'Wt': float,
    'Hz': float,
    'GF': lambda gf: gf == 'GF',
    'Toilet': lambda toilet: toilet == 'T',
    'Simulator': lambda simulator: simulator == 'T',
    'OvhaulYr': convert_date,
    'TuneYr': convert_date,
    'TowerBase': int,
    'SNLat': float,
    'SNLong': float,
}

class Tower:

    """The representation of a tower as read from the Dove CSV file."""

    def __init__(self, dove_row):
        """Fill in a Tower object from a row of the Dove CSV file."""
        for key, value in dove_row.items():
            setattr(self,
                    COLUMN_RENAMES.get(key, key).lower(),
                    COLUMN_CONVERTERS.get(key, lambda a: a)(value))

    def __str__(self):
        return "<%d-bell tower %s: %s>" % (self.bells, self.tower_id, self.Place)

def tower_names(tower):
    """Return various names by which a tower may be known."""
    return set([tower['PlaceCL'] or tower['Place'],
                tower['Place'],
                tower['AltName'] or tower['Place'],
                "%s, %s" % (tower['Place'], tower['Dedicn']),
                "%s (%s)" % (tower['Place'], tower['County']),
                ])

def download_dove(force_fetch=False):
    """Fetch the Dove data as a CSV file if it is not present, or if forced."""
    if force_fetch or not os.path.exists(DOVE_FILE):
        print("Downloading tower data from Dove's Guide")
        download = requests.get(DOVE_URL)
        if download.status_code == 200:
            print("Saving Dove data")
            start = 0
            while ord(download.text[start]) & 0x80:
                start += 1
            with open(DOVE_FILE, 'w') as dove_save:
                dove_save.write(download.text[start:])
        else:
            print("Failed to fetch Dove data")

def read_dove(force_fetch=False):
    """Read the Dove data as a dictionary of lists.

    Each tower appears under multiple names, as returned by the function `tower_names`.

    Each entry is a list of towers with that name (so you can tell
    whether you need more information for disambiguation).

    The numerical TowerID from the Dove data is also used as a key.
    """
    download_dove(force_fetch)
    dove = collections.defaultdict(list)
    with open(DOVE_FILE) as dovestream:
        for tower in csv.DictReader(dovestream):
            for name in tower_names(tower):
                if (tower['RingType'] == 'Full-circle ring'
                    and tower['Bells'] != "1"):
                    dove[name].append(tower)
            dove[int(tower['TowerID'])] = tower
    return dove
