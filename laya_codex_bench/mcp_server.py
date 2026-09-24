from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .laya_client import LayaClient


ROOT = Path(__file__).resolve().parents[1]
mcp = FastMCP("laya-local-decisions")


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
def laya_predict(state: Any, questions: dict[str, Any]) -> dict[str, Any]:
    """Classify typed questions about state with the already-running local Laya model."""
    client = LayaClient(ROOT)
    return client.predict(state, questions)


if __name__ == "__main__":
    mcp.run(transport="stdio")
