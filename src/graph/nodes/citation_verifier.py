"""CitationVerifier node — §5.4, §18.2-18.3. HTTP, DOI, NLI entailment."""
from __future__ import annotations

import logging
import re
from typing import Literal

logger = logging.getLogger(__name__)

_ENTAILMENT_THRESHOLD = 0.80
_HTTP_TIMEOUT = 5
_DOI_TIMEOUT = 8


class CitationVerifierNode:
    """§5.4 — Verify source existence and claim–source entailment via NLI.

    Pipeline: HTTP HEAD → DOI resolution → DeBERTa NLI entailment.
    """

    def __init__(self):
        self._nli_model = None

    def _get_nli_model(self):
        """Lazy-load DeBERTa NLI model."""
        if self._nli_model is None:
            try:
                from transformers import pipeline
                self._nli_model = pipeline(
                    "text-classification",
                    model="microsoft/deberta-v3-large-mnli",
                    device=-1,  # CPU
                )
            except Exception as e:
                logger.warning("DeBERTa NLI model unavailable: %s", e)
                self._nli_model = False  # sentinel
        return self._nli_model if self._nli_model is not False else None

    async def run(self, state: dict) -> dict:
        """Verify all current_sources. Returns partial state update."""
        sources = state.get("current_sources", [])
        ghost_citations: list[str] = []
        verified_sources: list[dict] = []

        for src in sources:
            sid = src.get("source_id", "")
            url = src.get("url")
            doi = src.get("doi")

            # HTTP HEAD check
            http_ok = await self._check_http(url) if url else False

            # DOI resolution
            doi_ok = await self._check_doi(doi) if doi else True  # no DOI → skip

            # Determine verification
            if url and not http_ok and not (doi and doi_ok):
                src["http_verified"] = False
                src["ghost_flag"] = True
                ghost_citations.append(sid)
                logger.info("Ghost citation: %s (HTTP=%s, DOI=%s)", sid, http_ok, doi_ok)
            else:
                src["http_verified"] = http_ok or doi_ok
                src["ghost_flag"] = False

            # NLI entailment (skip for ghosts)
            if not src.get("ghost_flag") and src.get("abstract"):
                nli_score = self._run_nli(
                    claim=src.get("title", ""),
                    source_text=src.get("abstract", "")[:512],
                )
                src["nli_entailment"] = nli_score

            verified_sources.append(src)

        return {
            "current_sources": verified_sources,
            "ghost_citations": ghost_citations,
        }

    async def _check_http(self, url: str) -> bool:
        """HTTP HEAD check with timeout. §18.2."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
                r = await client.head(url)
                return r.status_code in (200, 301, 302)
        except Exception:
            # Retry once with longer timeout
            try:
                import httpx
                async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT + 2, follow_redirects=True) as client:
                    r = await client.head(url)
                    return r.status_code in (200, 301, 302)
            except Exception:
                return False

    async def _check_doi(self, doi: str) -> bool:
        """DOI resolution via doi.org. §18.2."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=_DOI_TIMEOUT, follow_redirects=True) as client:
                r = await client.get(f"https://doi.org/{doi}")
                return r.status_code == 200
        except Exception:
            logger.warning("DOI resolve failed for %s", doi)
            return False

    def _run_nli(self, claim: str, source_text: str) -> float | None:
        """Run DeBERTa NLI entailment check. §18.3."""
        model = self._get_nli_model()
        if model is None:
            return None
        try:
            result = model(f"{source_text} [SEP] {claim}", truncation=True)
            # Extract entailment score
            for r in result if isinstance(result, list) else [result]:
                if r.get("label", "").lower() == "entailment":
                    return r.get("score", 0.0)
            return 0.0
        except Exception as e:
            logger.warning("NLI inference error: %s", e)
            return None


# ── Node function for graph registration ─────────────────────────────────────

_default_node = CitationVerifierNode()


async def citation_verifier_node(state: dict) -> dict:
    """Graph-compatible node function."""
    return await _default_node.run(state)
