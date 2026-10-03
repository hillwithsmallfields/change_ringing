#!/usr/bin/env python3

import argparse
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

def cell_text(column_name, cell_value):
    return (', '.join('<a href="%s">%s</a>' % (url, url)
                      for url in cell_value.split(' '))
            if column_name == 'web_page'
            else cell_value)

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

    def normalise(self):
        """Complete the setup of a Tower object."""
        self.longlat = (self.longitude, self.latitude)
        self.navlonglat = (self.satnav_longitude, self.satnav_latitude)
        if not isinstance(self.longitude, float) or not isinstance(self.latitude, float):
            self.longitude = 0.0
            self.latitude = 0.0
        self.xy = self.collection.transformer.transform(self.longitude, self.latitude)
        self.x, self.y = self.xy
        if isinstance(self.pounds, float):
            self.kilograms = self.pounds / 2.2046226218488
            self.weight = "%d-%d-%d" % (self.pounds // 112, (self.pounds // 28) % 4, self.pounds % 28)
        else:
            self.kilograms = ""
            self.weight = ""
        if not isinstance(self.bells, int):
            self.bells = 0
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

    def my_type_of_collection(self):
        """Make a new collection of the same type as the one containing this tower."""
        return type(self.collection)(projection=self.collection.projection,
                                     tower_type=type(self))

    def within(self, distance, miles=True):
        """Return a collection of towers within a given distance of this one."""
        if miles:
            distance *= 1609.344
        result = self.my_type_of_collection()
        for tower in self.collection.by_id.values():
            if math.dist(self.xy, tower.xy) <= distance:
                result.add_tower(copy.copy(tower))
        return result

    def crow(self, other, miles=True):
        """Return the distance to another tower as the crow flies.
        The distance is miles by default, metres on request."""
        return math.dist(self.xy, other.xy) / (1609.344 if miles else 1)

    def copy_into(self, collection):
        new = copy.copy(self)
        new.collection = collection
        return new

    def html(self, columns):
        """Return an HTML table row string representing this tower."""
        return ('      <tr>\n      '
                + '\n        '.join('<td class="%s">%s</td>' % (colname,
                                                                cell_text(colname, getattr(self, colname, "")))
                                for colname in columns)
                + '\n      </tr>')

class TowerCollection:

    """A collection of towers, by name and by ID."""

    tower_type = Tower

    def __init__(self,
                 projection="EPSG:3857",
                 tower_type=Tower,
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
        result = type(self)(projection=self.projection)
        for k, v in self.by_name.items():
            for t in v:
                if t.tower_id not in result.by_id and predicate(t):
                    result.by_name[k].append(t.copy_into(result))
        for k, v in self.by_id.items():
            if v.tower_id not in result.by_id and predicate(v):
                result.by_id[k] = v.copy_into(result)
        return result

    def bells_range(self, minimum=None, maximum=None):
        """Return a collection filtered by the number of bells."""
        return self.filter_towers(lambda tower: tower.bells in set(range(minimum or 1, (maximum or 19) + 1)))

    def weight_range(self, minimum=0.0, maximum=11200.0):
        """Return a collection filtered by the tenor weight."""
        return self.filter_towers(lambda tower: minimum <= tower.pounds <= maximum)

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

    def select(self, selectors):
        """Return a selected collection of towers.
        Selectors should be an iterable of tower names or IDs."""
        return self.filter_towers(lambda tower: any(selector in tower.names() or selector == tower.tower_id
                                                    for selector in selectors))

    def my_type_of_tower(self, *args, **kwargs):
        """Return a new tower of the type used in this collection."""
        return self.tower_type(*args, **kwargs)

    def html(self, columns):
        """Return an HTML table representing this collection."""
        return ('    <table class="towers">'
                + '\n      <tr>\n        ' + '\n        '.join('<th class="%s">%s</th>' % (col, col.title()) for col in columns) + '\n      </tr>\n'
                + '\n'.join(row.html(columns) for row in sorted(self.by_id.values(),
                                                                key=lambda row: getattr(row, columns[0])))
                + '\n    </table>\n')

    def html_page(self, filename, title, columns, style=""):
        """Write an HTML page containing a table representing this collection."""
        with open(filename, 'w') as page:
            page.write('<html>\n  <head>\n    <title>' + title + '</title>\n'
                       + style
                       + '  </head>\n  <body>\n'
                       + self.html(columns)
                       + '  </body>\n</html>\n')

    def read_dove(self, force_fetch=False):
        """Read the Dove data into a TowerCollection.

        Each tower appears under multiple names, as returned by the function `tower_names`.

        Each entry is a list of towers with that name (so you can tell
        whether you need more information for disambiguation).

        The numerical TowerID from the Dove data is also used as a key.
        """
        download_dove(force_fetch)
        with open(DOVE_FILE) as dovestream:
            for tower in csv.DictReader(dovestream):
                self.add_tower(self.my_type_of_tower(self).from_dove(tower))
        return self

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

def examples():
    dove = TowerCollection().read_dove().bells_range(6,8).ringable()
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
    ely = dove.in_diocese("Ely")
    ely.dump_csv("/tmp/ely.csv", ['place', 'dedication', 'weight', 'requested', 'replied'])
    selected = ely.select(["Cambridge", "Histon", "Cherry Hinton", "Fulbourn", "Trumpington"])
    selected.dump_csv("/tmp/selected.csv", ['place', 'dedication'])
    selected.html_page("/tmp/selected.html",
                       "Selected towers",
                       ['place', 'dedication', 'weight', 'web_page', 'requested', 'replied'])
    dove.in_county("Cambridgeshire").dump_csv("/tmp/cambs.csv", ['place', 'dedication', 'weight', 'requested', 'replied'])

def filter_towers_by_command_line_args(
        towers,
        min_weight, max_weight,
        min_bells, max_bells,
        ground_floor,
        county,
        diocese,
        affiliation,
        select,
        near,
        within,
):
    if near or within:
        towers = towers[near][0].within(within)
    else:
        if min_weight or max_weight:
            towers = towers.weight_range(min_weight, max_weight)
        if min_bells or max_bells:
            towers = towers.bells_range(min_bells, max_bells)
        if ground_floor:
            towers = towers.ground_floor()
        if county:
            towers = towers.in_county(county)
        if diocese:
            towers = towers.in_diocese(diocese)
        if affiliation:
            towers = towers.affiliated_to(affiliation)
        if select:
            towers = towers.select(select.split(","))
    return towers

def add_tower_args(parser):
    parser.add_argument("--min-weight", type=float)
    parser.add_argument("--max-weight", type=float)
    parser.add_argument("--min-bells", type=int)
    parser.add_argument("--max-bells", type=int)
    parser.add_argument("--ground-floor", action='store_true')
    parser.add_argument("--county", type=str)
    parser.add_argument("--diocese", type=str)
    parser.add_argument("--affiliation", type=str)
    parser.add_argument("--select", type=str)
    parser.add_argument("--near", type=str)
    parser.add_argument("--within", type=float)
    return parser

def get_args():
    parser = argparse.ArgumentParser()
    add_tower_args(parser)
    parser.add_argument("--html", type=str)
    parser.add_argument("--title", type=str, default="Tower list")
    parser.add_argument("--csv", type=str)
    parser.add_argument("--columns", type=str)
    parser.add_argument("--style", type=str, default="")
    return vars(parser.parse_args())

def main(
        min_weight, max_weight,
        min_bells, max_bells,
        ground_floor,
        county,
        diocese,
        affiliation,
        select,
        near,
        within,
        csv,
        html,
        columns,
        title,
        style,
):
    if not (near and within):
        raise ValueError("If either of --near or --within is given, both must be given.")
    if (csv or html) and not columns:
        raise ValueError("If either --csv or --html is given, --columns must be given.")
    towers = filter_towers_by_command_line_args(
        TowerCollection().read_dove(),
        min_weight, max_weight,
        min_bells, max_bells,
        ground_floor,
        county,
        diocese,
        affiliation,
        select,
        near,
        within,
    )
    if csv:
        towers.dump_csv(csv, columns.split(","))
    if html:
        towers.html_page(html, title, columns.split(","), style)

if __name__ == "__main__":
    main(**get_args())
