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


@pytest.mark.asyncio
async def test_github_server_whitelist(patch_get_function_tools):
    # Only the specified whitelist tools should be returned for github-mcp-server
    allowed = {
        "get_issue",
        "get_issue_comments",
        "create_issue",
        "add_issue_comment",
        "list_issues",
        "update_issue",
        "search_issues",
        "get_pull_request",
        "list_pull_requests",
        "get_pull_request_files",
        "get_pull_request_status",
        "update_pull_request_branch",
        "get_pull_request_comments",
        "get_pull_request_reviews",
        "create_pull_request",
        "add_pull_request_review_comment",
        "update_pull_request",
    }
    names = list(allowed) + ["other_tool"]
    async def fake(server, convert_strict):
        return [DummyTool(name) for name in names]

    patch_get_function_tools.setattr(MCPUtil, "get_function_tools", fake)
    servers = [SimpleNamespace(name="github-mcp-server")]

    for mode in ("default", "plan"):
        tools = await get_filtered_function_tools(servers, mode=mode)
        assert {t.name for t in tools} == allowed
