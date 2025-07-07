"""
Pure numeric animation engine for token counts in the console.

This module provides a TokenAnimator class that smoothly animates integer-based
input/output token counts over a specified duration and interval, and a helper
function to format large counts for display.
"""

import asyncio
from typing import Optional

from oai_coding_agent.agent.events import UsageEvent


class TokenAnimator:
    """
    Animate pure numeric token counts (input/output) over time.

    Attributes:
        interval: Time between animation ticks in seconds.
        animation_duration: Approximate total time for any count change to complete.
    """

    @staticmethod
    def format_count(v: int) -> str:
        """
        Abbreviate integer counts >= 1000 as '1.2k', otherwise return the integer string.
        Drops any trailing '.0' for whole thousands (e.g., '12k' instead of '12.0k').
        """
        if v >= 1000:
            value = v / 1000.0
            s = f"{value:.1f}k"
            if s.endswith(".0k"):
                s = s.replace(".0k", "k")
            return s
        return str(v)

    def __init__(
        self, *, interval: float = 0.1, animation_duration: float = 1.0
    ) -> None:
        self._interval = interval
        self._animation_duration = animation_duration
        self._target_input: int = 0
        self._target_output: int = 0
        self._current_input_val: float = 0.0
        self._current_output_val: float = 0.0
        self._last_delta: int = 0
        self._step_input: float = 0.0
        self._step_output: float = 0.0
        self._task: Optional[asyncio.Task[None]] = None

    @property
    def current_input(self) -> int:
        """Current animated input token count (int)."""
        return int(self._current_input_val)

    @property
    def current_output(self) -> int:
        """Current animated output token count (int)."""
        return int(self._current_output_val)

    @property
    def last_delta(self) -> int:
        """Total tokens delta from the most recent UsageEvent."""
        return self._last_delta

    def update(self, usage_delta: UsageEvent) -> None:
        """
        Update the animator with a new UsageEvent, recomputing per-tick steps.

        Args:
            usage_delta: UsageEvent containing input/output token counts and total delta.
        """
        new_input = usage_delta.input_tokens
        new_output = usage_delta.output_tokens
        # Compute difference from current integer display values
        delta_input = new_input - self.current_input
        delta_output = new_output - self.current_output
        # Compute per-tick step so full change happens in ~animation_duration
        if self._animation_duration > 0:
            factor = self._interval / self._animation_duration
        else:
            factor = 1.0
        self._step_input = delta_input * factor
        self._step_output = delta_output * factor
        self._target_input = new_input
        self._target_output = new_output
        self._last_delta = usage_delta.total_tokens

    def _tick(self) -> None:
        """
        Synchronous tick: advance current values by step and clamp to targets.
        """
        # Advance
        self._current_input_val += self._step_input
        self._current_output_val += self._step_output
        # Clamp input
        if self._step_input > 0:
            if self._current_input_val >= self._target_input:
                self._current_input_val = float(self._target_input)
        elif self._step_input < 0:
            if self._current_input_val <= self._target_input:
                self._current_input_val = float(self._target_input)
        # Clamp output
        if self._step_output > 0:
            if self._current_output_val >= self._target_output:
                self._current_output_val = float(self._target_output)
        elif self._step_output < 0:
            if self._current_output_val <= self._target_output:
                self._current_output_val = float(self._target_output)

    def start(self) -> None:
        """
        Start the background animation task if not already running.
        """
        if not self._task or self._task.done():
            loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._run())

    async def _run(self) -> None:
        """Background task: call _tick every interval seconds."""
        try:
            while True:
                await asyncio.sleep(self._interval)
                self._tick()
        except asyncio.CancelledError:
            # Graceful shutdown
            pass

    def stop(self) -> None:
        """
        Stop the background animation task if running.
        """
        if self._task and not self._task.done():
            self._task.cancel()
