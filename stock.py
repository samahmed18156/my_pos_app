"""Legacy compatibility wrapper. Product creation is handled only by Product Management.
Stock lookup is handled by Professional Lookup. GRN is the only stock-receiving workflow.
"""
from professional_lookup import PriceLookupWindow

class StockWindow(PriceLookupWindow):
    """Compatibility name for old code; lookup only, no product creation/editing."""
    pass
