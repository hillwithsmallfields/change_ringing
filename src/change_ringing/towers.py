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
    "Wt": "Pounds",
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
    'Affiliations': lambda affiliations: affiliations.split(';'),
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
        self._neighbours_cache = None
        self.routes_from = dict()

    def normalise(self):
        """Complete the setup of a Tower object."""
        self.longlat = (self.longitude, self.latitude)
        self.navlonglat = (self.satnav_longitude, self.satnav_latitude)
        self.xy = self.collection.transformer.transform(self.longitude, self.latitude)
        self.x, self.y = self.xy
        if isinstance(self.pounds, float):
            self.kilograms = self.pounds / 2.2046226218488
            self.weight = "%d-%d-%d" % (self.pounds // 112, (self.pounds // 28) % 4, self.pounds % 28)
        else:
            self.kilograms = ""
            self.weight = ""
        return self

    def from_dove(self, dove_row):
        """Fill in a Tower object from a row of the Dove CSV file."""
        for key, value in dove_row.items():
            setattr(self,
                    COLUMN_RENAMES.get(key, key).lower(),
                    convert_if_possible(value, COLUMN_CONVERTERS.get(key, lambda a: a)))
        return self.normalise()

    def to_dict(self, fields):
        """Return a dictionary of the specified fields of this tower."""
        return {field: (getattr(self, field)
                        if hasattr(self, field)
                        else "")
                for field in fields}

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
        if self._neighbours_cache is None:
            self._neighbours_cache = sorted(self.collection.by_id.values(),
                                            key=lambda other: math.dist(self.xy, other.xy))
        return self._neighbours_cache[1:(n+1) or 1000000]

    def within(self, distance, miles=True):
        """Return a collection of towers within a given distance of this one."""
        if miles:
            distance *= 1609.344
        result = TowerCollection(projection=self.collection.projection)
        for tower in self.collection.by_id.values():
            if math.dist(self.xy, tower.xy) <= distance:
                result.add_tower(copy.copy(tower))
        return result

    def crow(self, other, miles=True):
        """Return the distance to another tower as the crow flies.
        The distance is miles by default, metres on request."""
        return math.dist(self.xy, other.xy) / (1609.344 if miles else 1)

    def route_from(self, other, mode='driving'):
        """Return the route from another tower, as computed by OSRM."""
        other_id = "%s from %d" % (mode, other.tower_id)
        if other_id not in self.routes_from:
            self.routes_from[other_id] = requests.get(("http://router.project-osrm.org/route/v1/%s/%f,%f;%f,%f"
                                                       % (mode, other.longitude, other.latitude, self.longitude, self.latitude)),
                                                      params={'geometries': 'geojson'}).json()
        return self.routes_from[other_id]

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
            tower.collection = self

    def __getitem__(self, key):
        return self.by_name[key]

    def to_list(self, fields):
        """Return a list of dicts describing this collection."""
        return [tower.to_dict(fields) for tower in self.by_id.values()]

    def dump_csv(self, filename, fields):
        """Dump this collection to a CSV file.
        Only the specified attributes are written.
        Unknown columns are written as blanks."""
        with open(filename, 'w') as outstream:
            writer = csv.DictWriter(outstream, fields)
            writer.writeheader()
            for row in self.to_list(fields):
                writer.writerow(row)

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

    def ringable(self):
        """Return a collection of the ringable towers in this collection."""
        return self.filter_towers(lambda tower: not tower.unringable)

    def with_toilet(self):
        """Return a collection of the towers with toilets in this collection."""
        return self.filter_towers(lambda tower: tower.toilet)

    def ground_floor(self):
        """Return a collection of the ground-floor towers in this collection."""
        return self.filter_towers(lambda tower: tower.ground_floor)

    def in_county(self, county):
        """Return a collection of the towers in this collection in the given county."""
        return self.filter_towers(lambda tower: tower.county == county)

    def in_diocese(self, diocese):
        """Return a collection of the towers in this collection in the given diocese."""
        return self.filter_towers(lambda tower: tower.diocese == diocese)

    def affiliated_to(self, affiliation):
        """Return a collection of the towers in this collection with the given affiliation."""
        return self.filter_towers(lambda tower: affiliation in tower.affiliations)

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
    dove = read_dove().bells_range(6,8).ringable()
    # for k, v in dove.by_name.items():
    #     print(k, v)
    combe_florey = dove["Combe Florey"][0]
    print(combe_florey)
    nearby = combe_florey.neighbours(12)
    for i, tower in enumerate(nearby):
        print(i+1, combe_florey.crow(tower), tower)
    in_twelve_miles = combe_florey.within(12)
    in_twelve_miles.dump_csv("/tmp/12miles.csv", ['place', 'dedication', 'longitude', 'latitude'])
    for i, tower in enumerate(in_twelve_miles.by_id.values()):
        print(i+1, tower, combe_florey.crow(tower))
    dove.dump_csv("/tmp/some_cols.csv", ['place', 'dedication', 'weight', 'requested', 'replied'])
    dove.affiliated_to("Ely Diocesan Association").dump_csv("/tmp/eda.csv", ['place', 'dedication', 'weight', 'requested', 'replied'])
    dove.in_diocese("Ely").dump_csv("/tmp/ely.csv", ['place', 'dedication', 'weight', 'requested', 'replied'])
    dove.in_county("Cambridgeshire").dump_csv("/tmp/cambs.csv", ['place', 'dedication', 'weight', 'requested', 'replied'])
    print(combe_florey.route_from(dove["West Bagborough"][0]))

if __name__ == "__main__":
    main_for_testing()
