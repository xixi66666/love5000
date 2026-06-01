import time
import unittest

from anime_tools.task_manager import TaskBusyError, TaskManager


class TaskManagerTests(unittest.TestCase):
    def test_task_records_success_logs_and_result(self):
        manager = TaskManager()

        task = manager.submit("render", "demo_project", lambda log: _successful_task(log))
        manager.wait(task.id, timeout=2)

        saved = manager.get(task.id)
        self.assertEqual(saved.status, "success")
        self.assertEqual(saved.result, {"final_video": "output/final.mp4"})
        self.assertEqual(saved.logs, ["开始渲染", "渲染完成"])
        self.assertEqual(saved.error, "")
        self.assertTrue(saved.finished_at)

    def test_task_records_failure_message(self):
        manager = TaskManager()

        task = manager.submit("render", "demo_project", lambda log: _failed_task(log))
        manager.wait(task.id, timeout=2)

        saved = manager.get(task.id)
        self.assertEqual(saved.status, "failed")
        self.assertIn("FFmpeg 失败", saved.error)
        self.assertEqual(saved.logs, ["开始渲染"])

    def test_rejects_second_running_task(self):
        manager = TaskManager()
        release = []

        first = manager.submit("render", "demo_project", lambda log: _blocking_task(log, release))
        _wait_until(lambda: manager.get(first.id).status == "running")

        with self.assertRaises(TaskBusyError):
            manager.submit("render", "other_project", lambda log: None)

        release.append(True)
        manager.wait(first.id, timeout=2)


def _successful_task(log):
    log("开始渲染")
    log("渲染完成")
    return {"final_video": "output/final.mp4"}


def _failed_task(log):
    log("开始渲染")
    raise RuntimeError("FFmpeg 失败")


def _blocking_task(log, release):
    log("等待释放")
    while not release:
        time.sleep(0.01)


def _wait_until(predicate):
    deadline = time.time() + 2
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("等待条件超时")


if __name__ == "__main__":
    unittest.main()
