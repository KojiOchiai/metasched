"""Tests for src.awaitlist — async task scheduling."""

import uuid
from datetime import datetime, timedelta

import pytest

from src.awaitlist import ATask, AwaitList


# ── ATask model ───────────────────────────────────────────────────────


class TestATask:
    def test_creation(self):
        now = datetime.now()
        task = ATask(execution_time=now, id=uuid.uuid4(), content="test")
        assert task.content == "test"
        assert task.execution_time == now


# ── AwaitList ─────────────────────────────────────────────────────────


class TestAwaitList:
    @pytest.mark.asyncio
    async def test_add_task(self):
        al = AwaitList()
        now = datetime.now()
        task = await al.add_task(now, "task1")
        assert task.content == "task1"
        assert len(al.get_tasks()) == 1

    @pytest.mark.asyncio
    async def test_add_task_sorted(self):
        al = AwaitList()
        t1 = datetime.now() + timedelta(seconds=10)
        t2 = datetime.now() + timedelta(seconds=5)
        await al.add_task(t1, "later")
        await al.add_task(t2, "sooner")
        tasks = al.get_tasks()
        assert tasks[0].content == "sooner"
        assert tasks[1].content == "later"

    @pytest.mark.asyncio
    async def test_add_duplicate_id_raises(self):
        al = AwaitList()
        task_id = uuid.uuid4()
        await al.add_task(datetime.now(), "task1", id=task_id)
        with pytest.raises(ValueError, match="already exists"):
            await al.add_task(datetime.now(), "task2", id=task_id)

    @pytest.mark.asyncio
    async def test_cancel_task(self):
        al = AwaitList()
        task = await al.add_task(datetime.now(), "task1")
        assert await al.cancel_task(task.id) is True
        assert len(al.get_tasks()) == 0

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self):
        al = AwaitList()
        assert await al.cancel_task(uuid.uuid4()) is False

    @pytest.mark.asyncio
    async def test_update_task(self):
        al = AwaitList()
        task = await al.add_task(datetime.now(), "old")
        new_time = datetime.now() + timedelta(seconds=60)
        result = await al.update_task(task.id, new_time, "new")
        assert result is True
        updated = al.get_tasks()[0]
        assert updated.content == "new"
        assert updated.execution_time == new_time

    @pytest.mark.asyncio
    async def test_update_nonexistent(self):
        al = AwaitList()
        result = await al.update_task(uuid.uuid4(), datetime.now(), "x")
        assert result is False

    @pytest.mark.asyncio
    async def test_to_dict_from_dict(self):
        al = AwaitList()
        t1 = datetime(2025, 1, 1, 12, 0, 0)
        t2 = datetime(2025, 1, 1, 12, 5, 0)
        await al.add_task(t1, "task1")
        await al.add_task(t2, "task2")

        data = al.to_dict()
        restored = AwaitList.from_dict(data)
        assert len(restored.get_tasks()) == 2
        assert restored.get_tasks()[0].content == "task1"

    @pytest.mark.asyncio
    async def test_wait_for_next_task_yields_ready(self):
        """Tasks with past execution time should be yielded immediately."""
        al = AwaitList()
        past = datetime.now() - timedelta(seconds=1)
        await al.add_task(past, "ready")
        await al.mark_done()

        results = []
        async for task in al.wait_for_next_task():
            results.append(task)
        assert len(results) == 1
        assert results[0].content == "ready"

    @pytest.mark.asyncio
    async def test_wait_for_next_task_empty_done(self):
        """Empty + done should exit immediately."""
        al = AwaitList()
        await al.mark_done()
        results = []
        async for task in al.wait_for_next_task():
            results.append(task)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_wait_respects_order(self):
        """Multiple past tasks should be yielded in time order."""
        al = AwaitList()
        base = datetime.now() - timedelta(seconds=10)
        await al.add_task(base + timedelta(seconds=2), "second")
        await al.add_task(base, "first")
        await al.add_task(base + timedelta(seconds=4), "third")
        await al.mark_done()

        results = []
        async for task in al.wait_for_next_task():
            results.append(task.content)
        assert results == ["first", "second", "third"]
