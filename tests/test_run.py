# test_run.py
import json
from solvers.transportation_solver import solve_transport

params = {
    "plants": ["seattle", "san-diego"],
    "markets": ["new-york", "chicago", "topeka"],
    "capacity": {"seattle": 350, "san-diego": 600},
    "demand": {"new-york": 325, "chicago": 300, "topeka": 275},
    "distance": {
        "seattle": {"new-york": 2.5, "chicago": 1.7, "topeka": 1.8},
        "san-diego": {"new-york": 2.5, "chicago": 1.8, "topeka": 1.4}
    },
    "freight": 90
}

result = solve_transport(params)

# Pretty print
print("\n--- Solution Report ---")
print(f"Status: {result['status']}")
print(f"Objective (thousand $): {result['objective_thousand_usd']:.3f}\n")
print(f"{'Plant':<12}{'Market':<12}{'Flow (cases)':>15}")
print("-" * 40)
for rec in result["flows"]:
    if rec["value"] > 1e-8:
        print(f"{rec['plant']:<12}{rec['market']:<12}{rec['value']:>15.2f}")

# Save to JSON
with open("solution.json", "w") as f:
    json.dump(result, f, indent=2)
print("\nSaved: solution.json")