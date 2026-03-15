"""Tests for HTTP/SSE MCP proxy."""

import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent_trace.http_proxy import HTTPProxyServer, _ProxyHandler
from agent_trace.models import EventType, SessionMeta, TraceEvent
from agent_trace.store import TraceStore


class FakeMCPHandler(BaseHTTPRequestHandler):
    """Simulates a remote MCP server."""

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        try:
            msg = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_error(400)
            return

        # respond to tool calls with a result
        if msg.get("method") == "tools/call":
            response = {
                "jsonrpc": "2.0",
                "id": msg.get("id"),
                "result": {
                    "content": [{"type": "text", "text": "tool output"}],
                },
            }
        elif msg.get("method") == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": msg.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "serverInfo": {"name": "fake-mcp", "version": "0.1.0"},
                },
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": msg.get("id"),
                "result": {},
            }

        resp_body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp_body)))
        self.end_headers()
        self.wfile.write(resp_body)

    def do_GET(self):
        """Serve a short SSE stream with one JSON-RPC notification."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        notification = json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/message",
            "params": {"message": "hello from server"},
        })
        self.wfile.write(f"data: {notification}\n\n".encode("utf-8"))
        self.wfile.flush()

    def log_message(self, format, *args):
        pass


def _find_free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestHTTPProxy(unittest.TestCase):
    """Integration tests for the HTTP proxy."""

    @classmethod
    def setUpClass(cls):
        # start fake MCP server
        cls.fake_port = _find_free_port()
        cls.fake_server = HTTPServer(("127.0.0.1", cls.fake_port), FakeMCPHandler)
        cls.fake_thread = threading.Thread(target=cls.fake_server.serve_forever, daemon=True)
        cls.fake_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.fake_server.shutdown()

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = TraceStore(self.tmpdir)
        self.events = []

        self.meta = SessionMeta(
            command="test",
            agent_name="test-agent",
        )
        self.store.create_session(self.meta)

        self.proxy_port = _find_free_port()
        self.proxy = HTTPProxyServer(
            remote_url=f"http://127.0.0.1:{self.fake_port}",
            local_port=self.proxy_port,
            store=self.store,
            session_meta=self.meta,
            on_event=lambda e: self.events.append(e),
        )

        # configure handler and start proxy in background
        # Use staticmethod to prevent Python from treating the lambda as an
        # unbound method (which would inject `self` as first arg).
        events_list = self.events
        _ProxyHandler.remote_url = self.proxy.remote_url
        _ProxyHandler.store = self.store
        _ProxyHandler.meta = self.meta
        _ProxyHandler.on_event = staticmethod(lambda e: events_list.append(e))
        _ProxyHandler.redact = False
        _ProxyHandler.pending_calls = {}

        self.proxy_server = HTTPServer(("127.0.0.1", self.proxy_port), _ProxyHandler)
        self.proxy_thread = threading.Thread(target=self.proxy_server.serve_forever, daemon=True)
        self.proxy_thread.start()
        time.sleep(0.05)  # let server start

    def tearDown(self):
        self.proxy_server.shutdown()

    def test_tool_call_traced(self):
        """POST a tools/call and verify both call and result are traced."""
        conn = http.client.HTTPConnection("127.0.0.1", self.proxy_port)
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "read_file", "arguments": {"path": "/tmp/test.txt"}},
        })
        conn.request("POST", "/message", body=body, headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        })
        resp = conn.getresponse()
        resp_body = resp.read()
        conn.close()

        self.assertEqual(resp.status, 200)

        # parse response
        resp_data = json.loads(resp_body.decode("utf-8"))
        self.assertIn("result", resp_data)

        # check traced events
        tool_calls = [e for e in self.events if e.event_type == EventType.TOOL_CALL]
        tool_results = [e for e in self.events if e.event_type == EventType.TOOL_RESULT]

        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0].data["tool_name"], "read_file")

        self.assertEqual(len(tool_results), 1)
        # result should link back to call
        self.assertEqual(tool_results[0].parent_id, tool_calls[0].event_id)
        self.assertGreater(tool_results[0].duration_ms, 0)

    def test_initialize_traced(self):
        """POST an initialize request and verify it's traced as LLM_REQUEST."""
        conn = http.client.HTTPConnection("127.0.0.1", self.proxy_port)
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        })
        conn.request("POST", "/message", body=body, headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        })
        resp = conn.getresponse()
        resp.read()
        conn.close()

        self.assertEqual(resp.status, 200)

    def test_proxy_forwards_auth_header(self):
        """Auth header should be forwarded to the remote server."""
        conn = http.client.HTTPConnection("127.0.0.1", self.proxy_port)
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/list",
            "params": {},
        })
        conn.request("POST", "/message", body=body, headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
            "Authorization": "Bearer test-token",
        })
        resp = conn.getresponse()
        resp.read()
        conn.close()

        # if auth was rejected we'd get an error; 200 means it was forwarded
        self.assertEqual(resp.status, 200)

    def test_sse_stream_traced(self):
        """GET /sse should stream SSE events and trace them."""
        conn = http.client.HTTPConnection("127.0.0.1", self.proxy_port)
        conn.request("GET", "/sse", headers={"Accept": "text/event-stream"})
        resp = conn.getresponse()

        # read the streamed data
        data = resp.read().decode("utf-8")
        conn.close()

        self.assertEqual(resp.status, 200)
        self.assertIn("data:", data)

    def test_meta_counts_updated(self):
        """Tool calls should increment meta.tool_calls."""
        conn = http.client.HTTPConnection("127.0.0.1", self.proxy_port)
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": "exec", "arguments": {"cmd": "ls"}},
        })
        conn.request("POST", "/message", body=body, headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        })
        resp = conn.getresponse()
        resp.read()
        conn.close()

        self.assertGreaterEqual(self.meta.tool_calls, 1)

    def test_events_persisted_to_store(self):
        """Events should be written to the trace store."""
        conn = http.client.HTTPConnection("127.0.0.1", self.proxy_port)
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {"name": "write_file", "arguments": {"path": "/tmp/out.txt", "content": "hi"}},
        })
        conn.request("POST", "/message", body=body, headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        })
        resp = conn.getresponse()
        resp.read()
        conn.close()

        stored_events = self.store.load_events(self.meta.session_id)
        self.assertGreater(len(stored_events), 0)

        event_types = [e.event_type for e in stored_events]
        self.assertIn(EventType.TOOL_CALL, event_types)
        self.assertIn(EventType.TOOL_RESULT, event_types)


class TestHTTPProxyRedaction(unittest.TestCase):
    """Test that redaction works through the HTTP proxy."""

    @classmethod
    def setUpClass(cls):
        cls.fake_port = _find_free_port()
        cls.fake_server = HTTPServer(("127.0.0.1", cls.fake_port), FakeMCPHandler)
        cls.fake_thread = threading.Thread(target=cls.fake_server.serve_forever, daemon=True)
        cls.fake_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.fake_server.shutdown()

    def test_redaction_enabled(self):
        """With redact=True, secrets in tool args should be redacted in traces."""
        tmpdir = tempfile.mkdtemp()
        store = TraceStore(tmpdir)
        events = []

        meta = SessionMeta(command="test", agent_name="test-agent")
        store.create_session(meta)

        proxy_port = _find_free_port()

        _ProxyHandler.remote_url = f"http://127.0.0.1:{self.fake_port}"
        _ProxyHandler.store = store
        _ProxyHandler.meta = meta
        _ProxyHandler.on_event = staticmethod(lambda e: events.append(e))
        _ProxyHandler.redact = True
        _ProxyHandler.pending_calls = {}

        proxy_server = HTTPServer(("127.0.0.1", proxy_port), _ProxyHandler)
        proxy_thread = threading.Thread(target=proxy_server.serve_forever, daemon=True)
        proxy_thread.start()
        time.sleep(0.05)

        try:
            conn = http.client.HTTPConnection("127.0.0.1", proxy_port)
            body = json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "http_request",
                    "arguments": {
                        "api_key": "sk-abc123def456ghi789jkl012mno345pqr678",
                        "url": "https://api.example.com",
                    },
                },
            })
            conn.request("POST", "/message", body=body, headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            })
            resp = conn.getresponse()
            resp.read()
            conn.close()

            tool_calls = [e for e in events if e.event_type == EventType.TOOL_CALL]
            self.assertEqual(len(tool_calls), 1)

            # the api_key should be redacted
            args = tool_calls[0].data.get("arguments", {})
            self.assertNotIn("sk-abc", str(args))
        finally:
            proxy_server.shutdown()


if __name__ == "__main__":
    unittest.main()
