from ipm_model import solve_ipm

params = {
    "orders": ["A","B","C"],
    "units": ["U1","U2"],
    "eligible": {
        "A": ["U1","U2"],
        "B": ["U1","U2"],
        "C": ["U1","U2"]
    },
    "processing_time": {
        ("A","U1"):6, ("A","U2"):7,
        ("B","U1"):5, ("B","U2"):8,
        ("C","U1"):4, ("C","U2"):5.5
    },
    # optional changeovers (default=0 if missing)
    "changeover": {
        ("A","B","U1"): 1.2,
        ("B","C","U1"): 0.2
    },
    "due_date": {"A":25,"B":25,"C":25},
    "window": {"B":1},
    "lower": {"B":4.0},
    "objective": "makespan"   # ή "changeover"
}

result = solve_ipm(params)

print("Solver status:", result["status"])
print("Objective value:", result["objective"])
print("Assignments:", result["assignments"])
print("Arcs:", result["arcs"])
print("Completion times:", result["completion"])
print("Cmax:", result["Cmax"])