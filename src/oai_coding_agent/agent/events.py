"""
Alias of Agents SDK stream events for our public API.

Using this alias lets us stabilize our public interface even if the SDK renames or moves
its StreamEvent type in the future.
"""

from agents import StreamEvent, RunItemStreamEvent
from agents.items import ToolCallItem, ReasoningItem, MessageOutputItem


AgentEvent = StreamEvent
AgentRunItemStreamEvent = RunItemStreamEvent
AgentToolCallItem = ToolCallItem
AgentReasoningItem = ReasoningItem
AgentMessageOutputItem = MessageOutputItem
