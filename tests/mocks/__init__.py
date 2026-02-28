"""Test mock package.

Contains lightweight stub implementations of production nodes for use in
unit and integration tests.  None of these modules should ever be imported
from ``src/`` — they live here to prevent the graph builder from
auto-discovering them as production-routable nodes.
"""
