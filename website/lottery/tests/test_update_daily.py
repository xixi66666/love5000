"""增量更新写回、原子发布与失败重试测试（只使用临时数据）。

覆盖分支：
  * `publish` 的临时文件写入失败与 `os.replace` 失败：目标保持旧内容、临时文件清理；
  * `prepare_merge` 只读不写盘，返回顺序为奖级在前、开奖在后；
  * 缺值保留与整数格式（不出现 123.0）、UTF-8 BOM、可空整型列；
  * 重复导入幂等；四个文件全部发布且奖级先于开奖；
  * 奖级发布失败、开奖发布失败后按本轮备份补偿，重跑后收敛；
  * 补偿本身失败要在日志里留痕；暂存失败不动任何目标文件；
  * 数据目录锁被占用时本轮返回 1，释放后可重试成功。

隔离：每个用例用 `tempfile.TemporaryDirectory` 建独立的 data 目录与日志文件，
`fetch_ssq` / `fetch_dlt` 全部打桩，不联网，也不读写仓库里的真实 data/。
"""
import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import update_daily  # noqa: E402

SSQ_COLUMNS = [
    "issue", "date", "red1", "red2", "red3", "red4", "red5", "red6", "blue", "blue2",
    "sales", "pool", "source", "aux_source",
]
SSQ_PRIZE_COLUMNS = ["issue", "date", "level", "level_name", "count", "amount", "source"]
DLT_COLUMNS = [
    "issue", "date", "front1", "front2", "front3", "front4", "front5", "back1", "back2",
    "sales", "pool", "p1_count", "p1_amount", "p2_count", "p2_amount",
    "source", "aux_source", "quality_flag",
]
DLT_PRIZE_COLUMNS = [
    "issue", "date", "sort", "level_name", "is_add", "count", "amount",
    "source", "quality_flag",
]


def write_fixture(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def ssq_row(issue, date, red_start, blue, blue2=None, pool=None):
    row = {
        "issue": issue,
        "date": date,
        "blue": blue,
        "blue2": blue2,
        "sales": 1_000_000 + issue % 1000,
        "pool": pool,
        "source": "cwl.gov.cn",
        "aux_source": None,
    }
    for index in range(6):
        row[f"red{index + 1}"] = red_start + index
    return row


def dlt_row(issue, date, front_start, back_start):
    row = {
        "issue": issue,
        "date": date,
        "sales": 2_000_000 + issue % 1000,
        "pool": 50_000_000,
        "p1_count": 1,
        "p1_amount": 5_000_000,
        "p2_count": 2,
        "p2_amount": 100_000,
        "source": "sporttery.cn",
        "aux_source": None,
        "quality_flag": None,
    }
    for index in range(5):
        row[f"front{index + 1}"] = front_start + index
    for index in range(2):
        row[f"back{index + 1}"] = back_start + index
    return row


class UpdateDailyTests(unittest.TestCase):
    """更新流水线测试；fixture 写入临时目录并保存原始字节用于前后比对。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.data_dir = root / "data"
        self.data_dir.mkdir()
        self.log_path = root / "update.log"

        self.ssq_main = self.data_dir / "ssq.csv"
        self.ssq_prize = self.data_dir / "ssq_prizes.csv"
        self.dlt_main = self.data_dir / "dlt.csv"
        self.dlt_prize = self.data_dir / "dlt_prizes.csv"

        self.old_ssq = ssq_row(2026001, "2026-11-10", 10, 8, blue2=4, pool=None)
        self.new_ssq = ssq_row(2026002, "2026-11-13", 20, 9, blue2=None, pool=123456)
        self.old_ssq_prizes = [
            {"issue": 2026001, "date": "2026-11-10", "level": 1, "level_name": "一等奖",
             "count": 1, "amount": 5_000_000, "source": "cwl.gov.cn"},
        ]
        self.new_ssq_prizes = [
            {"issue": 2026002, "date": "2026-11-13", "level": 1, "level_name": "一等奖",
             "count": 2, "amount": 5_000_000, "source": "cwl.gov.cn"},
            {"issue": 2026002, "date": "2026-11-13", "level": 2, "level_name": "二等奖",
             "count": 8, "amount": 120_000, "source": "cwl.gov.cn"},
        ]

        self.old_dlt = dlt_row(2026001, "2026-11-09", 1, 1)
        self.new_dlt = dlt_row(2026002, "2026-11-11", 10, 5)
        self.old_dlt_prizes = [
            {"issue": 2026001, "date": "2026-11-09", "sort": 10, "level_name": "一等奖",
             "is_add": 0, "count": 1, "amount": 5_000_000, "source": "sporttery.cn",
             "quality_flag": None},
        ]
        self.new_dlt_prizes = [
            {"issue": 2026002, "date": "2026-11-11", "sort": 10, "level_name": "一等奖",
             "is_add": 0, "count": 2, "amount": 5_000_000, "source": "sporttery.cn",
             "quality_flag": None},
        ]

        write_fixture(self.ssq_main, SSQ_COLUMNS, [self.old_ssq])
        write_fixture(self.ssq_prize, SSQ_PRIZE_COLUMNS, self.old_ssq_prizes)
        write_fixture(self.dlt_main, DLT_COLUMNS, [self.old_dlt])
        write_fixture(self.dlt_prize, DLT_PRIZE_COLUMNS, self.old_dlt_prizes)

        self.old_ssq_bytes = self.ssq_main.read_bytes()
        self.old_ssq_prize_bytes = self.ssq_prize.read_bytes()
        self.old_dlt_bytes = self.dlt_main.read_bytes()
        self.old_dlt_prize_bytes = self.dlt_prize.read_bytes()

    def tearDown(self):
        self._tmp.cleanup()

    def assert_no_temp_files(self):
        leftovers = [
            path for path in self.data_dir.rglob("*")
            if path.is_file() and path.name.endswith(".tmp")
        ]
        self.assertEqual([], leftovers)

    def run_ssq_update(self):
        with patch.object(
            update_daily, "fetch_ssq", return_value=([self.new_ssq], self.new_ssq_prizes)
        ), patch.object(update_daily, "fetch_dlt", return_value=([], [])):
            return update_daily.run_once(self.data_dir, self.log_path, False, False)

    def test_write_interruption_keeps_old_file_and_cleans_temp(self):
        path = self.data_dir / "interrupted.csv"
        original = "\ufeffissue,date\n1,2026-01-01\n".encode("utf-8")
        path.write_bytes(original)
        frame = pd.DataFrame([{"issue": 2, "date": "2026-01-02"}])
        temp_paths = []

        def fail_replace(source, target):
            temp_paths.append(Path(source))
            raise OSError("replace failed")

        with patch.object(update_daily.os, "replace", side_effect=fail_replace):
            with self.assertRaises(OSError):
                update_daily.publish([(path, frame)], self.data_dir, self.log_path)

        self.assertEqual(original, path.read_bytes())
        self.assertEqual(1, len(temp_paths))
        self.assertEqual(self.data_dir, temp_paths[0].parent)
        self.assertFalse(temp_paths[0].exists())
        self.assert_no_temp_files()

    def test_temp_write_failure_keeps_old_file_and_cleans_temp(self):
        path = self.data_dir / "interrupted.csv"
        original = "\ufeffissue,date\n1,2026-01-01\n".encode("utf-8")
        path.write_bytes(original)
        frame = pd.DataFrame([{"issue": 2, "date": "2026-01-02"}])

        def fail_to_csv(self, handle, *args, **kwargs):
            handle.write("issue,date\n")
            handle.flush()
            raise OSError("disk full")

        with patch.object(pd.DataFrame, "to_csv", fail_to_csv):
            with self.assertRaises(OSError):
                update_daily._stage(path, frame)

        self.assertEqual(original, path.read_bytes())
        self.assert_no_temp_files()

    def test_prepare_merge_is_read_only_and_puts_prize_first(self):
        before = {
            path.name: path.read_bytes()
            for path in (self.ssq_main, self.ssq_prize, self.dlt_main, self.dlt_prize)
        }
        (prize_path, prize), (draw_path, draw) = update_daily.prepare_merge(
            self.ssq_main, self.ssq_prize, [self.new_ssq], self.new_ssq_prizes
        )

        self.assertEqual(self.ssq_prize, prize_path)
        self.assertEqual(self.ssq_main, draw_path)
        self.assertIn(2026002, draw["issue"].tolist())
        self.assertIn(2026002, prize["issue"].tolist())
        for name, content in before.items():
            self.assertEqual(content, (self.data_dir / name).read_bytes(), name)
        self.assert_no_temp_files()

    def test_publish_preserves_missing_values_and_integer_format(self):
        backup_dir = update_daily.backup(self.data_dir, "20260101_000000")
        prize_write, draw_write = update_daily.prepare_merge(
            self.ssq_main, self.ssq_prize, [self.new_ssq], self.new_ssq_prizes
        )
        update_daily.publish([prize_write, draw_write], backup_dir, self.log_path)

        raw = self.ssq_main.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        by_issue = {row["issue"]: row for row in rows}
        self.assertEqual("", by_issue["2026001"]["pool"])
        self.assertEqual("123456", by_issue["2026002"]["pool"])
        self.assertEqual("4", by_issue["2026001"]["blue2"])
        self.assertEqual("", by_issue["2026002"]["blue2"])
        numeric_values = [
            row[column]
            for row in rows
            for column in ("issue", "blue", "blue2", "sales", "pool")
        ]
        self.assertNotIn(".0", "\n".join(numeric_values))
        self.assertEqual("Int64", str(draw_write[1]["pool"].dtype))
        self.assertEqual("Int64", str(draw_write[1]["blue2"].dtype))

    def test_repeated_import_is_idempotent(self):
        backup_dir = update_daily.backup(self.data_dir, "20260101_000000")

        def import_once():
            ssq_prize_write, ssq_draw_write = update_daily.prepare_merge(
                self.ssq_main, self.ssq_prize, [self.new_ssq], self.new_ssq_prizes
            )
            dlt_prize_write, dlt_draw_write = update_daily.prepare_merge(
                self.dlt_main, self.dlt_prize, [self.new_dlt], self.new_dlt_prizes
            )
            update_daily.publish(
                [ssq_prize_write, dlt_prize_write, ssq_draw_write, dlt_draw_write],
                backup_dir,
                self.log_path,
            )
            return {
                path.name: path.read_bytes()
                for path in (self.ssq_main, self.ssq_prize, self.dlt_main, self.dlt_prize)
            }

        first = import_once()
        second = import_once()

        self.assertEqual(first, second)
        self.assertEqual([2026001, 2026002], update_daily._read(self.ssq_main)["issue"].tolist())
        self.assertEqual([2026001, 2026002], update_daily._read(self.dlt_main)["issue"].tolist())
        self.assert_no_temp_files()

    def test_all_prizes_are_published_before_draw_files(self):
        calls = []
        real_replace = update_daily.os.replace

        def recording_replace(source, target):
            calls.append(target.name)
            return real_replace(source, target)

        with patch.object(
            update_daily, "fetch_ssq", return_value=([self.new_ssq], self.new_ssq_prizes)
        ), patch.object(
            update_daily, "fetch_dlt", return_value=([self.new_dlt], self.new_dlt_prizes)
        ), patch.object(update_daily.os, "replace", side_effect=recording_replace):
            code = update_daily.run_once(self.data_dir, self.log_path, False, False)

        self.assertEqual(0, code)
        self.assertEqual(
            ["ssq_prizes.csv", "dlt_prizes.csv", "ssq.csv", "dlt.csv"],
            calls,
        )

    def test_prize_publish_failure_then_rerun_converges(self):
        real_replace = update_daily.os.replace

        def fail_prize(source, target):
            if target.name == "ssq_prizes.csv":
                raise OSError("prize publish failed")
            return real_replace(source, target)

        with patch.object(update_daily.os, "replace", side_effect=fail_prize):
            code = self.run_ssq_update()

        self.assertEqual(1, code)
        self.assertEqual(self.old_ssq_bytes, self.ssq_main.read_bytes())
        self.assertEqual(self.old_ssq_prize_bytes, self.ssq_prize.read_bytes())
        log_text = self.log_path.read_text(encoding="utf-8")
        self.assertIn("发布 ssq_prizes.csv 失败", log_text)
        self.assert_no_temp_files()

        self.assertEqual(0, self.run_ssq_update())
        self.assertEqual(2026002, int(update_daily._read(self.ssq_main)["issue"].max()))
        self.assertEqual(2026002, int(update_daily._read(self.ssq_prize)["issue"].max()))
        self.assert_no_temp_files()

    def test_draw_publish_failure_compensates_and_rerun_converges(self):
        real_replace = update_daily.os.replace

        def fail_draw(source, target):
            if target.name == "ssq.csv":
                raise OSError("draw publish failed")
            return real_replace(source, target)

        with patch.object(update_daily.os, "replace", side_effect=fail_draw):
            code = self.run_ssq_update()

        self.assertEqual(1, code)
        self.assertEqual(self.old_ssq_bytes, self.ssq_main.read_bytes())
        self.assertEqual(self.old_ssq_prize_bytes, self.ssq_prize.read_bytes())
        log_text = self.log_path.read_text(encoding="utf-8")
        self.assertIn("发布 ssq.csv 失败", log_text)
        self.assertIn("已用本轮备份恢复 ssq_prizes.csv", log_text)
        self.assert_no_temp_files()

        self.assertEqual(0, self.run_ssq_update())
        self.assertEqual(2026002, int(update_daily._read(self.ssq_main)["issue"].max()))
        self.assertEqual(2026002, int(update_daily._read(self.ssq_prize)["issue"].max()))
        self.assert_no_temp_files()

    def test_compensation_failure_is_visible(self):
        real_replace = update_daily.os.replace

        def fail_draw(source, target):
            if target.name == "ssq.csv":
                raise OSError("draw publish failed")
            return real_replace(source, target)

        with patch.object(update_daily.os, "replace", side_effect=fail_draw), patch.object(
            update_daily, "_restore_from_backup", side_effect=OSError("restore failed")
        ):
            code = self.run_ssq_update()

        self.assertEqual(1, code)
        self.assertEqual(self.old_ssq_bytes, self.ssq_main.read_bytes())
        log_text = self.log_path.read_text(encoding="utf-8")
        self.assertIn("恢复 ssq_prizes.csv 失败", log_text)
        self.assert_no_temp_files()


    def test_staging_failure_leaves_both_targets_untouched(self):
        real_stage = update_daily._stage

        def fail_draw_stage(path, frame):
            if path == self.ssq_main:
                raise OSError("disk full")
            return real_stage(path, frame)

        with patch.object(update_daily, "_stage", side_effect=fail_draw_stage):
            self.assertEqual(1, self.run_ssq_update())
        self.assertEqual(self.old_ssq_bytes, self.ssq_main.read_bytes())
        self.assertEqual(self.old_ssq_prize_bytes, self.ssq_prize.read_bytes())
        self.assert_no_temp_files()

    def test_competing_update_can_retry_after_lock_release(self):
        with update_daily._data_lock(self.data_dir):
            self.assertEqual(1, self.run_ssq_update())
            self.assertEqual(self.old_ssq_bytes, self.ssq_main.read_bytes())
        self.assertEqual(0, self.run_ssq_update())
        self.assertIn(2026002, update_daily._read(self.ssq_main)["issue"].tolist())


if __name__ == "__main__":
    unittest.main()
