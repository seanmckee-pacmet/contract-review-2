import functools
import json
from typing import Dict, Any

def memoize(func):
    cache = {}
    @functools.wraps(func)
    def memoized_func(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]
    return memoized_func

@memoize
def load_notable_clauses() -> Dict[str, Dict[str, Any]]:
    with open('notable_clauses.json', 'r') as f:
        return json.load(f)
