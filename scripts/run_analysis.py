"""Run notebook 03 offline, preserving its outputs and rebuilding both report formats.

    python scripts/run_analysis.py
"""

import os
import sys
from pathlib import Path

# Small GLMs do not benefit from nested BLAS thread pools.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import nbformat  # noqa: E402
from jupyter_client import KernelManager  # noqa: E402
from nbclient import NotebookClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / "notebooks" / "03_cafe_location_analysis.ipynb"
    notebook = nbformat.read(path, as_version=4)
    manager = KernelManager(kernel_name="python3")
    manager.kernel_spec.argv[0] = sys.executable

    def started(cell, cell_index, **kwargs):
        if cell.cell_type == "code":
            print(f"Running cell {cell_index}", flush=True)

    client = NotebookClient(notebook, km=manager, timeout=1800, resources={"metadata": {"path": str(ROOT)}},
                            on_cell_start=started)
    try:
        client.execute()
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
    nbformat.write(notebook, path)
    # Imported only after analysis so builders cannot accidentally use stale outputs.
    from build_markdown_reports import build as build_markdown
    from build_report_page import build as build_page

    build_markdown()
    (ROOT / "report" / "report_ru.html").write_text(build_page(), encoding="utf-8")
    print("Notebook, Markdown reports and HTML report rebuilt.", flush=True)


if __name__ == "__main__":
    main()
