import uuid
import random
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple
import numpy as np
from faker import Faker
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from synth_data_creator.db.bulk_ops import bulk_insert
from synth_data_creator.db.schema_init import initialize_schema
from synth_data_creator.generation.events import get_event_modifiers

# --- CONSTANTS & CONFIGS ---

STATES = [
    "HEALTHY",
    "GROWING",
    "EXPANDING",
    "OVERLEVERAGED",
    "STRESSED",
    "DISTRESSED",
    "RECOVERING",
    "DECLINING",
    "CHURN_RISK",
    "DORMANT",
]

STATE_TRANSITIONS = {
    "HEALTHY": {
        "HEALTHY": 0.9926,
        "GROWING": 0.0037,
        "EXPANDING": 0.0018,
        "OVERLEVERAGED": 0.0011,
        "STRESSED": 0.0008,
    },
    "GROWING": {"GROWING": 0.9926, "HEALTHY": 0.0037, "EXPANDING": 0.0018, "OVERLEVERAGED": 0.0019},
    "EXPANDING": {"EXPANDING": 0.9905, "GROWING": 0.0057, "OVERLEVERAGED": 0.0038},
    "OVERLEVERAGED": {
        "OVERLEVERAGED": 0.9831,
        "HEALTHY": 0.0042,
        "STRESSED": 0.0085,
        "DECLINING": 0.0042,
    },
    "STRESSED": {
        "STRESSED": 0.9772,
        "OVERLEVERAGED": 0.0068,
        "DISTRESSED": 0.0091,
        "DECLINING": 0.0046,
        "RECOVERING": 0.0023,
    },
    "DISTRESSED": {
        "DISTRESSED": 0.9737,
        "CHURN_RISK": 0.0120,
        "DECLINING": 0.0072,
        "RECOVERING": 0.0072,
    },
    "RECOVERING": {"RECOVERING": 0.9831, "HEALTHY": 0.0106, "STRESSED": 0.0042, "DORMANT": 0.0021},
    "DECLINING": {"DECLINING": 0.9831, "STRESSED": 0.0042, "CHURN_RISK": 0.0063, "DORMANT": 0.0063},
    "CHURN_RISK": {
        "CHURN_RISK": 0.9772,
        "DORMANT": 0.0137,
        "DISTRESSED": 0.0046,
        "RECOVERING": 0.0046,
    },
    "DORMANT": {"DORMANT": 0.9983, "RECOVERING": 0.0017},
}

STATE_ORDER_FREQ_MULTIPLIER = {
    "HEALTHY": 1.0,
    "GROWING": 0.7,  # Lower interval = more frequent orders
    "EXPANDING": 0.5,
    "OVERLEVERAGED": 1.2,
    "STRESSED": 1.5,
    "DISTRESSED": 2.0,
    "RECOVERING": 1.0,
    "DECLINING": 2.5,
    "CHURN_RISK": 4.0,
    "DORMANT": 999.0,  # Practically never
}

STATE_PAYMENT_DELAY_SHIFT = {
    "HEALTHY": (0.0, 2.0),
    "GROWING": (0.0, 2.0),
    "EXPANDING": (2.0, 3.0),
    "OVERLEVERAGED": (5.0, 3.0),
    "STRESSED": (10.0, 5.0),
    "DISTRESSED": (20.0, 10.0),
    "RECOVERING": (3.0, 3.0),
    "DECLINING": (12.0, 5.0),
    "CHURN_RISK": (20.0, 8.0),
    "DORMANT": (45.0, 15.0),
}


# --- PROCEDURAL ENTITY GENERATION ---


def generate_territories(num_territories: int, rng: np.random.Generator) -> List[Dict[str, Any]]:
    fake = Faker("en_IN")
    states = [
        "Maharashtra",
        "Karnataka",
        "Tamil Nadu",
        "Delhi",
        "Gujarat",
        "Uttar Pradesh",
        "West Bengal",
    ]
    territories = []
    for _ in range(num_territories):
        state = rng.choice(states)
        city = fake.city()
        district = city + " District"
        route = f"Route-{rng.choice(['A', 'B', 'C', 'D', 'E'])}-{rng.integers(101, 999)}"
        market_cluster = f"{city} {rng.choice(['Wholesale Market', 'Industrial Area', 'Commercial Hub', 'Retail Gali'])}"
        territories.append(
            {
                "id": uuid.uuid4(),
                "state": state,
                "district": district,
                "city": city,
                "route": route,
                "market_cluster": market_cluster,
            }
        )
    return territories


def generate_salespersons(
    num_salespersons: int, territories: List[Dict[str, Any]], rng: np.random.Generator
) -> List[Dict[str, Any]]:
    fake = Faker("en_IN")
    salespersons = []
    for _ in range(num_salespersons):
        terr = rng.choice(territories)
        salespersons.append(
            {
                "id": uuid.uuid4(),
                "name": fake.name(),
                "tenure_months": int(rng.integers(3, 48)),
                "effectiveness": float(round(rng.uniform(0.70, 1.30), 2)),
                "visit_frequency_days": int(rng.choice([7, 14, 30])),
                "territory_id": terr["id"],
            }
        )
    return salespersons


def generate_product_catalog(rng: np.random.Generator) -> List[Dict[str, Any]]:
    # 6 Categories
    catalog_source = {
        "Electronics": [
            {"name": "LED Panel 40W", "base_price": 850.00, "brand": "Syska"},
            {"name": "USB-C Cable 1m", "base_price": 120.00, "brand": "Mi"},
            {"name": "Power Adapter 65W", "base_price": 450.00, "brand": "Mi"},
            {"name": "Bluetooth Speaker", "base_price": 1200.00, "brand": "boAt"},
            {"name": "Smart Plug WiFi", "base_price": 680.00, "brand": "Wipro"},
        ],
        "FMCG": [
            {"name": "Detergent Powder 5kg", "base_price": 280.00, "brand": "Surf Excel"},
            {"name": "Cooking Oil 5L", "base_price": 520.00, "brand": "Fortune"},
            {"name": "Rice Basmati 25kg", "base_price": 1800.00, "brand": "India Gate"},
            {"name": "Sugar 50kg", "base_price": 2100.00, "brand": "Madhur"},
            {"name": "Tea Powder 1kg", "base_price": 350.00, "brand": "Red Label"},
        ],
        "Hardware": [
            {"name": "PVC Pipe 4inch 6ft", "base_price": 320.00, "brand": "Supreme"},
            {"name": "Cement 50kg", "base_price": 380.00, "brand": "Ultratech"},
            {"name": "Steel Rod 12mm", "base_price": 550.00, "brand": "Tata Tiscon"},
            {"name": "Paint Emulsion 20L", "base_price": 2800.00, "brand": "Asian Paints"},
            {"name": "Electrical Wire 90m", "base_price": 1500.00, "brand": "Finolex"},
        ],
        "Textiles": [
            {"name": "Cotton Fabric 100m", "base_price": 4500.00, "brand": "Raymond"},
            {"name": "Polyester Blend 50m", "base_price": 2200.00, "brand": "Siyaram"},
            {"name": "Denim Fabric 50m", "base_price": 3500.00, "brand": "Arvind"},
        ],
        "Pharmaceuticals": [
            {"name": "Paracetamol 500mg (100s)", "base_price": 45.00, "brand": "Cipla"},
            {"name": "Sanitizer 5L", "base_price": 350.00, "brand": "Dettol"},
            {"name": "Surgical Mask (50s)", "base_price": 180.00, "brand": "3M"},
        ],
        "Stationery": [
            {"name": "A4 Paper Ream 500", "base_price": 280.00, "brand": "JK Paper"},
            {"name": "Printer Ink Cartridge", "base_price": 650.00, "brand": "HP"},
            {"name": "Notebook 200pg (dozen)", "base_price": 480.00, "brand": "Classmate"},
        ],
    }
    products = []
    for category, items in catalog_source.items():
        for item in items:
            margin = rng.uniform(0.08, 0.25)
            products.append(
                {
                    "id": uuid.uuid4(),
                    "name": item["name"],
                    "category": category,
                    "brand": item["brand"],
                    "base_price": float(item["base_price"]),
                    "unit": "pack" if category in ("FMCG", "Stationery") else "piece",
                    "margin_profile": {
                        "cost_price": float(round(item["base_price"] * (1 - margin), 2)),
                        "margin_pct": float(round(margin * 100, 2)),
                        "tax_rate": 18.0 if category != "Pharmaceuticals" else 12.0,
                    },
                }
            )
    return products


# --- SIMULATION STATE ENGINE ---


class CustomerSimNode:
    def __init__(
        self,
        id_val: uuid.UUID,
        code: str,
        name: str,
        reg_date: date,
        b_type: str,
        territory: Dict[str, Any],
        salesperson: Dict[str, Any] | None,
        rng: np.random.Generator,
    ):
        self.id = id_val
        self.customer_code = code
        self.business_name = name
        self.registration_date = reg_date
        self.business_type = b_type
        self.territory = territory
        self.salesperson = salesperson
        self.rng = rng

        # Derived parameters
        self.credit_limit = self.derive_credit_limit()
        self.payment_terms_days = 30
        self.outstanding_balance = 0.0

        # Archetype assignment (Phase B: Behavioral Realism)
        if self.business_type in ("manufacturer", "distributor") or (
            self.business_type == "wholesaler" and self.credit_limit > 500_000.0
        ):
            self.archetype = "WHALE"
        else:
            self.archetype = rng.choice(
                ["STABLE_RETAILER", "GROWING_RETAILER", "LIQUIDITY_STRESSED", "DECLINING_RETAILER"],
                p=[0.50, 0.20, 0.15, 0.15],
            )

        # State initialization based on archetype
        if self.archetype == "STABLE_RETAILER":
            self.hidden_state = "HEALTHY"
        elif self.archetype == "GROWING_RETAILER":
            self.hidden_state = rng.choice(["GROWING", "EXPANDING"])
        elif self.archetype == "LIQUIDITY_STRESSED":
            self.hidden_state = rng.choice(["OVERLEVERAGED", "STRESSED"])
        elif self.archetype == "DECLINING_RETAILER":
            self.hidden_state = rng.choice(["DECLINING", "CHURN_RISK"])
        else:  # WHALE
            self.hidden_state = rng.choice(
                [
                    "HEALTHY",
                    "GROWING",
                    "EXPANDING",
                    "OVERLEVERAGED",
                    "STRESSED",
                    "DISTRESSED",
                    "DECLINING",
                ],
                p=[0.40, 0.25, 0.15, 0.10, 0.05, 0.03, 0.02],
            )

        # Behavioral attributes/factors
        self.growth_factor = 1.0
        self.decline_factor = 1.0
        self.stress_delay_accumulation = 0.0

        # Hidden variables (Phase D)
        self.liquidity = (
            int(rng.integers(70, 100))
            if self.hidden_state in ("HEALTHY", "GROWING", "EXPANDING")
            else int(rng.integers(20, 69))
        )
        self.growth_potential = (
            int(rng.integers(50, 95))
            if self.hidden_state in ("GROWING", "EXPANDING")
            else int(rng.integers(10, 49))
        )
        self.operational_stability = int(rng.integers(60, 95))
        self.payment_reliability = self.liquidity
        self.churn_probability = 0.05 if self.hidden_state != "CHURN_RISK" else 0.75
        self.creditworthiness = int(
            (self.liquidity + self.operational_stability + (100 - self.churn_probability * 100)) / 3
        )

        # Recalculate terms now that state is set
        self.payment_terms_days = self.derive_payment_terms()

        # Order pacing
        self.last_order_date = reg_date
        self.order_frequency_days = self.derive_base_order_frequency()

    def derive_credit_limit(self) -> float:
        if self.business_type == "manufacturer":
            return float(round(self.rng.uniform(1_000_000.0, 5_000_000.0), 2))
        elif self.business_type == "distributor":
            return float(round(self.rng.uniform(500_000.0, 2_000_000.0), 2))
        elif self.business_type == "wholesaler":
            return float(round(self.rng.uniform(200_000.0, 1_000_000.0), 2))
        else:  # retailer
            return float(round(self.rng.uniform(25_000.0, 300_000.0), 2))

    def derive_payment_terms(self) -> int:
        if self.hidden_state in ("HEALTHY", "GROWING"):
            return int(self.rng.choice([15, 20, 25]))
        elif self.hidden_state in ("EXPANDING"):
            return int(self.rng.choice([25, 30, 40]))
        else:  # risk states get shorter terms
            return int(self.rng.choice([10, 15]))

    def derive_base_order_frequency(self) -> float:
        freqs = {"manufacturer": 10.0, "distributor": 5.0, "wholesaler": 7.0, "retailer": 15.0}
        base = freqs[self.business_type]
        if getattr(self, "archetype", "") == "STABLE_RETAILER":
            return float(self.rng.uniform(7.0, 15.0))
        return float(self.rng.uniform(base * 0.7, base * 1.3))

    def update_state_and_variables(self, curr_date: date, active_shocks: List[Any]) -> None:
        """Transitions state & shifts variables chronologically."""
        if curr_date < self.registration_date:
            return

        # Monthly feedback loops (evaluated on the 1st of each month)
        if curr_date.day == 1:
            if self.hidden_state in ("GROWING", "EXPANDING"):
                self.credit_limit = float(round(self.credit_limit * 1.03, 2))
                if getattr(self, "archetype", "") == "GROWING_RETAILER":
                    self.growth_factor = min(3.0, self.growth_factor * 1.04)
            elif self.hidden_state in ("STRESSED", "DISTRESSED", "DECLINING"):
                self.credit_limit = float(round(max(10000.0, self.credit_limit * 0.95), 2))
                if getattr(self, "archetype", "") == "DECLINING_RETAILER":
                    self.decline_factor = max(0.1, self.decline_factor * 0.96)
                if getattr(self, "archetype", "") == "LIQUIDITY_STRESSED":
                    self.stress_delay_accumulation = min(40.0, self.stress_delay_accumulation + 1.5)

        # Drift towards target state-specific baselines
        state_baselines = {
            "HEALTHY": {"liquidity": 85, "growth": 65, "stability": 80},
            "GROWING": {"liquidity": 80, "growth": 85, "stability": 80},
            "EXPANDING": {"liquidity": 75, "growth": 90, "stability": 75},
            "OVERLEVERAGED": {"liquidity": 50, "growth": 55, "stability": 65},
            "STRESSED": {"liquidity": 35, "growth": 30, "stability": 50},
            "DISTRESSED": {"liquidity": 15, "growth": 10, "stability": 30},
            "RECOVERING": {"liquidity": 60, "growth": 50, "stability": 60},
            "DECLINING": {"liquidity": 40, "growth": 15, "stability": 45},
            "CHURN_RISK": {"liquidity": 20, "growth": 10, "stability": 30},
            "DORMANT": {"liquidity": 5, "growth": 5, "stability": 10},
        }
        targets = state_baselines.get(
            self.hidden_state, {"liquidity": 70, "growth": 50, "stability": 70}
        )
        self.liquidity = int(
            round(0.98 * self.liquidity + 0.02 * targets["liquidity"] + self.rng.integers(-1, 2))
        )
        self.growth_potential = int(
            round(
                0.98 * self.growth_potential + 0.02 * targets["growth"] + self.rng.integers(-1, 2)
            )
        )
        self.operational_stability = int(
            round(
                0.98 * self.operational_stability
                + 0.02 * targets["stability"]
                + self.rng.integers(-1, 2)
            )
        )

        # 1. Update Hidden Variables based on current state & shocks
        shock_mult = 1.0
        for shock in active_shocks:
            # Shocks degrade stability & liquidity
            self.liquidity = max(0, self.liquidity - int(self.rng.integers(1, 8)))
            self.operational_stability = max(
                0, self.operational_stability - int(self.rng.integers(1, 6))
            )
            self.growth_potential = max(0, self.growth_potential - int(self.rng.integers(1, 5)))
            shock_mult *= shock.delay_mult

        # Credit utilization stress
        credit_util_pct = (
            (self.outstanding_balance / self.credit_limit) if self.credit_limit > 0 else 0.0
        )
        if credit_util_pct > 0.85:
            self.liquidity = max(0, self.liquidity - int(self.rng.integers(1, 5)))
            self.growth_potential = max(0, self.growth_potential - int(self.rng.integers(0, 3)))

        # Clip variables
        self.liquidity = max(0, min(100, self.liquidity))
        self.growth_potential = max(0, min(100, self.growth_potential))
        self.operational_stability = max(0, min(100, self.operational_stability))

        # Update probabilities
        self.payment_reliability = max(0, min(100, self.liquidity + int(self.rng.integers(-2, 3))))

        if self.hidden_state == "CHURN_RISK":
            self.churn_probability = min(0.99, self.churn_probability + 0.02)
        elif self.hidden_state in ("DORMANT"):
            self.churn_probability = 0.99
        else:
            self.churn_probability = max(
                0.01,
                min(
                    0.95,
                    0.20 * (100 - self.growth_potential) / 100
                    + 0.10 * (100 - self.liquidity) / 100,
                ),
            )

        self.creditworthiness = int(
            (
                self.payment_reliability
                + self.operational_stability
                + int((1 - self.churn_probability) * 100)
            )
            / 3
        )

        # 2. Probability of State Transition (Markov Transitions)
        trans_weights = STATE_TRANSITIONS.get(self.hidden_state, {self.hidden_state: 1.0})
        states_pool = list(trans_weights.keys())
        weights = list(trans_weights.values())

        # Dynamic weights modification
        if credit_util_pct > 0.85 and "OVERLEVERAGED" in states_pool:
            idx = states_pool.index("OVERLEVERAGED")
            weights[idx] *= 2.0
        if shock_mult > 1.2 and "STRESSED" in states_pool:
            idx = states_pool.index("STRESSED")
            weights[idx] *= 1.8
        if shock_mult > 1.5 and "DISTRESSED" in states_pool:
            idx = states_pool.index("DISTRESSED")
            weights[idx] *= 2.5
        if self.liquidity < 30 and "DISTRESSED" in states_pool:
            idx = states_pool.index("DISTRESSED")
            weights[idx] *= 2.0

        # Normalize weights
        w_sum = sum(weights)
        weights = [w / w_sum for w in weights]

        self.hidden_state = self.rng.choice(states_pool, p=weights)

        # Recalculate credit limits/terms if major change
        self.payment_terms_days = self.derive_payment_terms()


# --- THE MAIN CHRONOLOGICAL SIMULATOR ---


async def simulate_ecosystem(
    engine: AsyncEngine,
    num_customers: int,
    start_date: date,
    end_date: date,
    seed: int,
    target_sales: int,
    target_payments: int,
    target_rgs: int,
    batch_size: int,
) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    fake = Faker("en_IN")
    fake.seed_instance(seed)

    print("Step 1: Generating Territories, Products & Salespersons...", flush=True)
    # Generate static entity databases
    territories = generate_territories(max(5, int(num_customers / 20)), rng)
    salespersons = generate_salespersons(max(3, int(num_customers / 10)), territories, rng)
    products = generate_product_catalog(rng)

    # Products by category for selection speed
    products_by_category: Dict[str, List[Dict[str, Any]]] = {}
    for p in products:
        products_by_category.setdefault(p["category"], []).append(p)

    # 6 Categories weights per business type
    biz_category_weights = {
        "retailer": {
            "FMCG": 0.50,
            "Stationery": 0.20,
            "Electronics": 0.10,
            "Textiles": 0.10,
            "Hardware": 0.10,
            "Pharmaceuticals": 0.00,
        },
        "wholesaler": {
            "Hardware": 0.30,
            "Textiles": 0.30,
            "Electronics": 0.20,
            "FMCG": 0.20,
            "Stationery": 0.00,
            "Pharmaceuticals": 0.00,
        },
        "distributor": {
            "Pharmaceuticals": 0.40,
            "FMCG": 0.30,
            "Electronics": 0.20,
            "Stationery": 0.10,
            "Hardware": 0.00,
            "Textiles": 0.00,
        },
        "manufacturer": {
            "Hardware": 0.60,
            "Electronics": 0.20,
            "Textiles": 0.20,
            "FMCG": 0.00,
            "Stationery": 0.00,
            "Pharmaceuticals": 0.00,
        },
    }

    print("Step 2: Initializing Base Customers...", flush=True)
    customer_nodes: List[CustomerSimNode] = []
    business_types = ["retailer", "distributor", "manufacturer", "wholesaler"]
    biz_p = [0.40, 0.25, 0.20, 0.15]

    for idx in range(1, num_customers + 1):
        id_val = uuid.uuid4()
        code = f"CUST-{idx:05d}"
        name = fake.company()
        b_type = rng.choice(business_types, p=biz_p)

        # Registration date spread across the timeline
        total_days = (end_date - start_date).days
        reg_days_offset = int(rng.integers(0, int(total_days * 0.8)))
        reg_date = start_date + timedelta(days=reg_days_offset)

        # Assign territory & salesperson
        terr = rng.choice(territories)
        applicable_salespersons = [s for s in salespersons if s["territory_id"] == terr["id"]]
        sp = rng.choice(applicable_salespersons) if applicable_salespersons else None

        node = CustomerSimNode(id_val, code, name, reg_date, b_type, terr, sp, rng)
        customer_nodes.append(node)

    # Relationships (Phase H)
    print("Step 3: Simulating Network Relationship Graph...", flush=True)
    relationships = []
    
    # Pre-group customers by city for O(N) lookup instead of O(N^2)
    customers_by_city = {}
    for node in customer_nodes:
        customers_by_city.setdefault(node.territory["city"], []).append(node)

    for node in customer_nodes:
        # Geographic or cluster related linkages
        same_city_nodes = [
            n
            for n in customers_by_city.get(node.territory["city"], [])
            if n.id != node.id
        ]
        if same_city_nodes and rng.random() < 0.15:
            related = rng.choice(same_city_nodes)
            rel_type = rng.choice(["shared_ownership", "competitor", "distributor_cluster"])
            relationships.append(
                {
                    "id": uuid.uuid4(),
                    "customer_id": node.id,
                    "related_customer_id": related.id,
                    "relationship_type": rel_type,
                }
            )

    # Collections
    events_log = []
    sales_records = []
    payment_records = []
    return_records = []
    benchmarks = []

    # State tracking variables
    invoice_tracker = 100000
    payment_seq = 100000
    return_seq = 100000
    cn_seq = 100000

    # Index customer nodes by ID for O(1) daily lookup
    customer_by_id = {node.id: node for node in customer_nodes}

    # Open invoices tracking for payments: customer_id -> list of open invoices dicts
    open_invoices: Dict[uuid.UUID, List[Dict[str, Any]]] = {}

    # Scheduled actions collections (Phase B/C)
    scheduled_payments = {}
    scheduled_returns = {}

    print(f"Step 4: Running Chronological Loop from {start_date} to {end_date}...", flush=True)

    # Pre-register customers created events
    for n in customer_nodes:
        dt_created = datetime.combine(n.registration_date, datetime.min.time())
        events_log.append(
            {
                "id": uuid.uuid4(),
                "event_type": "customer_created",
                "customer_id": n.id,
                "timestamp": dt_created,
                "metadata_json": {
                    "business_name": n.business_name,
                    "business_type": n.business_type,
                    "city": n.territory["city"],
                    "credit_limit": n.credit_limit,
                },
                "source_state": n.hidden_state,
            }
        )
        # Record initial salesperson assignment
        if n.salesperson:
            events_log.append(
                {
                    "id": uuid.uuid4(),
                    "event_type": "salesperson_assigned",
                    "customer_id": n.id,
                    "timestamp": dt_created + timedelta(hours=1),
                    "metadata_json": {"salesperson_name": n.salesperson["name"]},
                    "source_state": n.hidden_state,
                }
            )

    # Daily simulation loop
    total_sim_days = (end_date - start_date).days
    
    # Sort customers by registration date to track active customers chronologically and avoid scanning all customers daily
    customer_nodes_sorted = sorted(customer_nodes, key=lambda n: n.registration_date)
    active_customers: List[CustomerSimNode] = []
    cust_idx = 0

    for day_idx in range(total_sim_days + 1):
        sim_date = start_date + timedelta(days=day_idx)
        dt_sim = datetime.combine(sim_date, datetime.min.time())

        # Add newly registered customers
        while cust_idx < len(customer_nodes_sorted) and customer_nodes_sorted[cust_idx].registration_date <= sim_date:
            active_customers.append(customer_nodes_sorted[cust_idx])
            cust_idx += 1

        # Identify active events/shocks (Phase G)
        from synth_data_creator.generation.events import get_active_events

        active_events = get_active_events(sim_date)
        mods = get_event_modifiers(sim_date, "retailer")  # baseline

        # A. Process scheduled payments on sim_date
        todays_payments = scheduled_payments.get(sim_date, [])
        for p in todays_payments:
            node = customer_by_id.get(p["customer_id"])
            if not node:
                continue

            # Check payment failure (Phase D / distressed node 10% chance)
            if node.hidden_state == "DISTRESSED" and rng.random() < 0.10:
                events_log.append(
                    {
                        "id": uuid.uuid4(),
                        "event_type": "payment_failed",
                        "customer_id": node.id,
                        "timestamp": dt_sim + timedelta(hours=14),
                        "metadata_json": {
                            "invoice_number": p["invoice_ref"]["invoice_number"],
                            "reason": "Insufficient Funds",
                        },
                        "source_state": node.hidden_state,
                    }
                )
                continue

            pay_amt = min(p["payment_amount"], p["invoice_ref"]["balance_due"])
            if pay_amt <= 0.01:
                continue

            pay_num = f"PAY-{sim_date.year}-{payment_seq}"
            payment_seq += 1
            p_mode = (
                rng.choice(["upi", "neft", "rtgs", "bank_transfer"])
                if pay_amt > 10000
                else rng.choice(["upi", "cash"])
            )

            pay_rec = {
                "id": uuid.uuid4(),
                "customer_id": node.id,
                "invoice_id": p["invoice_id"],
                "payment_number": pay_num,
                "payment_date": sim_date,
                "payment_amount": pay_amt,
                "payment_mode": p_mode,
                "reference_number": f"TXN{int(rng.integers(10000000, 99999999))}",
                "remarks": f"Invoice Payment for {p['invoice_ref']['invoice_number']}",
            }
            payment_records.append(pay_rec)

            # Update invoice balance details
            p["invoice_ref"]["amount_paid"] = float(
                round(p["invoice_ref"]["amount_paid"] + pay_amt, 2)
            )
            p["invoice_ref"]["balance_due"] = float(
                round(p["invoice_ref"]["invoice_amount"] - p["invoice_ref"]["amount_paid"], 2)
            )
            node.outstanding_balance = max(0.0, node.outstanding_balance - pay_amt)

            event_type = (
                "payment_received" if p["invoice_ref"]["balance_due"] <= 0.01 else "payment_partial"
            )
            events_log.append(
                {
                    "id": uuid.uuid4(),
                    "event_type": event_type,
                    "customer_id": node.id,
                    "timestamp": dt_sim + timedelta(hours=14, minutes=30),
                    "metadata_json": {
                        "invoice_number": p["invoice_ref"]["invoice_number"],
                        "payment_amount": pay_amt,
                        "balance_due": p["invoice_ref"]["balance_due"],
                    },
                    "source_state": node.hidden_state,
                }
            )

            if p["invoice_ref"]["balance_due"] <= 0.01:
                p["invoice_ref"]["payment_status"] = "paid"
                # Remove from open invoices
                cust_opens = open_invoices.get(node.id, [])
                if p["invoice_ref"] in cust_opens:
                    cust_opens.remove(p["invoice_ref"])
            else:
                p["invoice_ref"]["payment_status"] = "partial"

        # B. Process scheduled returns on sim_date
        todays_returns = scheduled_returns.get(sim_date, [])
        for r in todays_returns:
            node = customer_by_id.get(r["customer_id"])
            if not node:
                continue

            ret_val = r["return_value"]
            if ret_val <= 0.01:
                continue

            ret_num = f"RET-{sim_date.year}-{return_seq}"
            cn_num = f"CN-{sim_date.year}-{cn_seq}"
            return_seq += 1
            cn_seq += 1

            ret_rec = {
                "id": uuid.uuid4(),
                "customer_id": node.id,
                "sale_id": r["sale_id"],
                "return_number": ret_num,
                "return_date": sim_date,
                "return_reason": r["return_reason"],
                "quantity_returned": r["quantity_returned"],
                "return_value": ret_val,
                "credit_note_number": cn_num,
                "credit_note_amount": ret_val,
                "status": "credited",
                "remarks": f"Returned {r['quantity_returned']} items for {r['invoice_ref']['invoice_number']}",
            }
            return_records.append(ret_rec)

            events_log.append(
                {
                    "id": uuid.uuid4(),
                    "event_type": "return_created",
                    "customer_id": node.id,
                    "timestamp": dt_sim + timedelta(hours=16),
                    "metadata_json": {
                        "invoice_number": r["invoice_ref"]["invoice_number"],
                        "return_value": ret_val,
                        "reason": r["return_reason"],
                    },
                    "source_state": node.hidden_state,
                }
            )

            events_log.append(
                {
                    "id": uuid.uuid4(),
                    "event_type": "credit_note_issued",
                    "customer_id": node.id,
                    "timestamp": dt_sim + timedelta(hours=16, minutes=30),
                    "metadata_json": {"credit_note_number": cn_num, "amount": ret_val},
                    "source_state": node.hidden_state,
                }
            )

            # Reconcile outstanding & invoice balance
            r["invoice_ref"]["balance_due"] = float(
                round(max(0.0, r["invoice_ref"]["balance_due"] - ret_val), 2)
            )
            r["invoice_ref"]["amount_paid"] = float(
                round(r["invoice_ref"]["invoice_amount"] - r["invoice_ref"]["balance_due"], 2)
            )
            node.outstanding_balance = max(0.0, node.outstanding_balance - ret_val)

            if r["invoice_ref"]["balance_due"] <= 0.01:
                r["invoice_ref"]["payment_status"] = "paid"
                cust_opens = open_invoices.get(node.id, [])
                if r["invoice_ref"] in cust_opens:
                    cust_opens.remove(r["invoice_ref"])
            else:
                r["invoice_ref"]["payment_status"] = "partial"

        # C. Process core B2B updates, orders, and schedule futures
        for node in active_customers:

            # Update Hidden states
            node.update_state_and_variables(sim_date, active_events)

            # Save benchmarks
            if day_idx % 30 == 0 or sim_date == end_date:
                risk_band = (
                    "LOW"
                    if node.creditworthiness > 70
                    else ("HIGH" if node.creditworthiness < 40 else "MEDIUM")
                )
                health_band = (
                    "HIGH" if node.liquidity > 75 else ("LOW" if node.liquidity < 35 else "MEDIUM")
                )
                growth_band = (
                    "EXPANDING"
                    if node.hidden_state == "EXPANDING"
                    else (
                        "GROWING"
                        if node.hidden_state == "GROWING"
                        else ("DECLINING" if node.hidden_state == "DECLINING" else "STABLE")
                    )
                )
                benchmarks.append(
                    {
                        "id": uuid.uuid4(),
                        "customer_id": node.id,
                        "hidden_state": node.hidden_state,
                        "snapshot_date": sim_date,
                        "expected_risk_band": risk_band,
                        "expected_health_band": health_band,
                        "expected_growth_band": growth_band,
                        "expected_churn_probability": float(round(node.churn_probability, 4)),
                    }
                )

            # Check Salesperson visit
            visit_occurred = False
            if node.salesperson and (day_idx % node.salesperson["visit_frequency_days"] == 0):
                visit_occurred = True
                events_log.append(
                    {
                        "id": uuid.uuid4(),
                        "event_type": "salesperson_visit",
                        "customer_id": node.id,
                        "timestamp": dt_sim + timedelta(hours=9),
                        "metadata_json": {"salesperson_name": node.salesperson["name"]},
                        "source_state": node.hidden_state,
                    }
                )

            # Order trigger probability
            freq_factor = 1.0
            if getattr(node, "archetype", "") == "DECLINING_RETAILER":
                dec = getattr(node, "decline_factor", 1.0)
                freq_factor = 1.0 / max(0.1, dec)
            elif getattr(node, "archetype", "") == "LIQUIDITY_STRESSED":
                freq_factor = 1.2

            node_freq_days = (
                node.order_frequency_days
                * STATE_ORDER_FREQ_MULTIPLIER.get(node.hidden_state, 1.0)
                * mods["frequency_mult"]
                * freq_factor
            )
            days_since_order = (sim_date - node.last_order_date).days
            order_p = 1.0 / max(1.0, node_freq_days)
            if visit_occurred and node.salesperson:
                order_p = min(0.99, order_p * node.salesperson["effectiveness"])

            if (
                rng.random() < order_p or days_since_order > (node_freq_days * 2)
            ) and node.hidden_state != "DORMANT":
                node.last_order_date = sim_date

                # Check credit limit utilization (Phase D/6)
                if node.outstanding_balance > node.credit_limit:
                    events_log.append(
                        {
                            "id": uuid.uuid4(),
                            "event_type": "order_cancelled",
                            "customer_id": node.id,
                            "timestamp": dt_sim + timedelta(hours=10),
                            "metadata_json": {
                                "reason": "Credit Limit Exceeded",
                                "outstanding": node.outstanding_balance,
                                "limit": node.credit_limit,
                            },
                            "source_state": node.hidden_state,
                        }
                    )

                    # Force payment to clear credit (Phase D/6 / Layer 6)
                    cust_opens = open_invoices.get(node.id, [])
                    if cust_opens:
                        target_inv = cust_opens[0]
                        # Pull forward payment to today
                        scheduled_payments.setdefault(sim_date, []).append(
                            {
                                "customer_id": node.id,
                                "invoice_id": target_inv["id"],
                                "payment_date": sim_date,
                                "payment_amount": target_inv["balance_due"],
                                "invoice_ref": target_inv,
                            }
                        )
                    continue

                # Generate invoice items
                order_items_count = int(rng.poisson(3)) + 1
                items_recs = []
                invoice_number = f"INV-{sim_date.year}-{invoice_tracker}"
                invoice_tracker += 1

                # Pick product categories
                cat_weights = biz_category_weights.get(node.business_type, {"FMCG": 1.0})
                cats = list(cat_weights.keys())
                probs = list(cat_weights.values())
                probs = [p / sum(probs) for p in probs]

                inv_total_amount = 0.0
                inv_total_tax = 0.0

                events_log.append(
                    {
                        "id": uuid.uuid4(),
                        "event_type": "order_placed",
                        "customer_id": node.id,
                        "timestamp": dt_sim + timedelta(hours=10, minutes=15),
                        "metadata_json": {"invoice_number": invoice_number},
                        "source_state": node.hidden_state,
                    }
                )

                for _ in range(order_items_count):
                    selected_cat = rng.choice(cats, p=probs)
                    cat_prods = products_by_category.get(selected_cat, products)
                    p_info = rng.choice(cat_prods)

                    # Quantity depends on size & state
                    if node.business_type == "manufacturer":
                        qty = int(rng.integers(300, 4000))
                    elif node.business_type == "distributor":
                        qty = int(rng.integers(100, 1000))
                    else:  # retailer/wholesaler
                        qty = int(rng.integers(5, 100))

                    factor = 1.0
                    if getattr(node, "archetype", "") == "GROWING_RETAILER":
                        factor = getattr(node, "growth_factor", 1.0)
                    elif getattr(node, "archetype", "") == "DECLINING_RETAILER":
                        factor = getattr(node, "decline_factor", 1.0)

                    qty = max(1, int(qty * mods["quantity_mult"] * factor))
                    unit_price = float(p_info["base_price"])

                    # State-based price negotiation / discount
                    disc_pct = 0.0
                    if node.hidden_state in ("EXPANDING", "GROWING"):
                        disc_pct = float(round(rng.uniform(2.0, 10.0), 2))
                    disc_pct = min(100.0, max(0.0, disc_pct + mods["discount_add"]))

                    gross = qty * unit_price
                    disc_amt = gross * (disc_pct / 100.0)
                    taxable = gross - disc_amt

                    # Taxes
                    tax_rate = p_info["margin_profile"]["tax_rate"]
                    tax_val = taxable * (tax_rate / 100.0)

                    inv_total_amount += taxable + tax_val
                    inv_total_tax += tax_val

                    items_recs.append(
                        {
                            "category": selected_cat,
                            "name": p_info["name"],
                            "qty": qty,
                            "price": unit_price,
                            "discount_pct": disc_pct,
                            "discount_amount": disc_amt,
                            "taxable": taxable,
                            "tax_rate": tax_rate,
                        }
                    )

                # Reconcile taxes split (Intra-state CGST+SGST vs Inter-state IGST)
                cgst = sgst = igst = 0.0
                if node.territory["state"] == "Maharashtra":  # Assume base warehouse is in MH
                    cgst = sgst = round(inv_total_tax / 2.0, 2)
                else:
                    igst = round(inv_total_tax, 2)

                due_date = sim_date + timedelta(days=node.payment_terms_days)
                sale_id = uuid.uuid4()

                # Single invoice record matching model
                sale_dict = {
                    "id": sale_id,
                    "customer_id": node.id,
                    "invoice_number": invoice_number,
                    "order_date": sim_date,
                    "invoice_date": sim_date,
                    "due_date": due_date,
                    "product_category": items_recs[0]["category"],
                    "product_name": items_recs[0]["name"]
                    if len(items_recs) == 1
                    else f"{items_recs[0]['name']} & {len(items_recs) - 1} others",
                    "quantity": sum(i["qty"] for i in items_recs),
                    "unit_price": items_recs[0]["price"],
                    "gross_amount": float(round(sum(i["taxable"] for i in items_recs), 2)),
                    "discount_pct": float(round(items_recs[0]["discount_pct"], 2)),
                    "discount_amount": float(
                        round(sum(i["discount_amount"] for i in items_recs), 2)
                    ),
                    "taxable_amount": float(round(sum(i["taxable"] for i in items_recs), 2)),
                    "tax_rate": items_recs[0]["tax_rate"],
                    "cgst_amount": float(cgst),
                    "sgst_amount": float(sgst),
                    "igst_amount": float(igst),
                    "total_tax": float(round(inv_total_tax, 2)),
                    "invoice_amount": float(round(inv_total_amount, 2)),
                    "payment_terms_days": node.payment_terms_days,
                    "amount_paid": 0.0,
                    "balance_due": float(round(inv_total_amount, 2)),
                    "payment_status": "unpaid",
                }

                sales_records.append(sale_dict)
                open_invoices.setdefault(node.id, []).append(sale_dict)
                node.outstanding_balance += sale_dict["invoice_amount"]

                events_log.append(
                    {
                        "id": uuid.uuid4(),
                        "event_type": "invoice_generated",
                        "customer_id": node.id,
                        "timestamp": dt_sim + timedelta(hours=11),
                        "metadata_json": {
                            "invoice_number": invoice_number,
                            "amount": sale_dict["invoice_amount"],
                            "due_date": due_date.isoformat(),
                        },
                        "source_state": node.hidden_state,
                    }
                )

                # --- SCHEDULE PAYMENTS (PHASE C) ---
                mean_shift, std_shift = STATE_PAYMENT_DELAY_SHIFT.get(node.hidden_state, (0.0, 1.0))
                delay_days = int(
                    rng.normal(
                        node.payment_terms_days + mean_shift * mods["delay_mult"],
                        max(1.0, std_shift),
                    )
                )
                payment_date = sim_date + timedelta(days=max(1, delay_days))

                will_pay = True
                if node.hidden_state == "DORMANT":
                    will_pay = False

                if will_pay:
                    full_pay_prob = 0.95 if node.hidden_state in ("HEALTHY", "GROWING") else 0.40
                    is_full_payment = rng.random() < full_pay_prob

                    if is_full_payment:
                        scheduled_payments.setdefault(payment_date, []).append(
                            {
                                "customer_id": node.id,
                                "invoice_id": sale_id,
                                "payment_date": payment_date,
                                "payment_amount": sale_dict["invoice_amount"],
                                "invoice_ref": sale_dict,
                            }
                        )
                    else:
                        num_splits = rng.choice([2, 3])
                        split_amt = float(round(sale_dict["invoice_amount"] / num_splits, 2))
                        for i in range(num_splits):
                            split_date = payment_date + timedelta(days=i * 10)
                            scheduled_payments.setdefault(split_date, []).append(
                                {
                                    "customer_id": node.id,
                                    "invoice_id": sale_id,
                                    "payment_date": split_date,
                                    "payment_amount": split_amt,
                                    "invoice_ref": sale_dict,
                                }
                            )

                # --- SCHEDULE RETURNS ---
                ret_rate = 0.16
                if node.hidden_state in ("STRESSED", "DISTRESSED"):
                    ret_rate = 0.35
                ret_rate *= mods["return_mult"]

                if rng.random() < ret_rate:
                    ret_delay = int(rng.integers(1, 15))
                    return_date = sim_date + timedelta(days=ret_delay)
                    qty_to_return = int(rng.integers(1, max(2, int(sale_dict["quantity"] * 0.5))))
                    ret_val = float(
                        round(
                            (qty_to_return / sale_dict["quantity"]) * sale_dict["invoice_amount"], 2
                        )
                    )

                    reasons = [
                        "quality_defect",
                        "damaged_goods",
                        "wrong_product",
                        "excess_inventory",
                    ]
                    reason = rng.choice(reasons)

                    scheduled_returns.setdefault(return_date, []).append(
                        {
                            "customer_id": node.id,
                            "sale_id": sale_id,
                            "return_date": return_date,
                            "return_reason": reason,
                            "quantity_returned": qty_to_return,
                            "return_value": ret_val,
                            "invoice_ref": sale_dict,
                        }
                    )

            # Check open invoices due states
            cust_opens = open_invoices.get(node.id, [])
            for open_inv in cust_opens:
                if open_inv["due_date"] == sim_date:
                    events_log.append(
                        {
                            "id": uuid.uuid4(),
                            "event_type": "invoice_due",
                            "customer_id": node.id,
                            "timestamp": dt_sim + timedelta(hours=9),
                            "metadata_json": {
                                "invoice_number": open_inv["invoice_number"],
                                "balance": open_inv["balance_due"],
                            },
                            "source_state": node.hidden_state,
                        }
                    )
                elif open_inv["due_date"] < sim_date and open_inv["payment_status"] != "paid":
                    if (sim_date - open_inv["due_date"]).days % 15 == 0:
                        events_log.append(
                            {
                                "id": uuid.uuid4(),
                                "event_type": "invoice_overdue",
                                "customer_id": node.id,
                                "timestamp": dt_sim + timedelta(hours=9, minutes=30),
                                "metadata_json": {
                                    "invoice_number": open_inv["invoice_number"],
                                    "days_overdue": (sim_date - open_inv["due_date"]).days,
                                    "balance": open_inv["balance_due"],
                                },
                                "source_state": node.hidden_state,
                            }
                        )

    # Final reconciliation of remaining open invoices overdue status
    for node in customer_nodes:
        cust_opens = open_invoices.get(node.id, [])
        for open_inv in cust_opens:
            if open_inv["payment_status"] != "paid" and end_date > open_inv["due_date"]:
                open_inv["payment_status"] = "overdue"

    # Format customer profiles record
    formatted_customers = []
    for node in customer_nodes:
        formatted_customers.append(
            {
                "id": node.id,
                "customer_code": node.customer_code,
                "business_name": node.business_name,
                "contact_name": fake.name(),
                "email": fake.company_email(),
                "phone": fake.phone_number(),
                "address_line1": fake.street_address(),
                "address_line2": "",
                "city": node.territory["city"],
                "state": node.territory["state"],
                "postal_code": fake.postcode(),
                "country": "IND",
                "business_type": node.business_type,
                "registration_date": node.registration_date,
                "credit_limit": node.credit_limit,
                "payment_terms_days": node.payment_terms_days,
                "is_active": node.hidden_state != "DORMANT",
                "behavioral_profile": {
                    "volume_segment": "Whale"
                    if node.credit_limit > 1_000_000
                    else ("Medium" if node.credit_limit > 200_000 else "Small"),
                    "lifecycle_segment": node.hidden_state
                    if node.hidden_state in ("GROWING", "STABLE", "DECLINING", "CHURN_RISK")
                    else "STABLE",
                    "payment_segment": "Hyper"
                    if node.hidden_state == "HEALTHY"
                    else ("Chronic Late" if node.hidden_state == "DISTRESSED" else "Moderate"),
                    "params": {
                        "liquidity": node.liquidity,
                        "growth_potential": node.growth_potential,
                        "operational_stability": node.operational_stability,
                        "payment_reliability": node.payment_reliability,
                        "churn_probability": node.churn_probability,
                        "creditworthiness": node.creditworthiness,
                    },
                },
                "territory_id": node.territory["id"],
                "salesperson_id": node.salesperson["id"] if node.salesperson else None,
            }
        )

    # Filter out records which occurred after end_date (since scheduled items can be outside sim bounds)
    final_payment_records = [p for p in payment_records if p["payment_date"] <= end_date]
    final_return_records = [r for r in return_records if r["return_date"] <= end_date]
    final_events_log = [e for e in events_log if e["timestamp"].date() <= end_date]

    print("Step 5: Writing simulation results to database...", flush=True)
    await batch_insert_all_async(engine, "territories", territories, batch_size)
    await batch_insert_all_async(engine, "salespersons", salespersons, batch_size)
    await batch_insert_all_async(engine, "products", products, batch_size)
    await batch_insert_all_async(engine, "customers", formatted_customers, batch_size)
    await batch_insert_all_async(engine, "raw_sales", sales_records, batch_size)
    await batch_insert_all_async(engine, "raw_payments", final_payment_records, batch_size)
    await batch_insert_all_async(engine, "raw_returns", final_return_records, batch_size)
    await batch_insert_all_async(engine, "event_logs", final_events_log, batch_size)
    await batch_insert_all_async(engine, "intelligence_benchmarks", benchmarks, batch_size)
    await batch_insert_all_async(engine, "relationships", relationships, batch_size)

    return {
        "customers": formatted_customers,
        "raw_sales": sales_records,
        "raw_payments": final_payment_records,
        "raw_returns": final_return_records,
        "event_logs": final_events_log,
        "intelligence_benchmarks": benchmarks,
        "relationships": relationships,
    }


async def batch_insert_all_async(engine, table_name, records, batch_size):
    for i in range(0, len(records), batch_size):
        chunk = records[i : i + batch_size]
        await bulk_insert(engine, table_name, chunk)
