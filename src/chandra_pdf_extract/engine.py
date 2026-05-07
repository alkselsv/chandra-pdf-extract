from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from chandra.model import InferenceManager
from chandra.model.schema import BatchInputItem, BatchOutputItem
from PIL import Image

@dataclass
class PageResult:
    pdf_path: Path
    page: int
    markdown: str
    html: str
    seconds: float
    error: bool
    error_detail: str | None = None


@dataclass
class RunSummary:
    backend: str
    model_load_seconds: float | None
    pages: list[PageResult] = field(default_factory=list)
    total_wall_seconds: float = 0.0

    def ok_pages(self) -> int:
        return sum(1 for p in self.pages if not p.error)

    def failed_pages(self) -> int:
        return sum(1 for p in self.pages if p.error)


class ChandraPdfEngine:
    """Lazy Chandra ``InferenceManager`` configured for vLLM backend."""

    def __init__(self) -> None:
        self._manager: InferenceManager | None = None
        self._load_time: float | None = None

    @property
    def manager(self) -> InferenceManager:
        if self._manager is None:
            t0 = time.perf_counter()
            self._manager = InferenceManager(method="vllm")
            self._load_time = time.perf_counter() - t0
        return self._manager

    def run_page(
        self,
        image: Image.Image,
        pdf_path: Path,
        page: int,
        prompt_type: str,
        max_output_tokens: int | None = None,
    ) -> PageResult:
        batch = [BatchInputItem(image=image, prompt_type=prompt_type)]
        t0 = time.perf_counter()
        try:
            out: list[BatchOutputItem] = self.manager.generate(
                batch, max_output_tokens=max_output_tokens
            )
        except Exception as exc:  # noqa: BLE001
            dt = time.perf_counter() - t0
            return PageResult(
                pdf_path=pdf_path,
                page=page,
                markdown="",
                html="",
                seconds=dt,
                error=True,
                error_detail=str(exc),
            )
        dt = time.perf_counter() - t0
        item = out[0]
        return PageResult(
            pdf_path=pdf_path,
            page=page,
            markdown=item.markdown or "",
            html=item.html or "",
            seconds=dt,
            error=bool(getattr(item, "error", False)),
        )
