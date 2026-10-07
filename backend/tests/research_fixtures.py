"""Synthetic SDK boundary fixture; never exported as live-provider evidence."""
from types import SimpleNamespace

OUTPUTS = {
    "Glossary:": "recovery time objective",
    "Note A:": "Cedar is owned by Mira and launches in May. Maple is owned by Ravi and launches in June.",
    "Requests by day:": '{"total":60,"average":20}',
    "Plan A:": "Plan A annual cost 1440. Plan B annual cost 1200. Choose Plan B; savings 240.",
    "Launch is": "Launch is 15 May. The risk is supplier delay; mitigation is a backup supplier.",
    "Pilot processed": "Findings: 40 tickets, six open. Risks: limited staffing. Recommendation: extend by one week.",
    "Ada prepares": "Owners: Ada, Ben, Cy. Dependency: Ben follows Ada, Cy follows Ben. Sequence: Ada, Ben, Cy.",
}


async def completion(**kwargs):
    prompt = kwargs["messages"][-1]["content"]
    output = next((value for key, value in OUTPUTS.items() if key in prompt), "Fixture evidence has no matching benchmark source")
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=output))],
                           usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7))
