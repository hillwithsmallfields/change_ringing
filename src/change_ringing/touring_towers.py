#!/usr/bin/env python

import argparse
import json
import os

from requests_ratelimiter import LimiterSession
import numpy as np
from python_tsp.exact import solve_tsp_dynamic_programming
from python_tsp.heuristics import solve_tsp_simulated_annealing

import towers
from cache_routes import RouteCache

class RoutingVenue(towers.Venue):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.index = None
        # how to get here from various places, keyed by id
        self._routes_from = dict()
        self.session = LimiterSession(per_minute=12)

    def route_from(self, other, mode='driving', verbose=False):
        """Return the route from another tower, as computed by OSRM."""
        other_id = "%s from %d" % (mode, other.tower_id)
        if other_id not in self._routes_from:
            if verbose:
                print("Fetching the route from", other.place, "to", self.place)
            self._routes_from[other_id] = {
                'description': "%s route from %s to %s" % (mode, other.place, self.place),
                'osrm': self.session.get(("http://router.project-osrm.org/route/v1/%s/%f,%f;%f,%f"
                                          % (mode, other.longitude, other.latitude, self.longitude, self.latitude)),
                                         params={'geometries': 'geojson'}).json()}
        else:
            if verbose:
                print("Using cached route from", other.place, "to", self.place)
        return self._routes_from[other_id]

class RoutingTower(RoutingVenue, towers.Tower):

    pass

class RoutingTowerCollection(towers.TowerCollection):

    venue_type = RoutingVenue
    tower_type = RoutingTower

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tower_list = None
        self.distance_matrix = None
        self._touring_order = None
        self.total_distance = None
        self.route = None

    def index_towers(self, first, last):
        """Number the towers, in preparation for making numpy arrays with them in.
        Moves the specified first and last entries to the appropriate places,
        or adds them if they were not in the list.
        Fills in self.tower_list.
        Returns the number of towers."""
        self.tower_list = list(self.by_id.values())
        if first not in self.tower_list:
            self.tower_list = [first] + self.tower_list
            # TODO: also add to self.by_id
        elif self.tower_list[0] != first:
            for i, tower in enumerate(self.tower_list):
                if tower == first:
                    self.tower_list = [tower] + self.tower_list[:i] + self.tower_list[i+1:]
                    break
        if last not in self.tower_list:
            self.tower_list.append(last)
            # TODO: also add to self.by_id
        elif self.tower_list[-1] != last:
            for i, tower in enumerate(self.tower_list):
                if tower == last:
                    self.tower_list = self.tower_list[:i] + self.tower_list[i+1:] + [tower]
                    break
        for i, tower in enumerate(self.tower_list):
            tower.index = i
        return len(self.by_id)

    def touring_order(self, first, last, heuristic):
        """Return the best order in which to visit the towers in this collection."""
        n = self.index_towers(first, last)
        if not self._touring_order:
            self.distance_matrix = np.zeros([n, n], dtype=float)
            for i, from_tower in enumerate(self.tower_list):
                for j, to_tower in enumerate(self.tower_list):
                    if i != j:
                        self.distance_matrix[i, j] = from_tower.crow(to_tower)
            self._touring_order, self.total_distance = (solve_tsp_simulated_annealing
                                                        if heuristic
                                                        else solve_tsp_dynamic_programming)(self.distance_matrix)
        return [self.tower_list[index] for index in self._touring_order], self.total_distance

    def touring_route(self, first, last, mode='driving', heuristic=False, verbose=False):
        """Return a list of the routes between towers, using the Open
        Source Routing Machine web service at https://project-osrm.org/."""
        tour, _ = self.touring_order(first, last, heuristic)
        if not self.route:
            self.route = ([(None, tour[0].to_dict())]
                          + [(b.route_from(a, mode=mode, verbose=verbose),
                              b.to_dict())
                             for a, b in zip(tour[:-1], tour[1:])])
        return self.route

    def geojson(self, first, last, mode='driving', heuristic=False, verbose=False):
        raw = self.touring_route(first, last, mode=mode, heuristic=heuristic, verbose=verbose)
        journeys, towers = zip(*raw)
        journeys = [{'description': j['description'],
                     'geometry': j['osrm']['routes'][0]['geometry']}
                    for j in journeys
                    if j]
        return {
            'type': 'FeatureCollection',
            'features': [
                    {
                        'type': 'Feature',
                        'properties': tower | {'type': 'tower'},
                        'geometry': {
                            'type': 'Point',
                            'coordinates': [
                            tower['longitude'],
                            tower['latitude'],
                        ]}
                    }
                    for tower in towers
                ] + [
                {
                    'type': 'Feature',
                    'geometry': journey['geometry'],
                    'properties': {'type': 'route',
                                   'description': journey['description']}
                }
                for journey in journeys
                ]
        }

    def _routes_to_dict(self):
        """Make a JSON-serializable dict for all the known OSRM routes in this collection.
        Intended for persisting the caches."""
        return {dove_id: tower._routes_from
                for dove_id, tower in self.by_id.items()}

    def _routes_from_dict(self, incoming):
        """Load a JSON-serializable dict for all the known OSRM routes in this collection.
        Intended for persisting the caches."""
        for tower_id, cached_data in incoming.items():
            # print("adding cached routes for", self.by_id[int(tower_id)])
            numeric_id = int(tower_id)
            if numeric_id in self.by_id:
                self.by_id[numeric_id]._routes_from.update(cached_data)
            # else:
            #     self.by_id[numeric_id]._routes_from = cached_data

    def save_routes(self, filename):
        """Save the routes to a JSON file."""
        with open(filename, 'w') as outstream:
            json.dump(self._routes_to_dict(), outstream, indent=4)

    def load_routes(self, filename):
        """Load the routes from a JSON file."""
        with open(filename) as instream:
            self._routes_from_dict(json.load(instream))

def main_for_testing():
    dove = RoutingTowerCollection().read_dove().bells_range(6,8).ringable()
    combe_florey = dove["Combe Florey"][0]
    in_miles = combe_florey.within(4)
    in_miles.dump_csv("/tmp/miles.csv", ['place', 'dedication', 'longitude', 'latitude'])
    for i, tower in enumerate(in_miles.by_id.values()):
        print(i+1, tower, combe_florey.crow(tower))
    order, total_distance = in_miles.touring_order()
    for i, t in enumerate(order):
        print(i, t)
    print("total distance", total_distance)
    for i, step in enumerate(in_miles.touring_route()):
        print(i, step)
    in_miles.save_routes("/tmp/routes.json")
    print(combe_florey.route_from(dove["West Bagborough"][0]))

def get_args():
    parser = argparse.ArgumentParser()
    towers.add_tower_args(parser)
    parser.add_argument("--first",
                        help="""The starting point of the route.""")
    parser.add_argument("--last",
                        help="""The end point of the route.""")
    parser.add_argument("--order", action='store_true')
    parser.add_argument("--route", type=str)
    parser.add_argument("--mode", type=str, default="driving")
    parser.add_argument("--geojson", type=str)
    parser.add_argument("--no-cache", action='store_true')
    parser.add_argument("--heuristic", action='store_true')
    parser.add_argument("--verbose", "-v", action='store_true')
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
        include_unringable,
        first,
        last,
        order,
        route,
        mode,
        geojson,
        no_cache,
        heuristic,
        verbose,
):
    all_towers = RoutingTowerCollection().read_dove()
    with RouteCache(all_towers, no_cache=no_cache):
        tower_list = towers.filter_towers_by_command_line_args(
            towers=all_towers,
            min_weight=min_weight, max_weight=max_weight,
            min_bells=min_bells, max_bells=max_bells,
            ground_floor=ground_floor,
            affiliation=affiliation,
            select=select,
            near=near,
            within=within,
            rating=rating,
            matching=matching,
            include_unringable=include_unringable,
        )
        first = tower_list[first][0]
        last = tower_list[last][0]
        if order:
            order, total_distance = tower_list.touring_order(first, last, mode=mode)
            print(order, total_distance)
        if route:
            with open(route, 'w') as json_stream:
                json.dump(tower_list.touring_route(mode=mode,
                                                   first=first,
                                                   last=last,
                                                   heuristic=heuristic,
                                                   verbose=verbose),
                          json_stream,
                          indent=4)
        if geojson:
            with open(geojson, 'w') as json_stream:
                json.dump(tower_list.geojson(mode=mode,
                                             first=first,
                                             last=last,
                                             heuristic=heuristic,
                                             verbose=verbose),
                          json_stream,
                          indent=4)

if __name__ == "__main__":
    main(**get_args())
