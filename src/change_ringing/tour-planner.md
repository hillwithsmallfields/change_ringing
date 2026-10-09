# Tour planner

This is in two parts:

 - towers.py, which selects and lists towers from Dove and can produce tables of them
 - touring_towers.py, which generates tour itinerary data

## towers.py

towers.py reads Dove data saved as a CSV file (it will download it for
you if necessary), optionally combines it with other data, filters it,
and produces tables of towers as CSV or HTML files.

### Loading and filtering data

The column names used in the original Dove data are renamed to follow
Python's conventions better.  Each tower in Dove is entered under
several names, because the simple placename isn't necessarily enough
to identify a tower uniquely.  The extra names appear as extra columns
in the internal data tail, thus:

 - `name_with_dedication` e.g. _Cambridge, S Andrew Gt_
 - `name_with_county` e.g. _Chippenham (Wiltshire)_

You can filter the data with these options:

 - `--select` _name1,name2,..._
 - `--min-weight` _weight_
 - `--max-weight` _weight_
 - `--min-bells` _number_
 - `--max-bells` _number_
 - `--ground-floor`
 - `--affiliation` _organisation_
 - `--near` _tower_name_ `--within` _miles_
 - `--matching` _column==value_ for an exact match on the value in a column (can be used for county or diocese, for example, or with user-supplied data); note the double `=` sign
 - `--matching` _column~=value_ for a regular expression match on the value in a column
 - `--rating` _min_rating_ for user-supplied ratings

Where a name is required (for `--select` and `-near`), it can be the
placename, or the `name_with_dedication` or the `name_with_county`.

If you give `--select`, that is the only form of selection applied;
otherwise, all of the selection operations you supply are applied as
successive layers of filtering, so the overall result will be the
towers which match all of your requirements.

### Providing extra data

You can provide further data using the `--extra` option, giving it the
name of a CSV file.  You can give this option multiple times.

There are two kinds of extra data:

- extra columns for existing rows of the data table (such as a
  `rating` column for the `--rating` option to use); these should have
  a `Name` column which is matched with the names of towers to add the
  data to the right tower

- extra rows of data giving locations of things other than towers that
  you might want to include in an itinerary (this is not useful for
  the towers.py program, but for touring_towers.py where it can be
  used to include lunchtime pubs in the route planning); such a file
  should have a header like this:

  `Place,Name,Venue Type,Longitude,Latitude`

### Producing output

You can output the data with either of these options:

 - `--html` _filename_
 - `--csv` _filename_

Which columns are output is controlled by the option `--columns',
which takes a comma-separated string of column names (with no spaces
between them).  As well as the columns loaded from Dove (with their
pythonified names) and from the `--extra` files, there are two
synthetic columns: `number`, which is the number of the row in the
output table, and `text`, which is a template for generating text.
The values from the row are interpolated into the template as
described at
https://docs.python.org/3/builtins/stdtypes.html#old-string-formatting

The templated text can be used to create form letters for making
enquiries about including a tower in a tour you are planning.

For HTML output, you can provide a `--style` option for some text to
include in the HTML head, either as a reference to another file or as
some inline CSS.

### Further details

For details of the command-line options, run `towers.py --help`.  Most
of its options also apply to touring_towers.py, which builds on top of
it.

## touring_towers.py

Once you have a selection of towers ready, you can use
touring_towers.py to produce an itinerary.

You can provide the selection of towers either with `--select`, as for
towers.py, or put selection data into a CSV file added with `--extra`
and use `--matching` to apply it; for example, for a multi-day ringing
tour, you could provide a `day` column, then produce each itinerary
with `--matching day==Monday` etc.

### Producing itineraries

touring_towers.py uses Python's "Travelling salesperson problem"
solver package to find the optimum order to visit a collection of
towers in.  This is done using the distances as the crow flies; if you
produce a route as well as an order, the actual travel distances will
be calculated.

Routing is done using the Open Source Routing Machine,
project-osrm.org, which can be given a travel mode; the default we use
is `driving`.  We cache the data from OSRM, to avoid pestering their
server more than necessary.

These are the output options:

 - `--order` Output the order in which to visit the towers

 - `--route` _filename_ Output the route data as a JSON file, in the
   internal format used in the software (which gets it from the OSRM API)

 - `--geojson` _filename_ Output the route data as GeoJSON, suitable
   for loading into a GIS for further processing such as producing a
   map.

### Further details

For details of the command-line options, run `touring_towers.py
--help`.  Most of its options also apply to towers.py, which it builds
on.
