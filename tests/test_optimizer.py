"""Tests for src.optimizer — schedule optimization with CP-SAT solver."""

from datetime import datetime, timedelta

import pytest

from src.optimizer import (
    Optimizer,
    TimeSecondsConverter,
    get_oldest_time,
    sum_durations,
)
from src.protocol import Delay, FromType, Protocol, Start


# ── Helper utilities ──────────────────────────────────────────────────


class TestTimeSecondsConverter:
    def test_roundtrip(self):
        base = datetime(2025, 1, 1, 12, 0, 0)
        tsc = TimeSecondsConverter(base)
        assert tsc.seconds_to_time(tsc.time_to_seconds(base)) == base

    def test_offset(self):
        base = datetime(2025, 1, 1, 12, 0, 0)
        tsc = TimeSecondsConverter(base)
        assert tsc.time_to_seconds(base + timedelta(seconds=60)) == 60.0
        assert tsc.seconds_to_time(120) == base + timedelta(seconds=120)


class TestGetOldestTime:
    def test_with_started_times(self):
        t1 = datetime(2025, 1, 1, 12, 0, 0)
        t2 = datetime(2025, 1, 1, 12, 5, 0)
        p1 = Protocol(name="P1", started_time=t1)
        p2 = Protocol(name="P2", started_time=t2)
        oldest = get_oldest_time([p1, p2])
        assert oldest == t1

    def test_without_started_times(self):
        p1 = Protocol(name="P1")
        # Should return approximately now
        result = get_oldest_time([p1])
        assert (datetime.now() - result).total_seconds() < 2


class TestSumDurations:
    def test_sum(self):
        p1 = Protocol(name="P1", duration=timedelta(minutes=10))
        p2 = Protocol(name="P2", duration=timedelta(seconds=30))
        d = Delay(duration=timedelta(seconds=5))
        s = Start()
        total = sum_durations([s, p1, p2, d])
        assert total == 10 * 60 + 30 + 5

    def test_empty(self):
        assert sum_durations([]) == 0


# ── Optimizer ─────────────────────────────────────────────────────────


class TestOptimizer:
    def test_simple_chain_assigns_times(self):
        """Two protocols in sequence should get scheduled times."""
        s = Start()
        p1 = Protocol(name="P1", duration=timedelta(seconds=10))
        p2 = Protocol(name="P2", duration=timedelta(seconds=5))
        s > p1 > p2

        opt = Optimizer(buffer_seconds=0)
        status = opt.optimize_schedule(s)
        assert status in ("OPTIMAL", "FEASIBLE")
        assert p1.scheduled_time is not None
        assert p2.scheduled_time is not None

    def test_ordering_constraint(self):
        """p2 must start after p1 finishes."""
        s = Start()
        p1 = Protocol(name="P1", duration=timedelta(seconds=10))
        p2 = Protocol(name="P2", duration=timedelta(seconds=5))
        s > p1 > p2

        Optimizer(buffer_seconds=0).optimize_schedule(s)
        assert p2.scheduled_time >= p1.scheduled_time + p1.duration

    def test_no_overlap(self):
        """Parallel branches should not overlap (NoOverlap constraint)."""
        s = Start()
        p1 = Protocol(name="P1", duration=timedelta(seconds=10))
        p2 = Protocol(name="P2", duration=timedelta(seconds=5))
        p3 = Protocol(name="P3", duration=timedelta(seconds=5))
        s > p1 > [p2, p3]

        Optimizer(buffer_seconds=0).optimize_schedule(s)

        # p2 and p3 intervals must not overlap
        p2_end = p2.scheduled_time + p2.duration
        p3_end = p3.scheduled_time + p3.duration
        assert p2.scheduled_time >= p3_end or p3.scheduled_time >= p2_end

    def test_delay_respected(self):
        """Delay between p1 and p2 should be approximately the delay duration."""
        s = Start()
        p1 = Protocol(name="P1", duration=timedelta(seconds=10))
        d = Delay(duration=timedelta(seconds=30), from_type=FromType.FINISH)
        p2 = Protocol(name="P2", duration=timedelta(seconds=5))
        s > p1 > d > p2

        Optimizer(buffer_seconds=0, time_loss_weight=100).optimize_schedule(s)

        gap = (p2.scheduled_time - (p1.scheduled_time + p1.duration)).total_seconds()
        # Gap should be close to delay duration (30s)
        assert abs(gap - 30) <= 1

    def test_buffer_seconds(self):
        """Buffer adds padding to protocol durations."""
        s = Start()
        p1 = Protocol(name="P1", duration=timedelta(seconds=10))
        p2 = Protocol(name="P2", duration=timedelta(seconds=5))
        s > p1 > p2

        Optimizer(buffer_seconds=5).optimize_schedule(s)
        gap = (p2.scheduled_time - p1.scheduled_time).total_seconds()
        # p1 effective duration = 10 + 5 = 15
        assert gap >= 15

    def test_delay_shorter_than_buffer_raises(self):
        """Delay duration shorter than buffer should raise ValueError."""
        s = Start()
        p1 = Protocol(name="P1", duration=timedelta(seconds=10))
        d = Delay(duration=timedelta(seconds=2))
        p2 = Protocol(name="P2", duration=timedelta(seconds=5))
        s > p1 > d > p2

        with pytest.raises(ValueError, match="shorter than buffer"):
            Optimizer(buffer_seconds=5).optimize_schedule(s)

    def test_with_already_started(self):
        """Optimizer handles already-started protocols (pins their times)."""
        s = Start()
        now = datetime(2025, 1, 1, 12, 0, 0)
        p1 = Protocol(
            name="P1",
            duration=timedelta(seconds=10),
            started_time=now,
            finished_time=now + timedelta(seconds=10),
        )
        p2 = Protocol(name="P2", duration=timedelta(seconds=5))
        s > p1 > p2

        Optimizer(buffer_seconds=0).optimize_schedule(s)
        # p1 should remain pinned
        assert p1.scheduled_time == now
        assert p2.scheduled_time >= now + timedelta(seconds=10)

    def test_makespan_minimized(self):
        """Optimizer should produce a compact schedule."""
        s = Start()
        p1 = Protocol(name="P1", duration=timedelta(seconds=10))
        p2 = Protocol(name="P2", duration=timedelta(seconds=10))
        p3 = Protocol(name="P3", duration=timedelta(seconds=10))
        s > p1 > p2 > p3

        Optimizer(buffer_seconds=0).optimize_schedule(s)
        total = (p3.scheduled_time + p3.duration - p1.scheduled_time).total_seconds()
        # Minimum possible makespan is 30s
        assert total == 30

    def test_complex_dag(self):
        """Test a more complex DAG structure similar to sample protocols."""
        s = Start()
        p1 = Protocol(name="P1", duration=timedelta(seconds=10))
        p2 = Protocol(name="P2", duration=timedelta(seconds=5))
        d = Delay(duration=timedelta(seconds=20), from_type=FromType.FINISH)
        p3 = Protocol(name="P3", duration=timedelta(seconds=5))
        s > p1 > [p2, d > p3]

        status = Optimizer(buffer_seconds=0).optimize_schedule(s)
        assert status in ("OPTIMAL", "FEASIBLE")
        # All protocols should have scheduled times
        for p in [p1, p2, p3]:
            assert p.scheduled_time is not None
