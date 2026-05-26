from pathlib import Path

from quant.factors.engine import FactorEngine
from quant.providers.mock_provider import MockProvider
from quant.scoring.service import ScoringService
from quant.services.pipeline import QuantPipeline
from quant.storage.repository import QuantRepository
from quant.universe.service import UniverseService


def build_repository(tmp_path: Path) -> QuantRepository:
    repository = QuantRepository(tmp_path / "quant.duckdb")
    QuantPipeline(repository=repository, provider=MockProvider()).sync_data("2024-01-02", "2024-03-31", ["CSI300"])
    return repository


def test_factor_engine_calculates_vqm_factors(tmp_path):
    repository = build_repository(tmp_path)
    universe = UniverseService(repository).build_universe("2024-03-29", ["CSI300"], 120, 50000000, False, True)
    factors = FactorEngine(repository).calculate("2024-03-29", universe)

    assert len(factors) == 6
    first = factors[0]
    assert first["code"] == "600001"
    assert "pb_inverse" in first["factor_raw_values"]
    assert "return_60d_exclude_5d" in first["factor_raw_values"]
    assert 0 <= first["value_score"] <= 100
    assert 0 <= first["quality_score"] <= 100
    assert 0 <= first["momentum_score"] <= 100


def test_scoring_service_ranks_total_score(tmp_path):
    repository = build_repository(tmp_path)
    universe = UniverseService(repository).build_universe("2024-03-29", ["CSI300"], 120, 50000000, False, True)
    factors = FactorEngine(repository).calculate("2024-03-29", universe)
    scores = ScoringService().score("2024-03-29", factors, "mock-2024-q1", "v0.1")

    assert len(scores) == 6
    assert scores[0]["rank"] == 1
    assert scores[0]["total_score"] >= scores[-1]["total_score"]
    total_scores = [item["total_score"] for item in scores]
    assert total_scores == sorted(total_scores, reverse=True)
    assert scores[0]["model_version"] == "v0.1"
