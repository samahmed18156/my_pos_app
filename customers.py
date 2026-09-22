# Compatibility wrapper: the POS now uses the combined Customer & Pricing manager.
from customer_pricing import CustomerPricingWindow, ensure_schema


class CustomerManagerWindow(CustomerPricingWindow):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Customer Management — Retail / Bulk / Wholesale")


__all__ = ["CustomerManagerWindow", "ensure_schema"]
