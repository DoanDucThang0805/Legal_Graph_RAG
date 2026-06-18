"""Knowledge processing package.

Keep package import lightweight. Runtime retrieval imports small utilities from
submodules directly, so this package initializer must not import Phase 1
loaders/builders that depend on optional heavy packages such as datasets.
"""

__all__: list[str] = []
