#!/usr/bin/env python

import requests

import towers

class RoutingTower(towers.Tower):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._routes_from = dict()

    def route_from(self, other, mode='driving'):
        """Return the route from another tower, as computed by OSRM."""
        other_id = "%s from %d" % (mode, other.tower_id)
        if other_id not in self._routes_from:
            self._routes_from[other_id] = requests.get(("http://router.project-osrm.org/route/v1/%s/%f,%f;%f,%f"
                                                        % (mode, other.longitude, other.latitude, self.longitude, self.latitude)),
                                                       params={'geometries': 'geojson'}).json()
        return self._routes_from[other_id]

class RoutingTowerCollection(towers.TowerCollection):

    tower_type = RoutingTower

def main_for_testing():
    dove = RoutingTowerCollection().read_dove().bells_range(6,8).ringable()
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
    print(combe_florey.route_from(dove["West Bagborough"][0]))

if __name__ == "__main__":
    main_for_testing()
