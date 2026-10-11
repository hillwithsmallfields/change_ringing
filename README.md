# change-ringing
Assorted code related to change-ringing.

## towers.py and touring_towers.py

Documented separately.

## dove_josm

## strip_csv.py

If your downloaded Dove CSV file has some rubbish bytes at the start,
run strip_csv.py on it and move the resulting
"\~/Downloads/dove-fixed.csv" into "\~/Downloads/dove.csv" once you've
checked it's done the right thing.

## dove_to_josm.py

The main program dove_to_josm.py takes the names of places to start
and end at, and for each ringable full-circle tower in that range,
directs a running JOSM (with remote control enabled) to download the
area around the tower and zoom to it; copies the ID to the clipboard;
it prints a line showing:

  * progress through your selected tower list
  * the tower ID (for you to add as `ref:dove`)
  * the tower name
  * the tower location

Then it waits for you to press `enter` to move on to the next tower.

Use --help to see its command line options.

## get_done_doves.py

Queries JOSM to get the towers that have been done so far.

