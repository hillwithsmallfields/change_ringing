#!/usr/bin/env python3

import collections
import copy
import csv
import datetime
import math
import os
import requests

import pyproj

DOVE_FILE = os.path.expanduser("~/Downloads/dove.csv")
DOVE_URL = "https://dove.cccbr.org.uk/towers.csv"

# Make column names more suitable for use as object attribute names;
# whether or not found in this table, they are downcased for use.
COLUMN_RENAMES = {
    "TowerID": "Tower_ID",
    "RingID": "Ring_ID",
    "RingType": "Full_Circle",
    "Place2": "Sub_Place2",
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
        return datetime.datetime.strptime(date_string, "%d %b %Y").date()
    except ValueError:
        try:
            return datetime.date(int(date_string), 1, 1)
        except ValueError:
            return date_string

def convert_if_possible(raw_value, converter):
    try:
        return converter(raw_value)
    except ValueError:
        return raw_value

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

    def __init__(self, dove_collection):
        """Set up a Tower object.
        It is given a back-reference to the collection of which it is part."""
        self.collection = dove_collection

    def normalise(self):
        """Complete the setup of a Tower object."""
        self.longlat = (self.longitude, self.latitude)
        self.navlonglat = (self.satnav_longitude, self.satnav_latitude)
        self.xy = self.collection.transformer.transform(self.longitude, self.latitude)
        self.x, self.y = self.xy
        return self

    def from_dove(self, dove_row):
        """Fill in a Tower object from a row of the Dove CSV file."""
        for key, value in dove_row.items():
            setattr(self,
                    COLUMN_RENAMES.get(key, key).lower(),
                    convert_if_possible(value, COLUMN_CONVERTERS.get(key, lambda a: a)))
        return self.normalise()

    def __str__(self):
        return "<%d-bell tower %s>" % (self.bells, self.place)

    def __repr__(self):
        return "<%d-bell tower %s: %s>" % (self.bells, self.tower_id, self.place)

    def names(self):
        """Return various names by which a tower may be known."""
        return set([self.placecl or self.place,
                    self.place,
                    self.alternative_name or self.place,
                    "%s, %s" % (self.place, self.dedication),
                    "%s (%s)" % (self.place, self.county),
                    ])

    def neighbours(self, n=None):
        """Return the rest of the towers in order of closeness to this one.
        If N is given, return only the nearest N neighbours."""
        return sorted(self.collection.by_id.values(),
                      key=lambda other: math.dist(self.xy, other.xy))[1:(n+1) or 1000000]

    def crow(self, other, miles=True):
        """Return the distance to another tower as the crow flies.
        The distance is miles by default, metres on request."""
        return math.dist(self.xy, other.xy) / (1609.344 if miles else 1)

    def copy_into(self, collection):
        new = copy.copy(self)
        new.collection = collection
        return new

class TowerCollection:

    """A collection of towers, by name and by ID."""

    def __init__(self,
                 projection="EPSG:3857",
                 ):
        self.by_name = collections.defaultdict(list)
        self.by_id = dict()
        self.projection = projection
        self.transformer = pyproj.Transformer.from_crs("EPSG:4326", self.projection)

    def add_tower(self, tower):
        if (tower.full_circle and tower.bells > 1):
            for name in tower.names():
                self.by_name[name].append(tower)
            self.by_name[tower.tower_id].append(tower)
            self.by_id[tower.tower_id] = tower

    def __getitem__(self, key):
        return self.by_name[key]

    def filter_towers(self, predicate):
        """Return a collection filtered by a predicate."""
        result = TowerCollection(projection=self.projection)
        for k, v in self.by_name.items():
            for t in v:
                if predicate(t):
                    result.by_name[k].append(t.copy_into(result))
        for k, v in self.by_id.items():
            if predicate(v):
                result.by_id[k] = v.copy_into(result)
        return result

    def bells_range(self, minimum=None, maximum=None):
        """Return a collection filtered by the number of bells."""
        return self.filter_towers(lambda tower: tower.bells in set(range(minimum or 1, (maximum or 19) + 1)))

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
    """Read the Dove data into a TowerCollection.

    Each tower appears under multiple names, as returned by the function `tower_names`.

    Each entry is a list of towers with that name (so you can tell
    whether you need more information for disambiguation).

    The numerical TowerID from the Dove data is also used as a key.
    """
    download_dove(force_fetch)
    dove = TowerCollection()
    with open(DOVE_FILE) as dovestream:
        for tower in csv.DictReader(dovestream):
            dove.add_tower(Tower(dove).from_dove(tower))
    return dove

def main_for_testing():
    dove = read_dove().bells_range(6,8)
    # for k, v in dove.by_name.items():
    #     print(k, v)
    combe_florey = dove["Combe Florey"][0]
    print(combe_florey)
    for i, tower in enumerate(combe_florey.neighbours(12)):
        print(i+1, combe_florey.crow(tower), tower)

if __name__ == "__main__":
    main_for_testing()
