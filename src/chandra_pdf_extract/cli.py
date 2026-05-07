from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from chandra_pdf_extract.engine import ChandraPdfEngine, PageResult, RunSummary
from chandra_pdf_extract.pagespec import parse_page_spec
from chandra_pdf_extract.pdf_render import pdf_page_count, render_pdf_page


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _collect_pdfs(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.glob("*.pdf"))
    raise FileNotFoundError(path)


def _write_outputs(
    result: PageResult,
    out_root: Path,
    save_html: bool,
) -> None:
    sub = out_root / result.pdf_path.stem
    sub.mkdir(parents=True, exist_ok=True)
    md_path = sub / f"page_{result.page:03d}.md"
    md_path.write_text(result.markdown, encoding="utf-8")
    if save_html and result.html:
        (sub / f"page_{result.page:03d}.html").write_text(result.html, encoding="utf-8")


def _write_combined_markdown(summary: RunSummary, out_root: Path) -> None:
    by_pdf: dict[Path, list[PageResult]] = defaultdict(list)
    for page_result in summary.pages:
        if page_result.error:
            continue
        by_pdf[page_result.pdf_path].append(page_result)

    for pdf_path, page_results in by_pdf.items():
        sub = out_root / pdf_path.stem
        sub.mkdir(parents=True, exist_ok=True)
        combined_path = sub / f"{pdf_path.stem}.md"
        ordered = sorted(page_results, key=lambda r: r.page)
        combined = "\n\n".join(item.markdown.rstrip() for item in ordered).strip() + "\n"
        combined_path.write_text(combined, encoding="utf-8")


def _print_final_summary(summary: RunSummary) -> None:
    _log("--- summary ---")
    _log(f"total wall time: {summary.total_wall_seconds:.2f}s")
    _log(f"pages processed: {len(summary.pages)} (ok {summary.ok_pages()}, failed {summary.failed_pages()})")
    if not summary.pages:
        return
    ok_times = [p.seconds for p in summary.pages if not p.error]
    if ok_times:
        _log(
            f"per-page inference: min {min(ok_times):.2f}s  "
            f"max {max(ok_times):.2f}s  "
            f"avg {sum(ok_times) / len(ok_times):.2f}s"
        )
    by_pdf = defaultdict(list)
    for p in summary.pages:
        by_pdf[p.pdf_path.name].append(p.seconds)
    _log("by document (sum of page times):")
    for name in sorted(by_pdf):
        t = sum(by_pdf[name])
        _log(f"  {name}: {t:.2f}s ({len(by_pdf[name])} pages)")


def _process_page_job(
    *,
    engine: ChandraPdfEngine,
    pdf_path: Path,
    page: int,
    n_pages: int,
    job_idx: int,
    total_jobs: int,
    render_scale: float,
    prompt_type: str,
    max_output_tokens: int | None,
) -> tuple[PageResult, float]:
    _log(
        f"render {pdf_path.name} page {page}/{n_pages} "
        f"({job_idx}/{total_jobs} jobs) scale={render_scale}"
    )
    t_r0 = time.perf_counter()
    image = render_pdf_page(pdf_path, page, scale=render_scale)
    render_s = time.perf_counter() - t_r0
    _log(f"  raster done in {render_s:.2f}s")

    _log("  Chandra inference…")
    res = engine.run_page(
        image,
        pdf_path,
        page,
        prompt_type=prompt_type,
        max_output_tokens=max_output_tokens,
    )
    return res, render_s


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Chandra OCR: extract PDF pages to Markdown/HTML via vLLM backend.",
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "pdf",
        nargs="?",
        type=Path,
        help="Single PDF file.",
    )
    src.add_argument(
        "--documents-dir",
        type=Path,
        help="Directory with .pdf files (all documents, all pages by default).",
    )
    parser.add_argument(
        "-p",
        "--pages",
        type=str,
        default="",
        help='Pages for a single PDF: e.g. "1", "3-5", "1,4,7-9". Empty = all pages.',
    )
    parser.add_argument(
        "--prompt-type",
        choices=("ocr_layout", "ocr"),
        default="ocr_layout",
        help="Chandra prompt preset (see chandra-ocr docs).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory for extracted page files.",
    )
    parser.add_argument(
        "--render-scale",
        type=float,
        default=2.0,
        help="PyMuPDF rasterization scale (higher = sharper, slower, more VRAM).",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=None,
        help="Override max new tokens (default: from chandra settings / env).",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Also write .html next to .md for each page.",
    )
    parser.add_argument(
        "--concurrent-sequences",
        type=int,
        default=1,
        help="How many pages to process concurrently (maps to client-side parallel requests).",
    )
    args = parser.parse_args(argv)
    if args.concurrent_sequences < 1:
        parser.error("--concurrent-sequences must be >= 1")

    if args.documents_dir is not None:
        pdfs = _collect_pdfs(args.documents_dir)
        if not pdfs:
            _log(f"no PDF files in {args.documents_dir}")
            return 1
        if args.pages:
            _log("warning: --pages applies only to a single PDF; ignored for --documents-dir")
    else:
        if args.pdf is None:
            parser.error("pass a PDF path or --documents-dir")
        pdfs = _collect_pdfs(args.pdf)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    engine = ChandraPdfEngine()
    summary = RunSummary(backend="vllm", model_load_seconds=None)
    wall_t0 = time.perf_counter()

    _log(f"backend=vllm prompt_type={args.prompt_type} documents={len(pdfs)}")

    jobs: list[tuple[Path, int, list[int]]] = []
    for pdf_path in pdfs:
        pdf_path = pdf_path.resolve()
        n = pdf_page_count(pdf_path)
        if args.documents_dir is not None or not args.pages:
            pages = list(range(1, n + 1))
        else:
            pages = parse_page_spec(args.pages, n)
        jobs.append((pdf_path, n, pages))

    total_jobs = sum(len(p[2]) for p in jobs)
    exit_code = 0

    try:
        _log("connecting to vLLM backend...")
        _ = engine.manager

        _log(f"concurrent_sequences={args.concurrent_sequences}")

        indexed_jobs: list[tuple[int, Path, int, int]] = []
        global_idx = 0
        for pdf_path, n, pages in jobs:
            _log(f"{pdf_path.name}: {len(pages)} page(s) (file has {n} pages)")
            for page in pages:
                global_idx += 1
                indexed_jobs.append((global_idx, pdf_path, n, page))

        with ThreadPoolExecutor(max_workers=args.concurrent_sequences) as pool:
            futures = [
                pool.submit(
                    _process_page_job,
                    engine=engine,
                    pdf_path=pdf_path,
                    page=page,
                    n_pages=n_pages,
                    job_idx=job_idx,
                    total_jobs=total_jobs,
                    render_scale=args.render_scale,
                    prompt_type=args.prompt_type,
                    max_output_tokens=args.max_output_tokens,
                )
                for job_idx, pdf_path, n_pages, page in indexed_jobs
            ]
            for fut in as_completed(futures):
                res, _ = fut.result()
                summary.pages.append(res)
                status = "FAIL" if res.error else "OK"
                _log(
                    f"  {status} inference {res.seconds:.2f}s "
                    f"(page {res.page} {res.pdf_path.name})"
                )
                if not res.error:
                    _write_outputs(res, args.output_dir, save_html=args.html)
                else:
                    if res.error_detail:
                        _log(f"  error: {res.error_detail[:500]}")
                    _log("  (no output files written for this page)")

    except KeyboardInterrupt:
        _log("interrupted by user")
        exit_code = 130
    finally:
        summary.total_wall_seconds = time.perf_counter() - wall_t0
        _write_combined_markdown(summary, args.output_dir)
        _print_final_summary(summary)

    if exit_code == 130:
        return exit_code
    if summary.failed_pages():
        return 2
    return 0


def main() -> None:
    raise SystemExit(run())
