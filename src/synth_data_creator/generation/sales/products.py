import numpy as np

PRODUCT_CATALOG = {
    "Electronics": [
        {"name": "LED Panel 40W", "base_price": 850.00, "unit": "piece"},
        {"name": "USB-C Cable 1m", "base_price": 120.00, "unit": "piece"},
        {"name": "Power Adapter 65W", "base_price": 450.00, "unit": "piece"},
        {"name": "Bluetooth Speaker", "base_price": 1200.00, "unit": "piece"},
        {"name": "Smart Plug WiFi", "base_price": 680.00, "unit": "piece"},
    ],
    "FMCG": [
        {"name": "Detergent Powder 5kg", "base_price": 280.00, "unit": "pack"},
        {"name": "Cooking Oil 5L", "base_price": 520.00, "unit": "can"},
        {"name": "Rice Basmati 25kg", "base_price": 1800.00, "unit": "bag"},
        {"name": "Sugar 50kg", "base_price": 2100.00, "unit": "bag"},
        {"name": "Tea Powder 1kg", "base_price": 350.00, "unit": "pack"},
    ],
    "Hardware": [
        {"name": "PVC Pipe 4inch 6ft", "base_price": 320.00, "unit": "piece"},
        {"name": "Cement 50kg", "base_price": 380.00, "unit": "bag"},
        {"name": "Steel Rod 12mm", "base_price": 550.00, "unit": "piece"},
        {"name": "Paint Emulsion 20L", "base_price": 2800.00, "unit": "bucket"},
        {"name": "Electrical Wire 90m", "base_price": 1500.00, "unit": "roll"},
    ],
    "Textiles": [
        {"name": "Cotton Fabric 100m", "base_price": 4500.00, "unit": "roll"},
        {"name": "Polyester Blend 50m", "base_price": 2200.00, "unit": "roll"},
        {"name": "Denim Fabric 50m", "base_price": 3500.00, "unit": "roll"},
    ],
    "Pharmaceuticals": [
        {"name": "Paracetamol 500mg (100s)", "base_price": 45.00, "unit": "strip"},
        {"name": "Sanitizer 5L", "base_price": 350.00, "unit": "can"},
        {"name": "Surgical Mask (50s)", "base_price": 180.00, "unit": "box"},
    ],
    "Stationery": [
        {"name": "A4 Paper Ream 500", "base_price": 280.00, "unit": "ream"},
        {"name": "Printer Ink Cartridge", "base_price": 650.00, "unit": "piece"},
        {"name": "Notebook 200pg (dozen)", "base_price": 480.00, "unit": "dozen"},
    ],
}

# Mapping of business_type to category weights
BUSINESS_TYPE_WEIGHTS = {
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

def pick_product(business_type: str, rng: np.random.Generator) -> tuple[str, dict]:
    """Pick a random product and its category based on the business type weights."""
    weights_dict = BUSINESS_TYPE_WEIGHTS.get(business_type)
    if not weights_dict:
        # Fallback to uniform
        categories = list(PRODUCT_CATALOG.keys())
        category = str(rng.choice(categories))
    else:
        categories = list(weights_dict.keys())
        probs = np.array(list(weights_dict.values()))
        probs /= probs.sum()  # Normalize just in case
        category = str(rng.choice(categories, p=probs))


    products = PRODUCT_CATALOG[category]
    product = rng.choice(products)
    return category, product
