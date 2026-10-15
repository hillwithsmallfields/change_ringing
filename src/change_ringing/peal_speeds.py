#!/usr/bin/env python3

import argparse
import csv
import collections
import re
import statistics

# Sample URL to download:
# https://bb.ringingworld.co.uk/export.php?region=somerset&length=peal&bells_type=tower&fmt=csv_header&pagesize=9999

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", "-o")
    parser.add_argument("data")
    return vars(parser.parse_args())

def minutes(duration):
    try:
        m = re.match("([0-9]+)h( ([0-9]+))?", duration)
        return int(m.group(1)) * 60 + (int(m.group(3)) if m.group(2) else 0)
    except:
        print("Could not parse duration string", duration)
        return 0

def duration_string(duration):
    return "%dh %d" % (duration // 60, duration % 60)

def peal_speeds(data, output):
    towers = collections.defaultdict(list)
    with open(data) as data_stream:
        for row in csv.DictReader(data_stream):
            towers[
                # "%s (%s)" % (row['place'], row['address'])
                row['place']
            ].append(5040 * minutes(row['duration']) / float(row['changes']))

    with open(output, 'w') as outstream:
        writer = csv.DictWriter(outstream,
                                fieldnames=['Place', 'Peals', 'Min', 'Average', 'Max'])
        writer.writeheader()
        for tower in sorted(towers.keys()):
            times = towers[tower]
            writer.writerow({
                'Place': tower,
                'Peals': len(times),
                'Min': duration_string(round(min([t for t in times if t]))),
                'Average': duration_string(round(statistics.mean(times))),
                'Max': duration_string(round(max(times))),
                })

if __name__ == "__main__":
    peal_speeds(**get_args())
