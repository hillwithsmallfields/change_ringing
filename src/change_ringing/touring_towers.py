#!/usr/bin/env python

from requests_ratelimiter import LimiterSession
import numpy as np
from python_tsp.exact import solve_tsp_dynamic_programming

import towers

class RoutingTower(towers.Tower):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.index = None
        self._routes_from = dict()
        self.session = LimiterSession(per_second=1)

    def route_from(self, other, mode='driving'):
        """Return the route from another tower, as computed by OSRM."""
        other_id = "%s from %d" % (mode, other.tower_id)
        if other_id not in self._routes_from:
            self._routes_from[other_id] = self.session.get(("http://router.project-osrm.org/route/v1/%s/%f,%f;%f,%f"
                                                            % (mode, other.longitude, other.latitude, self.longitude, self.latitude)),
                                                           params={'geometries': 'geojson'}).json()
        return self._routes_from[other_id]

class RoutingTowerCollection(towers.TowerCollection):

    tower_type = RoutingTower

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tower_list = None
        self.distance_matrix = None
        self._touring_order = None
        self.total_distance = None
        self.route = None

    def index_towers(self):
        """Number the towers, in preparation for making numpy arrays with them in.
        Fills in self.tower_list.
        Returns the number of towers."""
        self.tower_list = list(self.by_id.values())
        for i, tower in enumerate(self.tower_list):
            tower.index = i
        return len(self.by_id)

    def touring_order(self):
        """Return the best order in which to visit the towers in this collection."""
        n = self.index_towers()
        if not self._touring_order:
            self.distance_matrix = np.zeros([n, n], dtype=float)
            for i, from_tower in enumerate(self.tower_list):
                for j, to_tower in enumerate(self.tower_list):
                    if i != j:
                        self.distance_matrix[i, j] = from_tower.crow(to_tower)
            self._touring_order, self.total_distance = solve_tsp_dynamic_programming(self.distance_matrix)
        return [self.tower_list[index] for index in self._touring_order], self.total_distance

    def touring_route(self):
        """Return a list of the routes between towers."""
        tour, _ = self.touring_order()
        if not self.route:
            self.route = [(tour[0], None)] + [(b.route_from(a), b) for a, b in zip(tour[:-1], tour[1:])]
        return self.route

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
    print(combe_florey.route_from(dove["West Bagborough"][0]))

if __name__ == "__main__":
    main_for_testing()
