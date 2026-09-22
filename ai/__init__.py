"""BKPOS AI Intelligence Suite.

Integrates enterprise AI capabilities into the POS:
- Step A: AI Store Copilot / Natural Language Assistant (ai.copilot)
- Step B: AI Invoice & Receipt OCR for Auto-GRN (ai.ocr_grn)
- Step C: Computer Vision Produce & Bakery Recognition (ai.vision_checkout)
- Step D: Machine Learning Demand Forecasting & Smart Reorder (ai.forecasting)
- Step E: AI Fraud & Anomaly Audit Detection (ai.fraud_detection)
- Central AI Hub & Settings (ai.ai_hub, ai.config)
"""

from ai.config import get_ai_setting, set_ai_setting, ensure_ai_schema
from ai.copilot import AICopilotWindow, StoreCopilotEngine
from ai.ocr_grn import AIInvoiceOCRWindow, InvoiceOCREngine
from ai.vision_checkout import ProduceVisionCheckoutWindow, ProduceVisionEngine
from ai.forecasting import AIForecastingWindow, MLForecastingEngine
from ai.fraud_detection import AIFraudAnomalyWindow, FraudAnomalyEngine
from ai.recommendations import UpsellManagementWindow, MarketBasketEngine
from ai.dashboard_charts import AnalyticsChartsWindow, DashboardChartsFrame
from ai.ai_hub import AISuiteWindow, install as install_ai_suite

__all__ = [
    "get_ai_setting",
    "set_ai_setting",
    "ensure_ai_schema",
    "AICopilotWindow",
    "StoreCopilotEngine",
    "AIInvoiceOCRWindow",
    "InvoiceOCREngine",
    "ProduceVisionCheckoutWindow",
    "ProduceVisionEngine",
    "AIForecastingWindow",
    "MLForecastingEngine",
    "AIFraudAnomalyWindow",
    "FraudAnomalyEngine",
    "UpsellManagementWindow",
    "MarketBasketEngine",
    "AnalyticsChartsWindow",
    "DashboardChartsFrame",
    "AISuiteWindow",
    "install_ai_suite",
]
