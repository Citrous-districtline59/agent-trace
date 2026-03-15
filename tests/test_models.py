"""Tests for trace data model."""

import json
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent_trace.models import EventType, SessionMeta, TraceEvent


class TestTraceEvent(unittest.TestCase):
    def test_create_tool_call_event(self):
        event = TraceEvent(
            event_type=EventType.TOOL_CALL,
            session_id="abc123",
            data={"tool_name": "read_file", "arguments": {"path": "/tmp/test.py"}},
        )
        self.assertEqual(event.event_type, EventType.TOOL_CALL)
        self.assertEqual(event.data["tool_name"], "read_file")
        self.assertIsNotNone(event.event_id)
        self.assertIsNotNone(event.timestamp)

    def test_serialize_roundtrip(self):
        event = TraceEvent(
            event_type=EventType.TOOL_CALL,
            session_id="abc123",
            data={"tool_name": "search", "arguments": {"query": "test"}},
        )
        json_str = event.to_json()
        parsed = TraceEvent.from_json(json_str)
        self.assertEqual(parsed.event_type, EventType.TOOL_CALL)
        self.assertEqual(parsed.data["tool_name"], "search")
        self.assertEqual(parsed.session_id, "abc123")

    def test_json_omits_empty_fields(self):
        event = TraceEvent(
            event_type=EventType.ERROR,
            data={"message": "something broke"},
        )
        json_str = event.to_json()
        d = json.loads(json_str)
        self.assertNotIn("parent_id", d)
        self.assertNotIn("duration_ms", d)
        self.assertNotIn("session_id", d)

    def test_all_event_types_valid(self):
        for et in EventType:
            event = TraceEvent(event_type=et, data={})
            json_str = event.to_json()
            parsed = TraceEvent.from_json(json_str)
            self.assertEqual(parsed.event_type, et)


class TestSessionMeta(unittest.TestCase):
    def test_create_session(self):
        meta = SessionMeta(agent_name="test-agent")
        self.assertIsNotNone(meta.session_id)
        self.assertEqual(meta.agent_name, "test-agent")
        self.assertEqual(meta.tool_calls, 0)

    def test_serialize_roundtrip(self):
        meta = SessionMeta(
            agent_name="test",
            tool_calls=5,
            llm_requests=3,
            errors=1,
        )
        json_str = meta.to_json()
        parsed = SessionMeta.from_json(json_str)
        self.assertEqual(parsed.agent_name, "test")
        self.assertEqual(parsed.tool_calls, 5)
        self.assertEqual(parsed.llm_requests, 3)
        self.assertEqual(parsed.errors, 1)


if __name__ == "__main__":
    unittest.main()
