"""Pure benchmark and statistical contracts, without providers or persistence."""
import pytest
from app.experiments.research import catalog, canonical_hash, describe
from app.models.schemas import BenchmarkCase, ResearchExperimentInput


def test_registry_identity_snapshot_hashes_and_modes_are_stable():
    cases=catalog()
    assert len(cases)==7 and len({c.id for c in cases})==7
    for case in cases:
        assert case.modes==('single','fixed','adaptive')
        assert case.execution_directive==case.directive+'\n\nSource:\n'+case.source
        assert canonical_hash(case.model_dump(mode='json'))==canonical_hash(BenchmarkCase.model_validate(case.model_dump(mode='json')).model_dump(mode='json'))


@pytest.mark.parametrize('changes', [dict(directive=' '),dict(modes=[]),dict(modes=['single','single']),dict(checks=[]),dict(checks=[dict(id='x',description='Invalid',kind='contains',values=[' '])]),dict(checks=[dict(id='x',description='Invalid',kind='json_fields',values=['total=wrong'])])])
def test_benchmark_rejects_invalid_semantics(changes):
    payload=catalog()[0].model_dump(mode='json');payload.update(changes)
    with pytest.raises(ValueError):BenchmarkCase.model_validate(payload)


def test_descriptive_statistics_known_values_and_sample_sd():
    result=describe([1,2,3,None])
    assert result==dict(n=3,mean=2,median=2,min=1,max=3,sampleStdDev=1)
    assert describe([])==dict(n=0,mean=None,median=None,min=None,max=None,sampleStdDev=None)
