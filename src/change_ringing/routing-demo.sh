#!/bin/bash

# Examples using towers of West Somerset, of which Combe Florey is
# roughly central to the cluster I have in mind.

BIN=$MY_PROJECTS/change_ringing/src/change_ringing

$BIN/touring_towers.py --near "Combe Florey" \
                       --within 4 \
                       --first "Ash Priors" \
                       --last "Combe Florey" \
                       --geojson /tmp/combe-florey-tour-route.geojson \
                       --verbose

# Produce a route file for all the towers in a small county

# $BIN/towers.py --matching county==Rutland \
#                --csv /tmp/rutland-towers.csv \
#                --columns number,name_with_dedication,bells,weight,web_page \


