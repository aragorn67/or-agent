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
    - metadata: units, scale, characteristics
    - expected_schema: sets, params, vars, constraints (for validation)
    - solvable: bool - can current system solve it?
    - notes: testing/implementation notes
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
    JOB_SHOP = "job_shop"
    FLOW_SHOP = "flow_shop"
    OPEN_SHOP = "open_shop"
    SHIFT_ROSTERING = "shift_rostering"
    PROJECT_SCHEDULING = "project_scheduling"
    SINGLE_MACHINE_TARDINESS = "single_machine_tardiness"

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
        "solvable": True,
        "notes": "FIXED: Changed note from 'balanced' to unbalanced (Supply=2000 > Demand=1700)"
    },

    {
    "id": "transport/food_retail/001",
    "name": "fresh_food_distribution",
    "category": ProblemCategory.TRANSPORTATION.value,
    "expected_type": ProblemType.TRANSPORTATION.value,
    "text": """A national grocery chain distributes perishable goods from 3 regional warehouses 
(London, Manchester, Bristol) to 5 city stores. Each warehouse has daily capacity (tons) and 
each store daily demand (tons). Costs (£/ton) are known. 
Find a transport plan minimizing total cost while meeting all store demands 
without exceeding warehouse capacity.""",
    "metadata": {
        "units": {"cost": "GBP/ton", "capacity": "tons/day"},
        "scale": {"sources": 3, "sinks": 5},
        "balanced": True,
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
    "solvable": True,
    "notes": "Realistic perishable distribution network."
},

{
    "id": "transport/steel_construction/001",
    "name": "steel_supply_construction",
    "category": ProblemCategory.TRANSPORTATION.value,
    "expected_type": ProblemType.TRANSPORTATION.value,
    "text": """Two steel mills (Sheffield, Glasgow) supply five major construction projects. 
Each mill has weekly output limits and each project requires specified steel tonnage. 
Transport costs (£/ton) depend on distance. 
Decide shipping quantities to minimize total cost while meeting all demands.""",
    "metadata": {
        "units": {"cost": "GBP/ton", "capacity": "tons/week"},
        "scale": {"sources": 2, "sinks": 5},
        "balanced": False,
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
    "solvable": True,
    "notes": "Steel logistics example; good for unbalanced transport detection."
},

{
    "id": "transport/pharma_coldchain/001",
    "name": "vaccine_cold_chain",
    "category": ProblemCategory.TRANSPORTATION.value,
    "expected_type": ProblemType.MIN_COST_FLOW.value,
    "text": """A pharmaceutical company distributes temperature-sensitive vaccines from one national depot 
to 4 hospital clusters through 2 intermediate cold hubs. 
Hub capacities and transport costs (€/vial) are known. 
Decide shipment quantities along each route to minimize cost 
while respecting hub capacities and fulfilling hospital demand.""",
    "metadata": {
        "units": {"cost": "EUR/vial", "capacity": "vials/day"},
        "scale": {"nodes": 7, "arcs": 10},
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
    "solvable": True,
    "notes": "Realistic multi-stage min-cost flow in pharma cold-chain logistics."
}, 


    {
        "id": "transport/us_mfg/001",
        "name": "us_manufacturing_distribution",
        "category": ProblemCategory.TRANSPORTATION.value,
        "expected_type": ProblemType.TRANSPORTATION.value,
        "text": """Sources: Seattle (capacity 350 units), Denver (capacity 200 units), and Detroit (capacity 150 units).
Sinks: Chicago (demand 250 units), New York (demand 180 units), and Atlanta (demand 270 units).
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
        "solvable": True,
        "notes": "Unbalanced: supply 320 > demand 290"
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
]


# ============================================================================
# SCHEDULING PROBLEMS
# ============================================================================

SCHEDULING_PROBLEMS = [
    {
        "id": "sched/chem_batch/001",
        "name": "chemical_batch_production",
        "category": ProblemCategory.SCHEDULING.value,
        "expected_type": ProblemType.SINGLE_STAGE_SCHEDULING.value,
        "text": """A chemical plant needs to schedule 3 production orders on 2 batch reactors.
Orders and processing requirements:
- Order A: 2 hours on Reactor 1 OR 3 hours on Reactor 2, due by hour 10
- Order B: 1.5 hours on Reactor 1 only, due by hour 8
- Order C: 2.5 hours on Reactor 2 only, due by hour 12

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
        "solvable": True,
        "notes": "CLARIFIED: Each order goes to ONE reactor (single operation). 'OR' makes it clear."
    },

    {
    "id": "sched/ecommerce/001",
    "name": "warehouse_order_picking",
    "category": ProblemCategory.SCHEDULING.value,
    "expected_type": ProblemType.SINGLE_STAGE_SCHEDULING.value,
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
    "solvable": True,
    "notes": "Weighted tardiness scheduling from online-retail fulfilment."
}, 

{
    "id": "sched/semiconductor/001",
    "name": "wafer_processing_single_stage",
    "category": ProblemCategory.SCHEDULING.value,
    "expected_type": ProblemType.SINGLE_STAGE_SCHEDULING.value,
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
    "solvable": True,
    "notes": "Real industrial scheduling with setup-time dependency."
},

{
    "id": "sched/pharma_packaging/001",
    "name": "pharmaceutical_packaging_line",
    "category": ProblemCategory.SCHEDULING.value,
    "expected_type": ProblemType.SINGLE_STAGE_SCHEDULING.value,
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
    "solvable": True,
    "notes": "Classic single-machine Lmax problem in pharma packaging operations."
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
        "solvable": False,
        "notes": "Classic 1||∑T_j problem for testing classification"
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
        "solvable": False,
        "notes": "Maximization assignment - solver not yet implemented"
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
        "solvable": False,
        "notes": "Weight-constrained knapsack"
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
        "solvable": False,
        "notes": "Multi-product aggregate planning - solver not yet implemented"
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
        "solvable": False,
        "notes": "Baseline UFL for classification testing"
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
        "solvable": False,
        "notes": "Capacity only; good for label check"
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
        "solvable": False,
        "notes": "Binary cover model"
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
    """Validate that a problem has all required fields."""
    required_fields = ['id', 'name', 'category', 'expected_type', 'text', 'solvable', 'notes']
    errors = []

    for field in required_fields:
        if field not in problem:
            errors.append(f"Missing required field: {field}")

    if 'metadata' in problem:
        if 'units' not in problem['metadata']:
            errors.append("metadata should contain 'units' field")

    return errors

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

    # Single-stage scheduling family
    if expected_type in [
        ProblemType.SINGLE_STAGE_SCHEDULING.value,
        ProblemType.SINGLE_MACHINE_TARDINESS.value
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
