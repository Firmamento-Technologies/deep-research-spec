"""RAG retriever for Knowledge Spaces — TH.1.

Espone retrieve_chunks_for_spaces() come entry point pubblico.
Il modulo è autonomo: nessuna dipendenza da graph/ o altri componenti DRS.
"""

from src.rag.retriever import retrieve_chunks_for_spaces

__all__ = ["retrieve_chunks_for_spaces"]
