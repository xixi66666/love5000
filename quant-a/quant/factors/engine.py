from typing import Dict, List

from quant.storage.repository import QuantRepository


def rank_percentile(values: List[float], higher_is_better: bool = True) -> List[float]:
    indexed = list(enumerate(values))
    indexed.sort(key=lambda item: item[1], reverse=higher_is_better)
    if len(indexed) == 1:
        return [100.0]
    scores = [0.0] * len(indexed)
    rank = 0
    while rank < len(indexed):
        end_rank = rank
        while end_rank + 1 < len(indexed) and indexed[end_rank + 1][1] == indexed[rank][1]:
            end_rank += 1
        percentile = 100.0 * (len(indexed) - ((rank + end_rank) / 2.0) - 1) / (len(indexed) - 1)
        for tied_rank in range(rank, end_rank + 1):
            scores[indexed[tied_rank][0]] = round(percentile, 4)
        rank = end_rank + 1
    return scores


class FactorEngine:
    def __init__(self, repository: QuantRepository):
        self.repository = repository

    def calculate(self, trade_date: str, universe: List[Dict[str, object]]) -> List[Dict[str, object]]:
        codes = [str(item["code"]) for item in universe]
        if not codes:
            return []

        valuations = self._latest_valuations(trade_date, codes)
        financials = self._latest_financials(trade_date, codes)
        returns = self._momentum_returns(trade_date, codes)

        raw_rows = []
        for stock in universe:
            code = str(stock["code"])
            validation_errors = self._validate_inputs(code, valuations, financials, returns)
            if validation_errors:
                raise ValueError(f"Missing factor inputs for codes: {'; '.join(validation_errors)}")
            valuation = valuations[code]
            financial = financials[code]
            raw = {
                "pb_inverse": 1.0 / float(valuation["pb"]),
                "pe_ttm_inverse": 1.0 / float(valuation["pe_ttm"]),
                "ps_ttm_inverse": 1.0 / float(valuation["ps_ttm"]),
                "roe": float(financial["roe"]),
                "operating_cash_flow_to_profit": float(financial["operating_cash_flow"]) / float(financial["net_profit"]),
                "gross_margin": float(financial["gross_margin"]),
                "debt_ratio_inverse": 1.0 - float(financial["debt_ratio"]),
                "return_60d_exclude_5d": returns[code]["return_60d_exclude_5d"],
                "return_120d_exclude_5d": returns[code]["return_120d_exclude_5d"],
                "ma_trend_score": returns[code]["ma_trend_score"],
            }
            raw_rows.append({
                **stock,
                "factor_raw_values": raw,
                "missing_fields": [],
                "risk_flags": [],
            })

        value_scores = self._dimension_score(raw_rows, ["pb_inverse", "pe_ttm_inverse", "ps_ttm_inverse"])
        quality_scores = self._dimension_score(raw_rows, ["roe", "operating_cash_flow_to_profit", "gross_margin", "debt_ratio_inverse"])
        momentum_scores = self._dimension_score(raw_rows, ["return_60d_exclude_5d", "return_120d_exclude_5d", "ma_trend_score"])

        for index, row in enumerate(raw_rows):
            row["value_score"] = value_scores[index]
            row["quality_score"] = quality_scores[index]
            row["momentum_score"] = momentum_scores[index]
            row["risk_penalty"] = 0.0
            row["liquidity_flag"] = "ok"
        return raw_rows

    def _validate_inputs(
        self,
        code: str,
        valuations: Dict[str, Dict[str, object]],
        financials: Dict[str, Dict[str, object]],
        returns: Dict[str, Dict[str, float]],
    ) -> List[str]:
        errors = []
        valuation = valuations.get(code)
        if valuation is None:
            errors.append(f"{code}: valuation")
        else:
            for field in ["pe_ttm", "pb", "ps_ttm"]:
                if float(valuation[field]) <= 0:
                    errors.append(f"{code}: {field}")

        financial = financials.get(code)
        if financial is None:
            errors.append(f"{code}: financial")
        elif float(financial["net_profit"]) <= 0:
            errors.append(f"{code}: net_profit")

        if code not in returns:
            errors.append(f"{code}: daily_bar")
        return errors

    def _latest_valuations(self, trade_date: str, codes: List[str]) -> Dict[str, Dict[str, object]]:
        placeholders = ", ".join(["?"] * len(codes))
        rows = self.repository.fetch_dicts(
            f"""
            select *
            from (
                select *,
                       row_number() over (partition by code order by trade_date desc, available_date desc) as rn
                from valuation
                where trade_date <= ?
                  and available_date <= ?
                  and code in ({placeholders})
            )
            where rn = 1
            """,
            [trade_date, trade_date, *codes],
        )
        return {str(row["code"]): dict(row) for row in rows}

    def _latest_financials(self, trade_date: str, codes: List[str]) -> Dict[str, Dict[str, object]]:
        placeholders = ", ".join(["?"] * len(codes))
        rows = self.repository.fetch_dicts(
            f"""
            select *
            from (
                select *,
                       row_number() over (partition by code order by report_period desc, available_date desc) as rn
                from financial
                where available_date <= ?
                  and code in ({placeholders})
            )
            where rn = 1
            """,
            [trade_date, *codes],
        )
        return {str(row["code"]): dict(row) for row in rows}

    def _dimension_score(self, rows: List[Dict[str, object]], factor_names: List[str]) -> List[float]:
        per_factor_scores = []
        for name in factor_names:
            values = [float(row["factor_raw_values"][name]) for row in rows]
            per_factor_scores.append(rank_percentile(values, higher_is_better=True))
        result = []
        for row_index in range(len(rows)):
            result.append(round(sum(scores[row_index] for scores in per_factor_scores) / len(per_factor_scores), 4))
        return result

    def _momentum_returns(self, trade_date: str, codes: List[str]) -> Dict[str, Dict[str, float]]:
        placeholders = ", ".join(["?"] * len(codes))
        rows = self.repository.fetch_dicts(
            f"""
            select trade_date, code, close
            from daily_bar
            where trade_date <= ?
              and available_date <= ?
              and code in ({placeholders})
            order by code, trade_date
            """,
            [trade_date, trade_date, *codes],
        )
        by_code: Dict[str, List[Dict[str, object]]] = {code: [] for code in codes}
        for row in rows:
            by_code[str(row["code"])].append(dict(row))
        result = {}
        for code, series in by_code.items():
            if not series:
                continue
            closes = [float(row["close"]) for row in series]
            latest_index = max(0, len(closes) - 6)
            start_60 = max(0, latest_index - 60)
            start_120 = max(0, latest_index - 120)
            latest = closes[latest_index]
            ret_60 = latest / closes[start_60] - 1.0
            ret_120 = latest / closes[start_120] - 1.0
            ma5 = sum(closes[-5:]) / min(len(closes), 5)
            ma20 = sum(closes[-20:]) / min(len(closes), 20)
            result[code] = {
                "return_60d_exclude_5d": ret_60,
                "return_120d_exclude_5d": ret_120,
                "ma_trend_score": 1.0 if ma5 >= ma20 else 0.0,
            }
        return result
