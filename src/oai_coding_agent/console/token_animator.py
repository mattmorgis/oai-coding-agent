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
        self, *, interval: float = 0.1, animation_duration: float = 3.0
    ) -> None:
        self._interval = interval
        self._animation_duration = animation_duration
        self._target_input: int = 0
        self._target_output: int = 0
        self._current_input_val: float = 0.0
        self._current_output_val: float = 0.0
        self._total_token_val: int = 0
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
    def total_tokens(self) -> int:
        """Total tokens delta from the most recent UsageEvent."""
        return self._total_token_val

    def update(self, usage_delta: UsageEvent) -> None:
        """
        Update the animator with a new UsageEvent, setting new target values.

        Args:
            usage_delta: UsageEvent containing input/output token counts and total delta.
        """
        self._target_input = usage_delta.input_tokens
        self._target_output = usage_delta.output_tokens
        self._total_token_val = usage_delta.total_tokens

    def _tick(self) -> None:
        """
        Synchronous tick: advance current values using ease-out animation.
        Takes larger steps when far from target, smaller steps when close.
        """
        # Calculate ease-out steps (10% of remaining distance)
        ease_factor = 0.1

        # Animate input
        input_distance = self._target_input - self._current_input_val
        input_step = input_distance * ease_factor
        self._current_input_val += input_step

        # Animate output
        output_distance = self._target_output - self._current_output_val
        output_step = output_distance * ease_factor
        self._current_output_val += output_step

        # Clamp to targets when very close (avoid floating point imprecision)
        if abs(input_distance) < 0.1:
            self._current_input_val = float(self._target_input)
        if abs(output_distance) < 0.1:
            self._current_output_val = float(self._target_output)

    def start(self) -> None:
        """
        Start the background animation task if not already running.
        """
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._run())

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
