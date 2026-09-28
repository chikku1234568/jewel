"""Extract Mermaid blocks from docs/architecture.md into docs/diagrams/<name>.mmd.

Each block must start with a Mermaid comment line: ``%% name: <file-stem>``.
Stale .mmd/.png files that no longer correspond to a block are removed.
"""

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCH = HERE.parent / "architecture.md"

blocks = re.findall(r"```mermaid\n(.*?)```", ARCH.read_text(), re.S)
names = []
for block in blocks:
    match = re.match(r"%% name: ([\w-]+)\n", block)
    if not match:
        raise SystemExit(f"Mermaid block without '%% name:' header:\n{block[:80]}")
    names.append(match.group(1))
    (HERE / f"{match.group(1)}.mmd").write_text(block)

for stale in [*HERE.glob("*.mmd"), *HERE.glob("*.png")]:
    if stale.stem not in names:
        stale.unlink()
        print(f"removed stale {stale.name}")
print("extracted:", ", ".join(names))
