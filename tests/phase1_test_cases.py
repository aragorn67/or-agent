#!/usr/bin/env python3
"""
DATA: Phase 1 Test Cases (Legacy)

PURPOSE: Test cases for problem classification (assignment, knapsack, scheduling, etc.)
FORMAT: Dict with name, text, expected type, key_elements
USAGE: Imported by test_problem_classification_runner.py
NOTE: Consider migrating to or_problem_repository.py for centralized management
"""

# ============================================================================
# ASSIGNMENT PROBLEMS
# ============================================================================

ASSIGNMENT_CASES = [
    {
        "name": "Classic Worker-Task Assignment",
        "text": """I have 4 workers and 4 tasks. Each worker has different costs for each task.
        Worker A costs: Task1=$9, Task2=$2, Task3=$7, Task4=$8.
        Worker B costs: Task1=$6, Task2=$4, Task3=$3, Task4=$7.
        Worker C costs: Task1=$5, Task2=$8, Task3=$1, Task4=$8.
        Worker D costs: Task1=$7, Task2=$6, Task3=$9, Task4=$4.
        Each worker must be assigned to exactly one task, and each task needs exactly one worker.
        Minimize total cost.""",
        "expected": "assignment",
        "key_elements": ["workers", "tasks", "cost_matrix", "one_to_one_constraint", "objective"]
    },
    {
        "name": "Machine-Job Assignment",
        "text": """We have 5 machines and 5 jobs. Each machine can process any job but with different
        processing times. Machine 1 processes jobs in [10, 15, 9, 8, 12] minutes for jobs 1-5.
        Machine 2: [12, 8, 14, 11, 9]. Machine 3: [8, 11, 7, 13, 10]. Machine 4: [14, 9, 12, 8, 11].
        Machine 5: [11, 13, 10, 9, 14]. Assign each job to exactly one machine and each machine
        to exactly one job to minimize total processing time.""",
        "expected": "assignment",
        "key_elements": ["machines", "jobs", "processing_times", "one_to_one_constraint", "objective"]
    },
    {
        "name": "Salesperson-Territory Assignment",
        "text": """I need to assign 3 salespeople to 3 territories. Each salesperson generates different
        revenue in each territory. Person A: Territory1=$50k, Territory2=$70k, Territory3=$60k.
        Person B: Territory1=$80k, Territory2=$50k, Territory3=$70k.
        Person C: Territory1=$60k, Territory2=$80k, Territory3=$90k.
        Each person covers one territory, each territory gets one person. Maximize total revenue.""",
        "expected": "assignment",
        "key_elements": ["salespeople", "territories", "revenue_matrix", "one_to_one_constraint", "objective"]
    },
    {
        "name": "Unbalanced Assignment",
        "text": """I have 6 technicians and 4 repair jobs. Each technician has different skill costs for
        each job (ranging $100-$500). Only 4 technicians will work, others stay idle. Each job needs
        exactly one technician. Which technicians to assign to minimize total cost?""",
        "expected": "assignment",
        "key_elements": ["technicians", "jobs", "costs", "unbalanced", "objective"]
    },
    {
        "name": "ADVERSARIAL: Assignment vs Transportation",
        "text": """Ship containers from 3 ports to 3 destinations. Each port-destination pair has a cost.
        CONSTRAINT: Each port ships to EXACTLY ONE destination, each destination receives from EXACTLY ONE port.
        No capacity limits, no demand amounts. Just one-to-one matching. Minimize cost.""",
        "expected": "assignment",
        "key_elements": ["ports", "destinations", "costs", "one_to_one_constraint", "objective"]
    },
]


# ============================================================================
# NETWORK FLOW PROBLEMS
# ============================================================================

NETWORK_FLOW_CASES = [
    {
        "name": "Classic Max Flow",
        "text": """We have a network with nodes S (source), A, B, C, T (sink).
        Edges with capacities: S→A: 10, S→B: 8, A→C: 5, A→B: 2, B→C: 7, B→T: 6, C→T: 9.
        What is the maximum flow from S to T?""",
        "expected": "max_flow",
        "key_elements": ["nodes", "edges", "capacities", "source", "sink", "objective"]
    },
    {
        "name": "Pipeline Network",
        "text": """Network of water pipes from reservoir to city. Nodes: Reservoir, Pump1, Pump2,
        Junction1, Junction2, City. Pipe capacities in cubic meters/hour: Reservoir→Pump1: 1000,
        Reservoir→Pump2: 800, Pump1→Junction1: 600, Pump2→Junction1: 500, Pump1→Junction2: 400,
        Pump2→Junction2: 300, Junction1→City: 700, Junction2→City: 500. Maximize flow to city.""",
        "expected": "max_flow",
        "key_elements": ["nodes", "edges", "capacities", "source", "sink", "flow_conservation", "objective"]
    },
    {
        "name": "Min Cost Flow",
        "text": """Transport goods in a network. Nodes: Factory (supply=100), Warehouse1, Warehouse2,
        Store1 (demand=40), Store2 (demand=60). Edges have capacity and cost per unit:
        Factory→W1: capacity=60, cost=$2/unit; Factory→W2: capacity=50, cost=$3/unit;
        W1→Store1: capacity=50, cost=$1/unit; W1→Store2: capacity=40, cost=$2/unit;
        W2→Store1: capacity=30, cost=$2/unit; W2→Store2: capacity=50, cost=$1/unit.
        Minimize total cost while satisfying all demands.""",
        "expected": "max_flow",
        "key_elements": ["nodes", "edges", "capacities", "costs", "supply", "demand", "objective"]
    },
    {
        "name": "Shortest Path",
        "text": """Find shortest path from City A to City Z. Roads: A→B (50km), A→C (80km),
        B→D (60km), C→D (30km), B→Z (120km), C→Z (100km), D→Z (70km). What is the minimum distance?""",
        "expected": "shortest_path",
        "key_elements": ["nodes", "edges", "distances", "source", "sink", "objective"]
    },
    {
        "name": "ADVERSARIAL: Flow vs Transportation",
        "text": """Move oil through pipeline network. Source has 1000 barrels. Nodes: Source, A, B, Sink (needs 1000).
        Pipelines with capacities: Source→A (600), Source→B (500), A→Sink (700), B→Sink (400), A→B (200 bidirectional).
        Flow conservation at A and B (inflow = outflow). Maximize throughput to sink.""",
        "expected": "max_flow",
        "key_elements": ["nodes", "edges", "capacities", "flow_conservation", "source", "sink", "objective"]
    },
]


# ============================================================================
# KNAPSACK PROBLEMS
# ============================================================================

KNAPSACK_CASES = [
    {
        "name": "Classic 0/1 Knapsack",
        "text": """I have a backpack that can carry 50kg. I have 5 items with weights and values:
        Item 1: weight=10kg, value=$60; Item 2: weight=20kg, value=$100; Item 3: weight=30kg, value=$120;
        Item 4: weight=15kg, value=$75; Item 5: weight=25kg, value=$90.
        Each item can be taken at most once. Maximize total value.""",
        "expected": "knapsack",
        "key_elements": ["items", "weights", "values", "capacity", "binary_choice", "objective"]
    },
    {
        "name": "Investment Selection",
        "text": """I have $1,000,000 to invest. Available projects: Project A costs $400k, returns $500k.
        Project B costs $300k, returns $450k. Project C costs $500k, returns $700k. Project D costs $200k, returns $250k.
        Can only invest in each project once (all or nothing). Maximize returns.""",
        "expected": "knapsack",
        "key_elements": ["projects", "costs", "returns", "budget", "binary_choice", "objective"]
    },
    {
        "name": "Bounded Knapsack",
        "text": """Warehouse has 1000kg capacity. Products: Widget (weight=5kg, value=$12, available=50 units),
        Gadget (weight=8kg, value=$20, available=30 units), Tool (weight=12kg, value=$35, available=20 units).
        Can take multiple copies of each item up to availability. Maximize value.""",
        "expected": "knapsack",
        "key_elements": ["items", "weights", "values", "availability_limits", "capacity", "objective"]
    },
    {
        "name": "Unbounded Knapsack",
        "text": """Truck with 5000kg capacity. Can load items: Box type A (100kg, $500), Box type B (150kg, $800),
        Box type C (200kg, $1000). Unlimited supply of each box type. How many of each to maximize value?""",
        "expected": "knapsack",
        "key_elements": ["items", "weights", "values", "capacity", "unlimited_copies", "objective"]
    },
    {
        "name": "Multi-constraint Knapsack",
        "text": """Container has weight limit 1000kg AND volume limit 50 cubic meters. Items:
        Item 1: 100kg, 5m³, $200; Item 2: 150kg, 8m³, $350; Item 3: 200kg, 10m³, $500; Item 4: 80kg, 4m³, $150.
        Select items (0/1 choice) to maximize value without exceeding either limit.""",
        "expected": "knapsack",
        "key_elements": ["items", "weights", "volumes", "weight_capacity", "volume_capacity", "values", "objective"]
    },
    {
        "name": "ADVERSARIAL: Knapsack vs Assignment",
        "text": """Choose which projects to fund with $500k budget. Project A: cost=$100k, benefit=5 points.
        Project B: cost=$200k, benefit=12 points. Project C: cost=$150k, benefit=8 points.
        Project D: cost=$250k, benefit=15 points. Each project: fund or don't fund (no pairing). Maximize benefit.""",
        "expected": "knapsack",
        "key_elements": ["projects", "costs", "benefits", "budget", "binary_choice", "objective"]
    },
]


# ============================================================================
# SCHEDULING PROBLEMS
# ============================================================================

SCHEDULING_CASES = [
    {
        "name": "Single-Stage: Batch Processing",
        "text": """Schedule 3 production orders (O1, O2, O3) on 2 processing units (U1, U2).
        Order O1: can use U1 (2 hours) or U2 (3 hours), due by hour 10
        Order O2: can only use U1 (1.5 hours), due by hour 8
        Order O3: can use U1 (2.5 hours) or U2 (2 hours), due by hour 12
        Changeover from O2 to O1 on U1 takes 0.4 hours.
        Minimize the makespan.""",
        "expected": "single_stage_scheduling",
        "category": "SCHEDULING",
        "solvable": True,
        "key_elements": ["orders", "units", "processing_times", "due_dates", "changeover", "objective"],
        "expected_solution": {
            "status": "OPTIMAL",
            "makespan_max": 4.0,  # Upper bound on makespan
            "all_on_time": True,
            "num_assignments": 3
        }
    },
    {
        "name": "Single-Stage: Chemical Reactors",
        "text": """Schedule 4 batches (B1, B2, B3, B4) on 3 reactors (R1, R2, R3).
        Batch B1: 3h on R1, 4h on R2, 3.5h on R3, due by hour 15
        Batch B2: 2h on R1, 2.5h on R2, due by hour 10 (not eligible for R3)
        Batch B3: 4h on R2, 3h on R3, due by hour 20 (not eligible for R1)
        Batch B4: 2.5h on any reactor, due by hour 12
        Minimize makespan.""",
        "expected": "single_stage_scheduling",
        "category": "SCHEDULING",
        "solvable": True,
        "key_elements": ["orders", "units", "processing_times", "eligibility", "due_dates", "objective"],
        "expected_solution": {
            "status": "OPTIMAL",
            "makespan_max": 10.0,
            "all_on_time": True,
            "num_assignments": 4
        }
    },
    {
        "name": "Job Shop Scheduling",
        "text": """Schedule 5 jobs on 3 machines. Each job has specific sequence of operations on specific machines.
        Job 1: M1(5min)→M2(3min)→M3(4min). Job 2: M2(4min)→M1(6min)→M3(2min). Job 3: M1(3min)→M3(5min).
        Job 4: M2(7min)→M3(3min). Job 5: M3(4min)→M1(2min)→M2(5min).
        Minimize total completion time (makespan).""",
        "expected": "job_shop",
        "category": "SCHEDULING",
        "solvable": False,
        "key_elements": ["jobs", "machines", "operations", "processing_times", "precedence", "objective"]
    },
    {
        "name": "Flow Shop Scheduling",
        "text": """All jobs follow same machine sequence: M1→M2→M3→M4. Different processing times:
        Job A: M1=5, M2=3, M3=7, M4=4. Job B: M1=4, M2=6, M3=5, M4=3. Job C: M1=6, M2=4, M3=8, M4=5.
        Determine job order to minimize makespan.""",
        "expected": "flow_shop",
        "category": "SCHEDULING",
        "solvable": False,
        "key_elements": ["jobs", "machines", "processing_times", "fixed_sequence", "objective"]
    },
    {
        "name": "Project Scheduling (PERT/CPM)",
        "text": """Project has 10 activities with precedence constraints. Activity A (duration=5 days) must
        finish before B (3 days) starts. Activity C (4 days) must finish before D (6 days) and E (2 days) start.
        Activities F, G, H have their own precedences. Some activities can run in parallel.
        Minimize project completion time.""",
        "expected": "project_scheduling",
        "category": "SCHEDULING",
        "solvable": False,
        "key_elements": ["activities", "durations", "precedence_constraints", "objective"]
    },
    {
        "name": "Machine Scheduling with Setups",
        "text": """Schedule 8 jobs on a single machine. Each job has processing time. Switching between
        job types requires setup time: Type A to Type B needs 30min setup. Job sequence matters.
        Minimize total time including setups.""",
        "expected": "single_stage_scheduling",  # Will likely misclassify, but this is the expectation
        "category": "SCHEDULING",
        "solvable": False,
        "key_elements": ["jobs", "processing_times", "setup_times", "sequence_dependent", "objective"]
    },
    {
        "name": "Employee Shift Scheduling",
        "text": """Create weekly schedule for 10 employees over 7 days. Each day needs minimum coverage:
        morning shift=3, afternoon=4, night=2. Each employee works max 5 days, needs 2 consecutive days off.
        Some employees prefer certain shifts. Minimize total cost considering shift premiums.""",
        "expected": "shift_rostering",
        "category": "SCHEDULING",
        "solvable": False,
        "key_elements": ["employees", "days", "shifts", "coverage_requirements", "constraints", "objective"]
    },
    {
        "name": "Resource-Constrained Scheduling",
        "text": """Schedule tasks with limited resources. Have 5 workers, 3 machines. Tasks have different
        durations and resource requirements. Task 1 needs 2 workers + 1 machine for 4 hours.
        Tasks have precedence constraints. Minimize project duration.""",
        "expected": "project_scheduling",  # Resource-constrained is a type of project scheduling
        "category": "SCHEDULING",
        "solvable": False,
        "key_elements": ["tasks", "resources", "durations", "resource_requirements", "precedence", "objective"]
    },
    {
        "name": "Shift Rostering with Weekend Balance",
        "text": """Create a two-week nurse roster. Each day has morning (4), afternoon (4), and night (3) coverage requirements.
        Every nurse must have at least 2 consecutive days off in each two-week block. No nurse should work more than 2 weekends
        (Sat-Sun) across the horizon. Minimize deviations from coverage while respecting rest rules.""",
        "expected": "shift_rostering",
        "category": "SCHEDULING",
        "solvable": False,
        "key_elements": ["nurses", "days", "shifts", "coverage_requirements", "weekend_balance", "rest_rules", "objective"]
    },
    {
        "name": "Shift Preferences with Penalties",
        "text": """Schedule 12 agents over 7 days with morning/late/night shifts. Each agent has preferred shifts and unavailable days.
        Coverage: morning=5, late=4, night=3 per day. Violating a preference incurs a penalty; understaffing incurs a higher penalty.
        Build a roster to minimize total penalty while meeting coverage as much as possible.""",
        "expected": "shift_rostering",
        "category": "SCHEDULING",
        "solvable": False,
        "key_elements": ["agents", "preferences", "unavailability", "coverage_requirements", "penalties", "objective"]
    },
    {
        "name": "Consecutive Nights and Minimum Rest",
        "text": """Seven-day schedule with morning/afternoon/night shifts. Constraint: no more than 2 consecutive night shifts
        for any employee, and at least 11 hours rest between shifts. Coverage must be met daily. Minimize premium costs for nights.""",
        "expected": "shift_rostering",
        "category": "SCHEDULING",
        "solvable": False,
        "key_elements": ["employees", "shifts", "consecutive_nights_limit", "minimum_rest", "coverage_requirements", "objective"]
    },
    {
        "name": "Single-Machine Weighted Tardiness",
        "text": """One machine, 10 jobs with processing times, due dates, and importance weights.
        Decide the processing order to minimize total weighted tardiness (sum w_j * T_j).""",
        "expected": "single_stage_scheduling",  # Will likely misclassify, but this is the expectation
        "category": "SCHEDULING",
        "solvable": False,
        "key_elements": ["single_machine", "jobs", "processing_times", "due_dates", "weights", "tardiness", "objective"]
    },
    {
        "name": "Parallel Machines with Eligibility",
        "text": """There are 3 identical parallel machines and 15 jobs. Some jobs can only run on specific machines due to tooling.
        Each job has a processing time and a due date. Assign jobs to machines and sequence them to minimize maximum lateness (L_max).""",
        "expected": "single_stage_scheduling",
        "category": "SCHEDULING",
        "solvable": False,  # Could potentially be solvable but needs sequencing logic
        "key_elements": ["parallel_machines", "eligibility", "processing_times", "due_dates", "sequencing", "objective"]
    },
    {
        "name": "Sequence-Dependent Setups on Two Machines",
        "text": """Two machines, 12 jobs, each job has processing times on each machine. Switching from job i to j incurs a setup time s_ij
        on the chosen machine. Determine sequences on both machines to minimize total completion time including setups.""",
        "expected": "job_shop",  # Sequence-dependent setups on multiple machines
        "category": "SCHEDULING",
        "solvable": False,
        "key_elements": ["machines", "jobs", "processing_times", "sequence_dependent_setups", "objective"]
    },
    {
        "name": "Release Dates and Deadlines",
        "text": """Single-machine scheduling with 9 jobs. Each job j has a release date r_j (cannot start before) and a firm deadline d_j.
        Minimize the number of late jobs while respecting release dates.""",
        "expected": "single_stage_scheduling",  # Will likely misclassify, but this is the expectation
        "category": "SCHEDULING",
        "solvable": False,
        "key_elements": ["single_machine", "jobs", "release_dates", "deadlines", "late_jobs", "objective"]
    },
    {
        "name": "Maintenance Downtime Window",
        "text": """One machine will be unavailable from 13:00 to 15:00 for maintenance. Schedule 8 jobs with processing times and due dates
        around this downtime to minimize total tardiness. No preemption allowed.""",
        "expected": "single_stage_scheduling",  # Will likely misclassify, but this is the expectation
        "category": "SCHEDULING",
        "solvable": False,
        "key_elements": ["single_machine", "downtime", "jobs", "processing_times", "due_dates", "no_preemption", "objective"]
    },
    {
        "name": "Rostering with Skill Levels",
        "text": """Call center staffing over 7 days with morning/evening/night shifts. Agents have skill levels 1-3; each shift
        requires at least 2 agents of level >=2 and one agent of level 3. Each agent works at most 5 days and needs 2 consecutive days off.
        Minimize understaffing penalties and overtime costs.""",
        "expected": "shift_rostering",
        "category": "SCHEDULING",
        "solvable": False,
        "key_elements": ["agents", "skills", "coverage_requirements", "overtime", "rest_rules", "objective"]
    },
    {
        "name": "ADVERSARIAL: Assignment-like Wording in Rostering",
        "text": """Assign each of 10 nurses to exactly one shift per day over a 7-day horizon. Coverage must meet morning/afternoon/night requirements.
        No nurse should work more than 5 total shifts and must have at least 2 consecutive days off. Minimize premium payments. (Note: although it says 'assign',
        this is a multi-day roster with coverage/rest rules, not a one-day assignment.)""",
        "expected": "shift_rostering",
        "category": "SCHEDULING",
        "solvable": False,
        "key_elements": ["nurses", "days", "shifts", "coverage_requirements", "rest_rules", "objective", "adversarial_wording"]
    },
]


# ============================================================================
# PRODUCTION PLANNING / LOT SIZING
# ============================================================================

PRODUCTION_PLANNING_CASES = [
    {
        "name": "Single Product Lot Sizing",
        "text": """Factory produces widgets over 4 months. Demand: Jan=100, Feb=150, Mar=120, Apr=180.
        Production capacity: 160 units/month. Production cost: $50/unit. Holding cost: $5/unit/month.
        Can build inventory to meet future demand. Minimize total cost.""",
        "expected": "lot_sizing",
        "key_elements": ["periods", "demands", "capacity", "production_cost", "holding_cost", "objective"]
    },
    {
        "name": "Multi-product Production",
        "text": """Produce Products A and B over 3 periods. Demands per period: Period 1 (A=50, B=30),
        Period 2 (A=70, B=40), Period 3 (A=60, B=50). Shared machine hours: 200 hours/period.
        A needs 2hrs/unit, B needs 3hrs/unit. Production costs: A=$40, B=$60. Holding: A=$3/period, B=$4/period.
        Minimize total cost.""",
        "expected": "lot_sizing",
        "key_elements": ["products", "periods", "demands", "capacity", "production_costs", "holding_costs", "objective"]
    },
    {
        "name": "Lot Sizing with Setup Costs",
        "text": """Plan production over 6 weeks. Each week: produce or not. If produce, pay $1000 setup cost
        plus $20/unit. Demand each week: 50, 80, 60, 90, 70, 100 units. Storage costs $3/unit/week.
        Minimize total cost (setup + production + inventory).""",
        "expected": "lot_sizing",
        "key_elements": ["periods", "demands", "setup_cost", "unit_cost", "holding_cost", "binary_setup", "objective"]
    },
    {
        "name": "Simple Resource Allocation",
        "text": """Workshop with 100 labor hours available. Product A takes 2 hours each, profit $15.
        Product B takes 5 hours each, profit $30. How many of each to maximize profit?""",
        "expected": "custom_review",
        "key_elements": ["products", "resource_limit", "resource_usage", "profits", "objective"]
    },
]


# ============================================================================
# FACILITY LOCATION
# ============================================================================

FACILITY_LOCATION_CASES = [
    {
        "name": "Facility Location Problem",
        "text": """Decide which of 5 potential warehouse locations to open. Each warehouse has fixed
        opening cost: W1=$1M, W2=$1.5M, W3=$0.8M, W4=$1.2M, W5=$0.9M. Each warehouse can serve
        different customer zones with different transportation costs. Must serve all customers.
        Binary decision for each warehouse: open or don't open. Minimize total cost (fixed + transportation).""",
        "expected": "facility_location",
        "key_elements": ["facilities", "fixed_costs", "customers", "transportation_costs", "binary_decisions", "objective"]
    },
    {
        "name": "P-Median Problem",
        "text": """Choose exactly 3 locations from 8 candidates to place distribution centers. Each location
        can serve customers with different distances. Minimize total weighted distance from customers to
        their nearest center.""",
        "expected": "facility_location",
        "key_elements": ["candidate_locations", "num_to_open", "customers", "distances", "objective"]
    },
]


# ============================================================================
# TRANSPORTATION (Baseline - already working)
# ============================================================================

TRANSPORTATION_CASES = [
    {
        "name": "Standard Transportation",
        "text": """Ship goods from 3 factories to 4 warehouses. Factory supplies: F1=100, F2=150, F3=120.
        Warehouse demands: W1=80, W2=90, W3=70, W4=130. Shipping costs vary by route (given as cost matrix).
        Minimize total shipping cost.""",
        "expected": "transportation",
        "key_elements": ["sources", "destinations", "supplies", "demands", "costs", "objective"]
    },
    {
        "name": "ADVERSARIAL: Transportation vs Assignment",
        "text": """Ship from 3 suppliers to 5 customers. Suppliers have different capacities (not just 0/1).
        Customers have different demands (continuous amounts, not just one unit). Each supplier can ship
        to MULTIPLE customers (not one-to-one). Continuous flow variables. Minimize total cost.""",
        "expected": "transportation",
        "key_elements": ["suppliers", "customers", "capacities", "demands", "costs", "continuous_flow", "objective"]
    },
]


# ============================================================================
# AGGREGATE ALL CASES
# ============================================================================

ALL_TEST_CASES = [
    ("ASSIGNMENT", ASSIGNMENT_CASES),
    ("NETWORK FLOW", NETWORK_FLOW_CASES),
    ("KNAPSACK", KNAPSACK_CASES),
    ("SCHEDULING", SCHEDULING_CASES),
    ("PRODUCTION PLANNING", PRODUCTION_PLANNING_CASES),
    ("FACILITY LOCATION", FACILITY_LOCATION_CASES),
    ("TRANSPORTATION", TRANSPORTATION_CASES),
]


def get_all_cases():
    """Return all test cases as a flat list"""
    cases = []
    for category, case_list in ALL_TEST_CASES:
        for case in case_list:
            case['category'] = category
            cases.append(case)
    return cases


def get_cases_by_category(category):
    """Get test cases for a specific category"""
    for cat, cases in ALL_TEST_CASES:
        if cat == category:
            return cases
    return []
