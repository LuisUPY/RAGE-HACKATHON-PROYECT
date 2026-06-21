"""
Training-Center – Crescendo red-teaming automation for RAGE (rage_core).

Runs multi-turn Crescendo scenarios against DefensePipeline + SalesAgent,
measures ASR and exports actionable hardening insights.
"""

from .campaign import TrainingCampaign, CampaignResult
from .orchestrator import ScenarioRunResult

__all__ = ["TrainingCampaign", "CampaignResult", "ScenarioRunResult"]
