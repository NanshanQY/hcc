# -------------------------------------------------------------------
# main_executor_with_api.py
# -------------------------------------------------------------------
import os
import json
import argparse
import subprocess
import time
import logging
import sys
from datetime import datetime, timedelta
from threading import Thread, Lock
from typing import Dict, Any

# 【新增】引入Flask用于创建API服务器
from flask import Flask, jsonify

# -------------------------------------------------------------------
# 【新增】第1步：创建一个线程安全的状态管理器
# -------------------------------------------------------------------
# 这个类的作用是作为所有升级任务的中央数据库，实时记录它们的状态。
# 它将被API服务器和任务执行线程共享。
class UpgradeStateManager:
    def __init__(self):
        self._lock = Lock()  # 线程锁，防止多个任务同时写入数据造成冲突
        self._tasks: Dict[str, Dict[str, Any]] = {} # 存储所有任务的状态

    def register_task(self, task: dict):
        """在任务开始前，从计划文件中注册任务的基本信息"""
        name = task["name"]
        with self._lock:
            # 只有当任务首次出现时才注册
            if name not in self._tasks:
                self._tasks[name] = {
                    "status": "pending",  # 状态: pending -> running -> succeeded / failed
                    "start_time": None,   # 实际开始升级的时间戳
                    "end_time": None,     # 任务结束的时间戳
                    "duration": 0.0,      # 任务实际耗时
                    "from_ver": task.get("version", {}).get("from", "N/A"),
                    "to_ver": task.get("version", {}).get("to", "N/A"),
                    "expected_duration": task.get("timeline", {}).get("end", 0) - task.get("timeline", {}).get("start", 0)
                }

    def start_task(self, name: str):
        """标记一个任务已开始执行"""
        with self._lock:
            if name in self._tasks:
                self._tasks[name]["status"] = "running"
                self._tasks[name]["start_time"] = time.time()
                logging.info(f"[State Manager] 任务 '{name}' 状态更新为 running")

    def finish_task(self, name: str, success: bool, duration: float):
        """标记一个任务已结束，并记录最终状态和耗时"""
        with self._lock:
            if name in self._tasks:
                self._tasks[name]["status"] = "succeeded" if success else "failed"
                self._tasks[name]["end_time"] = time.time()
                self._tasks[name]["duration"] = duration
                logging.info(f"[State Manager] 任务 '{name}' 状态更新为 {self._tasks[name]['status']}")

    def get_data_for_visualizer(self) -> Dict[str, Any]:
        """
        【核心翻译函数】
        将内部存储的状态，转换成您可视化程序需要的、与AppUpgrader完全兼容的格式。
        """
        with self._lock:
            # 初始化可视化程序需要的6个变量
            upgrade_status = {}
            upgrade_times = {}
            start_times = {}
            upgrade_durations = {}
            available_versions = {}
            upgrade_candidates = {}

            # 遍历所有被管理状态的任务
            for name, data in self._tasks.items():
                # 1. 填充 upgrade_status
                upgrade_status[name] = (data["status"] == "running")

                # 2. 填充 upgrade_times (只有完成的任务才有)
                if data["status"] in ["succeeded", "failed"]:
                    upgrade_times[name] = data["duration"]

                # 3. 填充 start_times (只有开始或完成的任务才有)
                if data["start_time"]:
                    start_times[name] = data["start_time"]
                
                # 4. 填充 upgrade_durations (预计时长)
                upgrade_durations[name] = data["expected_duration"]
                
                # 5. 填充 available_versions (当前版本)
                available_versions[name] = [data["from_ver"]]
                
                # 6. 填充 upgrade_candidates (目标版本)
                upgrade_candidates[name] = data["to_ver"]

            return {
                "upgrade_status": upgrade_status,
                "upgrade_times": upgrade_times,
                "start_times": start_times,
                "upgrade_durations": upgrade_durations,
                "available_versions": available_versions,
                "upgrade_candidates": upgrade_candidates,
            }

# -------------------------------------------------------------------
# 原有代码部分 (稍作修改以集成状态管理器)
# -------------------------------------------------------------------

# 解析时间/持续时间的函数保持不变
def parse_time(time_str):
    try:
        return datetime.strptime(time_str, "%Y.%m.%d.%H:%M")
    except ValueError:
        today = datetime.today()
        time_part = datetime.strptime(time_str, "%H:%M").time()
        return datetime.combine(today, time_part)

def parse_duration(duration_str):
    if duration_str.endswith('s'):
        return int(duration_str[:-1])
    return int(duration_str)

# Helm 和 kubectl 的辅助函数保持不变
def release_exists(namespace: str, release: str) -> bool: # ... (代码不变)
    res = subprocess.run(["helm", "list", "-q", "-n", namespace], capture_output=True, text=True)
    return res.returncode == 0 and release in res.stdout.splitlines()
def ensure_pull_secret(namespace: str, secret_name: str = "cloudsim-docker"): # ... (代码不变)
    patch = json.dumps({"imagePullSecrets": [{"name": secret_name}]})
    subprocess.run([
        "kubectl", "patch", "serviceaccount", "default", "-n", namespace, "-p", patch
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def patch_deployment_image_pull(deploy_name: str, namespace: str, secret_name: str = "cloudsim-docker"): # ... (代码不变)
    patch = json.dumps({
        "spec": {"template": {"spec": {"imagePullSecrets": [{"name": secret_name}]}}}
    })
    subprocess.run([
        "kubectl", "patch", "deployment", deploy_name, "-n", namespace, "-p", patch
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def rollback_release(namespace: str, name: str, frm_ver: str): # ... (代码不变)
    release = f"{name}-{frm_ver}"
    chart_path = os.path.join(os.getenv('CHART_ROOT', '/home/zuo/ServiceSim/src/chart/'), name, frm_ver)
    if not release_exists(namespace, release):
        logging.warning(f"Release {release} 不存在，跳过回滚")
        return
    logging.info(f"回滚 {name} 到版本 {frm_ver} (namespace={namespace})")
    cmd = [
        "helm", "upgrade", release, chart_path,
        "--namespace", namespace, "--set", f"upgrade_path={frm_ver}-{frm_ver}", "--force"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        logging.error(f"回滚失败: {res.stderr.strip()}")
    else:
        logging.info(f"回滚成功: {name} → {frm_ver}")
def check_rollout(namespace: str, deploy_name: str, timeout: int) -> (bool, float): # ... (代码不变)
    logging.info(f"检查 Deployment/{deploy_name} 在命名空间 {namespace} 的就绪状态，时间窗剩余 {timeout}s")
    cmd = [
        "kubectl", "rollout", "status", f"deployment/{deploy_name}",
        "-n", namespace, f"--timeout={timeout}s"
    ]
    start = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - start
    if res.returncode != 0:
        logging.error(f"Deployment/{deploy_name} 就绪失败({duration:.2f}s): {res.stderr.strip()}")
        return False, duration
    logging.info(f"Deployment/{deploy_name} 已成功就绪 ({duration:.2f}s)")
    return True, duration


# 【修改】第2步：修改执行逻辑，让它向状态管理器汇报
def execute_task(task: dict, chart_root: str, window_start: datetime, window_end: datetime, state_manager: UpgradeStateManager):
    # (函数前半部分逻辑不变)
    name = task.get("name")
    ver = task.get("version", {})
    frm_ver, to_ver = ver.get("from"), ver.get("to")
    offset = task.get("timeline", {}).get("start", 0)
    ns = task.get("region", "default")
    readiness_delay = timeline.get("end", 0) - timeline.get("start", 0)

    now = datetime.now()
    if now > window_end:
        logging.info(f"当前时间 {now} 已不在时间窗 {window_start}~{window_end} 内, 跳过 {name}")
        return
    while datetime.now() < window_start:
        logging.info(f"当前时间 {datetime.now()}，等待时间窗 {window_start} 开始...")
        time.sleep(1)
    if offset > 0:
        logging.info(f"{name} 延迟 {offset}s 后开始升级")
        time.sleep(offset)
    
    # --- 新增汇报点 ---
    state_manager.start_task(name)
    task_start_time = time.time() # 记录任务实际开始时间点
    # ---

    helm_start = time.time()
    release = f"{name}-{frm_ver}"
    chart_path = os.path.join(chart_root, name, to_ver)
    # ... (helm upgrade, patch 等逻辑保持不变)
    logging.info(f"{name} 开始升级 {frm_ver} → {to_ver} (namespace={ns})")
    ensure_pull_secret(ns)
    res = subprocess.run([
        "helm", "upgrade", release, chart_path,
        "--install", "--namespace", ns, "--create-namespace",
        "--force", "--set", f"upgrade_path={frm_ver}-{to_ver}"
    ], capture_output=True, text=True)
    helm_duration = time.time() - helm_start
    logging.info(f"Helm 升级耗时 {helm_duration:.2f}s for {name}")

    deploy_name = f"{name}-deployment"
    patch_deployment_image_pull(deploy_name, ns)

    logging.info(f"{name} 等待 {readiness_delay}s 后进行就绪检查")
    time.sleep(readiness_delay)

    ready = False
    rollout_dur = 0.0
    if res.returncode == 0:
        remaining = int((window_end - datetime.now()).total_seconds())
        if remaining > 0:
            ready, rollout_dur = check_rollout(ns, deploy_name, remaining)
        else:
            logging.warning(f"已过时间窗 {window_end}, 跳过就绪检查 for {name}")
    else:
        logging.error(f"{name} 升级失败: {res.stderr.strip()}")
    
    # --- 新增汇报点 ---
    total_duration = time.time() - task_start_time # 计算总时长
    state_manager.finish_task(name, success=ready, duration=total_duration)
    # ---

    if not ready:
        logging.warning(f"{name} 未能在时间窗内就绪 (总耗时 {total_duration:.2f}s), 执行回滚")
        rollback_release(ns, name, frm_ver)
    else:
        logging.info(f"{name} 在窗口内就绪 (总升级时长: {total_duration:.2f}s)")

# 【修改】将 state_manager 传递下去
def run_window(window: dict, chart_root: str, state_manager: UpgradeStateManager):
    ws = parse_time(window["window_start_time"])
    duration = parse_duration(window["window_time"])
    we = ws + timedelta(seconds=duration)
    if we < ws: we += timedelta(days=1)
    
    logging.info(f"时间窗 {window['window_id']} => 开始: {ws}, 结束: {we}, 时长: {duration}s")
    
    threads = []
    for t in window.get("tasks", []):
        # 将 state_manager 实例传递给每个任务线程
        th = Thread(target=execute_task, args=(t, chart_root, ws, we, state_manager))
        th.start()
        threads.append(th)
    for th in threads:
        th.join()

# 【修改】将 state_manager 传递下去
def execute_schedule(schedule: dict, chart_root: str, state_manager: UpgradeStateManager):
    # 【新增】在执行前，先将所有任务注册到状态管理器
    for w in schedule.get("time_windows", []):
        for t in w.get("tasks", []):
            state_manager.register_task(t)
            
    threads = []
    for w in schedule.get("time_windows", []):
        th = Thread(target=run_window, args=(w, chart_root, state_manager))
        th.start()
        threads.append(th)
    for th in threads:
        th.join()

# 日志设置函数保持不变
def setup_logging(schedule_file: str): # ... (代码不变)
    current_dir = os.getcwd()
    log_dir = os.path.join(current_dir, "log")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file = os.path.join(log_dir, os.path.basename(schedule_file).replace(".json", "-log.txt"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file)
        ]
    )

# -------------------------------------------------------------------
# 【修改】第3步：主程序，同时启动调度器和API服务器
# -------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="按时间窗并行执行 Helm 升级任务, 并通过 API 广播状态")
    parser.add_argument("--schedule", default="schedule3.json")
    parser.add_argument("--chart-root", default="/home/zuo/ServiceSim/src/chart/")
    parser.add_argument("--api-port", type=int, default=5001, help="API 服务器监听的端口")
    args = parser.parse_args()
    
    setup_logging(args.schedule)
    
    # 1. 创建一个全局共享的状态管理器实例
    state_manager = UpgradeStateManager()

    # 2. 创建 Flask app 和 API 端点
    app = Flask(__name__)
    @app.route('/api/upgrade_status')
    def get_status():
        # 这个API端点每次被请求时，都会调用状态管理器的翻译函数
        data = state_manager.get_data_for_visualizer()
        return jsonify(data)

    # 3. 将 Flask 服务器放在一个后台线程中运行
    def run_api_server():
        logging.info(f"API 服务器启动，监听在 http://0.0.0.0:{args.api_port}")
        # 使用 werkzeug 提供的服务器，并关闭其自身的日志，避免与主日志混淆
        from werkzeug.serving import run_simple
        run_simple('0.0.0.0', args.api_port, app, log_startup=False)

    api_thread = Thread(target=run_api_server, daemon=True)
    api_thread.start()

    # 4. 在主线程中加载计划文件并开始执行调度
    logging.info(f"加载调度文件: {args.schedule}")
    try:
        with open(args.schedule) as f:
            schedule_data = json.load(f)
        
        # 将状态管理器实例传入，开始执行！
        execute_schedule(schedule_data.get("upgrade_schedule", {}), args.chart_root, state_manager)
        
        logging.info("所有调度任务已执行完毕。API 服务器将继续运行，按 Ctrl+C 退出。")
        # 让主线程保持存活，以便API可以继续服务
        while True:
            time.sleep(1)
            
    except FileNotFoundError:
        logging.error(f"错误：调度文件 '{args.schedule}' 未找到。")
    except Exception as e:
        logging.error(f"执行过程中发生未知错误: {e}")
    finally:
        sys.exit(0)
