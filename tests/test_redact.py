"""Tests for secret redaction."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent_trace.redact import REDACTED, redact_data, redact_value


class TestRedactValue(unittest.TestCase):
    def test_openai_key(self):
        result = redact_value("sk-abc123def456ghi789jkl012mno345pqr678")
        self.assertEqual(result, REDACTED)

    def test_github_token(self):
        result = redact_value("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl")
        self.assertEqual(result, REDACTED)

    def test_github_pat(self):
        result = redact_value("github_pat_ABCDEFGHIJKLMNOPQRSTUV_1234567890")
        self.assertEqual(result, REDACTED)

    def test_aws_key(self):
        result = redact_value("AKIAIOSFODNN7EXAMPLE")
        self.assertEqual(result, REDACTED)

    def test_bearer_token(self):
        result = redact_value("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test")
        self.assertIn(REDACTED, result)

    def test_connection_string(self):
        result = redact_value("postgres://user:pass@host:5432/db")
        self.assertEqual(result, REDACTED)

    def test_jwt(self):
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = redact_value(jwt)
        self.assertEqual(result, REDACTED)

    def test_anthropic_key(self):
        result = redact_value("sk-ant-api03-abcdefghijklmnopqrstuvwxyz")
        self.assertEqual(result, REDACTED)

    def test_slack_token(self):
        # Use a clearly fake token that still matches the xox[bpras]-... pattern
        result = redact_value("xoxb-fake-test-token-value")
        self.assertEqual(result, REDACTED)

    def test_safe_string_unchanged(self):
        result = redact_value("hello world")
        self.assertEqual(result, "hello world")

    def test_file_path_unchanged(self):
        result = redact_value("/usr/local/bin/python3")
        self.assertEqual(result, "/usr/local/bin/python3")

    def test_inline_redaction(self):
        result = redact_value("Authorization: Bearer sk-abc123def456ghi789jkl012mno345pqr678")
        self.assertIn(REDACTED, result)
        self.assertNotIn("sk-abc", result)


class TestRedactData(unittest.TestCase):
    def test_redact_by_key_name(self):
        data = {"username": "alice", "password": "secret123"}
        result = redact_data(data)
        self.assertEqual(result["username"], "alice")
        self.assertEqual(result["password"], REDACTED)

    def test_redact_api_key(self):
        data = {"api_key": "sk-abc123def456ghi789jkl012mno345pqr678"}
        result = redact_data(data)
        self.assertEqual(result["api_key"], REDACTED)

    def test_redact_token_key(self):
        data = {"token": "some-secret-value", "name": "test"}
        result = redact_data(data)
        self.assertEqual(result["token"], REDACTED)
        self.assertEqual(result["name"], "test")

    def test_redact_nested_dict(self):
        data = {
            "config": {
                "database_url": "postgres://user:pass@host/db",
                "name": "myapp",
            }
        }
        result = redact_data(data)
        self.assertEqual(result["config"]["database_url"], REDACTED)
        self.assertEqual(result["config"]["name"], "myapp")

    def test_redact_list_values(self):
        data = {
            "headers": [
                {"name": "Authorization", "value": "Bearer sk-abc123def456ghi789jkl012mno345pqr678"},
                {"name": "Content-Type", "value": "application/json"},
            ]
        }
        result = redact_data(data)
        self.assertEqual(result["headers"][1]["value"], "application/json")

    def test_redact_value_by_pattern(self):
        data = {
            "arguments": {
                "url": "postgres://admin:hunter2@db.example.com:5432/prod",
                "query": "SELECT * FROM users",
            }
        }
        result = redact_data(data)
        self.assertEqual(result["arguments"]["url"], REDACTED)
        self.assertEqual(result["arguments"]["query"], "SELECT * FROM users")

    def test_non_string_values_unchanged(self):
        data = {"count": 42, "enabled": True, "ratio": 3.14}
        result = redact_data(data)
        self.assertEqual(result, data)

    def test_empty_data(self):
        self.assertEqual(redact_data({}), {})
        self.assertEqual(redact_data([]), [])
        self.assertEqual(redact_data("hello"), "hello")

    def test_sensitive_key_case_insensitive(self):
        data = {"Password": "secret", "API_KEY": "key123"}
        # keys are checked lowercase
        result = redact_data(data)
        # "Password" lowered is "password" which is in SENSITIVE_KEYS
        self.assertEqual(result["Password"], REDACTED)

    def test_tool_call_with_secrets(self):
        """Simulate a real tool call event data with secrets."""
        data = {
            "tool_name": "http_request",
            "arguments": {
                "url": "https://api.example.com/data",
                "headers": {
                    "Authorization": "Bearer sk-abc123def456ghi789jkl012mno345pqr678",
                    "Content-Type": "application/json",
                },
                "api_key": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl",
            },
        }
        result = redact_data(data)
        self.assertEqual(result["tool_name"], "http_request")
        self.assertEqual(result["arguments"]["url"], "https://api.example.com/data")
        self.assertIn(REDACTED, result["arguments"]["headers"]["Authorization"])
        self.assertEqual(result["arguments"]["api_key"], REDACTED)


if __name__ == "__main__":
    unittest.main()
