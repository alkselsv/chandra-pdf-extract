from __future__ import annotations


def parse_page_spec(spec: str, n_pages: int) -> list[int]:
    """Parse ``1,3-5,7`` into sorted unique 1-based page numbers within ``1..n_pages``."""
    if not spec.strip():
        return list(range(1, n_pages + 1))
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            lo, hi = int(a.strip()), int(b.strip())
            if lo > hi:
                lo, hi = hi, lo
            for p in range(lo, hi + 1):
                out.add(p)
        else:
            out.add(int(part))
    invalid = sorted(p for p in out if p < 1 or p > n_pages)
    if invalid:
        raise ValueError(f"page(s) out of range 1..{n_pages}: {invalid[:10]}")
    return sorted(out)
