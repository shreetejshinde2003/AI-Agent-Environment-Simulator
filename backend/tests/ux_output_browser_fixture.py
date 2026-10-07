"""Disposable consolidation browser acceptance, never production/live evidence.

Existing benchmark fixture outputs remain unchanged. Four additional synthetic
request cases exercise contract plumbing, presentation and real authenticated
run APIs with an SDK mock. They do not establish live model instruction fidelity.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import phase10_browser_fixture as baseline

CASES = {
    'What is 6 times 7? Give only the final number.': '42',
    'Summarize this in 3 bullet points.\nSource: Cedar launches in May. Maple launches in June. Pine launches in July.': '- Cedar launches in May.\n- Maple launches in June.\n- Pine launches in July.',
    'Return JSON with keys x and y. Set x to 1 and y to 2.': '{"x":1,"y":2}',
    'Explain only the security risks of sharing a password in a longer analysis.': ('## Security risks\n\nSharing a password exposes access and removes individual attribution.\n\n' + '\n\n'.join(f'### Risk {n}\n\nA shared credential can be copied without the owner knowing. Access persists until the credential is rotated. Separate identities improve attribution; this fixture does not assess a real system.' for n in range(1,15))),
}

async def completion(**kwargs):
    prompt = kwargs['messages'][-1]['content']
    if 'Structured stage contract (data):\n' in prompt:
        contract = json.loads(prompt.split('Structured stage contract (data):\n',1)[1])
        original = contract['original_directive']
        if original in CASES:
            terminal = 'final answer' in contract['stage_objective'].lower() or 'directly' in contract['stage_objective'].lower()
            output = CASES[original] if terminal else 'Irrelevant fixture commentary must not redefine the task. '*220
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=output))],
                usage=SimpleNamespace(prompt_tokens=11,completion_tokens=7))
    return await baseline.sdk_completion(**kwargs)

baseline.patches.setattr(baseline.llm_client._client.chat.completions,'create',completion)
if __name__ == '__main__':
    import asyncio
    import uvicorn
    asyncio.run(baseline.seed_research())
    try: uvicorn.run(baseline.fixture.app,host='127.0.0.1',port=8019,log_level='warning')
    finally:
        baseline.patches.undo()
        baseline.fixture.repository.engine.dispose()
        baseline.fixture.fixture_directory.cleanup()
