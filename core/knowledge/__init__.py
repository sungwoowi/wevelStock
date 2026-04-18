"""Knowledge layer — Canon + RAG."""
from core.knowledge.compose import build_system_prompt, load_canon
from core.knowledge.retrieve import retrieve

__all__ = ["build_system_prompt", "load_canon", "retrieve"]
