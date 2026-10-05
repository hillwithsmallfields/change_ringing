#!/bin/bash

# Examples using towers of West Somerset, of which Combe Florey is
# roughly central to the cluster I have in mind.

BIN=$MY_PROJECTS/change_ringing/src/change_ringing

# Produce a web page with a table with tower links and texts to paste into emails or contact forms:

echo 1

$BIN/towers.py --near "Combe Florey" \
               --within 15 \
               --columns number,distance,name_with_dedication,bells,weight,web_page,text \
               --html /tmp/near-combe-florey.html \
               --min-bells 4 \
               --text "I am looking for towers for a ringing outing, and am interested in including %(place)s, either for the touring group (about 45 minutes of ringing) or for a quarter peal or a peal." \
               
# Produce a spreadsheet file for someone to fill in tower ratings:

echo 2

$BIN/towers.py --near "Combe Florey" \
               --within 20 \
               --columns number,distance,name_with_dedication,bells,weight \
               --csv /tmp/ratings-template.csv \
               --min-bells 3

# List all the towers in a diocese

echo 3

$BIN/towers.py --matching diocese=Ely \
               --csv /tmp/ely-towers.csv \
               --columns name_with_dedication,bells,weight,web_page

# Produce a route file for all the towers in a given disc of land:

echo 4

$BIN/touring_towers.py --near "Combe Florey" \
                       --within 4 --geojson /tmp/combe-florey-tour-route.geojson \
                       --verbose
