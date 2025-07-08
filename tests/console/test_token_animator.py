import asyncio

from oai_coding_agent.agent.events import UsageEvent
from oai_coding_agent.console.token_animator import TokenAnimator


def test_initial_state_before_update() -> None:
    anim = TokenAnimator()
    assert anim.current_input == 0
    assert anim.current_output == 0
    assert anim.total_tokens == 0


def test_format_count_small_and_large() -> None:
    assert TokenAnimator.format_count(42) == "42"
    assert TokenAnimator.format_count(999) == "999"
    assert TokenAnimator.format_count(1000) == "1k"
    assert TokenAnimator.format_count(1200) == "1.2k"
    assert TokenAnimator.format_count(12000) == "12k"
    assert TokenAnimator.format_count(12500) == "12.5k"


def test_update_sets_targets_and_total_tokens() -> None:
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
    # Target values should be set
    assert anim._target_input == 100
    assert anim._target_output == 50


def test_ease_out_animation_advances_to_target() -> None:
    anim = TokenAnimator(interval=0.1, animation_duration=0.2)
    usage = UsageEvent(
        input_tokens=100,
        cached_input_tokens=0,
        output_tokens=200,
        reasoning_output_tokens=0,
        total_tokens=300,
    )
    anim.update(usage)

    # First tick should move approximately 10% of the distance
    anim._tick()
    assert 9 <= anim.current_input <= 11  # ~10% of 100
    assert 19 <= anim.current_output <= 21  # ~10% of 200

    # Second tick should move approximately 10% of remaining distance
    anim._tick()
    assert 18 <= anim.current_input <= 20  # ~19
    assert 36 <= anim.current_output <= 40  # ~38

    # Eventually reaches target (or gets very close)
    for _ in range(50):  # More than enough ticks to reach target
        anim._tick()
    assert abs(anim.current_input - 100) <= 1
    assert abs(anim.current_output - 200) <= 1


def test_ease_out_decrement_animation() -> None:
    anim = TokenAnimator(interval=0.1, animation_duration=0.2)
    # First update to a higher value
    usage1 = UsageEvent(80, 0, 120, 0, 200)
    anim.update(usage1)
    # Complete initial increase
    for _ in range(50):
        anim._tick()
    assert abs(anim.current_input - 80) <= 1
    assert abs(anim.current_output - 120) <= 1

    # Now update to lower values
    usage2 = UsageEvent(20, 0, 40, 0, 260)
    anim.update(usage2)

    # First tick moves approximately 10% of the distance down
    anim._tick()
    assert 73 <= anim.current_input <= 75  # ~74
    assert 111 <= anim.current_output <= 113  # ~112

    # Eventually reaches lower target (or gets very close)
    for _ in range(50):
        anim._tick()
    assert abs(anim.current_input - 20) <= 1
    assert abs(anim.current_output - 40) <= 1


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
