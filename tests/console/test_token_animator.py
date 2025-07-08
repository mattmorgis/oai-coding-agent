import asyncio

import pytest

from oai_coding_agent.agent.events import UsageEvent
from oai_coding_agent.console.token_animator import TokenAnimator


def test_initial_state_before_update() -> None:
    anim = TokenAnimator()
    assert anim.current_input == 0
    assert anim.current_output == 0
    assert anim.total_tokens == 0
    # Private step attributes should be zero
    assert anim._step_input == pytest.approx(0.0)
    assert anim._step_output == pytest.approx(0.0)


def test_format_count_small_and_large() -> None:
    assert TokenAnimator.format_count(42) == "42"
    assert TokenAnimator.format_count(999) == "999"
    assert TokenAnimator.format_count(1000) == "1k"
    assert TokenAnimator.format_count(1200) == "1.2k"
    assert TokenAnimator.format_count(12000) == "12k"
    assert TokenAnimator.format_count(12500) == "12.5k"


def test_update_sets_total_tokens_and_step_sizes() -> None:
    anim = TokenAnimator(interval=0.2, animation_duration=1.0)
    # Create a UsageEvent with known tokens and total_tokens
    usage = UsageEvent(
        input_tokens=100,
        cached_input_tokens=0,
        output_tokens=50,
        reasoning_output_tokens=0,
        total_tokens=150,
    )
    anim.update(usage)
    # total_tokens should reflect total_tokens
    assert anim.total_tokens == 150
    # Step sizes: delta_input=100, delta_output=50, factor=interval/animation_duration=0.2
    assert anim._step_input == pytest.approx(100 * 0.2)
    assert anim._step_output == pytest.approx(50 * 0.2)


def test_synchronous_tick_advances_to_target() -> None:
    anim = TokenAnimator(interval=0.1, animation_duration=0.2)
    usage = UsageEvent(
        input_tokens=10,
        cached_input_tokens=0,
        output_tokens=20,
        reasoning_output_tokens=0,
        total_tokens=30,
    )
    anim.update(usage)
    # Two ticks should complete the animation (interval/duration = 0.5 factor)
    anim._tick()
    assert anim.current_input == 5
    assert anim.current_output == 10
    anim._tick()
    assert anim.current_input == 10
    assert anim.current_output == 20
    # Further ticks do not overshoot
    anim._tick()
    assert anim.current_input == 10
    assert anim.current_output == 20


def test_decrement_animation() -> None:
    anim = TokenAnimator(interval=0.1, animation_duration=0.2)
    # First update to a higher value
    usage1 = UsageEvent(8, 0, 12, 0, 20)
    anim.update(usage1)
    # Complete initial increase
    anim._tick()
    anim._tick()
    assert anim.current_input == 8
    assert anim.current_output == 12
    # Now update to lower values
    usage2 = UsageEvent(2, 0, 4, 0, 26)
    anim.update(usage2)
    # step_input = (2 - 8) * 0.5 = -3; step_output = (4 - 12) * 0.5 = -4
    anim._tick()
    assert anim.current_input == 5  # 8 + (-3)
    assert anim.current_output == 8  # 12 + (-4)
    anim._tick()
    assert anim.current_input == 2
    assert anim.current_output == 4


def test_start_and_stop_animation_task(event_loop: asyncio.AbstractEventLoop) -> None:
    # Use a short interval to ensure task runs at least once
    anim = TokenAnimator(interval=0.01, animation_duration=0.02)
    usage = UsageEvent(1, 0, 1, 0, 2)
    anim.update(usage)

    # Start the animation task within the event loop and then stop it
    async def stop_and_wait() -> None:
        anim.start()
        assert anim._task is not None
        await asyncio.sleep(0.02)
        anim.stop()
        # Await task completion; _run should catch CancelledError
        task = anim._task
        await task
        assert task.done()

    event_loop.run_until_complete(stop_and_wait())
