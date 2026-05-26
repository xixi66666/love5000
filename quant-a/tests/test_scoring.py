from pathlib import Path

import pytest

from quant.factors.engine import FactorEngine, rank_percentile
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


def test_rank_percentile_assigns_equal_score_to_ties():
    scores = rank_percentile([1.0, 1.0, 0.0])

    assert scores[0] == scores[1]
    assert scores[0] > scores[2]


def test_factor_engine_rejects_invalid_valuation_metric(tmp_path):
    repository = build_repository(tmp_path)
    repository.connection.execute("update valuation set pb = 0 where code = '600001'")
    universe = UniverseService(repository).build_universe("2024-03-29", ["CSI300"], 120, 50000000, False, True)

    with pytest.raises(ValueError, match="600001.*pb"):
        FactorEngine(repository).calculate("2024-03-29", universe)


def test_factor_engine_rejects_invalid_financial_profit(tmp_path):
    repository = build_repository(tmp_path)
    repository.connection.execute("update financial set net_profit = 0 where code = '600001'")
    universe = UniverseService(repository).build_universe("2024-03-29", ["CSI300"], 120, 50000000, False, True)

    with pytest.raises(ValueError, match="600001.*net_profit"):
        FactorEngine(repository).calculate("2024-03-29", universe)


def test_factor_engine_reports_missing_valuation_inputs(tmp_path):
    repository = build_repository(tmp_path)
    repository.connection.execute("delete from valuation where code = '600001'")
    universe = UniverseService(repository).build_universe("2024-03-29", ["CSI300"], 120, 50000000, False, True)

    with pytest.raises(ValueError, match="600001.*valuation"):
        FactorEngine(repository).calculate("2024-03-29", universe)


def test_factor_engine_reports_missing_financial_inputs(tmp_path):
    repository = build_repository(tmp_path)
    repository.connection.execute("delete from financial where code = '600001'")
    universe = UniverseService(repository).build_universe("2024-03-29", ["CSI300"], 120, 50000000, False, True)

    with pytest.raises(ValueError, match="600001.*financial"):
        FactorEngine(repository).calculate("2024-03-29", universe)


def test_factor_engine_reports_missing_momentum_inputs(tmp_path):
    repository = build_repository(tmp_path)
    repository.connection.execute("delete from daily_bar where code = '600001'")
    universe = UniverseService(repository).build_universe("2024-03-29", ["CSI300"], 120, 50000000, False, True)
    universe.append({
        "code": "600001",
        "name": "mock",
        "exchange": "SH",
        "list_date": "2010-01-01",
        "industry": "mock",
        "is_st": False,
        "avg_amount_20d": 100000000,
        "suspend_flag": False,
        "listed_days": 5000,
    })

    with pytest.raises(ValueError, match="600001.*daily_bar"):
        FactorEngine(repository).calculate("2024-03-29", universe)


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
