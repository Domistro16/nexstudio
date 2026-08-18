# Studio Source Intelligence

Deterministic, provenance-preserving ingestion for user source files before NexMind P8.

Supported document binaries: PDF, DOCX, PPTX, text, CSV and JSON. PDF page previews are rendered when PyMuPDF is available so visual-only/chart-heavy pages can be carried forward as real visual evidence rather than guessed from extracted text.

This layer does not make creative decisions and does not summarize away source truth. Each segment retains a locator and SHA-256. NexMind receives selected source segments as evidence and remains responsible for resolving relevance/contradictions.

Runtime Python requirements are pinned in `requirements.txt` and must be installed wherever the existing P8 Python sidecar runs.
