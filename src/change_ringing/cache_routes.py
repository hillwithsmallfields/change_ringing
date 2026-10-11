import os

class RouteCache:

    def __init__(self,
                 towers,
                 cache_file=None,
                 no_cache=False,
                 verbose=False):
        self.towers = towers
        self.no_cache = no_cache
        self.cache_file = cache_file or os.getenv("OSRM_CACHE", os.path.expanduser("~/.osrm_cache.json"))
        self.verbose = verbose

    def __enter__(self):
        if (not self.no_cache) and os.path.isfile(self.cache_file):
            if self.verbose:
                print("Loading cached routes from", self.cache_file)
            self.towers.load_routes(self.cache_file)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not self.no_cache:
            if self.verbose:
                print("Saving cached routes to", self.cache_file)
            self.towers.save_routes(self.cache_file)
        return False
