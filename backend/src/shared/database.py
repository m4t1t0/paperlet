"""Shared database registry and metadata for all contexts."""

from __future__ import annotations
from sqlalchemy.orm import registry

# Single shared registry for all models to enable cross-context foreign keys
mapper_registry = registry()
metadata = mapper_registry.metadata
