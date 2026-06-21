"""
RAGE Training-Center – Crescendo multi-turn red-teaming for Text-to-SQL agents.

Automates Crescendo-style benign escalation campaigns against the RAGE
DecisionGateway to measure ASR, gateway bypass rate, and export actionable
hardening insights.
"""

from .scenarios import CrescendoScenario, load_scenarios
from .orchestrator import CrescendoOrchestrator, CrescendoRunResult
from .campaign import CrescendoCampaign, CampaignSummary
from .reporter import export_campaign_results, export_actionable_insights

__all__ = [
    "CrescendoScenario",
    "load_scenarios",
    "CrescendoOrchestrator",
    "CrescendoRunResult",
    "CrescendoCampaign",
    "CampaignSummary",
    "export_campaign_results",
    "export_actionable_insights",
]
