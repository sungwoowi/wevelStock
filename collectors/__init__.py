"""Shared data collection library (pipeline-agnostic).

Used by multiple pipelines to avoid duplicating data-fetching logic.
Keep each module as a pure async function returning plain dicts/lists —
no pipeline or DB dependencies.
"""
