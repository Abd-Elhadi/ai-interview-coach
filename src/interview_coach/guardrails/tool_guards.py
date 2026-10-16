import sys
from pathlib import Path

from crewai.mcp import MCPServerStdio
from crewai.mcp.filters import create_static_tool_filter

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "mcp_server" / "server.py"

# Least privilege: each agent sees only the MCP tools it needs.
TOOL_ALLOWLIST = {
    "interview_planner": ["get_interview_questions"],
    "evaluation_coach": ["get_scoring_rubric", "get_delivery_guidelines"],
}


def mcp_for(agent_name: str) -> MCPServerStdio:
    return MCPServerStdio(
        command=sys.executable,
        args=[str(SERVER)],
        env={"PYTHONPATH": str(ROOT)},
        tool_filter=create_static_tool_filter(allowed_tool_names=TOOL_ALLOWLIST[agent_name]),
        cache_tools_list=True,
    )