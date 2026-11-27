"""因子引擎 `FactorEngine`。

对股票池计算价值、质量、动量三类原始因子，再按横截面百分位（0~100）合成维度分：

- 价值：`pb`/`pe_ttm`/`ps_ttm` 的倒数（越大越便宜）；
- 质量：`roe`、经营现金流/净利润、毛利率、`1 - 负债率`；
- 动量：剔除最近 5 个交易日的 60 日与 120 日收益，以及 5 日均线是否在 20 日均线之上。

防前视：估值、财务、行情三条查询都附加 `available_date <= trade_date`，即只用决策日
当天已经可见的数据；财务还按"报告期 + 可用日"倒序取最新一条。

输入缺失或非法（`pe_ttm`/`pb`/`ps_ttm` 非正、`net_profit` 非正、行情为空）时抛
`ValueError` 而不是用 0 填充，避免把"缺数据"算成"很便宜"。`risk_penalty` 与
`liquidity_flag` 目前固定为 0.0 与 `ok`，尚未接入风控规则。
"""

from typing import Dict, List

from quant.storage.repository import QuantRepository


def rank_percentile(values: List[float], higher_is_better: bool = True) -> List[float]:
    """把一组数值转换成 0~100 的横截面百分位分数。

    最优值得 100、最差值得 0；相同值（并列）取并列名次的平均值，因此同组内的并列
    会得到完全相同的分数，不会被随机拆开。只有一个元素时直接返回 `[100.0]`
    （分母为 0，无法归一化）。

    Args:
        values: 同一维度、同一横截面的原始因子值。
        higher_is_better: 为真时值越大分越高；为假时按升序排名。

    Returns:
        与输入等长、同序的分数列表；每个分数保留 4 位小数。
    """
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
    """计算 VQM 三类原始因子并转为横截面分数。"""

    def __init__(self, repository: QuantRepository):
        """注入仓储；引擎本身无状态。

        Args:
            repository: 提供估值、财务与日线查询的仓储。
        """
        self.repository = repository

    def calculate(self, trade_date: str, universe: List[Dict[str, object]]) -> List[Dict[str, object]]:
        """为股票池计算原始因子与三个维度分。

        逐只股票校验输入：估值倍数必须为正（倒数为因子），净利润必须为正（现金流
        比率的分母），其余质量字段必须存在且可转 float。任何一只不满足都会立刻抛错，
        尽管错误前缀写的是复数 "codes"——实际上是碰到第一只坏股票就中止。

        Args:
            trade_date: 决策日（ISO 日期），所有查询都以它为可见性上界。
            universe: 股票池行，至少含 `code`/`name`/`industry`。

        Returns:
            与 `universe` 等长的因子行：原始因子放在 `factor_raw_values`，
            另有 `value_score`/`quality_score`/`momentum_score`（0~100）、
            `risk_penalty`（当前恒 0.0）、`liquidity_flag`（当前恒 `ok`）等字段；
            股票池为空时返回空列表。

        Raises:
            ValueError: 任一股票的估值、财务或行情输入缺失/非法，消息形如
                `Invalid or missing factor inputs for codes: 600001: pb`。
        """
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
                raise ValueError(f"Invalid or missing factor inputs for codes: {'; '.join(validation_errors)}")
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

    def _require_present_number(
        self,
        row: Dict[str, object],
        code: str,
        field: str,
        errors: List[str],
        positive: bool = False,
    ) -> None:
        """校验某个字段存在且可转成数值，失败时把 `代码: 字段` 追加到 `errors`。

        Args:
            row: 数据行（估值或财务）。
            code: 股票代码，仅用于错误信息。
            field: 字段名。
            errors: 调用方传入的错误累加列表，命中问题时原地追加。
            positive: 为真时要求数值大于 0（用于估值倍数与净利润这类做分母的字段）。
        """
        try:
            value = row[field]
            numeric_value = float(value)
        except (KeyError, TypeError, ValueError):
            errors.append(f"{code}: {field}")
            return

        if positive and numeric_value <= 0:
            errors.append(f"{code}: {field}")

    def _validate_inputs(
        self,
        code: str,
        valuations: Dict[str, Dict[str, object]],
        financials: Dict[str, Dict[str, object]],
        returns: Dict[str, Dict[str, float]],
    ) -> List[str]:
        """校验单只股票的估值、财务与行情输入，返回错误描述列表。

        Args:
            code: 股票代码。
            valuations: 代码 → 最新估值行。
            financials: 代码 → 最新财报行。
            returns: 代码 → 动量指标，缺失表示没有可用行情。

        Returns:
            形如 `["600001: pb", "600001: financial"]` 的错误列表；为空表示输入齐全。
        """
        errors = []
        valuation = valuations.get(code)
        if valuation is None:
            errors.append(f"{code}: valuation")
        else:
            for field in ["pe_ttm", "pb", "ps_ttm"]:
                self._require_present_number(valuation, code, field, errors, positive=True)

        financial = financials.get(code)
        if financial is None:
            errors.append(f"{code}: financial")
        else:
            for field in ["roe", "operating_cash_flow", "gross_margin", "debt_ratio"]:
                self._require_present_number(financial, code, field, errors)
            self._require_present_number(financial, code, "net_profit", errors, positive=True)

        if code not in returns:
            errors.append(f"{code}: daily_bar")
        return errors

    def _latest_valuations(self, trade_date: str, codes: List[str]) -> Dict[str, Dict[str, object]]:
        """取每只股票在决策日可见的最新估值。

        用 `row_number()` 按 `trade_date`、`available_date` 倒序取 rn=1，并限制
        `available_date <= 决策日`，因此不会用到决策日收盘后才更新的估值。

        Args:
            trade_date: 决策日。
            codes: 股票代码列表。

        Returns:
            代码 → 估值行字典；没有可用数据的代码不出现在结果里。
        """
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
        """取每只股票在决策日可见的最新一期财报。

        按 `report_period`、`available_date` 倒序取第一条，并限制
        `available_date <= 决策日`：报告期更晚但尚未公告的财报不会被选中。

        Args:
            trade_date: 决策日。
            codes: 股票代码列表。

        Returns:
            代码 → 财报行字典；无可用财报的代码不出现在结果里。
        """
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
        """把一组因子合成一个 0~100 的维度分：各因子百分位的等权平均。

        每个因子都按"越大越好"排名，因此调用方必须先把方向逆转过
        （如 `pb_inverse`、`debt_ratio_inverse`）。

        Args:
            rows: 已填充 `factor_raw_values` 的因子行。
            factor_names: 参与合成的原始因子名，至少一个。

        Returns:
            与 `rows` 同序的维度分，保留 4 位小数。
        """
        per_factor_scores = []
        for name in factor_names:
            values = [float(row["factor_raw_values"][name]) for row in rows]
            per_factor_scores.append(rank_percentile(values, higher_is_better=True))
        result = []
        for row_index in range(len(rows)):
            result.append(round(sum(scores[row_index] for scores in per_factor_scores) / len(per_factor_scores), 4))
        return result

    def _momentum_returns(self, trade_date: str, codes: List[str]) -> Dict[str, Dict[str, float]]:
        """计算剔除最近 5 个交易日后的 60 日/120 日收益与均线趋势。

        以倒数第 6 根 K 线为终点（`latest_index = len - 6`），去掉最近一周，避免短期
        反转污染动量信号；同时限制 `available_date <= 决策日`，不使用未来价格。
        历史不足时窗口向前截断到序列起点（`max(0, ...)`），因此新股得到的是"上市以来"
        收益而不是 `None`。均线用可用收盘价的简单平均，`ma5 >= ma20` 记 1.0，否则 0.0。

        Args:
            trade_date: 决策日。
            codes: 股票代码列表。

        Returns:
            代码 → `{return_60d_exclude_5d, return_120d_exclude_5d, ma_trend_score}`；
            没有任何行情的代码不会出现在结果中（由 `_validate_inputs` 报缺失）。
        """
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
