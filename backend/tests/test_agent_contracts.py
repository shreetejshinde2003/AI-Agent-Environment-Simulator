"""Prompt alignment and request-local metrics; provider calls are mocked."""
import json
import asyncio
import importlib
import unittest
from unittest.mock import AsyncMock, patch
from pydantic import ValidationError

from app.agents.contracts import CONTRACTS, specialist_prompt
from app.agents.execution_context import (
    AgentInputError, AgentOutput, ExecutionContext, OUTPUT_BY_AGENT,
    RouteSelection, coerce_context,
)
from app.agents.llm_client import LLMResponse
from app.agents.execution_context import current_execution
from app.models.schemas import StageExecution, TaskExecutionMode
from app.api.routes.uploads import parse_upload
from app.core.errors import safe_error
from app.core.config import settings
from fastapi import HTTPException


def readable_prompt(prompt):
    anchor, serialized = prompt.split("\n\nStructured stage contract (data):\n")
    payload = json.loads(serialized)
    prior = payload["prior_result"]
    return anchor + "\n" + "\n".join(payload["relevant_sources"].values()) + (
        "\nSupplied " + prior["output_type"] + ":\n" + prior["prior_result_summary"] if prior else "")


class ContractTests(unittest.IsolatedAsyncioTestCase):
    def test_registry_exposes_capabilities_inputs_and_outputs(self):
        expected = {
            "research": ("research_findings", ()),
            "data": ("structured_data", ("research_findings",)),
            "analysis": ("insights", ("structured_data", "research_findings")),
            "summarizer": ("summary", ("insights", "structured_data", "research_findings")),
            "report": ("final_report", ("summary", "insights", "structured_data", "research_findings")),
            "direct": ("final_answer", ()),
        }
        self.assertEqual(set(CONTRACTS), set(expected))
        for agent_id, (output, alternatives) in expected.items():
            contract = CONTRACTS[agent_id]
            self.assertEqual((contract.agent_id, contract.output), (agent_id, output))
            self.assertEqual(contract.output, OUTPUT_BY_AGENT[agent_id])
            self.assertEqual(contract.required_inputs, ("original_directive",))
            self.assertTrue(contract.capabilities)
            self.assertEqual(contract.preferred_outputs, alternatives)
            self.assertTrue(set(alternatives) <= set(contract.optional_inputs))
        self.assertEqual(set(CONTRACTS["summarizer"].required_any_of),
                         {"source_text", "uploaded_context", "benchmark_context",
                          "insights", "structured_data", "research_findings"})
        self.assertNotIn("web_search", CONTRACTS)

    def test_typed_context_preserves_directive_and_exact_output_provenance(self):
        context = ExecutionContext(original_directive="ORIGINAL goal",
                                   execution_mode=TaskExecutionMode.ADAPTIVE,
                                   route=RouteSelection(selected_agents=("research", "analysis", "report"),
                                                        skipped_agents=("data", "summarizer")))
        self.assertEqual(context.missing_inputs(("research_findings", "structured_data")),
                         ("research_findings", "structured_data"))
        next_context = context.with_output("research", "EXACT finding\n")
        self.assertEqual(context.available_outputs, ())
        self.assertEqual(next_context.available_outputs, ("research_findings",))
        self.assertEqual(next_context.output("research_findings").text, "EXACT finding\n")
        self.assertEqual(next_context.original_directive, "ORIGINAL goal")
        self.assertEqual(next_context.route.skipped_agents, ("data", "summarizer"))
        self.assertNotIn("structured_data", next_context.available_inputs)
        with self.assertRaises(AgentInputError):
            next_context.with_output("data", "fabricated skipped result")

    def test_malformed_context_is_rejected_without_echoing_content(self):
        cases = [
            lambda: coerce_context("goal", {"unknown": "private value"}, "analysis"),
            lambda: coerce_context("goal", {"research_findings": "  "}, "analysis"),
            lambda: coerce_context("goal", {"uploaded_context": "x" * 19001}, "data"),
            lambda: coerce_context("goal", {"research_findings": 42}, "analysis"),
            lambda: coerce_context("changed", ExecutionContext(original_directive="goal"), "report"),
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(AgentInputError) as raised:
                case()
            self.assertNotIn("private value", str(raised.exception))
            self.assertIn(raised.exception.detail.code, ("invalid_context", "directive_mismatch"))
        with self.assertRaises(ValidationError):
            AgentOutput(agent_id="analysis", name="summary", text="wrong producer")
        with self.assertRaises(ValidationError):
            ExecutionContext(original_directive="goal", prior_outputs=(
                AgentOutput(agent_id="research", name="research_findings", text="one"),
                AgentOutput(agent_id="research", name="research_findings", text="two")))
        with self.assertRaises(ValidationError):
            RouteSelection(selected_agents=("analysis",), skipped_agents=("analysis",))

    async def test_missing_required_source_is_rejected_before_model_call(self):
        from app.agents import summarizer_agent
        context = ExecutionContext(original_directive="Summarize material",
                                   execution_mode=TaskExecutionMode.ADAPTIVE)
        with patch.object(summarizer_agent, "call_llm", new_callable=AsyncMock) as llm:
            with self.assertRaises(AgentInputError) as raised:
                await summarizer_agent.SummarizerAgent().process("Summarize material", context)
        llm.assert_not_awaited()
        self.assertEqual(raised.exception.detail.code, "missing_required_input")
        self.assertEqual(raised.exception.detail.agent_id, "summarizer")
        self.assertIn("insights", raised.exception.detail.missing_inputs)

    async def test_optional_absence_has_no_fake_prompt_sections(self):
        for agent_id, class_name in (("data", "DataAgent"), ("analysis", "AnalysisAgent"),
                                     ("report", "ReportAgent")):
            with self.subTest(agent=agent_id):
                module = importlib.import_module("app.agents." + agent_id + "_agent")
                mock = AsyncMock(return_value=LLMResponse("answer", 2, 3, 0.1, "test-model"))
                with patch.object(module, "call_llm", mock):
                    await getattr(module, class_name)().process("ORIGINAL goal", {})
                prompt = readable_prompt(mock.await_args.kwargs["prompt"])
                self.assertEqual(prompt.strip(), "Original user directive:\nORIGINAL goal")
                self.assertNotIn("Supplied", prompt)
        # Legacy individual specialist input may contain source text directly
        # in the directive, so its previous standalone action remains usable.
        from app.agents import summarizer_agent
        mock = AsyncMock(return_value=LLMResponse("answer", 2, 3, 0.1, "test-model"))
        with patch.object(summarizer_agent, "call_llm", mock):
            await summarizer_agent.SummarizerAgent().process("Summarize: stated facts", {})
        self.assertNotIn("Supplied insights", mock.await_args.kwargs["prompt"])

    async def test_alternative_upstream_material_without_fake_stages(self):
        # Internal contract exercise only: these are not exposed as routes.
        cases = [
            ("analysis", "AnalysisAgent", "research_findings", "research", "Research fact", "structured_data"),
            ("summarizer", "SummarizerAgent", "research_findings", "research", "Research fact", "insights"),
            ("report", "ReportAgent", "insights", "analysis", "Analysis insight", "summary"),
            ("report", "ReportAgent", "structured_data", "data", "Data record", "summary"),
        ]
        for agent_id, class_name, name, producer, text, absent in cases:
            with self.subTest(agent=agent_id, source=name):
                context = ExecutionContext(original_directive="ORIGINAL goal",
                                           execution_mode=TaskExecutionMode.ADAPTIVE).with_output(producer, text)
                module = importlib.import_module("app.agents." + agent_id + "_agent")
                mock = AsyncMock(return_value=LLMResponse("answer", 2, 3, 0.1, "test-model"))
                with patch.object(module, "call_llm", mock):
                    await getattr(module, class_name)().process("ORIGINAL goal", context)
                prompt = readable_prompt(mock.await_args.kwargs["prompt"])
                self.assertIn("ORIGINAL goal", prompt)
                self.assertIn(text, prompt)
                self.assertIn("Supplied " + name, prompt)
                self.assertNotIn("Supplied " + absent, prompt)
                self.assertEqual(context.available_outputs, (name,))

    async def test_internal_research_analysis_report_handoff_preserves_exact_text(self):
        from app.agents import analysis_agent, report_agent
        context = ExecutionContext(original_directive="ORIGINAL comparison",
                                   execution_mode=TaskExecutionMode.ADAPTIVE,
                                   route=RouteSelection(selected_agents=("research", "analysis", "report"),
                                                        skipped_agents=("data", "summarizer")))
        context = context.with_output("research", "EXACT research\nuncertain")
        analysis_response = LLMResponse("EXACT analysis\nwith caveat", 3, 4, 0.1, "test-model")
        with patch.object(analysis_agent, "call_llm", new_callable=AsyncMock,
                          return_value=analysis_response) as analysis_llm:
            actual = await analysis_agent.AnalysisAgent().process(context.original_directive, context)
        self.assertIn("EXACT research\nuncertain", readable_prompt(analysis_llm.await_args.kwargs["prompt"]))
        context = context.with_output("analysis", actual.text)
        report_response = LLMResponse("Final answer", 3, 4, 0.1, "test-model")
        with patch.object(report_agent, "call_llm", new_callable=AsyncMock,
                          return_value=report_response) as report_llm:
            await report_agent.ReportAgent().process(context.original_directive, context)
        prompt = readable_prompt(report_llm.await_args.kwargs["prompt"])
        self.assertIn("EXACT analysis\nwith caveat", prompt)
        self.assertNotIn("Supplied summary", prompt)
        self.assertEqual(context.available_outputs, ("research_findings", "insights"))
        self.assertEqual(context.route.skipped_agents, ("data", "summarizer"))

    async def test_direct_source_context_is_supported_without_upstream_artifact(self):
        from app.agents import data_agent, summarizer_agent
        context = ExecutionContext(original_directive="Summarize these records",
                                   execution_mode=TaskExecutionMode.ADAPTIVE,
                                   uploaded_context="File: safe.csv\nteam,count\nA,3")
        for module, agent in ((data_agent, data_agent.DataAgent()),
                              (summarizer_agent, summarizer_agent.SummarizerAgent())):
            mock = AsyncMock(return_value=LLMResponse("answer", 2, 3, 0.1, "test-model"))
            with patch.object(module, "call_llm", mock):
                await agent.process(context.original_directive, context)
            self.assertIn("team,count", mock.await_args.kwargs["prompt"])
            self.assertNotIn("Supplied research_findings", mock.await_args.kwargs["prompt"])
            self.assertNotIn("Supplied insights", mock.await_args.kwargs["prompt"])

    def test_fixed_mode_prefers_immediate_predecessor_and_keeps_raw_input_bounded(self):
        context = ExecutionContext(original_directive="ORIGINAL goal",
                                   execution_mode=TaskExecutionMode.FIXED,
                                   uploaded_context="File: safe.csv\nteam,count\nA,3",
                                   benchmark_context="Records: 3\nDepartment counts: A=3")
        context = context.with_output("research", "Research finding")
        context = context.with_output("data", "Structured record")
        context = context.with_output("analysis", "Analytical insight")
        context = context.with_output("summarizer", "Final summary")
        for agent_id, included, omitted in (
            ("data", "Research finding", "Structured record"),
            ("analysis", "Structured record", "Research finding"),
            ("summarizer", "Analytical insight", "Structured record"),
            ("report", "Final summary", "Analytical insight"),
        ):
            prompt = readable_prompt(specialist_prompt(agent_id, "ORIGINAL goal", context))
            self.assertIn(included, prompt)
            self.assertNotIn(omitted, prompt)
            self.assertIn("Records: 3", prompt)
            if agent_id in ("analysis", "summarizer", "report"):
                self.assertIn("team,count", prompt)
            else:
                self.assertIn("team,count", prompt)

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
