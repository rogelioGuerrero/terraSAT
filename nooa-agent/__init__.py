"""TerraSAT — Sistema de procesamiento de imágenes satelitales.

Verticales:
  - AgroSAT: Alerta temprana agrícola (NDVI, NDRE, LST, CHIRPS)
  - UrbanSAT: Monitoreo urbano satelital (NDBI, LST, NDVI urbano)

Framework basado en NOOA Pattern (NVIDIA OO-Agents).
"""

from base_agent import AutonomousAgent
from insurance_autonomous import InsuranceAutonomousAgent

# NOOA Harness
from harness import ToolResult, ResultRegistry
from memory_store import MemoryStore, Entity, Relation
from harness_api import HarnessAPI, HARNESS_TOOLS
from code_action import strategy, PredictStrategy
from shared_tools import tool_search_sentinel, tool_generate_deformation_map
