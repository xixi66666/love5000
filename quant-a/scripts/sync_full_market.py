import json
import os
import sys
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from quant.services.pipeline import QuantPipeline


def main():
    end_date = date.today()
    start_date = end_date.replace(year=end_date.year - 1)
    pipeline = QuantPipeline()
    result = pipeline.sync_data_daily_fast(
        start_date.isoformat(),
        end_date.isoformat(),
        ["ALL"],
        force=True,
    )
    print(json.dumps(result, ensure_ascii=False, default=str))

    batch_size = int(os.environ.get("QUANT_A_SYNC_BATCH_SIZE", "100"))
    max_batches = int(os.environ.get("QUANT_A_SYNC_MAX_BATCHES", "0"))
    batch_index = 0
    while True:
        batch_index += 1
        result = pipeline.sync_market_data_batch(
            start_date.isoformat(),
            end_date.isoformat(),
            batch_size=batch_size,
        )
        print(json.dumps({"batch": batch_index, **result}, ensure_ascii=False, default=str), flush=True)
        if result["remaining_count"] == 0 or result["processed_count"] == 0:
            break
        if max_batches > 0 and batch_index >= max_batches:
            break


if __name__ == "__main__":
    main()
