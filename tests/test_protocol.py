"""Tests for src.protocol — node creation, DAG construction, serialization."""

import json
from datetime import datetime, timedelta

import pytest

from src.protocol import (
    Delay,
    FromType,
    NodeType,
    Protocol,
    Start,
    protocol_from_dict,
)


# ── Node creation ──────────────────────────────────────────────────────


class TestNodeCreation:
    def test_start_node_type(self):
        s = Start()
        assert s.node_type == NodeType.START

    def test_protocol_defaults(self):
        p = Protocol(name="P1")
        assert p.node_type == NodeType.PROTOCOL
        assert p.name == "P1"
        assert p.duration == timedelta(0)
        assert p.scheduled_time is None
        assert p.started_time is None
        assert p.finished_time is None

    def test_protocol_with_duration(self):
        p = Protocol(name="P1", duration=timedelta(minutes=10))
        assert p.duration == timedelta(minutes=10)

    def test_delay_defaults(self):
        d = Delay()
        assert d.node_type == NodeType.DELAY
        assert d.duration == timedelta(0)
        assert d.from_type == FromType.START
        assert d.offset == timedelta(0)

    def test_delay_with_params(self):
        d = Delay(
            duration=timedelta(seconds=30),
            from_type=FromType.FINISH,
            offset=timedelta(seconds=5),
        )
        assert d.duration == timedelta(seconds=30)
        assert d.from_type == FromType.FINISH
        assert d.offset == timedelta(seconds=5)

    def test_unique_ids(self):
        p1 = Protocol(name="P1")
        p2 = Protocol(name="P2")
        assert p1.id != p2.id


# ── DAG construction via > operator ───────────────────────────────────


class TestDAGConstruction:
    def test_simple_chain(self):
        s = Start()
        p1 = Protocol(name="P1")
        p2 = Protocol(name="P2")
        s > p1 > p2

        assert len(s.post_node) == 1
        assert s.post_node[0].id == p1.id
        assert len(p1.post_node) == 1
        assert p1.post_node[0].id == p2.id

    def test_gt_returns_top(self):
        s = Start()
        p1 = Protocol(name="P1")
        result = s > p1
        assert result.id == s.id

    def test_branching(self):
        s = Start()
        p1 = Protocol(name="P1")
        p2 = Protocol(name="P2")
        p3 = Protocol(name="P3")
        s > p1 > [p2, p3]

        assert len(p1.post_node) == 2
        names = {n.name for n in p1.post_node}
        assert names == {"P2", "P3"}

    def test_pre_node_link(self):
        s = Start()
        p1 = Protocol(name="P1")
        s > p1
        assert p1.pre_node is not None
        assert p1.pre_node.id == s.id

    def test_recursive_add_raises(self):
        s = Start()
        p1 = Protocol(name="P1")
        s > p1
        with pytest.raises(ValueError, match="recursive"):
            p1.add(s)

    def test_delay_in_chain(self):
        s = Start()
        p1 = Protocol(name="P1")
        d = Delay(duration=timedelta(seconds=5))
        p2 = Protocol(name="P2")
        s > p1 > d > p2

        assert p1.post_node[0].id == d.id
        assert d.post_node[0].id == p2.id


# ── flatten / get_node ────────────────────────────────────────────────


class TestTreeTraversal:
    def test_flatten_simple(self):
        s = Start()
        p1 = Protocol(name="P1")
        p2 = Protocol(name="P2")
        s > p1 > p2
        flat = s.flatten()
        assert len(flat) == 3

    def test_flatten_branching(self):
        s = Start()
        p1 = Protocol(name="P1")
        p2 = Protocol(name="P2")
        p3 = Protocol(name="P3")
        s > p1 > [p2, p3]
        flat = s.flatten()
        assert len(flat) == 4

    def test_get_node_found(self):
        s = Start()
        p1 = Protocol(name="P1")
        s > p1
        assert s.get_node(p1.id) is not None
        assert s.get_node(p1.id).name == "P1"

    def test_get_node_not_found(self):
        s = Start()
        import uuid

        assert s.get_node(uuid.uuid4()) is None


# ── top property ──────────────────────────────────────────────────────


class TestTopProperty:
    def test_top_from_leaf(self):
        s = Start()
        p1 = Protocol(name="P1")
        p2 = Protocol(name="P2")
        s > p1 > p2
        assert p2.top.id == s.id

    def test_top_from_root(self):
        s = Start()
        assert s.top.id == s.id


# ── Serialization roundtrip ──────────────────────────────────────────


class TestSerialization:
    def test_roundtrip_simple(self):
        s = Start()
        p1 = Protocol(name="P1", duration=timedelta(minutes=10))
        p2 = Protocol(name="P2", duration=timedelta(seconds=3))
        s > p1 > p2

        data = s.model_dump(mode="json")
        restored = protocol_from_dict(data)

        assert isinstance(restored, Start)
        assert len(restored.post_node) == 1
        assert restored.post_node[0].name == "P1"
        assert restored.post_node[0].duration == timedelta(minutes=10)

    def test_roundtrip_with_delay(self):
        s = Start()
        p1 = Protocol(name="P1", duration=timedelta(minutes=5))
        d = Delay(duration=timedelta(seconds=10), from_type=FromType.FINISH)
        p2 = Protocol(name="P2", duration=timedelta(seconds=2))
        s > p1 > d > p2

        data = s.model_dump(mode="json")
        json_str = json.dumps(data)
        restored = protocol_from_dict(json.loads(json_str))

        flat = restored.flatten()
        assert len(flat) == 4
        delays = [n for n in flat if isinstance(n, Delay)]
        assert len(delays) == 1
        assert delays[0].from_type == FromType.FINISH

    def test_roundtrip_preserves_pre_node(self):
        s = Start()
        p1 = Protocol(name="P1")
        s > p1

        data = s.model_dump(mode="json")
        restored = protocol_from_dict(data)
        # pre_node is re-linked by _link_children validator
        assert restored.post_node[0].pre_node is not None
        assert restored.post_node[0].pre_node.id == restored.id

    def test_roundtrip_with_times(self):
        s = Start()
        now = datetime(2025, 1, 1, 12, 0, 0)
        p1 = Protocol(
            name="P1",
            duration=timedelta(minutes=10),
            scheduled_time=now,
            started_time=now,
            finished_time=now + timedelta(minutes=10),
        )
        s > p1

        data = s.model_dump(mode="json")
        restored = protocol_from_dict(data)
        rp = restored.post_node[0]
        assert rp.scheduled_time is not None
        assert rp.started_time is not None
        assert rp.finished_time is not None

    def test_roundtrip_branching(self):
        s = Start()
        p1 = Protocol(name="P1")
        p2 = Protocol(name="P2")
        d = Delay(duration=timedelta(seconds=5))
        p3 = Protocol(name="P3")
        s > p1 > [p2, d > p3]

        data = s.model_dump(mode="json")
        restored = protocol_from_dict(data)
        flat = restored.flatten()
        assert len(flat) == 5
        names = {n.name for n in flat if isinstance(n, Protocol)}
        assert names == {"P1", "P2", "P3"}


# ── __str__ ───────────────────────────────────────────────────────────


class TestStr:
    def test_start_str(self):
        s = Start()
        assert "Start()" in str(s)

    def test_protocol_str(self):
        p = Protocol(name="P1", duration=timedelta(minutes=5))
        assert "P1" in str(p)

    def test_delay_str(self):
        d = Delay(duration=timedelta(seconds=10))
        assert "Delay" in str(d)
