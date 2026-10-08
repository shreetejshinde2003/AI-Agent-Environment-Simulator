"""Opt-in local restricted PostgreSQL test; never production."""
from test_postgres_data_plane_integration import pg_repo
from test_oauth_portability import assert_one_time_consumption

def test_postgres_oauth_consumption(pg_repo):
    assert_one_time_consumption(pg_repo)
