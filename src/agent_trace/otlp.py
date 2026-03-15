"""OTLP/HTTP JSON exporter.

Converts agent-trace sessions to OpenTelemetry spans and sends them
to any OTLP-compatible collector over HTTP/JSON. Zero dependencies.

Each agent-trace session becomes an OTel trace. Tool calls become spans.
User prompts and assistant responses become events on the root span.

Works with: Datadog, Honeycomb, New Relic, Splunk, Grafana Tempo, Jaeger.

Usage:
    agent-strace export <session-id> --format otlp --endpoint http://localhost:4318
    agent-strace export <session-id> --format otlp --endpoint https://api.honeycomb.io
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
import time
import urllib.request
import urllib.error
from typing import Any

from .models import EventType, SessionMeta, TraceEvent
from .store import TraceStore


def _to_trace_id(session_id: str) -> str:
    """Convert session ID to a 32-hex-char trace ID."""
    h = hashlib.sha256(session_id.encode()).hexdigest()
    return h[:32]


def _to_span_id(event_id: str) -> str:
    """Convert event ID to a 16-hex-char span ID."""
    h = hashlib.sha256(event_id.encode()).hexdigest()
    return h[:16]


def _ts_to_nanos(ts: float) -> str:
    """Convert Unix timestamp to nanoseconds as string."""
    return str(int(ts * 1_000_000_000))


def _duration_to_nanos(ms: float | None) -> int:
    """Convert milliseconds to nanoseconds."""
    if ms is None or ms <= 0:
        return 1_000_000  # 1ms default
    return int(ms * 1_000_000)


def _make_attributes(data: dict) -> list[dict]:
    """Convert a flat dict to OTel attribute format."""
    attrs = []
    for key, value in data.items():
        if isinstance(value, bool):
            attrs.append({"key": key, "value": {"boolValue": value}})
        elif isinstance(value, int):
            attrs.append({"key": key, "value": {"intValue": str(value)}})
        elif isinstance(value, float):
            attrs.append({"key": key, "value": {"doubleValue": value}})
        elif isinstance(value, str):
            attrs.append({"key": key, "value": {"stringValue": value}})
        elif isinstance(value, dict):
            attrs.append({"key": key, "value": {"stringValue": json.dumps(value)}})
        elif isinstance(value, list):
            attrs.append({"key": key, "value": {"stringValue": json.dumps(value)}})
        else:
            attrs.append({"key": key, "value": {"stringValue": str(value)}})
    return attrs


def _make_event(name: str, timestamp: float, data: dict) -> dict:
    """Create an OTel span event."""
    return {
        "timeUnixNano": _ts_to_nanos(timestamp),
        "name": name,
        "attributes": _make_attributes(data),
    }


def session_to_otlp(
    meta: SessionMeta,
    events: list[TraceEvent],
    service_name: str = "agent-trace",
) -> dict:
    """Convert an agent-trace session to OTLP JSON trace format.

    Returns the full ExportTraceServiceRequest body ready to POST.
    """
    trace_id = _to_trace_id(meta.session_id)

    # Root span covers the entire session
    root_span_id = _to_span_id(f"root-{meta.session_id}")
    root_start = _ts_to_nanos(meta.started_at)
    root_end = _ts_to_nanos(meta.ended_at or (meta.started_at + (meta.total_duration_ms or 0) / 1000))

    root_attrs = _make_attributes({
        "agent.name": meta.agent_name or "unknown",
        "agent.command": meta.command or "",
        "agent.session_id": meta.session_id,
        "agent.tool_calls": meta.tool_calls,
        "agent.llm_requests": meta.llm_requests,
        "agent.errors": meta.errors,
    })

    # Collect span events (user prompts, assistant responses, decisions)
    # and child spans (tool calls, errors)
    root_events = []
    child_spans = []

    # Track tool_call events so we can pair them with tool_result
    pending_calls: dict[str, TraceEvent] = {}

    for event in events:
        if event.event_type == EventType.USER_PROMPT:
            root_events.append(_make_event(
                "user_prompt",
                event.timestamp,
                {"prompt": event.data.get("prompt", "")},
            ))

        elif event.event_type == EventType.ASSISTANT_RESPONSE:
            text = event.data.get("text", "")
            if len(text) > 500:
                text = text[:500] + "..."
            root_events.append(_make_event(
                "assistant_response",
                event.timestamp,
                {"text": text},
            ))

        elif event.event_type == EventType.DECISION:
            root_events.append(_make_event(
                "decision",
                event.timestamp,
                event.data,
            ))

        elif event.event_type == EventType.TOOL_CALL:
            pending_calls[event.event_id] = event

        elif event.event_type == EventType.TOOL_RESULT:
            # Find the matching tool_call
            call_event = None
            if event.parent_id and event.parent_id in pending_calls:
                call_event = pending_calls.pop(event.parent_id)

            tool_name = event.data.get("tool_name", "") or (
                call_event.data.get("tool_name", "tool") if call_event else "tool"
            )
            span_start = call_event.timestamp if call_event else event.timestamp
            duration_ns = _duration_to_nanos(event.duration_ms)

            span_attrs = {"tool.name": tool_name}
            if call_event:
                args = call_event.data.get("arguments", {})
                if args:
                    for k, v in args.items():
                        span_attrs[f"tool.input.{k}"] = str(v)[:200]

            result = event.data.get("result", "")
            if result:
                span_attrs["tool.output"] = str(result)[:500]

            child_spans.append({
                "traceId": trace_id,
                "spanId": _to_span_id(call_event.event_id if call_event else event.event_id),
                "parentSpanId": root_span_id,
                "name": tool_name,
                "kind": 1,  # SPAN_KIND_INTERNAL
                "startTimeUnixNano": _ts_to_nanos(span_start),
                "endTimeUnixNano": _ts_to_nanos(span_start + duration_ns / 1_000_000_000),
                "attributes": _make_attributes(span_attrs),
                "status": {"code": 1},  # STATUS_CODE_OK
            })

        elif event.event_type == EventType.ERROR:
            # Find the matching tool_call
            call_event = None
            if event.parent_id and event.parent_id in pending_calls:
                call_event = pending_calls.pop(event.parent_id)

            tool_name = event.data.get("tool_name", "error")
            error_msg = event.data.get("error", "") or event.data.get("message", "")
            span_start = call_event.timestamp if call_event else event.timestamp
            duration_ns = _duration_to_nanos(event.duration_ms)

            span_attrs = {"tool.name": tool_name}
            if error_msg:
                span_attrs["error.message"] = str(error_msg)[:500]
            if call_event:
                args = call_event.data.get("arguments", {})
                if args:
                    for k, v in args.items():
                        span_attrs[f"tool.input.{k}"] = str(v)[:200]

            child_spans.append({
                "traceId": trace_id,
                "spanId": _to_span_id(call_event.event_id if call_event else event.event_id),
                "parentSpanId": root_span_id,
                "name": tool_name,
                "kind": 1,
                "startTimeUnixNano": _ts_to_nanos(span_start),
                "endTimeUnixNano": _ts_to_nanos(span_start + duration_ns / 1_000_000_000),
                "attributes": _make_attributes(span_attrs),
                "status": {"code": 2, "message": str(error_msg)[:200]},  # STATUS_CODE_ERROR
                "events": [_make_event("exception", event.timestamp, {
                    "exception.message": str(error_msg)[:500],
                })],
            })

        elif event.event_type in (EventType.LLM_REQUEST, EventType.LLM_RESPONSE):
            root_events.append(_make_event(
                event.event_type.value,
                event.timestamp,
                event.data,
            ))

    # Emit any unmatched tool_calls as spans (no result received)
    for call_event in pending_calls.values():
        tool_name = call_event.data.get("tool_name", "tool")
        child_spans.append({
            "traceId": trace_id,
            "spanId": _to_span_id(call_event.event_id),
            "parentSpanId": root_span_id,
            "name": tool_name,
            "kind": 1,
            "startTimeUnixNano": _ts_to_nanos(call_event.timestamp),
            "endTimeUnixNano": _ts_to_nanos(call_event.timestamp + 0.001),
            "attributes": _make_attributes({
                "tool.name": tool_name,
                **{f"tool.input.{k}": str(v)[:200] for k, v in call_event.data.get("arguments", {}).items()},
            }),
            "status": {"code": 0},  # STATUS_CODE_UNSET
        })

    # Build root span
    root_span = {
        "traceId": trace_id,
        "spanId": root_span_id,
        "name": f"agent-session ({meta.agent_name or 'agent'})",
        "kind": 1,
        "startTimeUnixNano": root_start,
        "endTimeUnixNano": root_end,
        "attributes": root_attrs,
        "events": root_events,
        "status": {"code": 2 if meta.errors > 0 else 1},
    }

    all_spans = [root_span] + child_spans

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": _make_attributes({
                    "service.name": service_name,
                    "service.version": "agent-trace",
                    "agent.session_id": meta.session_id,
                }),
            },
            "scopeSpans": [{
                "scope": {
                    "name": "agent-trace",
                },
                "spans": all_spans,
            }],
        }],
    }


def export_otlp(
    store: TraceStore,
    session_id: str,
    endpoint: str,
    headers: dict[str, str] | None = None,
    service_name: str = "agent-trace",
) -> bool:
    """Export a session to an OTLP/HTTP endpoint.

    Args:
        store: TraceStore to load session from
        session_id: Session to export
        endpoint: OTLP collector URL (e.g. http://localhost:4318)
        headers: Extra HTTP headers (for auth tokens, API keys)
        service_name: OTel service name

    Returns:
        True if export succeeded
    """
    meta = store.load_meta(session_id)
    if not meta:
        sys.stderr.write(f"Session {session_id} not found\n")
        return False

    events = store.load_events(session_id)
    if not events:
        sys.stderr.write(f"No events for session {session_id}\n")
        return False

    payload = session_to_otlp(meta, events, service_name)
    body = json.dumps(payload).encode("utf-8")

    # POST to /v1/traces
    url = endpoint.rstrip("/") + "/v1/traces"

    req_headers = {
        "Content-Type": "application/json",
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            if status in (200, 202):
                sys.stderr.write(f"Exported {len(events)} events to {url} (HTTP {status})\n")
                return True
            else:
                sys.stderr.write(f"OTLP export returned HTTP {status}\n")
                return False
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"OTLP export failed: HTTP {e.code} {e.reason}\n")
        body = e.read().decode("utf-8", errors="replace")[:200]
        if body:
            sys.stderr.write(f"  {body}\n")
        return False
    except urllib.error.URLError as e:
        sys.stderr.write(f"OTLP export failed: {e.reason}\n")
        return False
