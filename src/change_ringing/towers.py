#!/usr/bin/env python3

import argparse
import collections
import copy
import csv
import datetime
import math
import os
import re
import requests

import pyproj

DOVE_FILE = os.path.expanduser("~/Downloads/dove.csv")
DOVE_URL = "https://dove.cccbr.org.uk/towers.csv"

METRES_PER_MILE = 1609.344

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
    """A safe wrapper for conversion functions."""
    try:
        return converter(raw_value)
    except ValueError:
        return raw_value

def cell_text(column_name,
              cell_value,
              row_number,
              templated_text):
    """Return the text for a cell."""
    return (', '.join('<a href="%s">%s</a>' % (url, url)
                      for url in cell_value.split(' '))
            if column_name == 'web_page'
            else (("%.2f" % cell_value)
                  if isinstance(cell_value, float)
                  else (str(row_number+1)
                        if column_name == "number"
                          else (templated_text
                                if column_name == "text"
                                else cell_value))))

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
    'Rating': float,
}

class Venue:

    """A representation of places where ringers may navigate to on a tour.

    This includes Towers, and also hotels, pubs, curry houses, etc."""

    def __init__(self, dove_collection):
        """Set up a Venue object.
        It is given a back-reference to the collection of which it is part."""
        self.collection = dove_collection
        self.venue_type = "Venue"
        # set up enough that .normalise() will work even if coordinates aren't provided
        self.longitude = 0.0
        self.latitude = 0.0
        self.satnav_longitude = 0.0
        self.satnav_latitude = 0.0

    def normalise(self):
        """Complete the setup of a Venue object."""
        self.longlat = (self.longitude, self.latitude)
        self.navlonglat = (self.satnav_longitude, self.satnav_latitude)
        if not isinstance(self.longitude, float) or not isinstance(self.latitude, float):
            self.longitude = 0.0
            self.latitude = 0.0
        self.xy = self.collection.transformer.transform(self.longitude, self.latitude)
        self.x, self.y = self.xy
        return self

    def add_data_from_row(self, dove_row):
        """Fill in a Tower object from a row of the Dove CSV file."""
        for key, value in dove_row.items():
            if key:             # skip unlabelled (e.g. blank) columns
                setattr(self,
                        COLUMN_RENAMES.get(key, key).lower(),
                        convert_if_possible(value, COLUMN_CONVERTERS.get(key, lambda a: a)))
        return self.normalise()

    def to_dict(self, fields=None):
        """Return a dictionary of the specified fields of this tower."""
        return {field_name: field_value
                for field_name, field_value in {k: getattr(self, k)
                                                for k in (fields or dir(self))
                                                if hasattr(self, k) and not k.startswith("_")
                                                }.items()
                if isinstance(field_value, (int, float, str, bool, list, dict))}

class Tower(Venue):

    """The representation of a tower as read from the Dove CSV file."""

    def __init__(self, dove_collection):
        """Set up a Tower object.
        It is given a back-reference to the collection of which it is part."""
        super().__init__(dove_collection)
        self._neighbours_cache = None
        self.rating = 0.0      # can be loaded from --extra
        self.venue_type = "Tower"

    def normalise(self):
        """Complete the setup of a Tower object."""
        super().normalise()
        if isinstance(self.pounds, float):
            self.kilograms = self.pounds / 2.2046226218488
            self.weight = "%d-%d-%d" % (self.pounds // 112, (self.pounds // 28) % 4, self.pounds % 28)
        else:
            self.kilograms = ""
            self.weight = ""
        if not isinstance(self.bells, int):
            self.bells = 0
        return self

    def __str__(self):
        return "<%d-bell tower %s>" % (self.bells, self.place)

    def __repr__(self):
        return "<%d-bell tower %s: %s>" % (self.bells, self.tower_id, self.place)

    def names(self):
        """Return various names by which a tower may be known."""
        self.name_with_dedication = "%s, %s" % (self.place, self.dedication)
        self.name_with_county = "%s (%s)" % (self.place, self.county)
        return set([self.placecl or self.place,
                    self.place,
                    self.alternative_name or self.place,
                    self.name_with_dedication,
                    self.name_with_county,
                    ])

    def neighbours(self, n=None):
        """Return the rest of the towers in order of closeness to this one.
        If N is given, return only the nearest N neighbours."""
        if self._neighbours_cache is None:
            self._neighbours_cache = sorted(self.collection.by_id.values(),
                                            key=lambda other: math.dist(self.xy, other.xy))
        return self._neighbours_cache[1:(n+1) or 1000000]

    def my_type_of_collection(self):
        """Make a new collection of the same type as the one containing this tower.
        This supports subclassing of the collection."""
        return type(self.collection)(projection=self.collection.projection,
                                     tower_type=type(self))

    def within(self, distance, miles=True):
        """Return a collection of towers within a given distance of this one."""
        if miles:
            distance *= METRES_PER_MILE
        result = self.my_type_of_collection()
        for tower in self.collection.by_id.values():
            if (my_distance := math.dist(self.xy, tower.xy)) <= distance:
                copied = copy.copy(tower)
                copied.distance = my_distance / METRES_PER_MILE
                result.add_tower(copied)
        return result

    def crow(self, other, miles=True):
        """Return the distance to another tower as the crow flies.
        The distance is miles by default, metres on request."""
        return math.dist(self.xy, other.xy) / (1609.344 if miles else 1)

    def copy_into(self, collection):
        new = copy.copy(self)
        new.collection = collection
        return new

    def html(self, columns, row_number, text):
        """Return an HTML table row string representing this tower."""
        attributes = self.to_dict()
        return ('      <tr>\n      '
                + '\n        '.join('<td class="%s">%s</td>' % (colname,
                                                                cell_text(colname,
                                                                          getattr(self, colname, ""),
                                                                          row_number,
                                                                          text % attributes))
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
        sorting_field = fields[1 if fields[0] == 'number' else 0]
        numbered = 'number' in fields
        with open(filename, 'w') as outstream:
            writer = csv.DictWriter(outstream, fields)
            writer.writeheader()
            for i, row in enumerate(sorted(self.to_list(fields), key=lambda r: r[sorting_field])):
                if numbered:
                    row['number'] = i # we could take a copy to put the number into, but I think this is harmless
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

    def affiliated_to(self, affiliation):
        """Return a collection of the towers in this collection with the given affiliation."""
        return self.filter_towers(lambda tower: affiliation in tower.affiliations)

    def rated(self, rated_at_least):
        """Return a collection of towers with at least the given rating."""
        return self.filter_towers(lambda tower: tower.rating >= rated_at_least)

    def matching(self, matcher):
        """Return a collection of towers where a specified field either:
        - has a specified value, given as fieldname=value
        - matches a specified regexp, given as fieldname~pattern
        """
        if "==" in matcher:
            key, value = matcher.split("==")
            return self.filter_towers(lambda tower: getattr(tower, key) == value)
        elif "~=" in matcher:
            key, regexp = matcher.split("~=")
            pattern = re.compile(regexp)
            return self.filter_towers(lambda tower: re.match(pattern, getattr(tower, key)))
        else:
            raise ValueError("matching must have either '==' or '~=' in it.")

    def select(self, selectors):
        """Return a selected collection of towers.
        Selectors should be an iterable of tower names or IDs."""
        return self.filter_towers(lambda tower: any(selector in tower.names() or selector == tower.tower_id
                                                    for selector in selectors))

    def my_type_of_tower(self, *args, **kwargs):
        """Return a new tower of the type used in this collection."""
        return self.tower_type(*args, **kwargs)

    def html(self, columns, text):
        """Return an HTML table representing this collection."""
        sorting_column = 1 if columns[0] == 'number' else 0
        return ('    <table class="towers">'
                + '\n      <tr>\n        ' + '\n        '.join('<th class="%s">%s</th>'
                                                               % (col,
                                                                  " ".join(col.split("_")).title())
                                                               for col in columns) + '\n      </tr>\n'
                + '\n'.join(row.html(columns, row_number, text)
                            for row_number, row in enumerate(sorted(self.by_id.values(),
                                                                    key=lambda row: getattr(row, columns[sorting_column]))))
                + '\n    </table>\n')

    def html_page(self, filename, title, columns, style="", text=""):
        """Write an HTML page containing a table representing this collection."""
        with open(filename, 'w') as page:
            page.write('<html>\n  <head>\n    <title>' + title + '</title>\n'
                       + style
                       + '  </head>\n  <body>\n'
                       + self.html(columns, text)
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
                self.add_tower(self.my_type_of_tower(self).add_data_from_row(tower))
        return self

    def add_extra_data(self, extra_files):
        """Load extra data from files."""
        for extra_file in extra_files:
            with open(extra_file) as data:
                for row in csv.DictReader(data):
                    name = row['Name']
                    if name in self.by_name:
                        self[name][0].add_data_from_row(row)
                    else:
                        # This is meant for adding things that aren't in
                        # Dove, such as hotels and pubs --- typically for
                        # the starts and ends of tours
                        self.by_name[name].append(Venue(self).add_data_from_row(row))

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

def filter_towers_by_command_line_args(
        towers,
        min_weight, max_weight,
        min_bells, max_bells,
        ground_floor,
        affiliation,
        select,
        near,
        within,
        rating,
        matching,
):
    if near or within:
        towers = towers[near][0].within(within)
    if min_weight or max_weight:
        towers = towers.weight_range(min_weight, max_weight)
    if min_bells or max_bells:
        towers = towers.bells_range(min_bells, max_bells)
    if ground_floor:
        towers = towers.ground_floor()
    if affiliation:
        towers = towers.affiliated_to(affiliation)
    if select:
        towers = towers.select(select.split(","))
    if rating:
        towers = towers.rated(rating)
    if matching:
        for matcher in matching:
            towers = towers.matching(matcher)
    return towers

def add_tower_args(parser):
    """Add tower selection args to an ArgumentParser."""
    parser.add_argument(
        "--min-weight",
        type=float,
        help="""Include only towers with at least this tenor weight.""")
    parser.add_argument(
        "--max-weight",
        type=float,
        help="""Include only towers with at most this tenor weight.""")
    parser.add_argument(
        "--min-bells",
        type=int,
        help="""Include only towers with at least this many bells.""")
    parser.add_argument(
        "--max-bells",
        type=int,
        help="""Include only towers with at most this many bells.""")
    parser.add_argument(
        "--ground-floor",
        action='store_true',
        help="""Include only towers with ground-floor ringing rooms.""")
    parser.add_argument(
        "--affiliation",
        type=str,
        help="""Include only towers with this affiliation.""")
    parser.add_argument(
        "--select",
        type=str,
        help="""Include only the named towers, given as a comma-separated list.""")
    parser.add_argument(
        "--near",
        type=str,
        help="""Include only towers with a given distance of the named tower.
        You must also give --within to specify the distance.""")
    parser.add_argument(
        "--within",
        type=float,
        help="""Include only towers within this number of miles from the tower given as --near.""")
    parser.add_argument(
        "--rating",
        type=float,
        default=0.0,
        help="""Include only towers with at least this rating.
        The ratings are not provided by Dove; they must be loaded separately using the --extra option.""")
    parser.add_argument(
        "--matching",
        type=str,
        action='append',
        help="""Include only towers where a given column matches a given value.
        Use the syntax "column=value".  May be given multiple times.

        Intended for use with data from a --extra file; for example,
        you could use this to mark which day of a multi-day tour each
        tower is to be included in.""")
    return parser

def get_args():
    parser = argparse.ArgumentParser(
    description="""
    Here is an example command line, for producing a table for arranging an outing:

    towers.py --near "Bury St Edmunds" --within 15 --html /tmp/near-bury-st-edmunds.html --columns number,distance,place,bells,weight,web_page,text --min-bells 4 --text "I am looking for towers for a ringing outing in July, and am interested in including %%(place)s, either for the touring group (about 45 minutes of ringing at each tower) or for a quarter peal or a peal. Do you think this might be possible?" --style "<style>td.bells { font-weight: bold;}</style>"
    """
    )
    add_tower_args(parser)
    parser.add_argument(
        "--extra",
        type=str,
        action='append',
        help="""The name of a CSV file containing supplementary data.

        The data should have a column called 'Name', which is used to identify the tower
        that row is about.

        If it has ratings, they should be in a column called 'Ratings'.

        This may be given multiple times, as you may need different
        collections of columns for different purposes.  For example,
        you may have a file specifying the mealtime pubs, which will
        need to give longitude and latitude of the pubs, and a
        separate one for tower ratings, in which if you provided
        blanks for longitude and latitude because of those columns
        being present to define pub locations, you would overwrite the
        longitude and latitude data coming from Dove.""")
    parser.add_argument(
        "--html",
        type=str,
        help="""Write an HTML page containing a table of towers, to this file.
        The columns are specified with the --columns option.""")
    parser.add_argument(
        "--title",
        type=str, default="Tower list",
        help="""The title to put in the HTML output.""")
    parser.add_argument(
        "--csv",
        type=str,
        help="""Write a CSV table of towers, to this file.
        The columns are specified with the --columns option.""")
    parser.add_argument(
        "--columns",
        type=str,
        help="""The names of columns to include in the HTML or CSV file, as a comma-separated list.
        The names are the snake-cased attribute names.
        For HTML output, two dummy column names are available:
        - number:   the row number in the table
        - text:     a templated value using Python's '%%' string-substitution operator
                    to do named substitution using a dictionary of the tower's attributes.
        The rows are sorted by the first column, unless the first column is 'number',
        in which case they are sorted by the second column.""")
    parser.add_argument(
        "--style",
        type=str,
        default="",
        help="""A style string to include in the header of the HTML output.
        The table cells have the column names as their 'class' values.""")
    parser.add_argument(
        "--text",
        type=str,
        default="",
        help="""A templated string to use in the synthetic HTML table column called 'text'.
        This uses Python's '%%' string-substitution operator with a dictionary containing the
        attributes of the tower.
        This is intended for writing form letters for organising tours, for example:
        "We would like to ring at %%(place)s."
        """)
    return vars(parser.parse_args())

def main(
        min_weight, max_weight,
        min_bells, max_bells,
        ground_floor,
        affiliation,
        select,
        near,
        within,
        rating,
        matching,
        extra,
        csv,
        html,
        columns,
        title,
        style,
        text,
):
    if (near or within) and not (near and within):
        raise ValueError("If either of --near or --within is given, both must be given.")
    if (csv or html) and not columns:
        raise ValueError("If either --csv or --html is given, --columns must be given.")
    towers = TowerCollection().read_dove()
    if extra:
        towers.add_extra_data(extra)
    towers = filter_towers_by_command_line_args(
        towers=towers,
        min_weight=min_weight, max_weight=max_weight,
        min_bells=min_bells, max_bells=max_bells,
        ground_floor=ground_floor,
        affiliation=affiliation,
        select=select,
        near=near,
        within=within,
        rating=rating,
        matching=matching,
    )
    if csv:
        towers.dump_csv(csv, columns.split(","))
    if html:
        towers.html_page(html, title, columns.split(","), style, text)

if __name__ == "__main__":
    main(**get_args())
