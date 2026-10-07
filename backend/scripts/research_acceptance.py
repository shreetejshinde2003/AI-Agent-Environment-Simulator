"""Reproduce fixture acceptance using the real API/engine and disposable SQLite.

Run from repository root: .venv/bin/python backend/scripts/research_acceptance.py
No provider network request is permitted; the SDK boundary is replaced before
admission. Exports synthetic Task/StageExecution evidence for all seven cases,
three modes and two repetitions. Does not modify application .env or database.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'backend/tests')]
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from app.main import app
from app.storage.database import Repository
from app.experiments.research import catalog
from test_tenant_repository_primitives import make_user
from test_research import wire, add_session


def main():
    with tempfile.TemporaryDirectory(prefix='fm-research-acceptance-') as directory, MonkeyPatch.context() as monkeypatch:
        repo=Repository('sqlite:///'+str(Path(directory)/'evidence.db'))
        repo.initialize();repo.save_user(make_user('USR-research-fixture'));repo.ensure_personal_workspace('USR-research-fixture')
        wire(monkeypatch,repo)
        with TestClient(app) as client:
            client.cookies.set('app_session',add_session(repo,'USR-research-fixture'))
            response=client.post('/api/v1/experiments/research',json={'purpose':'Deterministic local machinery acceptance; no live-provider conclusions','benchmarkIds':[c.id for c in catalog()],'repetitions':2})
            assert response.status_code==201, response.text
            eid=response.json()['experimentId']
            report=client.get('/api/v1/experiments/research/'+eid+'/report').json()
            assert report['observedEvidence']['status']=='complete' and len(report['runEvidence'])==42
            assert all(r['metrics']['status']=='completed' for r in report['runEvidence'])
            destination=ROOT/'docs/acceptance/phase9-fixture-report.json'
            destination.write_text(json.dumps(report,indent=2)+'\n')
            print(f'42 persisted fixture trials exported to {destination}; no live provider calls.')
        repo.engine.dispose()


if __name__=='__main__':main()
