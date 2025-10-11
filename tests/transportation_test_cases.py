"""
A collection of transportation problem descriptions for testing extraction.
Each case is a dict with:
- name: short identifier
- text: problem description (free text)
- notes: optional hints about the scenario (unbalanced, integers, forbidden routes, etc.)
"""

TEST_CASES = [

    {
        "name": "balanced_greece_baseline",
        "text": """A company operates two production sites in Greece: Athens and Thessaloniki.
Athens can make up to 120 units per week, Thessaloniki can supply 200 pieces.
They deliver products to three customer areas: Patras, Larisa, and Heraklion.
Patras requires 100 units, Larisa needs 80, Heraklion has a demand of 110.
Transport costs (in € per unit) are:
From Athens to Patras: 5, From Athens to Larisa: 4, From Athens to Heraklion: 7
From Thessaloniki to Patras: 6, From Thessaloniki to Larisa: 3, From Thessaloniki to Heraklion: 8
The company wants to find the cheapest shipping plan.""",
        "notes": "Balanced supply (320) vs demand (290) -> slight surplus, feasible as unbalanced=false (must leave slack at plants)."
    },

    {
        "name": "balanced_uk_simple",
        "text": """There are two factories in the UK: Manchester and Birmingham.
Manchester can produce 150 units weekly, Birmingham up to 170.
Goods go to three retailers: London, Bristol, and Leeds.
London needs 140 units, Bristol 80, and Leeds demands 100.
Per-unit shipping cost (£) is as follows:
Manchester→London: 6, Manchester→Bristol: 5, Manchester→Leeds: 4
Birmingham→London: 5, Birmingham→Bristol: 6, Birmingham→Leeds: 3
Minimise the total transport cost.""",
        "notes": "Supply 320 vs demand 320; exactly balanced."
    },

    {
        "name": "unbalanced_supply_gt_demand_allow",
        "text": """A vendor ships from three warehouses: Porto, Vigo, and A Coruña.
Capacities: Porto 200, Vigo 120, A Coruña 90 (units per week).
Customers are Salamanca and Bilbao with demands 150 and 120 respectively.
The company allows unshipped surplus to remain at warehouses.
Costs (€/unit):
Porto→Salamanca: 4, Porto→Bilbao: 7
Vigo→Salamanca: 5, Vigo→Bilbao: 4
A Coruña→Salamanca: 6, A Coruña→Bilbao: 3
Find the minimum cost plan.""",
        "notes": "Supply 410 vs demand 270; allow_unbalanced should be true."
    },

    {
        "name": "unbalanced_demand_gt_supply",
        "text": """A food producer has plants in Naples and Bari with weekly capacities of 90 and 110 units.
It serves three supermarkets: Rome (120), Florence (80), and Pisa (50).
Shipping costs in € per unit:
Naples→Rome: 3, Naples→Florence: 6, Naples→Pisa: 7
Bari→Rome: 5, Bari→Florence: 2, Bari→Pisa: 4
The firm seeks the lowest shipping cost plan.""",
        "notes": "Supply 200 vs demand 250; extractor should still parse; solver later must handle infeasibility or require allow_unbalanced."
    },

    {
        "name": "integer_shipments_required",
        "text": """Two depots, Oslo and Bergen, supply electronics.
Oslo can ship 75 units per week, Bergen up to 130.
Customers: Trondheim needs 60, Stavanger needs 70, Kristiansand needs 50.
Per-unit shipping costs (NOK):
Oslo→Trondheim: 8, Oslo→Stavanger: 7, Oslo→Kristiansand: 6
Bergen→Trondheim: 5, Bergen→Stavanger: 4, Bergen→Kristiansand: 9
Shipments must be in whole units (no fractional shipments).
Minimise total shipping cost.""",
        "notes": "Should set integer_shipments=true."
    },

    {
        "name": "forbidden_route_constraint",
        "text": """Three plants: Antwerp (capacity 120), Ghent (90), and Liège (110).
Destinations: Bruges (80), Namur (100), Mons (70).
Costs (€/unit):
Antwerp→Bruges: 5, Antwerp→Namur: 6, Antwerp→Mons: 9
Ghent→Bruges: 3, Ghent→Namur: 7, Ghent→Mons: 5
Liège→Bruges: 8, Liège→Namur: 4, Liège→Mons: 6
Note: Shipments from Antwerp to Mons are not allowed due to a contract restriction.
Objective: minimise the total cost.""",
        "notes": "Expect a constraint such as 'Antwerp cannot serve Mons'."
    },

    {
        "name": "distance_based_costs",
        "text": """A firm ships from Lyon and Marseille to Nice and Grenoble.
Capacities: Lyon 140, Marseille 160. Demands: Nice 150, Grenoble 120.
Freight rate is €0.06 per unit per km. Distances (km):
Lyon→Nice: 470, Lyon→Grenoble: 113
Marseille→Nice: 200, Marseille→Grenoble: 318
Find the cheapest shipping plan.""",
        "notes": "Extractor should compute costs by rate × distance."
    },

    {
        "name": "synonyms_sources_sinks",
        "text": """The distributor operates 2 sources: Dublin and Cork (weekly limits: 100 and 140).
It must serve 3 destinations: Galway (60), Limerick (80), and Waterford (90).
Unit freight charges (EUR):
Dublin→Galway: 4, Dublin→Limerick: 7, Dublin→Waterford: 5
Cork→Galway: 6, Cork→Limerick: 3, Cork→Waterford: 4
Goal: cheapest dispatch plan.""",
        "notes": "Uses synonyms (sources/destinations) instead of plants/markets."
    },

    {
        "name": "zero_cost_promo_route",
        "text": """Two factories: Prague (capacity 130) and Brno (capacity 120).
Stores: Ostrava demand 110, Olomouc demand 90, Zlín demand 40.
Per unit cost (CZK):
Prague→Ostrava: 0, Prague→Olomouc: 6, Prague→Zlín: 5
Brno→Ostrava: 4, Brno→Olomouc: 2, Brno→Zlín: 3
A temporary promotion makes shipping from Prague to Ostrava free.
Minimise total cost.""",
        "notes": "Zero cost arc."
    },

    {
        "name": "zero_demand_market",
        "text": """Plants: Tallinn (capacity 80) and Tartu (capacity 120).
Markets: Pärnu requires 0 units this week, Narva requires 140, and Viljandi needs 40.
Costs (€/unit):
Tallinn→Pärnu: 5, Tallinn→Narva: 6, Tallinn→Viljandi: 4
Tartu→Pärnu: 3, Tartu→Narva: 4, Tartu→Viljandi: 5
Minimise cost.""",
        "notes": "Includes a zero-demand market."
    },

    {
        "name": "zero_capacity_plant",
        "text": """Warehouses: Kyoto (0 capacity this week due to maintenance) and Osaka (capacity 180).
Customers: Tokyo needs 110, Nagoya 60.
Shipping cost (¥ per unit):
Kyoto→Tokyo: 9, Kyoto→Nagoya: 7
Osaka→Tokyo: 5, Osaka→Nagoya: 4
Minimise overall shipping expenditure.""",
        "notes": "Includes a zero-capacity source."
    },

    {
        "name": "thousands_separators",
        "text": """Three factories: Miami (capacity 1,200), Tampa (capacity 800), and Orlando (capacity 1,000).
Stores: Jacksonville demand 900, Tallahassee 700, Pensacola 300.
Unit shipping costs (USD):
Miami→Jacksonville: 6, Miami→Tallahassee: 7, Miami→Pensacola: 5
Tampa→Jacksonville: 4, Tampa→Tallahassee: 6, Tampa→Pensacola: 3
Orlando→Jacksonville: 5, Orlando→Tallahassee: 4, Orlando→Pensacola: 6
Minimise the total logistics cost.""",
        "notes": "Numbers with thousands separators."
    },

    {
        "name": "mixed_units_text",
        "text": """Production sites: Zurich (capacity 90 units/day) and Basel (capacity 110 per day).
Customers: Bern (needs 70 a day), Lausanne (requires 60 daily), Geneva (demands 50 per day).
Per-unit transport cost (CHF):
Zurich→Bern: 4, Zurich→Lausanne: 7, Zurich→Geneva: 8
Basel→Bern: 6, Basel→Lausanne: 3, Basel→Geneva: 5
Compute the cheapest daily plan.""",
        "notes": "Same units but different phrases; extractor should normalise numbers."
    },

    {
        "name": "implicit_minimise_phrase",
        "text": """Plants: Valencia (capacity 160) and Alicante (capacity 130).
Destinations: Murcia needs 120, Albacete needs 80, Cartagena needs 70.
Costs (€/unit):
Valencia→Murcia: 3, Valencia→Albacete: 5, Valencia→Cartagena: 4
Alicante→Murcia: 6, Alicante→Albacete: 2, Alicante→Cartagena: 5
Choose the plan with the lowest overall shipping expense.""",
        "notes": "Objective phrased without the word 'minimise'."
    },

    {
        "name": "partial_costs_missing_should_error",
        "text": """Factories: Porto (capacity 100) and Lisbon (capacity 150).
Customers: Faro (demand 120) and Coimbra (demand 90).
Costs (€/unit):
Porto→Faro: 4
Lisbon→Faro: 5, Lisbon→Coimbra: 3
Find the cheapest plan.""",
        "notes": "Missing Porto→Coimbra cost; your extractor should flag an error."
    },

    {
        "name": "capacity_as_range",
        "text": """Two plants, Hamburg and Bremen. Hamburg can supply between 80 and 120 per week; take 120 as the maximum.
Bremen can provide up to 140. Customers: Kiel needs 90, Lübeck 70, Rostock 60.
Costs (€/unit):
Hamburg→Kiel: 4, Hamburg→Lübeck: 5, Hamburg→Rostock: 7
Bremen→Kiel: 3, Bremen→Lübeck: 6, Bremen→Rostock: 4
Find the least-cost shipping plan.""",
        "notes": "Range phrasing for capacity."
    },

    {
        "name": "with_exclusions_multiple",
        "text": """Suppliers: Delhi (cap 180) and Jaipur (cap 160).
Customers: Gurgaon (demand 150), Noida (demand 90), Faridabad (demand 80).
Shipping costs (₹/unit):
Delhi→Gurgaon: 2, Delhi→Noida: 7, Delhi→Faridabad: 5
Jaipur→Gurgaon: 6, Jaipur→Noida: 3, Jaipur→Faridabad: 4
Constraints: Do not ship from Delhi to Noida, and do not send more than 40 units from Jaipur to Gurgaon.
Minimise total freight spend.""",
        "notes": "Includes two constraints: a forbidden route and a capacity-on-arc hint."
    },

    {
        "name": "three_sources_three_sinks_balanced",
        "text": """Sources: Seattle (cap 350), Denver (cap 200), and Detroit (cap 150).
Sinks: Chicago (demand 250), New York (demand 180), and Atlanta (demand 270).
Costs (USD/unit):
Seattle→Chicago: 2, Seattle→New York: 4, Seattle→Atlanta: 5
Denver→Chicago: 3, Denver→New York: 6, Denver→Atlanta: 2
Detroit→Chicago: 5, Detroit→New York: 3, Detroit→Atlanta: 4
Minimise total shipping cost.""",
        "notes": "Classic 3×3 with balance."
    },

    {
        "name": "rate_per_1000_miles",
        "text": """A company ships from Dallas (cap 300) and Phoenix (cap 250) to San Jose (demand 280) and San Diego (demand 240).
Freight rate is $90 per unit per 1000 miles. Distances (miles):
Dallas→San Jose: 1460, Dallas→San Diego: 1250
Phoenix→San Jose: 720, Phoenix→San Diego: 355
Find the plan with the smallest total shipping cost.""",
        "notes": "Requires converting distances to cost using the given rate."
    },
]

def get_cases():
    """Return the list of test cases."""
    return TEST_CASES

if __name__ == "__main__":
    # Quick visual check
    for i, case in enumerate(TEST_CASES, start=1):
        print(f"{i:02d}. {case['name']} — {len(case['text'].split())} words")