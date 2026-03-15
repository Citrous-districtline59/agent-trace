"""Tests for trace storage."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent_trace.models import EventType, SessionMeta, TraceEvent
from agent_trace.store import TraceStore


class TestTraceStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = TraceStore(self.tmpdir)

    def test_create_and_load_session(self):
        meta = SessionMeta(agent_name="test-agent")
        self.store.create_session(meta)

        loaded = self.store.load_meta(meta.session_id)
        self.assertEqual(loaded.agent_name, "test-agent")
        self.assertEqual(loaded.session_id, meta.session_id)

    def test_append_and_load_events(self):
        meta = SessionMeta()
        self.store.create_session(meta)

        e1 = TraceEvent(
            event_type=EventType.TOOL_CALL,
            session_id=meta.session_id,
            data={"tool_name": "read_file"},
        )
        e2 = TraceEvent(
            event_type=EventType.TOOL_RESULT,
            session_id=meta.session_id,
            parent_id=e1.event_id,
            duration_ms=42.5,
            data={"content_preview": "hello world"},
        )

        self.store.append_event(meta.session_id, e1)
        self.store.append_event(meta.session_id, e2)

        events = self.store.load_events(meta.session_id)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].event_type, EventType.TOOL_CALL)
        self.assertEqual(events[1].parent_id, e1.event_id)
        self.assertAlmostEqual(events[1].duration_ms, 42.5)

    def test_list_sessions(self):
        m1 = SessionMeta(agent_name="first")
        m2 = SessionMeta(agent_name="second")
        self.store.create_session(m1)
        self.store.create_session(m2)

        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 2)

    def test_find_session_by_prefix(self):
        meta = SessionMeta()
        self.store.create_session(meta)

        prefix = meta.session_id[:6]
        found = self.store.find_session(prefix)
        self.assertEqual(found, meta.session_id)

    def test_find_session_not_found(self):
        found = self.store.find_session("nonexistent")
        self.assertIsNone(found)

    def test_session_exists(self):
        meta = SessionMeta()
        self.store.create_session(meta)

        self.assertTrue(self.store.session_exists(meta.session_id))
        self.assertFalse(self.store.session_exists("fake"))

    def test_update_meta(self):
        meta = SessionMeta(agent_name="test")
        self.store.create_session(meta)

        meta.tool_calls = 10
        meta.errors = 2
        self.store.update_meta(meta)

        loaded = self.store.load_meta(meta.session_id)
        self.assertEqual(loaded.tool_calls, 10)
        self.assertEqual(loaded.errors, 2)

    def test_empty_events(self):
        meta = SessionMeta()
        self.store.create_session(meta)

        events = self.store.load_events(meta.session_id)
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
