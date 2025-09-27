# test_run.py
from solvers.transportation_solver import solve_transport

params = {
    "plants": ["seattle", "san-diego"],
    "markets": ["new-york", "chicago", "topeka"],
    "capacity": {"seattle": 350, "san-diego": 600},
    "demand": {"new-york": 325, "chicago": 300, "topeka": 275},
    "distance": {
        ("seattle","new-york"):2.5, ("seattle","chicago"):1.7, ("seattle","topeka"):1.8,
        ("san-diego","new-york"):2.5, ("san-diego","chicago"):1.8, ("san-diego","topeka"):1.4
    },
    "freight": 90.0
}

res = solve_transport(params)
print(res)