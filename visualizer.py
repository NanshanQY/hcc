import time
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from upgrader import AppUpgrader
plt.rcParams['font.sans-serif'] = ['SimHei'] # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False # 用来正常显示负号
class AppUpgradeVisualizer:
    def __init__(self, upgrader, services, total_time, start_time):
        self.upgrader:AppUpgrader = upgrader
        self.services = services  # 所有服务列表
        self.total_time = total_time  # 时间窗总时间
        self.start_time = start_time  # 时间窗开始的真实时间（time.time()）
        self.fig, self.ax = plt.subplots(figsize=(10, 6))
        self.completed_apps = []  # (component, start_time, end_time)

    def init_plot(self):
        """初始化图表"""
        self.ax.set_xlim(0, self.total_time)
        self.ax.set_ylim(-1, len(self.services))
        self.ax.set_xlabel("时间 (秒)")
        self.ax.set_ylabel("组件")
        self.ax.set_yticks(range(len(self.services)))
        self.ax.set_yticklabels(self.services)
        self.ax.set_title("升级时间线")
        self.bars = []
        self.texts = []
        self.time_line = self.ax.axvline(x=0, color='red', linestyle='--')
        self.time_text = self.ax.text(0.95, 0.95, "时间: 0秒", transform=self.ax.transAxes, ha='right', va='top')
        return self.bars + [self.time_line, self.time_text]

    def update_plot(self, frame):
        """更新图表"""
        # 计算当前时间相对于时间窗开始的偏移
        current_time = time.time() - self.start_time
        if current_time > self.total_time:
            current_time = self.total_time  # 限制在时间窗内

        self.ax.clear()
        self.ax.set_xlim(0, self.total_time)
        self.ax.set_ylim(-1, len(self.services))
        self.ax.set_xlabel("时间 (秒)")
        self.ax.set_ylabel("组件")
        self.ax.set_yticks(range(len(self.services)))
        self.ax.set_yticklabels(self.services)
        self.ax.set_title("升级时间线")

        # 获取当前状态
        status = self.upgrader.get_upgrade_status()
        upgrade_times = self.upgrader.get_upgrade_times()

        # 绘制时间条
        self.bars = []
        self.texts = []
        for component in self.services:
            app_index = self.services.index(component)
            start_time = self.upgrader.start_times.get(component, 0)
            if status.get(component, False):  # 正在升级
                duration = self.upgrader.upgrade_durations[component]
                remaining_time = duration - (time.time() - start_time)
                if remaining_time > 0:
                    bar = self.ax.barh(app_index, duration, left=start_time - self.start_time, color='skyblue')
                    self.bars.append(bar)
                    text = self.ax.text((start_time - self.start_time) + duration + 0.5, app_index, f"{remaining_time:.1f}秒", va='center')
                    self.texts.append(text)
                    # 添加版本信息
                    original = self.upgrader.available_versions[component][0]
                    target = self.upgrader.upgrade_candidates[component]
                    version_text = f"{original} -> {target}"
                    self.ax.text((start_time - self.start_time) + duration / 2, app_index + 0.3, version_text, ha='center', va='bottom', fontsize=8)
            elif component in upgrade_times:  # 已完成
                duration = upgrade_times[component]
                # 判断升级是否成功
                success = self.upgrader.available_versions[component][0] != self.upgrader.upgrade_candidates[component]
                color = 'lightgreen' if not success else 'red'
                label = "完成" if not success else "失败"
                bar = self.ax.barh(app_index, duration, left=start_time - self.start_time, color=color)
                self.bars.append(bar)
                text = self.ax.text((start_time - self.start_time) + duration + 0.5, app_index, label, va='center')
                self.texts.append(text)
                # 添加版本信息
                original = self.upgrader.available_versions[component][0]
                target = self.upgrader.upgrade_candidates[component]
                version_text = f"{original} -> {target}"
                self.ax.text((start_time - self.start_time) + duration / 2, app_index + 0.3, version_text, ha='center', va='bottom', fontsize=8)

        # 更新时间线和时间文本
        self.time_line = self.ax.axvline(x=current_time, color='red', linestyle='--')
        self.time_text = self.ax.text(0.95, 0.95, f"时间: {current_time:.1f}秒", transform=self.ax.transAxes, ha='right', va='top')

        # 检查是否所有升级完成且时间窗结束
        if (not any(status.values()) and len(upgrade_times) == len(self.upgrader.upgrade_durations)) or current_time >= self.total_time:
            self.ani.event_source.stop()

        return self.bars + [self.time_line, self.time_text]

    def animate(self):
        """启动动画"""
        self.ani = FuncAnimation(self.fig, self.update_plot, init_func=self.init_plot,
                                interval=100, blit=False, repeat=False)

        plt.show()
        