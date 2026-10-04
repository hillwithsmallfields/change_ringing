#!/bin/bash

# Examples using towers of West Somerset, of which Combe Florey is
# roughly central to the cluster I have in mind.

# Produce a web page with a table with tower links and texts to paste into emails or contact forms:

./towers.py --near "Combe Florey" \
            --within 15 \
            --extra ratings.csv \
            --extra pubs.csv \
            --columns number,distance,name_with_dedication,bells,weight,rating,web_page,text \
            --html /tmp/near-combe-florey.html \
            --min-bells 4 \
            --text "I am looking for towers for a ringing outing, and am interested in including %(place)s, either for the touring group (about 45 minutes of ringing) or for a quarter peal or a peal." \

# Produce a spreadsheet file for someone to fill in tower ratings:

./towers.py --near "Combe Florey" \
            --within 20 \
            --extra ratings.csv \
            --columns number,distance,name_with_dedication,bells,weight,rating \
            --csv /tmp/ratings-template.csv \
            --min-bells 3

# Produce a route file for all the towers in a given disc of land:

./touring_towers.py --near "Combe Florey" \
                    --within 4 --geojson /tmp/combe-florey-tour-route.geojson \
                    --verbose
