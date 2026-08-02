"""Provider-neutral project knowledge acquisition primitives."""

from projectlore.acquisition.digest import content_digest
from projectlore.acquisition.models import Generation, KnowledgeRoot
from projectlore.acquisition.store import KnowledgeStore

__all__ = ["Generation", "KnowledgeRoot", "KnowledgeStore", "content_digest"]
