"""Prompt alignment and request-local metrics; provider calls are mocked."""
import asyncio
import importlib
import unittest
from unittest.mock import AsyncMock, patch
from app.agents.llm_client import LLMResponse
from app.agents.execution_context import current_execution
from app.models.schemas import StageExecution
from app.api.routes.uploads import parse_upload
from app.core.errors import safe_error
from app.core.config import settings
from fastapi import HTTPException


class ContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_original_directive_and_supplied_output_in_every_prompt(self):
        cases = [("research", "ResearchAgent", None), ("data", "DataAgent", "research_findings"),
                 ("analysis", "AnalysisAgent", "structured_data"),
                 ("summarizer", "SummarizerAgent", "insights"), ("report", "ReportAgent", "summary")]
        for aid, class_name, key in cases:
            with self.subTest(agent=aid):
                module = importlib.import_module("app.agents." + aid + "_agent")
                response = LLMResponse("Actual text", 11, 7, 0.2, "test-model")
                mock = AsyncMock(return_value=response)
                context = {key: "UNIQUE supplied output"} if key else {}
                with patch.object(module, "call_llm", mock):
                    result = await getattr(module, class_name)().process("ORIGINAL request", context)
                self.assertIs(result, response)
                self.assertIn("ORIGINAL request", mock.call_args.kwargs["prompt"])
                if key:
                    self.assertIn("UNIQUE supplied output", mock.call_args.kwargs["prompt"])
                self.assertTrue(mock.call_args.kwargs["system"])

    async def test_concurrent_run_metrics_are_isolated(self):
        from app.agents.research_agent import ResearchAgent
        async def provider(prompt, **kwargs):
            await asyncio.sleep(0)
            n = 11 if "FIRST" in prompt else 22
            return LLMResponse(prompt, n, 5, 0.01, "test-model")
        async def run(directive):
            stage = StageExecution(agent_id="research", output_key="research_findings")
            token = current_execution.set(stage)
            try:
                await ResearchAgent().run(directive)
            finally:
                current_execution.reset(token)
            return stage
        with patch("app.agents.research_agent.call_llm", provider):
            first, second = await asyncio.gather(run("FIRST"), run("SECOND"))
        self.assertEqual((first.total_tokens, second.total_tokens), (16, 27))
        self.assertEqual(first.model, "test-model")
        self.assertIsNone(current_execution.get())

    def test_upload_preparation_limits_and_safe_filename(self):
        upload = parse_upload("../../reference.txt", b"x" * 6500)
        self.assertEqual(upload.filename, "reference.txt")
        self.assertTrue(upload.truncated)
        self.assertIn("Context truncated", upload.prepared_context)
        rows = b"name,value\n" + b"a,42\n" * 25
        csv = parse_upload("sample.csv", rows)
        self.assertEqual(csv.row_count, 25)
        self.assertTrue(csv.truncated)
        self.assertEqual(csv.prepared_context.count("a,42"), 20)
        parsed = parse_upload("sample.json", b'{"value":42}')
        self.assertIn('"value": 42', parsed.preview)

    def test_invalid_uploads_rejected(self):
        for name, content in [("x.txt", b"\x00"), ("x.txt", b"\xff"),
                              ("x.csv", b"a,b\nx\n"), ("x.json", b"NaN")]:
            with self.subTest(name=name), self.assertRaises(HTTPException):
                parse_upload(name, content)

    def test_errors_redact_configured_credentials_and_tokens(self):
        with patch.object(settings, "GROQ_API_KEY", "unit-test-secret"):
            result = safe_error(RuntimeError("unit-test-secret Bearer abc123 gsk_testtoken123"))
        self.assertNotIn("unit-test-secret", result)
        self.assertNotIn("abc123", result)
        self.assertNotIn("gsk_testtoken123", result)


if __name__ == "__main__":
    unittest.main()
