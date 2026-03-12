# SHINE — lazy imports to avoid hard dependency on torch
# torch/SHINE are optional; context_compressor falls back gracefully

try:
    from .hypernetwork import SHINEHypernetwork, LoRAAdapter
    from .adapter_registry import AdapterRegistry
    from .chunker import TextChunker
    SHINE_AVAILABLE = True
except ImportError:
    SHINEHypernetwork = None  # type: ignore[assignment,misc]
    LoRAAdapter = None  # type: ignore[assignment,misc]
    AdapterRegistry = None  # type: ignore[assignment,misc]
    TextChunker = None  # type: ignore[assignment,misc]
    SHINE_AVAILABLE = False

__all__ = ["SHINEHypernetwork", "LoRAAdapter", "AdapterRegistry", "TextChunker", "SHINE_AVAILABLE"]
