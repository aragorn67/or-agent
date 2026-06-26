"""
Central Repository of OR Problem Descriptions

A comprehensive collection of Operations Research problem descriptions for testing.
All test files should import from this repository instead of hardcoding problems.

USAGE:
    from or_problem_repository import get_problem_by_name, ProblemCategory

    problem = get_problem_by_name("european_wine_distribution")
    prompt = problem["text"]

    # CLI usage:
    python or_problem_repository.py list --solvable
    python or_problem_repository.py get european_wine_distribution
    python or_problem_repository.py count

STRUCTURE:
Each problem dict contains:
    - id: unique hierarchical identifier (e.g., "transport/wine_eu/001")
    - name: snake_case name for code
    - category: problem family (transportation, scheduling, etc.)
    - expected_type: specific problem type classifier should detect
    - text: natural language problem description
    - metadata: units, scale, characteristics, graph_signature
    - expected_schema: sets, params, vars, constraints (for validation)
    - feasible: bool - is problem mathematically feasible (has solution)?
    - solvable: bool - can current solvers handle it?
    - notes: testing/implementation notes
    - origin: "literature" | "synthetic" - provenance GATE (defaults to
      "synthetic"). A "literature" problem is transcribed from a cited published
      source and MUST carry metadata.source + ground_truth_params +
      published_optimum; the smoke harness asserts the solver reproduces that
      optimum at 0.00% gap. "synthetic" problems are hand-authored and exercise
      the pipeline (classification/extraction/refusal) only — never gated on an
      objective value. See validate_problem_schema() for the enforced invariant.
    - ground_truth_params: exact numeric inputs transcribed verbatim from the
      cited source (literature problems only). This is the answer key's FIXED
      input — never LLM-extracted — so the published_optimum is meaningful.
    - published_optimum: optimal objective value stated in the source
      (literature + solvable problems; may be None when the source gives only a
      solution structure, e.g. an unsolvable-by-us variant).
    - published_solution: OPTIONAL structured optimal decision variables from the
      source (e.g. {"x": {("P1","C2"): 10, ...}} for transport, or
      {"sequence": [2,1,4,5,3]} for scheduling). Captures the full solution, not
      just the objective value — stronger than published_optimum alone when a
      problem has alternative optima. Until populated, the solution structure
      lives in prose `notes`; prefer this field for new literature entries.
    - metadata.source: full citation (book, edition, section, example, page).

PROBLEM TYPE TAXONOMY:

Transportation Family:
    - transportation (SOLVABLE via transport_basic_bipartite):
        * Bipartite: sources I ship directly to sinks J
        * No intermediate nodes or flow conservation
        * Keywords: "direct shipping", "bipartite", "no intermediate"
        * Example: european_wine_distribution

    - min_cost_flow (NOT SOLVABLE - no solver yet):
        * General network with intermediate transshipment nodes
        * Flow conservation at internal nodes
        * Keywords: "through hubs", "via warehouses", "transshipment"
        * Example: vaccine_cold_chain, two_echelon_hub_network

Scheduling Family:
    - single_stage_scheduling (SOLVABLE via single_stage_ipm_scheduling):
        * Each job has ONE operation
        * Assign jobs to machines, no operation sequences
        * Keywords: "one operation per job", "parallel machines"
        * Example: chemical_batch_production, bottling_line_parallel_machines

    - job_shop / flow_shop (NOT SOLVABLE - no solver yet):
        * Each job has MULTIPLE operations with precedence
        * Keywords: "operation sequence", "routing", "multi-stage"
        * Example: job_shop_manufacturing, two_machine_flow_shop

FEASIBLE vs SOLVABLE:
    - feasible=True: Problem has valid mathematical solution
    - solvable=True: We have a solver that can handle it (implies feasible=True)
    - feasible=False: Infeasible problems (for testing feasibility checking)

    Examples:
        - european_wine_distribution: feasible=True, solvable=True (we can solve it)
        - vaccine_cold_chain: feasible=True, solvable=False (no min-cost-flow solver)
        - infeasible_transport_*: feasible=False, solvable=False (test cases)

STATISTICS (as of 2026-05-19):
    - Total problems: 41
    - Infeasible test cases: 9 (transport + scheduling, Layers 0/1/2);
      7 are machine-checkable (structured `params` +
      `expected_infeasible_layer`) — see get_infeasible_problems()
    - Solvable: 14 (9 transport + 5 scheduling)
    - Need solvers: 18 (including 2 min-cost-flow, 3 job-shop/flow-shop)
"""

from enum import Enum
from typing import List, Dict, Optional
import argparse

__all__ = [
    'ProblemCategory',
    'ProblemType',
    'get_all_problems',
    'get_problem_by_name',
    'get_problems_by_category',
    'get_solvable_problems',
    'get_infeasible_problems',
    'get_categories',
    'list_problems',
    'get_solver_id'  # Helper to map problem types to solver IDs
]

# ============================================================================
# ENUMS FOR TYPE SAFETY
# ============================================================================

class ProblemCategory(Enum):
    """Problem families for organization"""
    TRANSPORTATION = "transportation"
    SCHEDULING = "scheduling"
    ASSIGNMENT = "assignment"
    KNAPSACK = "knapsack"
    NETWORK_FLOW = "network_flow"
    PRODUCTION_PLANNING = "production_planning"
    FACILITY_LOCATION = "facility_location"
    VEHICLE_ROUTING = "vehicle_routing"
    SET_COVER = "set_cover"
    BIN_PACKING = "bin_packing"
    MULTICOMMODITY_FLOW = "multicommodity_flow"

class ProblemType(Enum):
    """Specific problem types for classification"""
    # Transportation
    TRANSPORTATION = "transportation"
    MIN_COST_FLOW = "min_cost_flow"

    # Scheduling
    SINGLE_STAGE_SCHEDULING = "single_stage_scheduling"
    SINGLE_MACHINE_TARDINESS = "single_machine_tardiness"
    SINGLE_MACHINE_MAKESPAN = "single_machine_makespan"
    PARALLEL_MACHINE_SCHEDULING = "parallel_machine_scheduling"
    JOB_SHOP = "job_shop"
    FLOW_SHOP = "flow_shop"
    OPEN_SHOP = "open_shop"
    SHIFT_ROSTERING = "shift_rostering"
    PROJECT_SCHEDULING = "project_scheduling"

    # Assignment
    ASSIGNMENT = "assignment"
    BIPARTITE_MATCHING = "bipartite_matching"

    # Knapsack
    ZERO_ONE_KNAPSACK = "zero_one_knapsack"
    BOUNDED_KNAPSACK = "bounded_knapsack"

    # Network
    MAX_FLOW = "max_flow"
    SHORTEST_PATH = "shortest_path"

    # Facility Location
    UNCAPACITATED_FACILITY_LOCATION = "uncapacitated_facility_location"
    CAPACITATED_FACILITY_LOCATION = "capacitated_facility_location"

    # VRP
    CVRP = "cvrp"
    VRPTW = "vrptw"

    # Set problems
    SET_COVER = "set_cover"
    SET_PACKING = "set_packing"

    # Others
    BIN_PACKING = "bin_packing"
    CUTTING_STOCK = "cutting_stock"
    LOT_SIZING = "lot_sizing"
    PRODUCTION_PLANNING = "production_planning"

# ============================================================================
# TRANSPORTATION PROBLEMS
# ============================================================================

TRANSPORTATION_PROBLEMS = [
    {
        "id": "transport/wine_eu/001",
        "name": "european_wine_distribution",
        "category": ProblemCategory.TRANSPORTATION.value,
        "expected_type": ProblemType.TRANSPORTATION.value,
        "text": """A European wine distribution company operates three wineries:
- Bordeaux (France) can produce 800 bottles per week
- Tuscany (Italy) can produce 650 bottles per week
- Rioja (Spain) can produce 550 bottles per week

They supply four distribution centers:
- Amsterdam needs 500 bottles per week
- Berlin requires 450 bottles per week
- Vienna demands 400 bottles per week
- Prague needs 350 bottles per week

Transportation costs (€ per bottle):
Bordeaux to Amsterdam: 2.50, Berlin: 3.20, Vienna: 4.10, Prague: 3.80
Tuscany to Amsterdam: 4.50, Berlin: 3.80, Vienna: 2.20, Prague: 2.90
Rioja to Amsterdam: 3.80, Berlin: 4.20, Vienna: 3.50, Prague: 3.20

Minimize the total transportation cost while meeting all demand.""",
        "metadata": {
            "units": {"cost": "EUR/bottle", "capacity": "bottles/week", "demand": "bottles/week"},
            "scale": {"sources": 3, "sinks": 4},
            "balanced": False,  # Supply=2000, Demand=1700
            "graph_signature": "bipartite_supply_demand",
            "tags": ["cost_min", "capacity", "unbalanced"]
        },
        "expected_schema": {
            "sets": ["I_plants", "J_markets"],
            "params": ["capacity[i]", "demand[j]", "cost[i,j]"],
            "vars": ["x[i,j] >= 0"],
            "objective": "min sum_{i,j} cost[i,j]*x[i,j]",
            "constraints": [
                "sum_j x[i,j] <= capacity[i] for all i",
                "sum_i x[i,j] >= demand[j] for all j"
            ]
        },
                "feasible": True,
        "solvable": True,
        "notes": "FIXED: Changed note from 'balanced' to unbalanced (Supply=2000 > Demand=1700)"
    },

    {
    "id": "transport/food_retail/001",
    "name": "fresh_food_distribution",
    "category": ProblemCategory.TRANSPORTATION.value,
    "expected_type": ProblemType.TRANSPORTATION.value,
    "text": """This is a direct bipartite transportation problem with no intermediate hubs.

A national grocery chain distributes perishable goods from 3 regional warehouses
(London, Manchester, Bristol) to 5 city stores. Each warehouse has daily capacity (tons) and
each store daily demand (tons). Costs (£/ton) are known.
Find a transport plan minimizing total cost while meeting all store demands
without exceeding warehouse capacity.""",
    "metadata": {
        "units": {"cost": "GBP/ton", "capacity": "tons/day"},
        "scale": {"sources": 3, "sinks": 5},
        "balanced": True,
        "graph_signature": "bipartite_supply_demand",
        "industry": "retail_food",
        "tags": ["perishable", "cost_min", "balanced"]
    },
    "expected_schema": {
        "sets": ["I_warehouses", "J_stores"],
        "params": ["capacity[i]", "demand[j]", "cost[i,j]"],
        "vars": ["x[i,j] >= 0"],
        "objective": "min sum_{i,j} cost[i,j]*x[i,j]",
        "constraints": [
            "sum_j x[i,j] <= capacity[i]",
            "sum_i x[i,j] = demand[j]"
        ]
    },
        "feasible": True,
    "solvable": False,
    "notes": "Narrative-only: gives the schema (warehouses/stores/cost) but no numeric capacities/demands/costs. Cannot be solved without data — pipeline correctly returns 'Parameter validation failed'. Marked solvable=False so smoke runner treats the graceful refusal as a PASS. Future feature: agent could prompt the user to supply missing numbers."
},

{
    "id": "transport/steel_construction/001",
    "name": "steel_supply_construction",
    "category": ProblemCategory.TRANSPORTATION.value,
    "expected_type": ProblemType.TRANSPORTATION.value,
    "text": """This is a bipartite shipping problem: mills ship directly to construction sites with no intermediate nodes.

Two steel mills (Sheffield, Glasgow) supply five major construction projects.
Each mill has weekly output limits and each project requires specified steel tonnage.
Transport costs (£/ton) depend on distance.
Decide shipping quantities to minimize total cost while meeting all demands.""",
    "metadata": {
        "units": {"cost": "GBP/ton", "capacity": "tons/week"},
        "scale": {"sources": 2, "sinks": 5},
        "balanced": False,
        "graph_signature": "bipartite_supply_demand",
        "industry": "construction_materials",
        "tags": ["heavy_industry", "unbalanced", "cost_min"]
    },
    "expected_schema": {
        "sets": ["I_mills", "J_projects"],
        "params": ["capacity[i]", "demand[j]", "cost[i,j]"],
        "vars": ["x[i,j] >= 0"],
        "objective": "min sum_{i,j} cost[i,j]*x[i,j]",
        "constraints": [
            "sum_j x[i,j] <= capacity[i]",
            "sum_i x[i,j] >= demand[j]"
        ]
    },
        "feasible": True,
    "solvable": False,
    "notes": "Narrative-only: gives the schema (mills/projects/cost) but no numeric capacities/demands/costs. Cannot be solved without data — pipeline correctly returns 'Parameter validation failed'. Marked solvable=False so smoke runner treats the graceful refusal as a PASS. Future feature: agent could prompt the user to supply missing numbers."
},

{
    "id": "transport/pharma_coldchain/001",
    "name": "vaccine_cold_chain",
    "category": ProblemCategory.TRANSPORTATION.value,
    "expected_type": ProblemType.MIN_COST_FLOW.value,
    "text": """This is a multi-stage network flow problem with intermediate transshipment nodes.

A pharmaceutical company distributes temperature-sensitive vaccines from one national depot
to 4 hospital clusters through 2 intermediate cold hubs.
Hub capacities and transport costs (€/vial) are known.
Flow must be conserved at each hub (incoming = outgoing within capacity).
Decide shipment quantities along each route to minimize cost
while respecting hub capacities and fulfilling hospital demand.""",
    "metadata": {
        "units": {"cost": "EUR/vial", "capacity": "vials/day"},
        "scale": {"nodes": 7, "arcs": 10},
        "graph_signature": "directed_network_with_transshipment",
        "industry": "pharmaceutical",
        "tags": ["cold_chain", "multi_stage_transport", "min_cost_flow"]
    },
    "expected_schema": {
        "sets": ["N_nodes", "A_arcs"],
        "params": ["capacity[a]", "cost[a]", "supply[n]", "demand[n]"],
        "vars": ["flow[a] >= 0"],
        "objective": "min sum_a cost[a]*flow[a]",
        "constraints": [
            "flow_conservation[n] for all n",
            "flow[a] <= capacity[a] for all a"
        ]
    },
        "feasible": True,
    "solvable": False,
    "notes": "Realistic multi-stage min-cost flow in pharma cold-chain logistics."
}, 


    {
        "id": "transport/us_mfg/001",
        "name": "us_manufacturing_distribution",
        "category": ProblemCategory.TRANSPORTATION.value,
        "expected_type": ProblemType.TRANSPORTATION.value,
        "text": """This is a direct bipartite shipping problem with no intermediate nodes or hubs.

Sources: Seattle (capacity 350 units), Denver (capacity 200 units), and Detroit (capacity 150 units).
Sinks: Chicago (demand 250 units), New York (demand 180 units), and Atlanta (demand 270 units).

Goods ship directly from sources to sinks.

Costs (USD per unit):
Seattle→Chicago: 2, Seattle→New York: 4, Seattle→Atlanta: 5
Denver→Chicago: 3, Denver→New York: 6, Denver→Atlanta: 2
Detroit→Chicago: 5, Detroit→New York: 3, Detroit→Atlanta: 4

Minimize total shipping cost.""",
        "metadata": {
            "units": {"cost": "USD/unit", "capacity": "units", "demand": "units"},
            "scale": {"sources": 3, "sinks": 3},
            "balanced": True,  # Supply=700, Demand=700
            "graph_signature": "bipartite_supply_demand",
            "tags": ["cost_min", "balanced"]
        },
        "expected_schema": {
            "sets": ["I_sources", "J_sinks"],
            "params": ["capacity[i]", "demand[j]", "cost[i,j]"],
            "vars": ["x[i,j] >= 0"],
            "objective": "min sum_{i,j} cost[i,j]*x[i,j]",
            "constraints": [
                "sum_j x[i,j] <= capacity[i] for all i",
                "sum_i x[i,j] = demand[j] for all j"
            ]
        },
                "feasible": True,
        "solvable": True,
        "notes": "Perfectly balanced 3×3 transportation problem"
    },

    {
        "id": "transport/greece/001",
        "name": "greek_production_sites",
        "category": ProblemCategory.TRANSPORTATION.value,
        "expected_type": ProblemType.TRANSPORTATION.value,
        "text": """A company operates two production sites in Greece: Athens and Thessaloniki.
Athens can make up to 120 units per week, Thessaloniki can supply 200 units per week.
They deliver products to three customer areas: Patras, Larisa, and Heraklion.
Patras requires 100 units, Larisa needs 80 units, Heraklion has a demand of 110 units.
Transport costs (EUR per unit):
From Athens to Patras: 5, From Athens to Larisa: 4, From Athens to Heraklion: 7
From Thessaloniki to Patras: 6, From Thessaloniki to Larisa: 3, From Thessaloniki to Heraklion: 8
Find the cheapest shipping plan.""",
        "metadata": {
            "units": {"cost": "EUR/unit", "capacity": "units/week", "demand": "units/week"},
            "scale": {"sources": 2, "sinks": 3},
            "balanced": False,  # Supply=320, Demand=290
            "graph_signature": "bipartite_supply_demand",
            "tags": ["cost_min", "unbalanced", "excess_supply"]
        },
        "expected_schema": {
            "sets": ["I_plants", "J_markets"],
            "params": ["capacity[i]", "demand[j]", "cost[i,j]"],
            "vars": ["x[i,j] >= 0"],
            "objective": "min sum_{i,j} cost[i,j]*x[i,j]",
            "constraints": [
                "sum_j x[i,j] <= capacity[i] for all i",
                "sum_i x[i,j] >= demand[j] for all j"
            ]
        },
                "feasible": True,
        "solvable": True,
        "notes": "Unbalanced: supply 320 > demand 290"
    },

    {
        "id": "transport/renewables/001",
        "name": "renewable_energy_allocation",
        "category": ProblemCategory.TRANSPORTATION.value,
        "expected_type": ProblemType.TRANSPORTATION.value,
        "text": """A national grid operator must allocate renewable energy from wind farms and solar parks to cities.

Supply:
- Wind Farm North: up to 120 MWh per day
- Wind Farm Coast: up to 90 MWh per day
- Solar Park East: up to 70 MWh per day

Demand:
- City A: requires 80 MWh per day
- City B: requires 60 MWh per day
- City C: requires 50 MWh per day
- City D: requires 40 MWh per day

Transmission loss (equivalent cost) in MWh per unit of energy delivered:
- Wind Farm North → City A: 0.05, City B: 0.10, City C: 0.08, City D: 0.12
- Wind Farm Coast → City A: 0.07, City B: 0.06, City C: 0.09, City D: 0.10
- Solar Park East → City A: 0.09, City B: 0.08, City C: 0.04, City D: 0.06

Decide how much energy to send from each renewable source to each city to minimise total effective loss, while meeting all city demands and not exceeding farm capacities.""",
        "metadata": {
            "units": {"energy": "MWh/day", "loss": "MWh per delivered MWh"},
            "scale": {"sources": 3, "sinks": 4},
            "balanced": False,  # Supply=280, Demand=230
            "graph_signature": "bipartite_supply_demand",
            "tags": ["loss_min", "renewables", "unbalanced"]
        },
        "expected_schema": {
            "sets": ["S_sources", "C_cities"],
            "params": ["capacity[s]", "demand[c]", "loss[s,c]"],
            "vars": ["x[s,c] >= 0"],
            "objective": "min sum_{s,c} loss[s,c]*x[s,c]",
            "constraints": [
                "sum_c x[s,c] <= capacity[s] for all s",
                "sum_s x[s,c] >= demand[c] for all c"
            ]
        },
        "feasible": True,
        "solvable": True,
        "notes": "Clean bipartite transportation formulated in terms of losses instead of costs; tests structure-not-keywords classification."
    },

    {
        "id": "transport/ecommerce/001",
        "name": "ecommerce_fulfilment_centres",
        "category": ProblemCategory.TRANSPORTATION.value,
        "expected_type": ProblemType.TRANSPORTATION.value,
        "text": """An e-commerce company ships parcels from 3 fulfilment centres to 4 metro areas.

Daily shipping capacity:
- FC North: 2,000 parcels/day
- FC South: 1,500 parcels/day
- FC Central: 1,800 parcels/day

Expected demand (parcels/day):
- Metro West: 1,200
- Metro East: 900
- Metro North: 800
- Metro South: 1,000

Each centre–metro pair has an average shipping cost (€/parcel) and a service level (not explicitly modelled).

The company wants to minimise total shipping cost, while guaranteeing that each metro area is fully served from some combination of centres and that no centre exceeds its capacity.

Formulate and solve this as a transportation problem.""",
        "metadata": {
            "units": {"parcels": "parcels/day", "cost": "EUR/parcel"},
            "scale": {"sources": 3, "sinks": 4},
            "balanced": False,  # Supply=5300, Demand=3900
            "graph_signature": "bipartite_supply_demand",
            "tags": ["cost_min", "service_level", "unbalanced", "ecommerce"]
        },
        "expected_schema": {
            "sets": ["F_centres", "M_metros"],
            "params": ["capacity[f]", "demand[m]", "cost[f,m]"],
            "vars": ["x[f,m] >= 0"],
            "objective": "min sum_{f,m} cost[f,m]*x[f,m]",
            "constraints": [
                "sum_m x[f,m] <= capacity[f] for all f",
                "sum_f x[f,m] >= demand[m] for all m"
            ]
        },
        "feasible": True,
        "solvable": True,
        "notes": "Another pure bipartite transport; text mentions service levels but structure is clean transportation."
    },

    {
        "id": "transport/hub_network/001",
        "name": "two_echelon_hub_network",
        "category": ProblemCategory.TRANSPORTATION.value,
        "expected_type": ProblemType.MIN_COST_FLOW.value,
        "text": """A logistics provider ships pallets from 2 plants to 3 retail regions through 2 intermediate hubs.

Supply:
- Plant P1: up to 150 pallets/day
- Plant P2: up to 180 pallets/day

Intermediate hubs:
- Hub H1: can process at most 200 pallets/day
- Hub H2: can process at most 180 pallets/day

Demand (pallets/day):
- Region R1: 120
- Region R2: 110
- Region R3: 80

Arcs exist only along the following directed routes:
- P1 → H1, P1 → H2
- P2 → H1, P2 → H2
- H1 → R1, H1 → R2, H1 → R3
- H2 → R1, H2 → R2, H2 → R3

Each arc has a shipping cost (€/pallet) and a capacity (pallets/day).
Flow must be conserved at hubs (incoming pallets = outgoing pallets, within hub capacity).

Decide pallet flows on each arc to meet all regional demands at minimum total cost.""",
        "metadata": {
            "units": {"flow": "pallets/day", "cost": "EUR/pallet", "capacity": "pallets/day"},
            "scale": {"nodes": 7, "arcs": 10},
            "graph_signature": "directed_network_with_transshipment",
            "tags": ["min_cost_flow", "two_echelon", "hubs", "transshipment"]
        },
        "expected_schema": {
            "sets": ["N_nodes", "A_arcs"],
            "params": ["capacity[a]", "cost[a]", "supply[n]", "demand[n]"],
            "vars": ["flow[a] >= 0"],
            "objective": "min sum_a cost[a]*flow[a]",
            "constraints": [
                "flow_conservation[n] for all nodes n",
                "flow[a] <= capacity[a] for all a"
            ]
        },
        "feasible": True,
        "solvable": False,
        "notes": "Structurally min-cost flow: explicit transshipment nodes (hubs) and network flow conservation. Should NOT be classified as 'transportation'."
    },

    {
        "id": "transport/infeasible_struct/001",
        "name": "infeasible_transport_struct_mismatched_costs",
        "category": ProblemCategory.TRANSPORTATION.value,
        "expected_type": ProblemType.TRANSPORTATION.value,
        "text": """A company ships goods from 2 factories (F1, F2) to 3 regional warehouses (W1, W2, W3).

Weekly capacities:
- F1 can ship up to 80 tons
- F2 can ship up to -60 tons (ERROR: negative capacity)

Weekly demands:
- W1 needs 40 tons
- W2 needs 50 tons
- W3 needs 30 tons

Transportation costs (£/ton):
From F1 to W1: 10, W2: 12, W3: 15
From F2 to W1: 11, W2: 13, W3: 14

Find a minimum-cost shipping plan that satisfies all warehouse demand without exceeding factory capacities.""",
        "metadata": {
            "units": {"cost": "GBP/ton", "capacity": "tons/week", "demand": "tons/week"},
            "scale": {"sources": 2, "sinks": 3},
            "balanced": True,  # 80 + 60 = 140, 40 + 50 + 30 = 120 (still OK, extra capacity)
            "graph_signature": "bipartite_supply_demand",
            "tags": [
                "cost_min",
                "infeasible_struct_layer0",
                "mismatched_cost_matrix",
                "simple_transport"
            ]
        },
        "expected_schema": {
            "sets": ["I_factories", "J_warehouses"],
            "params": ["capacity[i]", "demand[j]", "cost[i,j]"],
            "vars": ["x[i,j] >= 0"],
            "objective": "min sum_{i,j} cost[i,j]*x[i,j]",
            "constraints": [
                "sum_j x[i,j] <= capacity[i] for all i",
                "sum_i x[i,j] >= demand[j] for all j"
            ]
        },
                "feasible": False,
        "solvable": False,
        "notes": "LAYER 0: Structurally inconsistent description: 2 factories × 3 warehouses but only 2×2 costs given. A good structural check should flag dimension mismatch / missing cost entries before building the model."
    },

    {
        "id": "transport/infeasible_aggregate/001",
        "name": "infeasible_transport_supply_less_than_demand",
        "category": ProblemCategory.TRANSPORTATION.value,
        "expected_type": ProblemType.TRANSPORTATION.value,
        "text": """A fertilizer producer ships product from 2 plants to 3 agricultural distribution centres.

Weekly plant capacities:
- Plant North: 40 tonnes
- Plant South: 30 tonnes

Weekly distribution centre demands:
- Centre A: 35 tonnes
- Centre B: 25 tonnes
- Centre C: 20 tonnes

Transport costs (€/tonne):
Plant North → Centre A: 10, Centre B: 8, Centre C: 12
Plant South → Centre A: 9, Centre B: 11, Centre C: 7

Determine the shipping quantities from each plant to each centre to minimise total transport cost while meeting all distribution centre demands and not exceeding plant capacities.""",
        "metadata": {
            "units": {"cost": "EUR/tonne", "capacity": "tonnes/week", "demand": "tonnes/week"},
            "scale": {"sources": 2, "sinks": 3},
            "balanced": False,  # Supply=70, Demand=80 -> globally infeasible
            "graph_signature": "bipartite_supply_demand",
            "tags": [
                "cost_min",
                "infeasible_layer1",
                "supply_less_than_demand",
                "simple_transport"
            ]
        },
        "expected_schema": {
            "sets": ["I_plants", "J_centres"],
            "params": ["capacity[i]", "demand[j]", "cost[i,j]"],
            "vars": ["x[i,j] >= 0"],
            "objective": "min sum_{i,j} cost[i,j]*x[i,j]",
            "constraints": [
                "sum_j x[i,j] <= capacity[i] for all i",
                "sum_i x[i,j] >= demand[j] for all j"
            ]
        },
                "feasible": False,
        "solvable": False,
        "notes": "LAYER 1: Analytic infeasibility: total supply (40+30=70) is strictly less than total demand (35+25+20=80). A problem-specific aggregate check on supply vs demand should reject this before calling the solver."
    },

    {
        "id": "transport/infeasible_network/001",
        "name": "infeasible_transport_capacity_pattern",
        "category": ProblemCategory.TRANSPORTATION.value,
        "expected_type": ProblemType.TRANSPORTATION.value,
        "text": """Three factories (F1, F2, F3) deliver components to three assembly plants (A, B, C).

Weekly factory supplies:
- F1: up to 60 units
- F2: up to 60 units
- F3: up to 30 units

Weekly assembly plant demands:
- Plant A: 50 units
- Plant B: 50 units
- Plant C: 50 units

All routes exist, but some lanes are capacity-limited:

Maximum shipping capacities per week (units):
- From F1 to A: 50, to B: 50, to C: 0
- From F2 to A: 0,  to B: 10, to C: 60
- From F3 to A: 10, to B: 10, to C: 10

Transport costs ($/unit) are defined for every existing route (values not important here).

Find a shipping plan that meets all assembly plant demands without exceeding factory supplies or lane capacities and minimises total transport cost.""",
        "metadata": {
            "units": {
                "cost": "USD/unit",
                "capacity": "units/week",
                "demand": "units/week",
                "arc_capacity": "units/week"
            },
            "scale": {"sources": 3, "sinks": 3},
            "balanced": True,  # Total supply 150, total demand 150
            "graph_signature": "bipartite_supply_demand",
            "tags": [
                "cost_min",
                "infeasible_layer2",
                "capacity_pattern_infeasible",
                "simple_transport"
            ]
        },
        "expected_schema": {
            "sets": ["I_factories", "J_plants"],
            "params": ["capacity[i]", "demand[j]", "cost[i,j]", "arc_capacity[i,j]"],
            "vars": ["x[i,j] >= 0"],
            "objective": "min sum_{i,j} cost[i,j]*x[i,j]",
            "constraints": [
                "sum_j x[i,j] <= capacity[i] for all i",
                "sum_i x[i,j] >= demand[j] for all j",
                "x[i,j] <= arc_capacity[i,j] for all i,j"
            ]
        },
        "params": {
            "plants": ["F1", "F2", "F3"], "markets": ["A", "B", "C"],
            "capacity": {"F1": 60, "F2": 60, "F3": 30},
            "demand": {"A": 50, "B": 50, "C": 50},
            "cost": {
                "F1": {"A": 1, "B": 1, "C": 1},
                "F2": {"A": 1, "B": 1, "C": 1},
                "F3": {"A": 1, "B": 1, "C": 1},
            },
            "arc_capacity": {
                "F1": {"A": 50, "B": 50, "C": 0},
                "F2": {"A": 0, "B": 10, "C": 60},
                "F3": {"A": 10, "B": 10, "C": 10},
            },
        },
        "expected_infeasible_layer": 2,
                "feasible": False,
        "solvable": False,
        "notes": (
            "LAYER 2: Feasible in aggregates and simple checks but infeasible under full capacity "
            "constraints. Total supply = total demand = 150. Each plant's demand appears supportable "
            "by incoming lane capacities individually, but coupling with factory supplies makes the "
            "system infeasible. For example, Plant B needs 50 units but can receive at most 50 in total "
            "(F1→B up to 50, F2→B up to 10, F3→B up to 10). Plant C must get 50 units entirely from F2 and F3, "
            "but then there is insufficient F2 capacity left to help cover B while respecting factory supply "
            "limits. This should pass simple aggregate checks and be caught only by the solver-based feasibility LP."
        )
    },

    {
        "id": "transport/infeasible_struct/002",
        "name": "infeasible_transport_negative_demand",
        "category": ProblemCategory.TRANSPORTATION.value,
        "expected_type": ProblemType.TRANSPORTATION.value,
        "text": """A distributor ships from 2 depots (P1, P2) to 2 retail zones (M1, M2).

Depot capacities: P1 = 50 units, P2 = 50 units.
Zone demands: M1 = -30 units (ERROR: negative demand), M2 = 40 units.
Costs ($/unit): P1→M1 2, P1→M2 3, P2→M1 4, P2→M2 1.

Minimise total shipping cost while meeting demand within capacity.""",
        "metadata": {
            "units": {"cost": "USD/unit", "capacity": "units", "demand": "units"},
            "scale": {"sources": 2, "sinks": 2},
            "tags": ["cost_min", "infeasible_struct_layer0", "negative_demand"],
        },
        "expected_schema": {
            "sets": ["I_plants", "J_markets"],
            "params": ["capacity[i]", "demand[j]", "cost[i,j]"],
            "vars": ["x[i,j] >= 0"],
            "objective": "min sum_{i,j} cost[i,j]*x[i,j]",
            "constraints": [
                "sum_j x[i,j] <= capacity[i] for all i",
                "sum_i x[i,j] >= demand[j] for all j",
            ],
        },
        "params": {
            "plants": ["P1", "P2"], "markets": ["M1", "M2"],
            "capacity": {"P1": 50, "P2": 50},
            "demand": {"M1": -30, "M2": 40},
            "cost": {"P1": {"M1": 2, "M2": 3}, "P2": {"M1": 4, "M2": 1}},
        },
        "expected_infeasible_layer": 0,
        "feasible": False,
        "solvable": False,
        "notes": "LAYER 0: a negative demand is structurally impossible; the "
                 "domain-agnostic non-negativity check must reject it before "
                 "any domain logic runs.",
    },

    {
        "id": "transport/infeasible_aggregate/002",
        "name": "infeasible_transport_sink_capacity_shortfall",
        "category": ProblemCategory.TRANSPORTATION.value,
        "expected_type": ProblemType.TRANSPORTATION.value,
        "text": """Two plants (P1, P2) supply two markets (M1, M2).

Plant capacities: P1 = 100, P2 = 100 (ample total supply).
Market demands: M1 = 40, M2 = 60.
All routes have defined costs ($/unit): P1→M1 2, P1→M2 3, P2→M1 4, P2→M2 1.
Per-lane weekly capacity limits: into M1 = 100 each; into M2 only 20 from
P1 and 20 from P2 (so at most 40 can ever reach M2, which needs 60).

Minimise cost while meeting all demand within plant and lane capacities.""",
        "metadata": {
            "units": {"cost": "USD/unit", "capacity": "units",
                      "demand": "units", "arc_capacity": "units"},
            "scale": {"sources": 2, "sinks": 2},
            "tags": ["cost_min", "infeasible_layer1", "sink_capacity_shortfall"],
        },
        "expected_schema": {
            "sets": ["I_plants", "J_markets"],
            "params": ["capacity[i]", "demand[j]", "cost[i,j]", "arc_capacity[i,j]"],
            "vars": ["x[i,j] >= 0"],
            "objective": "min sum_{i,j} cost[i,j]*x[i,j]",
            "constraints": [
                "sum_j x[i,j] <= capacity[i] for all i",
                "sum_i x[i,j] >= demand[j] for all j",
                "x[i,j] <= arc_capacity[i,j] for all i,j",
            ],
        },
        "params": {
            "plants": ["P1", "P2"], "markets": ["M1", "M2"],
            "capacity": {"P1": 100, "P2": 100},
            "demand": {"M1": 40, "M2": 60},
            "cost": {"P1": {"M1": 2, "M2": 3}, "P2": {"M1": 4, "M2": 1}},
            "arc_capacity": {"P1": {"M1": 100, "M2": 20},
                             "P2": {"M1": 100, "M2": 20}},
        },
        "expected_infeasible_layer": 1,
        "feasible": False,
        "solvable": False,
        "notes": "LAYER 1: total supply is ample and all routes exist (passes "
                 "Layer 0), but the incoming lane capacities into M2 sum to 40 "
                 "< demand 60 — a problem-specific necessary-condition check "
                 "(per-sink capacity) catches this without the solver.",
    },

    # ------------------------------------------------------------------
    # REAL-DATA BENCHMARK ENTRIES (textbook problems with published optima)
    # ------------------------------------------------------------------
    {
        "id": "transport/winston_powerco/001",
        "name": "winston_powerco_transportation",
        "category": ProblemCategory.TRANSPORTATION.value,
        "expected_type": ProblemType.TRANSPORTATION.value,
        "text": """Powerco has three electric power plants that supply the needs of four cities. Each power plant can supply the following numbers of kilowatt-hours (kwh) of electricity: plant 1 — 35 million; plant 2 — 50 million; plant 3 — 40 million. The peak power demands in these cities, which occur at the same time (2 P.M.), are as follows (in kwh): city 1 — 45 million; city 2 — 20 million; city 3 — 30 million; city 4 — 30 million. The costs of sending 1 million kwh of electricity from plant to city depend on the distance the electricity must travel.

Shipping costs ($ per million kwh):
Plant 1 to City 1: 8, City 2: 6, City 3: 10, City 4: 9
Plant 2 to City 1: 9, City 2: 12, City 3: 13, City 4: 7
Plant 3 to City 1: 14, City 2: 9, City 3: 16, City 4: 5

Formulate an LP to minimize the cost of meeting each city's peak power demand.""",
        "metadata": {
            "units": {"cost": "USD/million_kwh", "capacity": "million_kwh", "demand": "million_kwh"},
            "scale": {"sources": 3, "sinks": 4},
            "balanced": True,  # supply=125, demand=125
            "graph_signature": "bipartite_supply_demand",
            "tags": ["real_data_benchmark", "textbook", "cost_min", "balanced"],
            "source": "Winston, Operations Research: Applications and Algorithms, 4th ed., Ch.7 §7.1 Example 1 (Powerco), p.360-361",
        },
        "expected_schema": {
            "sets": ["I_plants", "J_cities"],
            "params": ["supply[i]", "demand[j]", "cost[i,j]"],
            "vars": ["x[i,j] >= 0"],
            "objective": "min sum_{i,j} cost[i,j]*x[i,j]",
            "constraints": [
                "sum_j x[i,j] <= supply[i] for all i",
                "sum_i x[i,j] >= demand[j] for all j",
            ],
        },
        "ground_truth_params": {
            "plants": ["P1", "P2", "P3"],
            "cities": ["C1", "C2", "C3", "C4"],
            "supply": {"P1": 35, "P2": 50, "P3": 40},
            "demand": {"C1": 45, "C2": 20, "C3": 30, "C4": 30},
            "cost": {
                "P1": {"C1": 8,  "C2": 6,  "C3": 10, "C4": 9},
                "P2": {"C1": 9,  "C2": 12, "C3": 13, "C4": 7},
                "P3": {"C1": 14, "C2": 9,  "C3": 16, "C4": 5},
            },
        },
        "published_optimum": 1020.0,
        "origin": "literature",
        "feasible": True,
        "solvable": True,
        "notes": "Canonical balanced transportation problem. Published optimum z=1020 with x12=10, x13=25, x21=45, x23=5, x32=10, x34=30 (Winston §7.3).",
    },

    {
        "id": "transport/winston_reservoir/001",
        "name": "winston_reservoir_water_shortage",
        "category": ProblemCategory.TRANSPORTATION.value,
        "expected_type": ProblemType.TRANSPORTATION.value,
        "text": """Two reservoirs are available to supply the water needs of three cities. Each reservoir can supply up to 50 million gallons of water per day. Each city would like to receive 40 million gallons per day. For each million gallons per day of unmet demand, there is a penalty. At city 1, the penalty is $20; at city 2, the penalty is $22; and at city 3, the penalty is $23.

Shipping costs ($ per million gallons):
Reservoir 1 to City 1: 7, City 2: 8, City 3: 10
Reservoir 2 to City 1: 9, City 2: 7, City 3: 8

Formulate a balanced transportation problem that can be used to minimize the sum of shortage and transport costs.""",
        "metadata": {
            "units": {"cost": "USD/million_gallons", "capacity": "million_gallons/day"},
            "scale": {"sources": 2, "sinks": 3},
            "balanced": False,  # supply=100 < demand=120; uses dummy shortage supply
            "graph_signature": "bipartite_supply_demand_with_shortage_penalty",
            "tags": ["real_data_benchmark", "textbook", "cost_min", "shortage_penalty", "unbalanced_demand_exceeds_supply"],
            "source": "Winston, Operations Research: Applications and Algorithms, 4th ed., Ch.7 §7.1 Example 2 (Reservoir), p.365",
        },
        "expected_schema": {
            "sets": ["I_reservoirs", "J_cities"],
            "params": ["supply[i]", "demand[j]", "ship_cost[i,j]", "shortage_penalty[j]"],
            "vars": ["x[i,j] >= 0", "shortage[j] >= 0"],
            "objective": "min sum_{i,j} ship_cost[i,j]*x[i,j] + sum_j shortage_penalty[j]*shortage[j]",
            "constraints": [
                "sum_j x[i,j] <= supply[i] for all i",
                "sum_i x[i,j] + shortage[j] = demand[j] for all j",
            ],
        },
        "ground_truth_params": {
            "reservoirs": ["R1", "R2"],
            "cities": ["C1", "C2", "C3"],
            "supply": {"R1": 50, "R2": 50},
            "demand": {"C1": 40, "C2": 40, "C3": 40},
            "ship_cost": {
                "R1": {"C1": 7, "C2": 8, "C3": 10},
                "R2": {"C1": 9, "C2": 7, "C3": 8},
            },
            "shortage_penalty": {"C1": 20, "C2": 22, "C3": 23},
        },
        "published_optimum": None,  # text gives solution structure (R1→C1:20, R1→C2:30, R2→C2:10, R2→C3:40, C1 short 20) but not aggregated z
        "origin": "literature",
        "feasible": True,
        "solvable": False,  # current solver does not model shortage penalty term
        "notes": "Unbalanced transport with explicit per-city shortage penalty. Published solution: R1→C1=20, R1→C2=30, R2→C2=10, R2→C3=40, City 1 shortage 20. Out of scope for current solver (no shortage-penalty objective term).",
    },

    {
        "id": "transport/winston_widgetco/001",
        "name": "winston_widgetco_transshipment",
        "category": ProblemCategory.TRANSPORTATION.value,
        "expected_type": ProblemType.MIN_COST_FLOW.value,
        "text": """Widgetco manufactures widgets at two factories, one in Memphis and one in Denver. The Memphis factory can produce as many as 150 widgets per day, and the Denver factory can produce as many as 200 widgets per day. Widgets are shipped by air to customers in Los Angeles and Boston. The customers in each city require 130 widgets per day. Because of the deregulation of airfares, Widgetco believes that it may be cheaper to first fly some widgets to New York or Chicago and then fly them to their final destinations.

Memphis and Denver are supply points; New York and Chicago are transshipment points; Los Angeles and Boston are demand points.

Shipping costs ($ per widget; "—" indicates shipment is impossible):
From Memphis: to N.Y. 8, to Chicago 13, to L.A. 25, to Boston 28
From Denver:  to N.Y. 15, to Chicago 12, to L.A. 26, to Boston 25
From N.Y.:    to Chicago 6, to L.A. 16, to Boston 17
From Chicago: to N.Y. 6, to L.A. 14, to Boston 16
(L.A. and Boston are demand points and do not ship onward.)

Widgetco wants to minimize the total cost of shipping the required widgets to its customers.""",
        "metadata": {
            "units": {"cost": "USD/widget", "capacity": "widgets/day"},
            "scale": {"nodes": 6, "supply_points": 2, "transshipment_points": 2, "demand_points": 2},
            "graph_signature": "directed_network_with_transshipment",
            "tags": ["real_data_benchmark", "textbook", "cost_min", "transshipment", "min_cost_flow"],
            "source": "Winston, Operations Research: Applications and Algorithms, 4th ed., Ch.7 §7.6 Example 5 (Widgetco), p.400-402",
        },
        "expected_schema": {
            "sets": ["N_nodes", "A_arcs"],
            "params": ["supply[n]", "demand[n]", "cost[a]"],
            "vars": ["flow[a] >= 0"],
            "objective": "min sum_a cost[a]*flow[a]",
            "constraints": [
                "flow_conservation at each transshipment node",
                "supply >= net_outflow at each supply node",
                "demand <= net_inflow at each demand node",
            ],
        },
        "ground_truth_params": {
            "nodes": ["Memphis", "Denver", "NY", "Chicago", "LA", "Boston"],
            "supply": {"Memphis": 150, "Denver": 200},
            "demand": {"LA": 130, "Boston": 130},
            "arcs": [
                ("Memphis", "NY", 8),  ("Memphis", "Chicago", 13), ("Memphis", "LA", 25), ("Memphis", "Boston", 28),
                ("Denver", "NY", 15),  ("Denver", "Chicago", 12),  ("Denver", "LA", 26),  ("Denver", "Boston", 25),
                ("NY", "Chicago", 6),  ("NY", "LA", 16),           ("NY", "Boston", 17),
                ("Chicago", "NY", 6),  ("Chicago", "LA", 14),      ("Chicago", "Boston", 16),
            ],
        },
        "published_optimum": 6370.0,  # 130*8 (Mem→NY) + 130*16 (NY→LA) + 130*25 (Den→Bos) = 1040 + 2080 + 3250
        "origin": "literature",
        "feasible": True,
        "solvable": False,  # min-cost-flow with intermediate nodes — no solver yet
        "notes": "Transshipment example. Published optimal flow: Memphis ships 130 to NY then NY→LA (130), Denver ships 130 directly to Boston. Total cost = 6370. Out of scope for the bipartite transport solver.",
    },

    {
        "id": "transport/hillier_pt_company/001",
        "name": "hillier_pt_company_distribution",
        "origin": "literature",
        "category": ProblemCategory.TRANSPORTATION.value,
        "expected_type": ProblemType.TRANSPORTATION.value,
        "text": """The P&T Company ships canned peas by truck from three canneries to four distributing warehouses. The shipping cost per truckload depends on the cannery-warehouse pair.

Outputs (truckloads available):
- Cannery 1: 75
- Cannery 2: 125
- Cannery 3: 100

Allocations (truckloads required):
- Warehouse 1: 80
- Warehouse 2: 65
- Warehouse 3: 70
- Warehouse 4: 85

Shipping cost ($ per truckload):
Cannery 1 to Warehouse 1: 464, 2: 513, 3: 654, 4: 867
Cannery 2 to Warehouse 1: 352, 2: 416, 3: 690, 4: 791
Cannery 3 to Warehouse 1: 995, 2: 682, 3: 388, 4: 685

Determine the shipping plan that minimizes total shipping cost.""",
        "metadata": {
            "units": {"cost": "USD/truckload", "capacity": "truckloads", "demand": "truckloads"},
            "scale": {"sources": 3, "sinks": 4},
            "balanced": True,  # supply=300, demand=300
            "graph_signature": "bipartite_supply_demand",
            "tags": ["real_data_benchmark", "textbook", "cost_min", "balanced"],
            "source": ("Hillier & Lieberman, Introduction to Operations Research, "
                       "McGraw-Hill (2015), §9.1, Table 9.2 (P&T Co. prototype). "
                       "Optimal Z=$152,535 stated in text (Table near p.323, objective "
                       "cell TotalCost). Double-matched against transport_basic_bipartite "
                       "at 0.00% gap."),
        },
        "expected_schema": {
            "sets": ["I_canneries", "J_warehouses"],
            "params": ["supply[i]", "demand[j]", "cost[i,j]"],
            "vars": ["x[i,j] >= 0"],
            "objective": "min sum_{i,j} cost[i,j]*x[i,j]",
            "constraints": [
                "sum_j x[i,j] <= supply[i] for all i",
                "sum_i x[i,j] >= demand[j] for all j",
            ],
        },
        "ground_truth_params": {
            "plants": ["C1", "C2", "C3"],
            "markets": ["W1", "W2", "W3", "W4"],
            "capacity": {"C1": 75, "C2": 125, "C3": 100},
            "demand": {"W1": 80, "W2": 65, "W3": 70, "W4": 85},
            "cost": {
                "C1": {"W1": 464, "W2": 513, "W3": 654, "W4": 867},
                "C2": {"W1": 352, "W2": 416, "W3": 690, "W4": 791},
                "C3": {"W1": 995, "W2": 682, "W3": 388, "W4": 685},
            },
        },
        "published_optimum": 152535.0,
        # One optimal allocation reproduced by transport_basic_bipartite (objective
        # is uniquely 152535; alternative optimal allocations may exist).
        "published_solution": {
            "x": {"C1-W2": 20, "C1-W4": 55, "C2-W1": 80, "C2-W2": 45,
                  "C3-W3": 70, "C3-W4": 30},
        },
        "feasible": True,
        "solvable": True,
        "notes": ("Classic balanced transportation prototype (Hillier P&T Co.). "
                  "Optimal total cost $152,535, double-matched against the solver at "
                  "0.00% gap. Companion to winston_powerco_transportation on the gated bar."),
    },
]


# ============================================================================
# SCHEDULING PROBLEMS
# ============================================================================

SCHEDULING_PROBLEMS = [
    {
        "id": "sched/hillier_seqdep_setup/001",
        "name": "hillier_sequence_dependent_setup",
        "origin": "literature",
        "category": ProblemCategory.SCHEDULING.value,
        "expected_type": ProblemType.SINGLE_STAGE_SCHEDULING.value,
        "text": """Five jobs must be processed on a single machine. The setup time needed before a job depends on which job immediately preceded it (a sequence-dependent setup). A job processed first incurs an initial setup from the machine's idle ("None") state.

Setup times (hours) — row = immediately preceding job, column = job being set up:
            Job 1   Job 2   Job 3   Job 4   Job 5
None          4       5       8       9       4
After 1       —       7      12      10       9
After 2       6       —      10      14      11
After 3      10      11       —      12      10
After 4       7       8      15       —       7
After 5      12       9       8      16       —

In what order should the five jobs be processed to minimize the total setup time?""",
        "metadata": {
            "units": {"setup_time": "hours"},
            "scale": {"orders": 5, "units": 1},
            "graph_signature": "single_machine_sequence_dependent_setup",
            "tags": ["real_data_benchmark", "textbook", "scheduling",
                     "sequence_dependent_setup", "changeover_min", "enumeration_verified"],
            "source": ("Hillier & Lieberman, Introduction to Operations Research, "
                       "McGraw-Hill (2015), Ch.12 Integer Programming, Problem 12.6-8. "
                       "Posed as a B&B exercise (no optimum stated in text); z*=36 derived "
                       "by exhaustive enumeration of all 5!=120 sequences — the method the "
                       "exercise itself prescribes — and cross-checked against "
                       "single_stage_ipm_scheduling at 0.00% gap. See "
                       "tests/test_scheduling_ground_truth.py."),
        },
        "expected_schema": {
            "sets": ["O_orders", "U_units"],
            "params": ["setup[prev,job]", "initial_setup[job]"],
            "vars": ["assign[o,u] in {0,1}", "precedence[o,o',u] in {0,1}"],
            "objective": "min total setup (initial + inter-job)",
            "constraints": [
                "each job processed exactly once",
                "single contiguous sequence on the one machine",
            ],
        },
        # Verbatim solver inputs. processing_time=0 and a slack due_date isolate
        # the pure sequence-dependent-setup objective (no processing/deadline
        # interaction), exactly matching the textbook problem. initial_changeover
        # carries the "None" row so the first job's setup is counted.
        "ground_truth_params": {
            "orders": ["1", "2", "3", "4", "5"],
            "units": ["U1"],
            "eligible": {"1": ["U1"], "2": ["U1"], "3": ["U1"], "4": ["U1"], "5": ["U1"]},
            "processing_time": {o: {"U1": 0.0} for o in ["1", "2", "3", "4", "5"]},
            "due_date": {"1": 1000.0, "2": 1000.0, "3": 1000.0, "4": 1000.0, "5": 1000.0},
            "changeover": {"U1": {
                "1": {"2": 7,  "3": 12, "4": 10, "5": 9},
                "2": {"1": 6,  "3": 10, "4": 14, "5": 11},
                "3": {"1": 10, "2": 11, "4": 12, "5": 10},
                "4": {"1": 7,  "2": 8,  "3": 15, "5": 7},
                "5": {"1": 12, "2": 9,  "3": 8,  "4": 16},
            }},
            "initial_changeover": {
                "1": {"U1": 4}, "2": {"U1": 5}, "3": {"U1": 8},
                "4": {"U1": 9}, "5": {"U1": 4},
            },
            "objective": "changeover",
        },
        "published_optimum": 36.0,  # enumerated optimum; optimal sequence 2->1->4->5->3
        "feasible": True,
        "solvable": True,
        "notes": ("Single-machine sequence-dependent setup minimization (Hillier 12.6-8). "
                  "Optimal sequence 2->1->4->5->3 with total setup 36 (initial 5 + inter-job 31). "
                  "Exercises the IPM changeover objective + the initial-setup term. Without that "
                  "term the model has alternative optima at inter-job-total 31, one of which "
                  "(4->2->1->5->3) is suboptimal for the real problem (40) — which is why "
                  "initial_changeover was added to the solver."),
    },
    {
        "id": "sched/chem_batch/001",
        "name": "chemical_batch_production",
        "category": ProblemCategory.SCHEDULING.value,
        "expected_type": ProblemType.SINGLE_STAGE_SCHEDULING.value,
        "text": """This is a single-stage scheduling problem: each order has exactly ONE operation.

A chemical plant needs to schedule 3 production orders on 2 batch reactors.

Orders and processing requirements:
- Order A: 2 hours on Reactor 1 OR 3 hours on Reactor 2, due by hour 10
- Order B: 1.5 hours on Reactor 1 only, due by hour 8
- Order C: 2.5 hours on Reactor 2 only, due by hour 12

Each order is processed once on one reactor (no operation sequences).

Changeover times between orders on the same reactor:
Reactor 1: A→B takes 0.5 hours, B→A takes 0.5 hours
Reactor 2: A→C takes 0.3 hours, C→A takes 0.4 hours

Minimize the total makespan while meeting all due dates.""",
        "metadata": {
            "units": {"time": "hours"},
            "scale": {"orders": 3, "machines": 2},
            "characteristics": ["single_stage", "eligible_machines", "changeovers", "due_dates"],
            "tags": ["makespan_min", "single_operation_per_job"]
        },
        "expected_schema": {
            "sets": ["O_orders", "U_units"],
            "params": ["proc_time[o,u]", "due[o]", "changeover[u,o1,o2]", "eligible[o,u]"],
            "vars": ["start[o,u] >= 0", "assign[o,u] in {0,1}"],
            "objective": "min makespan",
            "constraints": [
                "sum_u assign[o,u] = 1 for all o",
                "start[o,u] + proc_time[o,u] <= due[o] for all o,u where eligible[o,u]",
                "no_overlap[u] for all u"
            ]
        },
                "feasible": True,
        "solvable": True,
        "notes": "CLARIFIED: Each order goes to ONE reactor (single operation). 'OR' makes it clear."
    },

    {
    "id": "sched/ecommerce/001",
    "name": "warehouse_order_picking",
    "category": ProblemCategory.SCHEDULING.value,
    "expected_type": "single_machine_tardiness",  # More specific than single_stage_scheduling
    "text": """An e-commerce warehouse operates one picking line that can process one batch at a time.
10 orders must be processed with known picking times and shipping deadlines.
Each order's lateness incurs penalty cost (£/min).
Decide the order sequence to minimize total weighted tardiness.""",
    "metadata": {
        "units": {"time": "minutes"},
        "scale": {"jobs": 10, "machines": 1},
        "industry": "ecommerce_logistics",
        "characteristics": ["single_machine", "weighted_tardiness"],
        "tags": ["1||sum_wTj", "sequencing", "penalty_cost"]
    },
    "expected_schema": {
        "sets": ["J_orders"],
        "params": ["proc_time[j]", "due_date[j]", "weight[j]"],
        "vars": ["sequence[j]", "completion[j]", "tardiness[j]"],
        "objective": "min sum_j weight[j]*tardiness[j]",
        "constraints": [
            "completion[j] = cumulative(proc_time[k]) up to sequence[j]",
            "tardiness[j] >= completion[j] - due_date[j]",
            "all_different(sequence)"
        ]
    },
    "feasible": True,
    "solvable": False,  # Solver lacks tardiness objective (only has makespan/changeover)
    "notes": "Weighted tardiness scheduling from online-retail fulfilment. NOT SOLVABLE: single_stage_ipm solver lacks weighted tardiness objective."
}, 

{
    "id": "sched/semiconductor/001",
    "name": "wafer_processing_single_stage",
    "category": ProblemCategory.SCHEDULING.value,
    "expected_type": "single_machine_makespan",  # More specific: single machine with makespan objective
    "text": """A semiconductor fab schedules 6 wafer lots on a single photolithography machine.
Each lot requires a setup time dependent on the previous lot's photoresist type.
The goal is to minimize total completion time (makespan).""",
    "metadata": {
        "units": {"time": "hours"},
        "scale": {"jobs": 6, "machines": 1},
        "industry": "semiconductor",
        "characteristics": ["single_machine", "sequence_dependent_setup"],
        "tags": ["makespan_min", "setup_time", "manufacturing"]
    },
    "expected_schema": {
        "sets": ["J_lots"],
        "params": ["proc_time[j]", "setup[j1,j2]"],
        "vars": ["sequence[j]", "completion[j]"],
        "objective": "min max_j completion[j]",
        "constraints": [
            "completion[j] >= completion[prev(j)] + proc_time[j] + setup[prev(j), j]",
            "all_different(sequence)"
        ]
    },
    "feasible": True,
    "solvable": False,
    "notes": "Narrative-only: '6 wafer lots' + setup-time mention but no actual processing times, setup matrix, or eligibility data. Cannot be solved without data — pipeline correctly fails extraction. Marked solvable=False so smoke runner treats the graceful refusal as a PASS. Future feature: agent could prompt the user to supply missing numbers."
},

{
    "id": "sched/pharma_packaging/001",
    "name": "pharmaceutical_packaging_line",
    "category": ProblemCategory.SCHEDULING.value,
    "expected_type": "single_machine_tardiness",  # Lateness/tardiness are related concepts
    "text": """A drug manufacturer packages 8 different medicines on one automated line.
Each product requires a fixed processing time and must finish before its delivery due time.
The objective is to minimize the maximum lateness (Lmax).""",
    "metadata": {
        "units": {"time": "minutes"},
        "scale": {"jobs": 8, "machines": 1},
        "industry": "pharmaceutical",
        "characteristics": ["single_machine", "lateness_min"],
        "tags": ["1||Lmax", "pharma_packaging", "due_date"]
    },
    "expected_schema": {
        "sets": ["J_products"],
        "params": ["proc_time[j]", "due_date[j]"],
        "vars": ["sequence[j]", "completion[j]", "lateness[j]"],
        "objective": "min max_j lateness[j]",
        "constraints": [
            "lateness[j] = completion[j] - due_date[j]",
            "all_different(sequence)"
        ]
    },
    "feasible": True,
    "solvable": False,  # Solver lacks Lmax objective (only has makespan/changeover)
    "notes": "Classic single-machine Lmax problem in pharma packaging operations. NOT SOLVABLE: single_stage_ipm solver lacks maximum lateness objective."
},

    {
        "id": "sched/packaging/001",
        "name": "bottling_line_parallel_machines",
        "category": ProblemCategory.SCHEDULING.value,
        "expected_type": "parallel_machine_scheduling",  # More specific: parallel machines with makespan
        "text": """This is a parallel machine scheduling problem with 3 identical machines.

A beverage company must schedule 5 bottling orders on 3 identical filling lines.

Orders:
- Order A: processing time 3 hours on any line, due by hour 12
- Order B: processing time 4 hours on any line, due by hour 10
- Order C: processing time 2 hours on any line, due by hour 8
- Order D: processing time 5 hours on any line, due by hour 16
- Order E: processing time 3 hours on any line, due by hour 14

All orders require exactly one processing operation on exactly one line (no further stages).
Lines can process at most one order at a time.

There are small sequence-dependent changeover times between orders on the same line (e.g. switching flavour requires rinsing), but routing is trivial: each order only visits one line.

Decide assignment of orders to lines and the processing sequence on each line to minimise the maximum completion time (makespan).""",
        "metadata": {
            "units": {"time": "hours"},
            "scale": {"jobs": 5, "machines": 3},
            "characteristics": ["single_stage", "parallel_machines", "changeovers_optional"],
            "tags": ["makespan_min", "single_operation_per_job"]
        },
        "expected_schema": {
            "sets": ["J_jobs", "M_machines"],
            "params": ["proc_time[j]", "due[j]"],
            "vars": ["assign[j,m] in {0,1}", "start[j] >= 0", "completion[j] >= 0"],
            "objective": "min max_j completion[j]",
            "constraints": [
                "sum_m assign[j,m] = 1 for all j",
                "no_overlap_per_machine[m] for all m",
                "completion[j] >= start[j] + proc_time[j] for all j"
            ]
        },
        "feasible": True,
        "solvable": True,
        "notes": "Pure single-stage parallel-machine scheduling; should map to single_stage_ipm_scheduling solver."
    },

    {
        "id": "sched/flowshop/001",
        "name": "two_machine_flow_shop",
        "category": ProblemCategory.SCHEDULING.value,
        "expected_type": ProblemType.FLOW_SHOP.value,
        "text": """A small factory processes 4 jobs through 2 machines in the same fixed sequence (flow shop).

Processing times (hours):
Job 1: M1 = 2, M2 = 3
Job 2: M1 = 4, M2 = 1
Job 3: M1 = 3, M2 = 2
Job 4: M1 = 1, M2 = 4

Each job must be processed on M1 before it starts on M2.
Machines can handle at most one job at a time.
No preemption is allowed.

Decide the processing sequence of the jobs (same order on both machines) to minimise the total makespan.""",
        "metadata": {
            "units": {"time": "hours"},
            "scale": {"jobs": 4, "machines": 2},
            "characteristics": ["multi_stage", "flow_shop", "two_machine"],
            "tags": ["makespan_min", "fixed_machine_order"]
        },
        "expected_schema": {
            "sets": ["J_jobs", "M_machines"],
            "params": ["proc_time[j,m]"],
            "vars": ["sequence[j] in {1..n}", "start[j,m] >= 0", "completion[j,m] >= 0"],
            "objective": "min max_j completion[j,2]",
            "constraints": [
                "completion[j,1] >= start[j,1] + proc_time[j,1] for all j",
                "completion[j,2] >= max(completion[j,1], start[j,2]) + proc_time[j,2]",
                "no_overlap_on_each_machine",
                "all_different(sequence)"
            ]
        },
        "feasible": True,
        "solvable": False,
        "notes": "Textbook two-machine flow shop; should be classified as flow_shop and mapped to solver_id='none'."
    },


    {
        "id": "sched/pcb/001",
        "name": "pcb_assembly_scheduling",
        "category": ProblemCategory.SCHEDULING.value,
        "expected_type": ProblemType.OPEN_SHOP.value,
        "text": """A PCB assembly facility has 3 production lines. Schedule 4 orders:
- Order 1: needs Line A (3 hours) AND Line B (2 hours), due hour 15
- Order 2: needs Line A (2.5 hours) only, due hour 12
- Order 3: needs Line B (4 hours) AND Line C (1.5 hours), due hour 18
- Order 4: needs Line C (3 hours) only, due hour 14

Processing order is flexible (orders can visit machines in any sequence).

Changeover between orders (hours):
Line A: Order 1→2: 0.5, Order 2→1: 0.4
Line B: Order 1→3: 0.6, Order 3→1: 0.5
Line C: Order 3→4: 0.3, Order 4→3: 0.3

Minimize total completion time.""",
        "metadata": {
            "units": {"time": "hours"},
            "scale": {"orders": 4, "machines": 3},
            "characteristics": ["multi_stage", "flexible_routing", "open_shop", "changeovers"],
            "tags": ["makespan_min", "flexible_operation_sequence"]
        },
        "expected_schema": {
            "sets": ["O_orders", "M_machines", "Operations[o]"],
            "params": ["proc_time[o,m]", "due[o]", "changeover[m,o1,o2]"],
            "vars": ["start[o,m] >= 0", "completion[o] >= 0"],
            "objective": "min max_o completion[o]",
            "constraints": [
                "completion[o] >= start[o,m] + proc_time[o,m] for all o,m",
                "no_overlap[m] for all m",
                "operations_precedence_flexible for all o"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "FIXED: Changed from single_stage to open_shop (multiple operations, flexible order)"
    },

    {
        "id": "sched/jobshop/001",
        "name": "job_shop_manufacturing",
        "category": ProblemCategory.SCHEDULING.value,
        "expected_type": ProblemType.JOB_SHOP.value,
        "text": """A machine shop has 3 machines (M1, M2, M3). Schedule 3 jobs:
Job 1: M1 (2h) → M2 (3h) → M3 (1h)
Job 2: M2 (2h) → M1 (4h) → M3 (2h)
Job 3: M1 (3h) → M3 (2h) → M2 (1h)

Each job must visit machines in the specified order.
Minimize total makespan.""",
        "metadata": {
            "units": {"time": "hours"},
            "scale": {"jobs": 3, "machines": 3},
            "characteristics": ["multi_stage", "precedence_constraints", "job_shop"],
            "tags": ["makespan_min", "fixed_operation_sequence"]
        },
        "expected_schema": {
            "sets": ["J_jobs", "M_machines", "Operations[j]"],
            "params": ["proc_time[j,m]", "route[j]"],
            "vars": ["start[j,m] >= 0", "makespan >= 0"],
            "objective": "min makespan",
            "constraints": [
                "makespan >= start[j,m] + proc_time[j,m] for all j,m",
                "no_overlap[m] for all m",
                "precedence[j] follows route[j] for all j"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "Multi-stage with precedence - NOT solvable by current system"
    },

    {
        "id": "sched/nurse/001",
        "name": "nurse_shift_rostering",
        "category": ProblemCategory.SCHEDULING.value,
        "expected_type": ProblemType.SHIFT_ROSTERING.value,
        "text": """A hospital needs to schedule 8 nurses across 3 shifts (morning, evening, night) for 7 days.
Requirements:
- Each shift needs 2-3 nurses
- Each nurse works max 5 shifts per week
- No nurse works consecutive night shifts
- Fair distribution of weekend shifts

Minimize schedule cost while meeting coverage requirements.""",
        "metadata": {
            "units": {"time": "days"},
            "scale": {"nurses": 8, "shifts_per_day": 3, "days": 7},
            "characteristics": ["rostering", "coverage", "fairness", "constraints"],
            "tags": ["cost_min", "workforce_scheduling"]
        },
        "expected_schema": {
            "sets": ["N_nurses", "S_shifts", "D_days"],
            "params": ["min_coverage[s,d]", "max_coverage[s,d]", "max_shifts_per_nurse"],
            "vars": ["assign[n,s,d] in {0,1}"],
            "objective": "min cost or max_fairness",
            "constraints": [
                "min_coverage[s,d] <= sum_n assign[n,s,d] <= max_coverage[s,d]",
                "sum_{s,d} assign[n,s,d] <= max_shifts_per_nurse for all n",
                "no_consecutive_nights for all n"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "Employee scheduling - NOT solvable by current system"
    },

    {
        "id": "sched/single_machine/001",
        "name": "single_machine_tardiness",
        "category": ProblemCategory.SCHEDULING.value,
        "expected_type": ProblemType.SINGLE_MACHINE_TARDINESS.value,
        "text": """Schedule 5 jobs on a single machine to minimize total tardiness.
Jobs with processing times (p_j) and due dates (d_j):
- Job 1: p=4, d=8
- Job 2: p=3, d=6
- Job 3: p=5, d=12
- Job 4: p=2, d=5
- Job 5: p=6, d=15

Tardiness T_j = max(0, C_j - d_j) where C_j is completion time.
Minimize sum of T_j (total tardiness).""",
        "metadata": {
            "units": {"time": "hours"},
            "scale": {"jobs": 5, "machines": 1},
            "characteristics": ["single_machine", "tardiness", "graham_notation_1||sum_Tj"],
            "tags": ["tardiness_min", "sequencing"]
        },
        "expected_schema": {
            "sets": ["J_jobs"],
            "params": ["proc_time[j]", "due_date[j]"],
            "vars": ["sequence[j] in {1..n}", "completion[j] >= 0", "tardiness[j] >= 0"],
            "objective": "min sum_j tardiness[j]",
            "constraints": [
                "completion[j] = sum_{k in sequence[k]<=sequence[j]} proc_time[k]",
                "tardiness[j] >= completion[j] - due_date[j]",
                "all_different(sequence)"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "Classic 1||∑T_j problem for testing classification"
    },

    {
        "id": "sched/infeasible_struct/001",
        "name": "infeasible_scheduling_negative_processing",
        "category": ProblemCategory.SCHEDULING.value,
        "expected_type": ProblemType.SINGLE_STAGE_SCHEDULING.value,
        "text": """Single-stage scheduling: 2 orders (A, B) on one unit U1.

Processing times (hours): A = -2 on U1 (ERROR: negative), B = 3 on U1.
Due dates: A by hour 10, B by hour 10. Both orders may run on U1.

Minimise makespan while meeting due dates.""",
        "metadata": {
            "units": {"time": "hours"},
            "scale": {"orders": 2, "machines": 1},
            "tags": ["makespan_min", "infeasible_struct_layer0",
                     "negative_processing_time"],
        },
        "expected_schema": {
            "sets": ["O_orders", "U_units"],
            "params": ["proc_time[o,u]", "due[o]", "eligible[o,u]"],
            "vars": ["start[o,u] >= 0", "assign[o,u] in {0,1}"],
            "objective": "min makespan",
            "constraints": ["sum_u assign[o,u] = 1 for all o"],
        },
        "params": {
            "orders": ["A", "B"], "units": ["U1"],
            "processing_time": {"A": {"U1": -2.0}, "B": {"U1": 3.0}},
            "due_date": {"A": 10.0, "B": 10.0},
            "eligible": {"A": ["U1"], "B": ["U1"]},
        },
        "expected_infeasible_layer": 0,
        "feasible": False,
        "solvable": False,
        "notes": "LAYER 0: a negative processing time is structurally "
                 "impossible; the recursive non-negativity check (which now "
                 "descends into nested processing_time dicts) rejects it.",
    },

    {
        "id": "sched/infeasible_necessary/001",
        "name": "infeasible_scheduling_deadline_shorter_than_work",
        "category": ProblemCategory.SCHEDULING.value,
        "expected_type": ProblemType.SINGLE_STAGE_SCHEDULING.value,
        "text": """Single-stage scheduling: 3 orders (A, B, C) on one unit U1.

Processing times (hours) on U1: A = 2, B = 2, C = 5.
Due dates: A by hour 10, B by hour 10, C by hour 4.
Every order may run on U1.

Minimise makespan while meeting all due dates.""",
        "metadata": {
            "units": {"time": "hours"},
            "scale": {"orders": 3, "machines": 1},
            "tags": ["makespan_min", "infeasible_layer1",
                     "deadline_shorter_than_processing"],
        },
        "expected_schema": {
            "sets": ["O_orders", "U_units"],
            "params": ["proc_time[o,u]", "due[o]", "eligible[o,u]"],
            "vars": ["start[o,u] >= 0", "assign[o,u] in {0,1}"],
            "objective": "min makespan",
            "constraints": [
                "start[o,u] + proc_time[o,u] <= due[o] for eligible (o,u)",
            ],
        },
        "params": {
            "orders": ["A", "B", "C"], "units": ["U1"],
            "processing_time": {"A": {"U1": 2.0}, "B": {"U1": 2.0},
                                "C": {"U1": 5.0}},
            "due_date": {"A": 10.0, "B": 10.0, "C": 4.0},
            "eligible": {"A": ["U1"], "B": ["U1"], "C": ["U1"]},
        },
        "expected_infeasible_layer": 1,
        "feasible": False,
        "solvable": False,
        "notes": "LAYER 1: order C needs 5 h on its only eligible unit but is "
                 "due at hour 4 — no schedule on any number of units can meet "
                 "that. The scheduling necessary-condition check (min eligible "
                 "processing <= due date) catches it before the solver.",
    },

    {
        "id": "sched/infeasible_necessary/002",
        "name": "infeasible_scheduling_no_eligible_unit",
        "category": ProblemCategory.SCHEDULING.value,
        "expected_type": ProblemType.SINGLE_STAGE_SCHEDULING.value,
        "text": """Single-stage scheduling: 2 orders (A, B) and one unit U1.

A may run on U1 (2 h). B has NO eligible unit (its eligible list is empty),
so it can never be scheduled. Due dates: A by 10, B by 10.

Minimise makespan while meeting due dates.""",
        "metadata": {
            "units": {"time": "hours"},
            "scale": {"orders": 2, "machines": 1},
            "tags": ["makespan_min", "infeasible_layer1", "no_eligible_unit"],
        },
        "expected_schema": {
            "sets": ["O_orders", "U_units"],
            "params": ["proc_time[o,u]", "due[o]", "eligible[o,u]"],
            "vars": ["start[o,u] >= 0", "assign[o,u] in {0,1}"],
            "objective": "min makespan",
            "constraints": ["sum_u assign[o,u] = 1 for all o"],
        },
        "params": {
            "orders": ["A", "B"], "units": ["U1"],
            "processing_time": {"A": {"U1": 2.0}, "B": {"U1": 3.0}},
            "due_date": {"A": 10.0, "B": 10.0},
            "eligible": {"A": ["U1"], "B": []},
        },
        "expected_infeasible_layer": 1,
        "feasible": False,
        "solvable": False,
        "notes": "LAYER 1: order B has an explicitly empty eligibility list, "
                 "so it can never be assigned — caught by the scheduling "
                 "necessary-condition check, not the solver.",
    },

    {
        "id": "sched/infeasible_network/001",
        "name": "infeasible_scheduling_joint_overload",
        "category": ProblemCategory.SCHEDULING.value,
        "expected_type": ProblemType.SINGLE_STAGE_SCHEDULING.value,
        "text": """Single-stage scheduling: 2 orders (A, B) on one unit U1.

Each takes 3 hours on U1. Both are due by hour 4.
Individually each fits (3 <= 4), but U1 can run only one at a time, so the
second necessarily finishes at hour 6 > 4.

Minimise makespan while meeting all due dates.""",
        "metadata": {
            "units": {"time": "hours"},
            "scale": {"orders": 2, "machines": 1},
            "tags": ["makespan_min", "infeasible_layer2",
                     "joint_capacity_overload"],
        },
        "expected_schema": {
            "sets": ["O_orders", "U_units"],
            "params": ["proc_time[o,u]", "due[o]", "eligible[o,u]"],
            "vars": ["start[o,u] >= 0", "assign[o,u] in {0,1}"],
            "objective": "min makespan",
            "constraints": [
                "start[o,u] + proc_time[o,u] <= due[o] for eligible (o,u)",
                "no_overlap on each unit",
            ],
        },
        "params": {
            "orders": ["A", "B"], "units": ["U1"],
            "processing_time": {"A": {"U1": 3.0}, "B": {"U1": 3.0}},
            "due_date": {"A": 4.0, "B": 4.0},
            "eligible": {"A": ["U1"], "B": ["U1"]},
        },
        "expected_infeasible_layer": 2,
        "feasible": False,
        "solvable": False,
        "notes": "LAYER 2: each order alone meets its 4 h deadline (Layer 1 "
                 "passes: 3 <= 4), but two 3 h jobs cannot both finish by hour "
                 "4 on a single unit. Only the solver-based LP-relaxation "
                 "layer — now genuinely available for scheduling — sees the "
                 "coupling.",
    },

    # ------------------------------------------------------------------
    # REAL-DATA BENCHMARK ENTRIES (textbook scheduling problems)
    # ------------------------------------------------------------------
    {
        "id": "sched/winston_post_office/001",
        "name": "winston_post_office_shift_rostering",
        "origin": "literature",
        "category": ProblemCategory.SCHEDULING.value,
        "expected_type": ProblemType.SHIFT_ROSTERING.value,
        "text": """A post office requires different numbers of full-time employees on different days of the week. The number of full-time employees required on each day is as follows: Monday 17, Tuesday 13, Wednesday 15, Thursday 19, Friday 14, Saturday 16, Sunday 11. Union rules state that each full-time employee must work five consecutive days and then receive two days off. For example, an employee who works Monday to Friday must be off on Saturday and Sunday. The post office wants to meet its daily requirements using only full-time employees.

Formulate an LP that the post office can use to minimize the number of full-time employees who must be hired.""",
        "metadata": {
            "units": {"requirement": "employees", "objective": "employees_total"},
            "scale": {"shift_patterns": 7, "days": 7},
            "tags": ["real_data_benchmark", "textbook", "shift_rostering", "set_covering_style", "min_workforce"],
            "source": "Winston, Operations Research: Applications and Algorithms, 4th ed., Ch.3 §3.5 Example 7 (Post Office), p.72-74",
        },
        "expected_schema": {
            "sets": ["S_start_days", "D_days"],
            "params": ["requirement[d]", "covers[s,d]"],
            "vars": ["x[s] >= 0 (integer)"],
            "objective": "min sum_s x[s]",
            "constraints": [
                "sum_s covers[s,d] * x[s] >= requirement[d] for all d",
            ],
        },
        "ground_truth_params": {
            "start_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "requirement": {"Mon": 17, "Tue": 13, "Wed": 15, "Thu": 19, "Fri": 14, "Sat": 16, "Sun": 11},
            # covers[s][d] = 1 iff an employee starting on day s works on day d (5 consecutive days)
        },
        "published_optimum": 23.0,  # IP optimum z=23; LP relaxation z = 67/3 ≈ 22.33
        "feasible": True,
        "solvable": False,  # set-covering shift-rostering — outside the single-stage IPM solver
        "notes": "Classic set-covering-style shift-rostering LP. IP optimum z=23 (x1=4, x2=4, x3=2, x4=6, x5=0, x6=4, x7=3). LP relaxation z=67/3≈22.33 (fractional). Note: alternative optimal IP solutions exist (Winston notes LINDO/LINGO finds z=23 with 23 employees in a different schedule). Out of scope for current solver.",
    },
]

# ============================================================================
# ASSIGNMENT PROBLEMS
# ============================================================================

ASSIGNMENT_PROBLEMS = [
    {
        "id": "assign/worker_task/001",
        "name": "worker_task_assignment",
        "category": ProblemCategory.ASSIGNMENT.value,
        "expected_type": ProblemType.ASSIGNMENT.value,
        "text": """Assign 4 workers to 4 tasks (one-to-one assignment).
Cost matrix (hours required):
- Worker A: Task 1=3h, Task 2=5h, Task 3=4h, Task 4=6h
- Worker B: Task 1=4h, Task 2=3h, Task 3=5h, Task 4=4h
- Worker C: Task 1=5h, Task 2=4h, Task 3=3h, Task 4=5h
- Worker D: Task 1=6h, Task 2=5h, Task 3=4h, Task 4=3h

Minimize total time required.""",
        "metadata": {
            "units": {"cost": "hours"},
            "scale": {"workers": 4, "tasks": 4},
            "balanced": True,
            "characteristics": ["one_to_one", "bipartite", "hungarian_solvable"],
            "tags": ["cost_min", "matching"]
        },
        "expected_schema": {
            "sets": ["W_workers", "T_tasks"],
            "params": ["cost[w,t]"],
            "vars": ["x[w,t] in {0,1}"],
            "objective": "min sum_{w,t} cost[w,t]*x[w,t]",
            "constraints": [
                "sum_t x[w,t] = 1 for all w",
                "sum_w x[w,t] = 1 for all t"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "Classic assignment problem - solver not yet implemented"
    },

    {
        "id": "assign/sales/001",
        "name": "sales_territory_assignment",
        "category": ProblemCategory.ASSIGNMENT.value,
        "expected_type": ProblemType.ASSIGNMENT.value,
        "text": """Assign 5 salespeople to 5 territories.
Expected monthly revenue (kUSD):
- Alice: North=45, South=38, East=52, West=41, Central=48
- Bob: North=42, South=46, East=39, West=50, Central=44
- Carol: North=50, South=40, East=48, West=43, Central=47
- David: North=38, South=52, East=41, West=49, Central=40
- Emma: North=46, South=43, East=50, West=44, Central=51

Maximize total monthly revenue.""",
        "metadata": {
            "units": {"revenue": "kUSD/month"},
            "scale": {"salespeople": 5, "territories": 5},
            "balanced": True,
            "characteristics": ["one_to_one", "maximization"],
            "tags": ["revenue_max", "matching"]
        },
        "expected_schema": {
            "sets": ["S_salespeople", "T_territories"],
            "params": ["revenue[s,t]"],
            "vars": ["x[s,t] in {0,1}"],
            "objective": "max sum_{s,t} revenue[s,t]*x[s,t]",
            "constraints": [
                "sum_t x[s,t] = 1 for all s",
                "sum_s x[s,t] = 1 for all t"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "Maximization assignment - solver not yet implemented"
    },

    # ------------------------------------------------------------------
    # REAL-DATA BENCHMARK ENTRIES (textbook assignment problems)
    # ------------------------------------------------------------------
    {
        "id": "assign/winston_machineco/001",
        "name": "winston_machineco_assignment",
        "origin": "literature",
        "category": ProblemCategory.ASSIGNMENT.value,
        "expected_type": ProblemType.ASSIGNMENT.value,
        "text": """Machineco has four machines and four jobs to be completed. Each machine must be assigned to complete one job. The time required to set up each machine for completing each job is given below. Machineco wants to minimize the total setup time needed to complete the four jobs.

Setup times (hours):
Machine 1: Job 1 = 14, Job 2 = 5,  Job 3 = 8,  Job 4 = 7
Machine 2: Job 1 = 2,  Job 2 = 12, Job 3 = 6,  Job 4 = 5
Machine 3: Job 1 = 7,  Job 2 = 8,  Job 3 = 3,  Job 4 = 9
Machine 4: Job 1 = 2,  Job 2 = 4,  Job 3 = 6,  Job 4 = 10

Use linear programming to solve this problem.""",
        "metadata": {
            "units": {"cost": "hours"},
            "scale": {"machines": 4, "jobs": 4},
            "balanced": True,
            "characteristics": ["one_to_one", "bipartite", "hungarian_solvable"],
            "tags": ["real_data_benchmark", "textbook", "cost_min", "matching"],
            "source": "Winston, Operations Research: Applications and Algorithms, 4th ed., Ch.7 §7.5 Example 4 (Machineco), p.393-396",
        },
        "expected_schema": {
            "sets": ["M_machines", "J_jobs"],
            "params": ["time[m,j]"],
            "vars": ["x[m,j] in {0,1}"],
            "objective": "min sum_{m,j} time[m,j]*x[m,j]",
            "constraints": [
                "sum_j x[m,j] = 1 for all m",
                "sum_m x[m,j] = 1 for all j",
            ],
        },
        "ground_truth_params": {
            "machines": ["M1", "M2", "M3", "M4"],
            "jobs": ["J1", "J2", "J3", "J4"],
            "time": {
                "M1": {"J1": 14, "J2": 5,  "J3": 8,  "J4": 7},
                "M2": {"J1": 2,  "J2": 12, "J3": 6,  "J4": 5},
                "M3": {"J1": 7,  "J2": 8,  "J3": 3,  "J4": 9},
                "M4": {"J1": 2,  "J2": 4,  "J3": 6,  "J4": 10},
            },
        },
        "published_optimum": 15.0,  # x12=1 (5h), x24=1 (5h), x33=1 (3h), x41=1 (2h) → 5+5+3+2 = 15
        "feasible": True,
        "solvable": False,  # no dedicated assignment solver yet (Hungarian/binary)
        "notes": "Canonical 4x4 assignment problem. Published optimum z=15 with M1→J2, M2→J4, M3→J3, M4→J1. Out of scope for current bipartite-transport solver (assignment binary structure).",
    },
]

# ============================================================================
# KNAPSACK PROBLEMS
# ============================================================================

KNAPSACK_PROBLEMS = [
    {
        "id": "knapsack/project/001",
        "name": "project_selection_budget",
        "category": ProblemCategory.KNAPSACK.value,
        "expected_type": ProblemType.ZERO_ONE_KNAPSACK.value,
        "text": """A company has a 500 kUSD budget for new projects. Select which projects to fund:
- Project A: Cost 180 kUSD, Expected return 250 kUSD
- Project B: Cost 220 kUSD, Expected return 300 kUSD
- Project C: Cost 150 kUSD, Expected return 200 kUSD
- Project D: Cost 120 kUSD, Expected return 160 kUSD
- Project E: Cost 200 kUSD, Expected return 280 kUSD

Projects are all-or-nothing (cannot partially fund).
Maximize total expected return within budget.""",
        "metadata": {
            "units": {"cost": "kUSD", "return": "kUSD"},
            "scale": {"items": 5},
            "capacity": 500,
            "characteristics": ["binary", "budget_constraint"],
            "tags": ["return_max", "capital_budgeting"]
        },
        "expected_schema": {
            "sets": ["P_projects"],
            "params": ["cost[p]", "return[p]", "budget"],
            "vars": ["select[p] in {0,1}"],
            "objective": "max sum_p return[p]*select[p]",
            "constraints": [
                "sum_p cost[p]*select[p] <= budget"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "0/1 knapsack - solver not yet implemented"
    },

    {
        "id": "knapsack/cargo/001",
        "name": "cargo_loading_optimization",
        "category": ProblemCategory.KNAPSACK.value,
        "expected_type": ProblemType.ZERO_ONE_KNAPSACK.value,
        "text": """A cargo ship has 50 tonnes capacity. Select items to load:
- Item 1: 10 tonnes, value 8 kUSD
- Item 2: 15 tonnes, value 12 kUSD
- Item 3: 8 tonnes, value 7 kUSD
- Item 4: 12 tonnes, value 9.5 kUSD
- Item 5: 20 tonnes, value 15 kUSD
- Item 6: 6 tonnes, value 5.5 kUSD

Maximize total cargo value without exceeding capacity.""",
        "metadata": {
            "units": {"weight": "tonnes", "value": "kUSD"},
            "scale": {"items": 6},
            "capacity": 50,
            "characteristics": ["binary", "weight_constraint"],
            "tags": ["value_max", "cargo_loading"]
        },
        "expected_schema": {
            "sets": ["I_items"],
            "params": ["weight[i]", "value[i]", "capacity"],
            "vars": ["select[i] in {0,1}"],
            "objective": "max sum_i value[i]*select[i]",
            "constraints": [
                "sum_i weight[i]*select[i] <= capacity"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "Weight-constrained knapsack"
    },

    {
        "id": "knapsack/winston_stockco/001",
        "name": "winston_stockco_capital_budgeting",
        "origin": "literature",
        "category": ProblemCategory.KNAPSACK.value,
        "expected_type": ProblemType.ZERO_ONE_KNAPSACK.value,
        "text": """Stockco is considering four investments. Investment 1 will yield a net present value (NPV) of $16,000; investment 2, an NPV of $22,000; investment 3, an NPV of $12,000; and investment 4, an NPV of $8,000. Each investment requires a certain cash outflow at the present time: investment 1, $5,000; investment 2, $7,000; investment 3, $4,000; and investment 4, $3,000. Currently, $14,000 is available for investment.

Formulate an IP whose solution will tell Stockco how to maximize the NPV obtained from investments 1–4.""",
        "metadata": {
            "units": {"npv": "USD", "outflow": "USD", "budget": "USD"},
            "scale": {"items": 4},
            "capacity": 14000,
            "characteristics": ["binary", "budget_constraint"],
            "tags": ["real_data_benchmark", "textbook", "return_max", "capital_budgeting"],
            "source": "Winston, Operations Research: Applications and Algorithms, 4th ed., Ch.9 §9.2 Example 1 (Stockco), p.478",
        },
        "expected_schema": {
            "sets": ["I_investments"],
            "params": ["npv[i]", "outflow[i]", "budget"],
            "vars": ["select[i] in {0,1}"],
            "objective": "max sum_i npv[i]*select[i]",
            "constraints": ["sum_i outflow[i]*select[i] <= budget"],
        },
        "ground_truth_params": {
            "investments": ["I1", "I2", "I3", "I4"],
            "npv": {"I1": 16000, "I2": 22000, "I3": 12000, "I4": 8000},
            "outflow": {"I1": 5000, "I2": 7000, "I3": 4000, "I4": 3000},
            "budget": 14000,
        },
        "published_optimum": 42000.0,
        "feasible": True,
        "solvable": False,
        "notes": "Canonical 0-1 knapsack (capital budgeting). Published optimum z=42000 with x1=0, x2=x3=x4=1 (Winston §9.5).",
    },
]

# ============================================================================
# NETWORK FLOW PROBLEMS
# ============================================================================

NETWORK_FLOW_PROBLEMS = [
    {
        "id": "netflow/pipeline/001",
        "name": "oil_pipeline_max_flow",
        "category": ProblemCategory.NETWORK_FLOW.value,
        "expected_type": ProblemType.MAX_FLOW.value,
        "text": """An oil pipeline network has nodes (wells, pumping stations, refineries).
Find maximum flow from source to sink:

Network structure:
- Source S connects to: A (capacity 20), B (capacity 15)
- A connects to: C (capacity 12), D (capacity 8)
- B connects to: C (capacity 10), E (capacity 7)
- C connects to: Sink T (capacity 15)
- D connects to: T (capacity 10)
- E connects to: T (capacity 8)

What is the maximum oil flow (barrels/hour) from S to T?""",
        "metadata": {
            "units": {"flow": "barrels/hour"},
            "scale": {"nodes": 7, "arcs": 9},
            "characteristics": ["max_flow", "single_commodity"],
            "tags": ["flow_max", "ford_fulkerson"]
        },
        "expected_schema": {
            "sets": ["N_nodes", "A_arcs"],
            "params": ["capacity[a]", "source", "sink"],
            "vars": ["flow[a] >= 0"],
            "objective": "max flow_into_sink",
            "constraints": [
                "flow[a] <= capacity[a] for all a",
                "flow_conservation at all nodes except source and sink"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "Max flow problem - solver not yet implemented"
    },

    {
        "id": "netflow/shortest/001",
        "name": "shortest_delivery_route",
        "category": ProblemCategory.NETWORK_FLOW.value,
        "expected_type": ProblemType.SHORTEST_PATH.value,
        "text": """Find shortest delivery route from warehouse to customer:
Network distances (km):
- Warehouse to A: 5
- Warehouse to B: 8
- A to C: 3
- A to D: 7
- B to C: 4
- B to D: 2
- C to Customer: 6
- D to Customer: 5

What is the shortest path from Warehouse to Customer?""",
        "metadata": {
            "units": {"distance": "km"},
            "scale": {"nodes": 6, "arcs": 8},
            "characteristics": ["shortest_path", "dijkstra_solvable"],
            "tags": ["distance_min", "routing"]
        },
        "expected_schema": {
            "sets": ["N_nodes", "A_arcs"],
            "params": ["distance[a]", "source", "sink"],
            "vars": ["use[a] in {0,1}"],
            "objective": "min sum_a distance[a]*use[a]",
            "constraints": [
                "flow_conservation: path from source to sink"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "Shortest path - solver not yet implemented"
    },
]

# ============================================================================
# PRODUCTION PLANNING PROBLEMS
# ============================================================================

PRODUCTION_PLANNING_PROBLEMS = [
    {
        "id": "prod/lotsizing/001",
        "name": "lot_sizing_multi_period",
        "category": ProblemCategory.PRODUCTION_PLANNING.value,
        "expected_type": ProblemType.LOT_SIZING.value,
        "text": """A factory produces widgets over 4 months. Plan production to minimize costs:

Monthly demand: Month 1=100, Month 2=150, Month 3=120, Month 4=180
Production capacity: 200 units/month
Production cost: 50 USD/unit
Holding cost: 5 USD/unit/month
Setup cost (if produce anything): 1000 USD/month

Can hold inventory between months (starting inventory = 0, ending ≥ 0).
Minimize total production + holding + setup costs.""",
        "metadata": {
            "units": {"cost": "USD", "quantity": "units", "time": "months"},
            "scale": {"periods": 4},
            "characteristics": ["multi_period", "setup_costs", "inventory"],
            "tags": ["cost_min", "wagner_whitin"]
        },
        "expected_schema": {
            "sets": ["T_periods"],
            "params": ["demand[t]", "capacity", "prod_cost", "holding_cost", "setup_cost"],
            "vars": ["produce[t] >= 0", "inventory[t] >= 0", "setup[t] in {0,1}"],
            "objective": "min sum_t (prod_cost*produce[t] + holding_cost*inventory[t] + setup_cost*setup[t])",
            "constraints": [
                "inventory[t] = inventory[t-1] + produce[t] - demand[t]",
                "produce[t] <= capacity*setup[t]",
                "inventory[0] = 0"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "Multi-period production planning - solver not yet implemented"
    },

    {
        "id": "prod/aggregate/001",
        "name": "aggregate_production_planning",
        "category": ProblemCategory.PRODUCTION_PLANNING.value,
        "expected_type": ProblemType.PRODUCTION_PLANNING.value,
        "text": """A manufacturer produces 3 products over 6 months. Plan production:

Products: A, B, C
Demand (units/month):
- Product A: [100, 120, 110, 130, 140, 120]
- Product B: [80, 90, 100, 85, 95, 90]
- Product C: [60, 70, 65, 75, 70, 80]

Constraints:
- Monthly labor hours: 2000
- Product A: 2h/unit, Product B: 3h/unit, Product C: 1.5h/unit
- Can use overtime (max 400h/month at 1.5× cost)
- Inventory holding costs apply

Minimize total production + overtime + inventory costs.""",
        "metadata": {
            "units": {"time": "hours", "cost": "USD", "quantity": "units"},
            "scale": {"products": 3, "periods": 6},
            "characteristics": ["multi_product", "multi_period", "overtime", "resource_constraints"],
            "tags": ["cost_min", "aggregate_planning"]
        },
        "expected_schema": {
            "sets": ["P_products", "T_periods"],
            "params": ["demand[p,t]", "labor_hours[p]", "regular_capacity", "overtime_capacity"],
            "vars": ["produce[p,t] >= 0", "overtime[t] >= 0", "inventory[p,t] >= 0"],
            "objective": "min total_cost",
            "constraints": [
                "sum_p labor_hours[p]*produce[p,t] <= regular_capacity + overtime[t]",
                "overtime[t] <= overtime_capacity",
                "inventory_balance[p,t] for all p,t"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "Multi-product aggregate planning - solver not yet implemented"
    },

    {
        "id": "prod/winston_gandhi/001",
        "name": "winston_gandhi_fixed_charge_production",
        "origin": "literature",
        "category": ProblemCategory.PRODUCTION_PLANNING.value,
        "expected_type": ProblemType.PRODUCTION_PLANNING.value,
        "text": """Gandhi Cloth Company is capable of manufacturing three types of clothing: shirts, shorts, and pants. The manufacture of each type of clothing requires that Gandhi have the appropriate type of machinery available. The machinery needed to manufacture each type of clothing must be rented at the following rates: shirt machinery, $200 per week; shorts machinery, $150 per week; pants machinery, $100 per week. The manufacture of each type of clothing also requires the amounts of cloth and labor shown below. Each week, 150 hours of labor and 160 sq yd of cloth are available.

Resource requirements:
Shirt:  3 labor hours, 4 sq yd cloth
Shorts: 2 labor hours, 3 sq yd cloth
Pants:  6 labor hours, 4 sq yd cloth

Revenue / cost per unit:
Shirt:  Sales price $12, Variable cost $6
Shorts: Sales price $8,  Variable cost $4
Pants:  Sales price $15, Variable cost $8

Formulate an IP whose solution will maximize Gandhi's weekly profits.""",
        "metadata": {
            "units": {"price": "USD/unit", "rent": "USD/week", "labor": "hours/unit", "cloth": "sqyd/unit"},
            "scale": {"products": 3},
            "tags": ["real_data_benchmark", "textbook", "fixed_charge", "profit_max", "production_with_setup"],
            "source": "Winston, Operations Research: Applications and Algorithms, 4th ed., Ch.9 §9.2 Example 3 (Gandhi), p.480-482",
        },
        "expected_schema": {
            "sets": ["P_products"],
            "params": ["margin[p]", "fixed_cost[p]", "labor[p]", "cloth[p]", "labor_budget", "cloth_budget"],
            "vars": ["x[p] >= 0 integer", "y[p] in {0,1}"],
            "objective": "max sum_p margin[p]*x[p] - sum_p fixed_cost[p]*y[p]",
            "constraints": [
                "sum_p labor[p]*x[p] <= labor_budget",
                "sum_p cloth[p]*x[p] <= cloth_budget",
                "x[p] <= M[p]*y[p] for all p (fixed-charge linking)",
            ],
        },
        "ground_truth_params": {
            "products": ["shirt", "shorts", "pants"],
            "margin": {"shirt": 6, "shorts": 4, "pants": 7},  # price - var cost
            "fixed_cost": {"shirt": 200, "shorts": 150, "pants": 100},
            "labor": {"shirt": 3, "shorts": 2, "pants": 6},
            "cloth": {"shirt": 4, "shorts": 3, "pants": 4},
            "labor_budget": 150,
            "cloth_budget": 160,
            "big_M": {"shirt": 40, "shorts": 53, "pants": 25},
        },
        "published_optimum": 75.0,
        "feasible": True,
        "solvable": False,
        "notes": "Classic fixed-charge production IP (Winston). Published optimum z=75. OUT OF SCOPE for current pipeline: our fixed_cost MIP solver is bipartite-transport-specific (plants→markets schema); Gandhi is production planning (products + multi-resource constraints + machinery setup costs), which the LLM correctly classifies as ~knapsack-family — but we don't have a solver registered for that family. Flipped solvable=True→False on 2026-05-24 after the smoke benchmark surfaced the mismatch; the prior 'matches our fixed_cost MIP solver' claim was wrong.",
    },

    {
        "id": "prod/winston_dorian/001",
        "name": "winston_dorian_either_or_production",
        "origin": "literature",
        "category": ProblemCategory.PRODUCTION_PLANNING.value,
        "expected_type": ProblemType.PRODUCTION_PLANNING.value,
        "text": """Dorian Auto is considering manufacturing three types of autos: compact, midsize, and large. The resources required for, and the profits yielded by, each type of car are shown below. Currently, 6,000 tons of steel and 60,000 hours of labor are available. For production of a type of car to be economically feasible, at least 1,000 cars of that type must be produced.

Resource and profit per car:
Compact: 1.5 tons steel, 30 hours labor, $2,000 profit
Midsize: 3 tons steel,   25 hours labor, $3,000 profit
Large:   5 tons steel,   40 hours labor, $4,000 profit

Formulate an IP to maximize Dorian's profit.""",
        "metadata": {
            "units": {"steel": "tons", "labor": "hours", "profit": "USD"},
            "scale": {"products": 3},
            "tags": ["real_data_benchmark", "textbook", "either_or", "batch_minimum", "profit_max"],
            "source": "Winston, Operations Research: Applications and Algorithms, 4th ed., Ch.9 §9.2 Example 6 (Dorian), p.488-489",
        },
        "expected_schema": {
            "sets": ["P_products"],
            "params": ["profit[p]", "steel[p]", "labor[p]", "min_batch", "steel_budget", "labor_budget"],
            "vars": ["x[p] >= 0 integer", "y[p] in {0,1}"],
            "objective": "max sum_p profit[p]*x[p]",
            "constraints": [
                "sum_p steel[p]*x[p] <= steel_budget",
                "sum_p labor[p]*x[p] <= labor_budget",
                "x[p] = 0 OR x[p] >= min_batch for all p (either-or)",
            ],
        },
        "ground_truth_params": {
            "products": ["compact", "midsize", "large"],
            "profit": {"compact": 2000, "midsize": 3000, "large": 4000},
            "steel": {"compact": 1.5, "midsize": 3, "large": 5},
            "labor": {"compact": 30, "midsize": 25, "large": 40},
            "min_batch": 1000,
            "steel_budget": 6000,
            "labor_budget": 60000,
        },
        "published_optimum": 6000000.0,  # text says z=6000 in thousands → $6,000,000
        "feasible": True,
        "solvable": False,
        "notes": "Either-or batch-minimum production IP. Published optimum z=$6,000,000 with x_midsize=2000, y_midsize=1, others=0. Without the 1000-batch minimum the optimum would be 570 compacts + 1715 midsize. Out of scope (either-or constraint not in our current MIP templates).",
    },

    {
        "id": "prod/wolsey_lot_sizing_6period/001",
        "name": "wolsey_lot_sizing_6period",
        "origin": "literature",
        "category": ProblemCategory.PRODUCTION_PLANNING.value,
        "expected_type": ProblemType.LOT_SIZING.value,
        "text": """Formulate and solve an instance of the (capacitated) lot-sizing problem over six periods.

Per-period data:
- demands:            d = (6, 7, 4, 6, 3, 8)
- unit production costs: p = (3, 4, 3, 4, 4, 5)
- unit storage costs:    h = (1, 1, 1, 1, 1, 1)
- set-up costs:          f = (12, 15, 30, 23, 19, 45)
- maximum production capacity: C = 10 items per period

Decide a per-period production plan (with set-ups when producing) and inventory levels to minimize total production + storage + setup costs while meeting all demand.""",
        "metadata": {
            "units": {"cost": "abstract", "production": "items/period"},
            "scale": {"periods": 6},
            "tags": ["real_data_benchmark", "textbook", "wolsey", "lot_sizing", "capacitated", "cost_min"],
            "source": "Wolsey, Integer Programming, 2nd ed. (2021), Ch.1 §1.9 Exercise 14, p.22",
        },
        "expected_schema": {
            "sets": ["T_periods"],
            "params": ["demand[t]", "prod_cost[t]", "storage_cost[t]", "setup_cost[t]", "capacity"],
            "vars": ["y[t] >= 0 (production)", "s[t] >= 0 (stock)", "x[t] in {0,1} (setup)"],
            "objective": "min sum_t prod_cost[t]*y[t] + storage_cost[t]*s[t] + setup_cost[t]*x[t]",
            "constraints": [
                "s[t-1] + y[t] = d[t] + s[t] for all t",
                "y[t] <= capacity * x[t] for all t",
                "s[0] = 0",
            ],
        },
        "ground_truth_params": {
            "periods": [1, 2, 3, 4, 5, 6],
            "demand": {1: 6, 2: 7, 3: 4, 4: 6, 5: 3, 6: 8},
            "prod_cost": {1: 3, 2: 4, 3: 3, 4: 4, 5: 4, 6: 5},
            "storage_cost": {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1},
            "setup_cost": {1: 12, 2: 15, 3: 30, 4: 23, 5: 19, 6: 45},
            "capacity": 10,
        },
        "published_optimum": None,
        "feasible": True,
        "solvable": False,
        "notes": "Wolsey 6-period CLSP instance — book gives data, not optimum. Compute optimum offline before scoring objective_gap.",
    },

    {
        "id": "prod/wolsey_unit_commitment/001",
        "name": "wolsey_unit_commitment_5gen_12period",
        "origin": "literature",
        "category": ProblemCategory.PRODUCTION_PLANNING.value,
        "expected_type": ProblemType.PRODUCTION_PLANNING.value,
        "text": """Consider a unit commitment problem with 5 generators and 12 two-hour time periods. Period 1 follows on again from period 12, and the pattern repeats daily.

Per-period demands: d = (50, 60, 50, 100, 80, 70, 90, 60, 50, 120, 110, 70)
Reserve requirement: total capacity switched on in any period >= 1.2 * demand.

Generator capacities:        C = (12, 12, 35, 50, 75)
Generator minimum production: L = (2, 2, 5, 20, 40)

Each generator, when on, must stay on for at least two periods.
Ramping constraints (apply only to the fifth generator): when on in two successive periods, output cannot increase by more than 20 from one period to the next, and cannot decrease by more than 15.

Costs (approximate):
- start-up cost: g = (100, 100, 300, 400, 800)
- fixed cost per on-period: f = (1, 1, 5, 10, 15)
- variable cost per unit:   p = (10, 10, 4, 3, 2)

Formulate and solve with a MIP system.""",
        "metadata": {
            "units": {"demand": "MW", "cost": "abstract"},
            "scale": {"generators": 5, "periods": 12},
            "tags": ["real_data_benchmark", "textbook", "wolsey", "unit_commitment", "ramping", "min_uptime", "cost_min"],
            "source": "Wolsey, Integer Programming, 2nd ed. (2021), Ch.14 §14.8 Exercise 2, p.288",
        },
        "expected_schema": {
            "sets": ["G_generators", "T_periods"],
            "params": ["demand[t]", "capacity[g]", "min_load[g]", "startup_cost[g]", "fixed_cost[g]", "var_cost[g]", "reserve_factor", "min_uptime"],
            "vars": ["x[g,t] in {0,1} (on/off)", "y[g,t] >= 0 (output)", "z[g,t] in {0,1} (startup)"],
            "objective": "min sum_{g,t} startup_cost[g]*z[g,t] + fixed_cost[g]*x[g,t] + var_cost[g]*y[g,t]",
            "constraints": [
                "sum_g y[g,t] = demand[t] for all t",
                "sum_g capacity[g]*x[g,t] >= reserve_factor*demand[t] for all t",
                "min_load[g]*x[g,t] <= y[g,t] <= capacity[g]*x[g,t]",
                "min uptime + ramping for generator 5",
            ],
        },
        "ground_truth_params": {
            "generators": ["G1", "G2", "G3", "G4", "G5"],
            "periods": list(range(1, 13)),
            "demand": {1: 50, 2: 60, 3: 50, 4: 100, 5: 80, 6: 70, 7: 90, 8: 60, 9: 50, 10: 120, 11: 110, 12: 70},
            "capacity": {"G1": 12, "G2": 12, "G3": 35, "G4": 50, "G5": 75},
            "min_load": {"G1": 2, "G2": 2, "G3": 5, "G4": 20, "G5": 40},
            "startup_cost": {"G1": 100, "G2": 100, "G3": 300, "G4": 400, "G5": 800},
            "fixed_cost": {"G1": 1, "G2": 1, "G3": 5, "G4": 10, "G5": 15},
            "var_cost": {"G1": 10, "G2": 10, "G3": 4, "G4": 3, "G5": 2},
            "reserve_factor": 1.2,
            "min_uptime": 2,
            "ramp_up_g5": 20,
            "ramp_down_g5": 15,
        },
        "published_optimum": None,
        "feasible": True,
        "solvable": False,
        "notes": "Wolsey unit commitment instance with reserve, min-uptime, and generator-5 ramping. Book gives data only; optimum must be computed via MIP solver. Cyclic boundary (period 1 follows period 12) is non-trivial.",
    },
]

# ============================================================================
# FACILITY LOCATION PROBLEMS
# ============================================================================

FACILITY_LOCATION_PROBLEMS = [
    {
        "id": "loc/ufl/001",
        "name": "small_uncapacitated_facility_location",
        "category": ProblemCategory.FACILITY_LOCATION.value,
        "expected_type": ProblemType.UNCAPACITATED_FACILITY_LOCATION.value,
        "text": """Open from 4 candidate facilities to serve 6 customers. Each facility has a fixed opening cost and variable shipping costs.

Facilities with opening costs (kEUR):
- F1: 100 kEUR, F2: 120 kEUR, F3: 90 kEUR, F4: 110 kEUR

Shipping costs (EUR/unit):
- F1 to customers: [5, 8, 6, 9, 7, 4]
- F2 to customers: [7, 4, 8, 5, 6, 9]
- F3 to customers: [6, 7, 5, 8, 4, 7]
- F4 to customers: [8, 6, 7, 4, 9, 5]

Customer demands (units): [100, 150, 120, 180, 90, 140]

Minimize total opening cost + shipping cost.""",
        "metadata": {
            "units": {"cost_open": "kEUR", "ship_cost": "EUR/unit", "demand": "units"},
            "scale": {"facilities": 4, "customers": 6},
            "characteristics": ["uncapacitated", "fixed_charges", "binary_location"],
            "tags": ["cost_min", "ufl"]
        },
        "expected_schema": {
            "sets": ["F_facilities", "C_customers"],
            "params": ["open_cost[f]", "ship_cost[f,c]", "demand[c]"],
            "vars": ["open[f] in {0,1}", "serve[f,c] >= 0"],
            "objective": "min sum_f open_cost[f]*open[f] + sum_{f,c} ship_cost[f,c]*serve[f,c]",
            "constraints": [
                "sum_f serve[f,c] = demand[c] for all c",
                "serve[f,c] <= M*open[f] for all f,c"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "Baseline UFL for classification testing"
    },

    {
        "id": "facloc/winston_nickles_lockbox/001",
        "name": "winston_nickles_lockbox_location",
        "origin": "literature",
        "category": ProblemCategory.FACILITY_LOCATION.value,
        "expected_type": ProblemType.UNCAPACITATED_FACILITY_LOCATION.value,
        "text": """J. C. Nickles receives credit card payments from four regions of the country (West, Midwest, East, and South). The average daily value of payments mailed by customers from each region is: the West, $70,000; the Midwest, $50,000; the East, $60,000; the South, $40,000. Nickles must decide where customers should mail their payments. Because Nickles can earn 20% annual interest by investing these revenues, it would like to receive payments as quickly as possible. Nickles is considering setting up operations to process payments (often referred to as lockboxes) in four different cities: Los Angeles, Chicago, New York, and Atlanta. The average number of days (from time payment is sent) until a check clears and Nickles can deposit the money depends on the city to which the payment is mailed. The annual cost of running a lockbox in any city is $50,000. Assume that each region must send all its money to a single city and that there is no limit on the amount of money that each lockbox can handle.

Average days from mailing until payment clears:
              City 1 (L.A.)  City 2 (Chicago)  City 3 (N.Y.)  City 4 (Atlanta)
West:              2               6                  8                8
Midwest:           6               2                  5                5
East:              8               5                  2                5
South:             8               5                  5                2

Formulate an IP to minimize the sum of costs due to lost interest and lockbox operations.""",
        "metadata": {
            "units": {"days": "days", "lockbox_cost": "USD/year", "interest_rate": "0.20"},
            "scale": {"regions": 4, "candidate_cities": 4},
            "tags": ["real_data_benchmark", "textbook", "facility_location", "cost_min", "single_assignment"],
            "source": "Winston, Operations Research: Applications and Algorithms, 4th ed., Ch.9 §9.2 Example 4 (Nickles Lockbox), p.483-485",
        },
        "expected_schema": {
            "sets": ["I_regions", "J_cities"],
            "params": ["daily_value[i]", "days[i,j]", "interest_rate", "lockbox_cost[j]"],
            "vars": ["x[i,j] in {0,1}", "y[j] in {0,1}"],
            "objective": "min sum_{i,j} interest_rate*daily_value[i]*days[i,j]*x[i,j] + sum_j lockbox_cost[j]*y[j]",
            "constraints": [
                "sum_j x[i,j] = 1 for all i",
                "x[i,j] <= y[j] for all (i,j)",
            ],
        },
        "ground_truth_params": {
            "regions": ["West", "Midwest", "East", "South"],
            "cities": ["LA", "Chicago", "NY", "Atlanta"],
            "daily_value": {"West": 70000, "Midwest": 50000, "East": 60000, "South": 40000},
            "days": {
                "West":    {"LA": 2, "Chicago": 6, "NY": 8, "Atlanta": 8},
                "Midwest": {"LA": 6, "Chicago": 2, "NY": 5, "Atlanta": 5},
                "East":    {"LA": 8, "Chicago": 5, "NY": 2, "Atlanta": 5},
                "South":   {"LA": 8, "Chicago": 5, "NY": 5, "Atlanta": 2},
            },
            "interest_rate": 0.20,
            "lockbox_cost": {"LA": 50000, "Chicago": 50000, "NY": 50000, "Atlanta": 50000},
        },
        "published_optimum": 242000.0,  # $ thousands in text — z=242 (thousands) = $242,000
        "feasible": True,
        "solvable": False,
        "notes": "Uncapacitated facility location IP. Published optimum z=$242,000 with lockboxes in LA + NY; West→LA, Midwest+East+South→NY.",
    },

    {
        "id": "facloc/wolsey_ufl_ex12/001",
        "name": "wolsey_ufl_5depots_6clients",
        "origin": "literature",
        "category": ProblemCategory.FACILITY_LOCATION.value,
        "expected_type": ProblemType.UNCAPACITATED_FACILITY_LOCATION.value,
        "text": """Solve an instance of the uncapacitated facility location problem with 5 candidate depots and 6 clients. f_j is the cost of opening depot j, and c_ij is the cost of satisfying all client i's demand from depot j.

Depot opening costs: f = (4, 3, 4, 4, 7)

Cost matrix c[client i][depot j] (6 rows × 5 columns):
Client 1: 12 13  6  0  1
Client 2:  8  4  9  1  2
Client 3:  2  6  6  0  1
Client 4:  3  5  2  1  8
Client 5:  8  0  5 10  8
Client 6:  2  0  3  4  1

Decide which depots to open and which depot serves each client to minimize the sum of opening + transportation costs.""",
        "metadata": {
            "units": {"cost": "abstract"},
            "scale": {"depots": 5, "clients": 6},
            "tags": ["real_data_benchmark", "textbook", "wolsey", "facility_location", "cost_min"],
            "source": "Wolsey, Integer Programming, 2nd ed. (2021), Ch.1 §1.9 Exercise 12, p.22",
        },
        "expected_schema": {
            "sets": ["J_depots", "I_clients"],
            "params": ["fixed_cost[j]", "transport_cost[i,j]"],
            "vars": ["y[i,j] >= 0", "x[j] in {0,1}"],
            "objective": "min sum_{i,j} transport_cost[i,j]*y[i,j] + sum_j fixed_cost[j]*x[j]",
            "constraints": [
                "sum_j y[i,j] = 1 for all i",
                "y[i,j] <= x[j] for all (i,j)",
            ],
        },
        "ground_truth_params": {
            "depots": ["D1", "D2", "D3", "D4", "D5"],
            "clients": ["C1", "C2", "C3", "C4", "C5", "C6"],
            "fixed_cost": {"D1": 4, "D2": 3, "D3": 4, "D4": 4, "D5": 7},
            "transport_cost": {
                "C1": {"D1": 12, "D2": 13, "D3": 6,  "D4": 0,  "D5": 1},
                "C2": {"D1": 8,  "D2": 4,  "D3": 9,  "D4": 1,  "D5": 2},
                "C3": {"D1": 2,  "D2": 6,  "D3": 6,  "D4": 0,  "D5": 1},
                "C4": {"D1": 3,  "D2": 5,  "D3": 2,  "D4": 1,  "D5": 8},
                "C5": {"D1": 8,  "D2": 0,  "D3": 5,  "D4": 10, "D5": 8},
                "C6": {"D1": 2,  "D2": 0,  "D3": 3,  "D4": 4,  "D5": 1},
            },
        },
        "published_optimum": None,  # Wolsey gives instance only; optimum to be computed via MIP solver
        "feasible": True,
        "solvable": False,
        "notes": "Wolsey UFL instance — book does not publish optimum (exercise prompt: 'Solve using a MIP system'). Optimum must be computed externally before this entry can score objective_gap.",
    },
]

# ============================================================================
# VEHICLE ROUTING PROBLEMS
# ============================================================================

VEHICLE_ROUTING_PROBLEMS = [
    {
        "id": "vrp/cvrp/001",
        "name": "cvrp_small_depot",
        "category": ProblemCategory.VEHICLE_ROUTING.value,
        "expected_type": ProblemType.CVRP.value,
        "text": """Single depot, 5 customers with demands (kg). Vehicles capacity 100 kg, unlimited vehicles available.

Customer demands (kg): [30, 40, 25, 35, 45]
Distances from depot (km): [10, 15, 8, 12, 18]
Inter-customer distances (km matrix):
    C1  C2  C3  C4  C5
C1  0   12  8   10  14
C2  12  0   9   11  8
C3  8   9   0   7   13
C4  10  11  7   0   9
C5  14  8   13  9   0

Minimize total distance traveled.""",
        "metadata": {
            "units": {"distance": "km", "demand": "kg", "capacity": "kg"},
            "scale": {"customers": 5, "vehicles": "unlimited"},
            "characteristics": ["capacitated", "homogeneous_fleet", "single_depot"],
            "tags": ["distance_min", "cvrp"]
        },
        "expected_schema": {
            "sets": ["C_customers", "V_vehicles"],
            "params": ["demand[c]", "capacity", "distance[i,j]"],
            "vars": ["route[v,i,j] in {0,1}"],
            "objective": "min sum_{v,i,j} distance[i,j]*route[v,i,j]",
            "constraints": [
                "sum_v sum_i route[v,i,c] = 1 for all c",
                "sum_c demand[c]*sum_i route[v,i,c] <= capacity for all v",
                "subtour_elimination"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "Capacity only; good for label check"
    },

    {
        "id": "vrp/wolsey_tsp_time_windows/001",
        "name": "wolsey_tsp_with_time_windows_9customers",
        "origin": "literature",
        "category": ProblemCategory.VEHICLE_ROUTING.value,
        "expected_type": ProblemType.VRPTW.value,
        "text": """A truck driver must deliver to nine customers on a given day, starting and finishing at the depot. Each customer i = 1,…,9 has a time window [r_i, d_i] and an unloading time p_i. The driver must start unloading at client i during the specified time interval. If she is early, she has to wait till time r_i before starting to unload. Node 0 denotes the depot, and c_ij is the travel time between nodes i and j.

Processing times:    p = (0, 1, 5, 9, 2, 7, 5, 1, 5, 3)        (index 0 = depot, then customers 1..9)
Release times:       r = (0, 1, 5, 9, 2, 7, 5, 1, 5, 3)        — start of time window (same indexing)
Deadlines:           d = (150, 45, 42, 40, 150, 48, 96, 100, 127, 66)  — end of time window

Travel-time matrix c_ij (10×10; '—' = same node):
       0   1   2   3   4   5   6   7   8   9
  0:   —   5   4   4   4   6   3   2   1   8
  1:   7   —   2   5   3   5   4   4   4   9
  2:   3   4   —   1   1  12   4   3  11   6
  3:   2   2   3   —   2  23   2   9  11   4
  4:   6   4   7   2   —   9   8   3   2   1
  5:   1   4   6   7   3   —   8   5   7   4
  6:  12  32   5  12  18   5   —   7   9   6
  7:   9  11   4  12  32   5  12   —   5  22
  8:   6   4   7   3   5   8   6   9   —   5
  9:   4   6   4   7   3   5   8   6   9   —

Determine a tour visiting all 9 customers starting and ending at the depot, respecting time windows and unloading times.""",
        "metadata": {
            "units": {"time": "abstract"},
            "scale": {"nodes": 10, "customers": 9},
            "tags": ["real_data_benchmark", "textbook", "wolsey", "tsp", "time_windows", "single_vehicle"],
            "source": "Wolsey, Integer Programming, 2nd ed. (2021), Ch.14 §14.8 Exercise 11, p.290",
        },
        "expected_schema": {
            "sets": ["N_nodes (includes depot)"],
            "params": ["travel_time[i,j]", "release[i]", "deadline[i]", "service[i]"],
            "vars": ["x[i,j] in {0,1} (arc used)", "t[i] >= 0 (start of service at i)"],
            "objective": "min total_completion_time (or feasibility-only)",
            "constraints": [
                "tour visits every customer exactly once",
                "release[i] <= t[i] <= deadline[i]",
                "t[j] >= t[i] + service[i] + travel_time[i,j] if x[i,j]=1",
            ],
        },
        "ground_truth_params": {
            "nodes": list(range(10)),
            "depot": 0,
            "processing": {0: 0, 1: 1, 2: 5, 3: 9, 4: 2, 5: 7, 6: 5, 7: 1, 8: 5, 9: 3},
            "release":    {0: 0, 1: 1, 2: 5, 3: 9, 4: 2, 5: 7, 6: 5, 7: 1, 8: 5, 9: 3},
            "deadline":   {0: 150, 1: 45, 2: 42, 3: 40, 4: 150, 5: 48, 6: 96, 7: 100, 8: 127, 9: 66},
            "travel_time_rows": [
                [None, 5, 4, 4, 4, 6, 3, 2, 1, 8],
                [7, None, 2, 5, 3, 5, 4, 4, 4, 9],
                [3, 4, None, 1, 1, 12, 4, 3, 11, 6],
                [2, 2, 3, None, 2, 23, 2, 9, 11, 4],
                [6, 4, 7, 2, None, 9, 8, 3, 2, 1],
                [1, 4, 6, 7, 3, None, 8, 5, 7, 4],
                [12, 32, 5, 12, 18, 5, None, 7, 9, 6],
                [9, 11, 4, 12, 32, 5, 12, None, 5, 22],
                [6, 4, 7, 3, 5, 8, 6, 9, None, 5],
                [4, 6, 4, 7, 3, 5, 8, 6, 9, None],
            ],
        },
        "published_optimum": None,
        "feasible": True,
        "solvable": False,
        "notes": "Wolsey TSP-with-time-windows instance. Single-vehicle routing on 10 nodes (depot + 9 customers). Book provides instance data only; optimum to be computed externally.",
    },
]

# ============================================================================
# SET COVER PROBLEMS
# ============================================================================

SET_COVER_PROBLEMS = [
    {
        "id": "set/cover/001",
        "name": "minimal_sensor_placement",
        "category": ProblemCategory.SET_COVER.value,
        "expected_type": ProblemType.SET_COVER.value,
        "text": """Choose the minimum number of sensors to cover all zones; each sensor covers a subset of zones.

Sensors and their coverage:
- Sensor 1: covers zones {A, B, C}
- Sensor 2: covers zones {B, D, E}
- Sensor 3: covers zones {A, C, F}
- Sensor 4: covers zones {D, E, F}
- Sensor 5: covers zones {B, C, E}

All zones {A, B, C, D, E, F} must be covered.
Minimize number of sensors used.""",
        "metadata": {
            "units": {},
            "scale": {"sensors": 5, "zones": 6},
            "characteristics": ["binary", "covering", "greedy_approximable"],
            "tags": ["sensors_min", "set_cover"]
        },
        "expected_schema": {
            "sets": ["S_sensors", "Z_zones", "covers[s]"],
            "params": [],
            "vars": ["use[s] in {0,1}"],
            "objective": "min sum_s use[s]",
            "constraints": [
                "sum_{s: z in covers[s]} use[s] >= 1 for all z"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "Binary cover model"
    },

    {
        "id": "setcover/winston_kilroy/001",
        "name": "winston_kilroy_fire_station_set_covering",
        "origin": "literature",
        "category": ProblemCategory.SET_COVER.value,
        "expected_type": ProblemType.SET_COVER.value,
        "text": """There are six cities (cities 1–6) in Kilroy County. The county must determine where to build fire stations. The county wants to build the minimum number of fire stations needed to ensure that at least one fire station is within 15 minutes (driving time) of each city.

Driving times between cities in Kilroy County (minutes):
        City 1  City 2  City 3  City 4  City 5  City 6
City 1:   0      10      20      30      30      20
City 2:  10       0      25      35      20      10
City 3:  20      25       0      15      30      20
City 4:  30      35      15       0      15      25
City 5:  30      20      30      15       0      14
City 6:  20      10      20      25      14       0

Formulate an IP that will tell Kilroy how many fire stations should be built and where they should be located.""",
        "metadata": {
            "units": {"time": "minutes"},
            "scale": {"cities": 6, "candidate_locations": 6},
            "coverage_radius": 15,
            "tags": ["real_data_benchmark", "textbook", "set_cover", "facility_location_covering"],
            "source": "Winston, Operations Research: Applications and Algorithms, 4th ed., Ch.9 §9.2 Example 5 (Kilroy Fire Station), p.486-487",
        },
        "expected_schema": {
            "sets": ["C_cities", "L_locations"],
            "params": ["covers[l,c]"],
            "vars": ["x[l] in {0,1}"],
            "objective": "min sum_l x[l]",
            "constraints": ["sum_l covers[l,c]*x[l] >= 1 for all c"],
        },
        "ground_truth_params": {
            "cities": ["C1", "C2", "C3", "C4", "C5", "C6"],
            "locations": ["C1", "C2", "C3", "C4", "C5", "C6"],
            "covers": {
                "C1": ["C1", "C2"],
                "C2": ["C1", "C2", "C6"],
                "C3": ["C3", "C4"],
                "C4": ["C3", "C4", "C5"],
                "C5": ["C4", "C5", "C6"],
                "C6": ["C2", "C5", "C6"],
            },
        },
        "published_optimum": 2.0,
        "feasible": True,
        "solvable": False,
        "notes": "Classic set-covering IP. Published optimum z=2 with stations in cities 2 and 4. Multiple alternative optima.",
    },
]

# ============================================================================
# BIN PACKING / CUTTING STOCK PROBLEMS
# ============================================================================

BIN_PACKING_PROBLEMS = [
    {
        "id": "binpack/basic/001",
        "name": "one_dim_bin_packing",
        "category": ProblemCategory.BIN_PACKING.value,
        "expected_type": ProblemType.BIN_PACKING.value,
        "text": """Pack items into minimum number of bins.

Item sizes: [40, 30, 25, 50, 35, 20, 45, 30, 25, 40]
Bin capacity: 100

Minimize number of bins used.""",
        "metadata": {
            "units": {"size": "units"},
            "scale": {"items": 10},
            "bin_capacity": 100,
            "characteristics": ["one_dimensional", "bin_minimize"],
            "tags": ["bins_min", "packing"]
        },
        "expected_schema": {
            "sets": ["I_items", "B_bins"],
            "params": ["size[i]", "capacity"],
            "vars": ["assign[i,b] in {0,1}", "use_bin[b] in {0,1}"],
            "objective": "min sum_b use_bin[b]",
            "constraints": [
                "sum_b assign[i,b] = 1 for all i",
                "sum_i size[i]*assign[i,b] <= capacity*use_bin[b] for all b"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "1D bin packing - column generation candidate"
    },
]

# ============================================================================
# MULTICOMMODITY FLOW PROBLEMS
# ============================================================================

MULTICOMMODITY_FLOW_PROBLEMS = [
    {
        "id": "mcf/telecom/001",
        "name": "multicommodity_network_flow",
        "category": ProblemCategory.MULTICOMMODITY_FLOW.value,
        "expected_type": "multicommodity_flow",
        "text": """Route 3 commodities through a shared network.

Network: 5 nodes, 8 directed arcs with capacities
Arc capacities (shared among all commodities): {(1,2):50, (1,3):40, (2,4):45, (3,4):30, (3,5):35, (4,5):40, (2,5):25, (1,4):30}

Commodities:
- Commodity A: source=1, sink=5, demand=20
- Commodity B: source=2, sink=5, demand=15
- Commodity C: source=1, sink=4, demand=18

Minimize total flow cost (cost=1 per unit per arc) subject to shared arc capacities.""",
        "metadata": {
            "units": {"flow": "units", "capacity": "units"},
            "scale": {"commodities": 3, "nodes": 5, "arcs": 8},
            "characteristics": ["multicommodity", "shared_capacity"],
            "tags": ["cost_min", "mcf"]
        },
        "expected_schema": {
            "sets": ["K_commodities", "N_nodes", "A_arcs"],
            "params": ["capacity[a]", "demand[k]", "source[k]", "sink[k]"],
            "vars": ["flow[k,a] >= 0"],
            "objective": "min sum_{k,a} flow[k,a]",
            "constraints": [
                "sum_k flow[k,a] <= capacity[a] for all a",
                "flow_conservation[k,n] for all k,n"
            ]
        },
                "feasible": True,
        "solvable": False,
        "notes": "Multicommodity flow - shared arc capacities"
    },
]

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_all_problems() -> List[Dict]:
    """
    Return all problems from all categories.

    Automatically adds 'solver_id' field to each problem based on expected_type.
    """
    all_problems = (
        TRANSPORTATION_PROBLEMS +
        SCHEDULING_PROBLEMS +
        ASSIGNMENT_PROBLEMS +
        KNAPSACK_PROBLEMS +
        NETWORK_FLOW_PROBLEMS +
        PRODUCTION_PLANNING_PROBLEMS +
        FACILITY_LOCATION_PROBLEMS +
        VEHICLE_ROUTING_PROBLEMS +
        SET_COVER_PROBLEMS +
        BIN_PACKING_PROBLEMS +
        MULTICOMMODITY_FLOW_PROBLEMS
    )

    # Automatically add solver_id to each problem
    for problem in all_problems:
        if 'solver_id' not in problem:
            problem['solver_id'] = get_solver_id(problem)
        # Provenance defaults to "synthetic" unless a problem explicitly opts
        # into the literature gate. The two-way check in validate_problem_schema
        # guarantees this default can't silently hide a literature problem that
        # forgot the flag (any entry carrying published_optimum/ground_truth_params
        # must be marked "literature").
        if 'origin' not in problem:
            problem['origin'] = 'synthetic'

    return all_problems

def get_problems_by_category(category: str) -> List[Dict]:
    """Get problems of a specific category."""
    category_map = {
        ProblemCategory.TRANSPORTATION.value: TRANSPORTATION_PROBLEMS,
        ProblemCategory.SCHEDULING.value: SCHEDULING_PROBLEMS,
        ProblemCategory.ASSIGNMENT.value: ASSIGNMENT_PROBLEMS,
        ProblemCategory.KNAPSACK.value: KNAPSACK_PROBLEMS,
        ProblemCategory.NETWORK_FLOW.value: NETWORK_FLOW_PROBLEMS,
        ProblemCategory.PRODUCTION_PLANNING.value: PRODUCTION_PLANNING_PROBLEMS,
        ProblemCategory.FACILITY_LOCATION.value: FACILITY_LOCATION_PROBLEMS,
        ProblemCategory.VEHICLE_ROUTING.value: VEHICLE_ROUTING_PROBLEMS,
        ProblemCategory.SET_COVER.value: SET_COVER_PROBLEMS,
        ProblemCategory.BIN_PACKING.value: BIN_PACKING_PROBLEMS,
        ProblemCategory.MULTICOMMODITY_FLOW.value: MULTICOMMODITY_FLOW_PROBLEMS,
    }
    return category_map.get(category.lower(), [])

def get_solvable_problems() -> List[Dict]:
    """Return only problems that current system can solve."""
    return [p for p in get_all_problems() if p.get("solvable", False)]

def get_infeasible_problems(machine_checkable: bool = False) -> List[Dict]:
    """Return the curated infeasible problems (``feasible == False``).

    With ``machine_checkable=True`` return only those that carry a
    structured ``params`` dict and an ``expected_infeasible_layer`` — the
    subset a deterministic, LLM-free feasibility test can iterate to assert
    each instance is rejected at exactly its tagged layer (0/1/2), across
    both transportation and single-stage scheduling.
    """
    infeasible = [p for p in get_all_problems() if not p.get("feasible", True)]
    if machine_checkable:
        return [
            p for p in infeasible
            if "params" in p and "expected_infeasible_layer" in p
        ]
    return infeasible

def get_problem_by_name(name: str) -> Optional[Dict]:
    """Get a specific problem by its name."""
    for problem in get_all_problems():
        if problem["name"] == name:
            return problem
    return None

def get_problem_by_id(problem_id: str) -> Optional[Dict]:
    """Get a specific problem by its hierarchical ID."""
    for problem in get_all_problems():
        if problem["id"] == problem_id:
            return problem
    return None

def get_categories() -> List[str]:
    """Get list of all available categories."""
    return [cat.value for cat in ProblemCategory]

def list_problems(category: Optional[str] = None, solvable_only: bool = False):
    """Print a formatted list of problems."""
    if category:
        problems = get_problems_by_category(category)
        if not problems:
            print(f"Category '{category}' not found. Available: {', '.join(get_categories())}")
            return
    else:
        problems = get_all_problems()

    if solvable_only:
        problems = [p for p in problems if p.get("solvable", False)]

    print(f"\n{'='*80}")
    if category:
        print(f"  {category.upper()} PROBLEMS")
    else:
        print(f"  ALL OR PROBLEMS")
    if solvable_only:
        print(f"  (Showing only solvable problems)")
    print(f"{'='*80}\n")

    for i, problem in enumerate(problems, 1):
        solvable = "✓" if problem.get("solvable", False) else "✗"
        print(f"{i:2d}. [{solvable}] {problem['id']}")
        print(f"     Name: {problem['name']}")
        print(f"     Type: {problem['expected_type']}")
        if 'metadata' in problem and 'tags' in problem['metadata']:
            print(f"     Tags: {', '.join(problem['metadata']['tags'])}")
        print(f"     {problem['notes']}")
        print()

def validate_problem_schema(problem: Dict) -> List[str]:
    """Validate that a problem has all required fields and a consistent provenance.

    Beyond the basic required-field check, this enforces the literature-gate
    invariant (two-way, so the "synthetic" default can never silently hide a
    literature problem):

      - origin == "literature"  ==>  must carry a citation (metadata.source),
        ground_truth_params, and — when solvable — a non-None published_optimum.
      - carries published_optimum or ground_truth_params  ==>  origin MUST be
        "literature" (you cannot leave answer-key data in a synthetic problem).

    The actual "solver reproduces published_optimum at 0.00% gap" check lives in
    the smoke harness, not here — this only guarantees the *data* is well-formed
    and correctly classified.
    """
    required_fields = ['id', 'name', 'category', 'expected_type', 'text', 'solvable', 'notes']
    errors = []

    for field in required_fields:
        if field not in problem:
            errors.append(f"Missing required field: {field}")

    if 'metadata' in problem:
        if 'units' not in problem['metadata']:
            errors.append("metadata should contain 'units' field")

    # Provenance gate. origin defaults to "synthetic" at read time, so treat a
    # missing value as synthetic here too.
    origin = problem.get('origin', 'synthetic')
    if origin not in ('literature', 'synthetic'):
        errors.append(f"origin must be 'literature' or 'synthetic', got {origin!r}")

    has_optimum = problem.get('published_optimum') is not None
    has_gt = 'ground_truth_params' in problem
    has_source = bool(problem.get('metadata', {}).get('source'))

    if origin == 'literature':
        if not has_source:
            errors.append("origin='literature' requires a metadata.source citation")
        if not has_gt:
            errors.append("origin='literature' requires ground_truth_params (verbatim from source)")
        if problem.get('solvable') and not has_optimum:
            errors.append("origin='literature' + solvable requires a non-None published_optimum")
    else:  # synthetic
        if has_optimum:
            errors.append("published_optimum present but origin!='literature' (mark it 'literature')")
        if has_gt:
            errors.append("ground_truth_params present but origin!='literature' (mark it 'literature')")

    return errors


def validate_repository() -> Dict[str, List[str]]:
    """Validate every problem; return {problem_name: [errors]} for any with issues.

    Empty dict == repository is internally consistent. Call from a test or the
    CLI ('validate' subcommand) to fail loudly on a malformed/mis-tagged entry.
    """
    report: Dict[str, List[str]] = {}
    for problem in get_all_problems():
        errs = validate_problem_schema(problem)
        if errs:
            report[problem.get('name', problem.get('id', '<unknown>'))] = errs
    return report

# ============================================================================
# COMMAND-LINE INTERFACE (with argparse)
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='OR Problem Repository - Centralized problem descriptions for testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python or_problem_repository.py list
  python or_problem_repository.py list transportation --solvable
  python or_problem_repository.py get european_wine_distribution
  python or_problem_repository.py count
  python or_problem_repository.py validate
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # List command
    list_parser = subparsers.add_parser('list', help='List problems')
    list_parser.add_argument('category', nargs='?', help='Category to filter by')
    list_parser.add_argument('--solvable', action='store_true', help='Show only solvable problems')

    # Get command
    get_parser = subparsers.add_parser('get', help='Get specific problem')
    get_parser.add_argument('name', help='Problem name or ID')

    # Count command
    subparsers.add_parser('count', help='Show statistics')

    # Validate command
    subparsers.add_parser('validate', help='Validate all problems')

    # Categories command
    subparsers.add_parser('categories', help='List available categories')

    args = parser.parse_args()

    if args.command == 'list':
        list_problems(args.category, args.solvable)

    elif args.command == 'get':
        problem = get_problem_by_name(args.name) or get_problem_by_id(args.name)
        if problem:
            print(f"\n{'='*80}")
            print(f"Problem: {problem['name']}")
            print(f"ID: {problem['id']}")
            print(f"Category: {problem['category']}")
            print(f"Expected Type: {problem['expected_type']}")
            print(f"Solvable: {'✓ Yes' if problem.get('solvable') else '✗ No'}")
            print(f"{'='*80}\n")
            print("Description:")
            print(problem['text'])
            print(f"\n{'='*80}")
            if 'metadata' in problem:
                print("Metadata:")
                for key, value in problem['metadata'].items():
                    print(f"  {key}: {value}")
            print(f"\n{'='*80}")
            print(f"Notes: {problem['notes']}")
            print()
        else:
            print(f"Problem '{args.name}' not found.")

    elif args.command == 'count':
        all_probs = get_all_problems()
        solvable = get_solvable_problems()
        print(f"\n{'='*80}")
        print("  PROBLEM STATISTICS")
        print(f"{'='*80}\n")
        print(f"Total problems: {len(all_probs)}")
        print(f"Solvable: {len(solvable)}")
        print(f"Not yet solvable: {len(all_probs) - len(solvable)}")
        print(f"\nBy category:")
        for cat in get_categories():
            probs = get_problems_by_category(cat)
            solv = [p for p in probs if p.get("solvable", False)]
            print(f"  {cat:25s}: {len(probs):2d} total, {len(solv):2d} solvable")
        print()

    elif args.command == 'validate':
        print(f"\n{'='*80}")
        print("  VALIDATING ALL PROBLEMS")
        print(f"{'='*80}\n")
        all_problems = get_all_problems()
        total_errors = 0
        for problem in all_problems:
            errors = validate_problem_schema(problem)
            if errors:
                print(f"✗ {problem.get('name', 'UNKNOWN')}")
                for error in errors:
                    print(f"    - {error}")
                total_errors += len(errors)
            else:
                print(f"✓ {problem['name']}")
        print(f"\n{'='*80}")
        if total_errors == 0:
            print("All problems validated successfully!")
        else:
            print(f"Found {total_errors} errors")
        print()
        # Non-zero exit so this doubles as a CI / pre-commit gate.
        if total_errors:
            raise SystemExit(1)

    elif args.command == 'categories':
        print(f"\n{'='*80}")
        print("  AVAILABLE CATEGORIES")
        print(f"{'='*80}\n")
        for cat in get_categories():
            count = len(get_problems_by_category(cat))
            print(f"  - {cat:25s} ({count} problems)")
        print()

    else:
        parser.print_help()

# ============================================================================
# SOLVER FAMILY MAPPING
# ============================================================================

def get_solver_id(problem: Dict) -> str:
    """
    Map fine-grained expected_type to a solver_id that matches
    what the current system can actually handle.

    Args:
        problem: Problem dict with expected_type field

    Returns:
        solver_id: "transport_basic_bipartite", "single_stage_ipm_scheduling", or "none"

    Examples:
        - 'transportation' -> 'transport_basic_bipartite' (if bipartite)
        - 'min_cost_flow' -> 'none' (not yet supported, needs network solver)
        - 'single_stage_scheduling' -> 'single_stage_ipm_scheduling'
        - 'job_shop' -> 'none' (not yet implemented)
    """
    expected_type = problem.get("expected_type", "")
    metadata = problem.get("metadata", {})

    # Transportation family: only basic bipartite plant→market
    if expected_type == ProblemType.TRANSPORTATION.value:
        # Check if it's truly bipartite (no transshipment)
        graph_sig = metadata.get("graph_signature", "")
        if "bipartite" in graph_sig or graph_sig == "":
            return "transport_basic_bipartite"
        else:
            return "none"  # Has transshipment or other complexity

    # Min-cost flow: requires general network solver (not yet implemented)
    if expected_type == ProblemType.MIN_COST_FLOW.value:
        return "none"

    # Single-stage scheduling family. Parallel-machine scheduling routes here
    # too: the classifier maps PARALLEL_MACHINE_SCHEDULING ->
    # single_stage_ipm_scheduling (multi-unit support), and the pipeline solves
    # it end-to-end, so the repo metadata must agree (was falling through to
    # "none", which mislabeled bottling_line_parallel_machines).
    if expected_type in [
        ProblemType.SINGLE_STAGE_SCHEDULING.value,
        ProblemType.SINGLE_MACHINE_TARDINESS.value,
        ProblemType.PARALLEL_MACHINE_SCHEDULING.value
    ]:
        return "single_stage_ipm_scheduling"

    # Job shop, flow shop: not yet implemented
    if expected_type in [
        ProblemType.JOB_SHOP.value,
        ProblemType.FLOW_SHOP.value,
        ProblemType.OPEN_SHOP.value
    ]:
        return "none"

    # Everything else: not supported yet
    return "none"


if __name__ == "__main__":
    main()
