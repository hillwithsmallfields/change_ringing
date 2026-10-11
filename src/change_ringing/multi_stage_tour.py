#!/usr/bin/env python

import argparse
import datetime
import yaml

from touring_towers import RoutingTowerCollection
from cache_routes import RouteCache

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("tour_file")
    return vars(parser.parse_args())

class TourPlanner:

    def __init__(self, towers):
        self.towers = towers

    def plan_session(self, date, name, start, end, towers):
        day_of_week = date.strftime("%A")
        print("planning", date, day_of_week, name, "session starting at", start, "and ending at", end, "taking in", towers)
        start_venue = self.towers[start][0]
        # for name in towers:
        #     print("checking", name)
        #     if name not in self.towers:
        #         raise ValueError("No tower or venue called %s", name)
        tower_venues = [self.towers[name][0] for name in towers]
        end_venue = self.towers[end][0]
        # print("start venue", start_venue)
        # print("tower venues", tower_venues)
        # print("end venue", end_venue)
        places = self.towers.select([start] + towers + [end])
        print("places", places)

def main(
        tour_file
):
    with open(tour_file) as tour_stream:
        tour = yaml.safe_load(tour_stream)
    planner = TourPlanner(RoutingTowerCollection().read_dove())
    with RouteCache(planner.towers):
        planner.towers.add_extra_data(tour.get('extra-files', []))
        start_date = tour['dates']['start']
        end_date = tour['dates']['end']
        days = tour['days']
        for i, d in enumerate(range(start_date.toordinal(), end_date.toordinal() + 1), start=1):
            date = datetime.date.fromordinal(d)
            day_definition = days.get("day %d" % i)
            if day_definition:
                for session_name, session in day_definition.items():
                    planner.plan_session(date, session_name, **session)
            else:
                print("No plans given for day", i, "which is", datetime.date.fromordinal(d))

if __name__ == "__main__":
    main(**get_args())
