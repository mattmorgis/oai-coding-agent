import pytest
from types import SimpleNamespace

from agents.mcp.util import MCPUtil
from oai_coding_agent.mcp_tool_selector import get_filtered_function_tools


class DummyTool:
    def __init__(self, name):
        self.name = name


@pytest.fixture(autouse=True)
def patch_get_function_tools(monkeypatch):
    """
    By default, stub out MCPUtil.get_function_tools to avoid touching real servers.
    Individual tests will override this.
    """
    async def _fake(server, convert_strict):
        return []

    monkeypatch.setattr(MCPUtil, "get_function_tools", _fake)
    return monkeypatch


@pytest.mark.asyncio
async def test_default_mode_no_filter(patch_get_function_tools):
    # Both edit_file and read_file should pass through in default mode
    async def fake(server, convert_strict):
        return [DummyTool("edit_file"), DummyTool("read_file")]

    patch_get_function_tools.setattr(MCPUtil, "get_function_tools", fake)
    servers = [SimpleNamespace(name="file-system-mcp")]
    tools = await get_filtered_function_tools(servers, mode="default")
    assert {t.name for t in tools} == {"edit_file", "read_file"}


@pytest.mark.asyncio
async def test_plan_mode_filesystem_filter(patch_get_function_tools):
    # edit_file should be removed in plan mode for file-system-mcp
    async def fake(server, convert_strict):
        return [DummyTool("edit_file"), DummyTool("read_file")]

    patch_get_function_tools.setattr(MCPUtil, "get_function_tools", fake)
    servers = [SimpleNamespace(name="file-system-mcp")]
    tools = await get_filtered_function_tools(servers, mode="plan")
    assert {t.name for t in tools} == {"read_file"}


@pytest.mark.asyncio
async def test_plan_mode_git_filter(patch_get_function_tools):
    # Only clone_repo and list_branches should remain for mcp-server-git in plan mode
    async def fake(server, convert_strict):
        return [
            DummyTool("clone_repo"),
            DummyTool("list_branches"),
            DummyTool("commit"),
        ]

    patch_get_function_tools.setattr(MCPUtil, "get_function_tools", fake)
    servers = [SimpleNamespace(name="mcp-server-git")]
    tools = await get_filtered_function_tools(servers, mode="plan")
    assert {t.name for t in tools} == {"clone_repo", "list_branches"}
