"""Run a selected Phase 2 group with disposable defaults and no network sockets.

Usage from repository root: .venv/bin/python backend/tests/run_phase2_security_acceptance.py budget -q -ra
Provider mocks remain in the individual tests; this outer guard rejects accidental HTTP/DB connections.
"""
import os
from pathlib import Path
import socket
import sys
import tempfile

GROUPS = {
    'auth': ['test_google_auth_api', 'test_oauth_portability', 'test_oauth_reliability', 'test_browser_session_security'],
    'organization-hr': ['test_rbac_adversarial', 'test_hr_human_role_adversarial', 'test_product_invites',
                        'test_membership_role_management', 'test_hr_reviews_api', 'test_hr_review_storage',
                        'test_hr_workflow_integration'],
    'research': ['test_research_demo_budget', 'test_research', 'test_research_contracts', 'test_llm_client'],
    'budget': ['test_research_demo_budget'],
    'agents-retention': ['test_agent_builder', 'test_recycle_bin', 'test_upload_tenant_ownership',
                         'test_upload_tenant_api', 'test_provider_failure_disclosure'],
    'text-postgres-gates': ['test_oauth_portability_postgres', 'test_product_invites_postgres',
                            'test_hr_reviews_postgres', 'test_agent_builder_postgres', 'test_research_postgres',
                            'test_upload_tenant_ownership', 'test_agent_contracts', 'test_hr_agent_contracts',
                            'test_hr_agents'],
    'gaps': ['test_phase2_security_acceptance'],
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in GROUPS:
        raise SystemExit('Choose one group: ' + ', '.join(GROUPS))
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    sys.path[:0] = [str(root / 'backend'), str(root / 'backend/tests')]
    with tempfile.TemporaryDirectory(prefix='fm-phase2-') as scratch:
        os.environ.update(
            DATABASE_URL='sqlite:///' + str(Path(scratch) / 'unused-default.db'),
            GROQ_API_KEY='mock-only-not-a-credential', GOOGLE_CLIENT_ID='', GOOGLE_CLIENT_SECRET='',
            RESEARCH_LIVE_ENABLED='false', RESEARCH_JUDGE_ENABLED='false', RESEARCH_DEMO_ENABLED='false',
            LANGGRAPH_RUNTIME_ENABLED='false', CHECKPOINT_DATABASE_URL='', RUN_LOCAL_CHECKPOINT_SQL_TESTS='0',
        )
        for name in ('TENANT_TEST_DATABASE_URL', 'TEST_POSTGRES_URL', 'TEST_DATABASE_URL', 'POSTGRES_TEST_URL'):
            os.environ.pop(name, None)
        original_connect = socket.socket.connect
        def isolated_connect(sock, address):
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                raise AssertionError('Phase 2 forbids network socket connections')
            return original_connect(sock, address)
        socket.socket.connect = isolated_connect
        try:
            import pytest
            files = ['backend/tests/' + name + '.py' for name in GROUPS[sys.argv[1]]]
            return pytest.main(files + sys.argv[2:])
        finally:
            socket.socket.connect = original_connect


if __name__ == '__main__':
    raise SystemExit(main())
