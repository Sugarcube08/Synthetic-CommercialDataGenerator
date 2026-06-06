from enum import Enum

class ReturnReason(str, Enum):
    DAMAGED_GOODS = "damaged_goods"
    DELIVERY_ISSUES = "delivery_issues"
    QUALITY_DEFECT = "quality_defect"
    WRONG_PRODUCT = "wrong_product"
    EXCESS_INVENTORY = "excess_inventory"
    CUSTOMER_DISSATISFACTION = "customer_dissatisfaction"
    EXPIRED_PRODUCT = "expired_product"
    PRICING_DISPUTE = "pricing_dispute"


# Return rate category multipliers
CATEGORY_MULTIPLIERS = {
    "Electronics": 1.5,
    "FMCG": 0.8,
    "Hardware": 1.2,
    "Textiles": 1.3,
    "Pharmaceuticals": 0.5,
    "Stationery": 0.7,
}

# Reason weights by category
REASON_WEIGHTS = {
    "Electronics": {
        ReturnReason.DAMAGED_GOODS: 0.25,
        ReturnReason.DELIVERY_ISSUES: 0.15,
        ReturnReason.QUALITY_DEFECT: 0.30,
        ReturnReason.WRONG_PRODUCT: 0.10,
        ReturnReason.EXCESS_INVENTORY: 0.05,
        ReturnReason.CUSTOMER_DISSATISFACTION: 0.10,
        ReturnReason.EXPIRED_PRODUCT: 0.00,
        ReturnReason.PRICING_DISPUTE: 0.05,
    },
    "FMCG": {
        ReturnReason.DAMAGED_GOODS: 0.15,
        ReturnReason.DELIVERY_ISSUES: 0.10,
        ReturnReason.QUALITY_DEFECT: 0.10,
        ReturnReason.WRONG_PRODUCT: 0.05,
        ReturnReason.EXCESS_INVENTORY: 0.30,
        ReturnReason.CUSTOMER_DISSATISFACTION: 0.15,
        ReturnReason.EXPIRED_PRODUCT: 0.10,
        ReturnReason.PRICING_DISPUTE: 0.05,
    },
    "Hardware": {
        ReturnReason.DAMAGED_GOODS: 0.35,
        ReturnReason.DELIVERY_ISSUES: 0.25,
        ReturnReason.QUALITY_DEFECT: 0.15,
        ReturnReason.WRONG_PRODUCT: 0.05,
        ReturnReason.EXCESS_INVENTORY: 0.10,
        ReturnReason.CUSTOMER_DISSATISFACTION: 0.05,
        ReturnReason.EXPIRED_PRODUCT: 0.00,
        ReturnReason.PRICING_DISPUTE: 0.05,
    },
    "Textiles": {
        ReturnReason.DAMAGED_GOODS: 0.20,
        ReturnReason.DELIVERY_ISSUES: 0.10,
        ReturnReason.QUALITY_DEFECT: 0.30,
        ReturnReason.WRONG_PRODUCT: 0.10,
        ReturnReason.EXCESS_INVENTORY: 0.15,
        ReturnReason.CUSTOMER_DISSATISFACTION: 0.10,
        ReturnReason.EXPIRED_PRODUCT: 0.00,
        ReturnReason.PRICING_DISPUTE: 0.05,
    },
    "Pharmaceuticals": {
        ReturnReason.DAMAGED_GOODS: 0.10,
        ReturnReason.DELIVERY_ISSUES: 0.05,
        ReturnReason.QUALITY_DEFECT: 0.15,
        ReturnReason.WRONG_PRODUCT: 0.05,
        ReturnReason.EXCESS_INVENTORY: 0.20,
        ReturnReason.CUSTOMER_DISSATISFACTION: 0.05,
        ReturnReason.EXPIRED_PRODUCT: 0.35,
        ReturnReason.PRICING_DISPUTE: 0.05,
    },
    "Stationery": {
        ReturnReason.DAMAGED_GOODS: 0.10,
        ReturnReason.DELIVERY_ISSUES: 0.10,
        ReturnReason.QUALITY_DEFECT: 0.10,
        ReturnReason.WRONG_PRODUCT: 0.15,
        ReturnReason.EXCESS_INVENTORY: 0.30,
        ReturnReason.CUSTOMER_DISSATISFACTION: 0.15,
        ReturnReason.EXPIRED_PRODUCT: 0.05,
        ReturnReason.PRICING_DISPUTE: 0.05,
    },
}
