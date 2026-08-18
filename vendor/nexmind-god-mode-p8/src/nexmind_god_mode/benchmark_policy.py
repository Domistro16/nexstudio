from __future__ import annotations
from pathlib import Path
from typing import Any
from .provider import RecordedModelProvider

class BenchmarkEligibilityError(RuntimeError):
    pass

RECORDED_FIXTURE_MARKERS=(
    'recorded_provider', 'recorded-model', 'contract_regression_only',
    'P1P2_RECORDED_PROVIDER_CONTRACT_REGRESSION_ONLY'
)

def assert_commercial_brain_benchmark_eligible(provider:Any, brief_source:str|None=None)->None:
    if isinstance(provider,RecordedModelProvider):
        raise BenchmarkEligibilityError('RECORDED_MODEL_PROVIDER_FORBIDDEN_FOR_COMMERCIAL_CREATIVE_BENCHMARK')
    if brief_source:
        p=str(Path(brief_source)).lower()
        if any(x.lower() in p for x in RECORDED_FIXTURE_MARKERS):
            raise BenchmarkEligibilityError('RECORDED_OR_CONTRACT_FIXTURE_FORBIDDEN_FOR_COMMERCIAL_CREATIVE_BENCHMARK')

def benchmark_classification(provider:Any, brief_source:str|None=None)->str:
    try:
        assert_commercial_brain_benchmark_eligible(provider,brief_source)
        return 'LIVE_BLIND_ELIGIBLE'
    except BenchmarkEligibilityError:
        return 'CONTRACT_REGRESSION_ONLY'
