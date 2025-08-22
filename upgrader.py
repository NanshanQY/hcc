
import time
import threading
from typing import Dict, List, Tuple, Callable, Optional
import random
import json
import os


class AppUpgrader:
    def __init__(self, 
                 upgrade_durations: Dict[str, int],
                 available_versions: Dict[str, List[str]],
                 upgrade_candidates: Dict[str, str]):
        """
        增强版App升级器，带用时统计
        
        :param upgrade_durations: 各组件升级所需时间(秒)
        :param available_versions: 各组件可用版本 {组件: [当前版本, ...]}
        :param upgrade_candidates: 各组件目标升级版本 {组件: 目标版本}
        """
        self.upgrade_durations = upgrade_durations
        self.available_versions = available_versions
        self.upgrade_candidates = upgrade_candidates
        self.upgrade_status = {c: False for c in upgrade_durations}
        self.version_history = {}
        self.upgrade_times = {}  # 记录各组件实际升级用时
        self.start_times = {} # 记录组件开始时间
        self.success = False # 记录升级是否成功
        self.initial_versions_for_plot = {
        s: available_versions[s][0] for s in upgrade_durations.keys()
        }
    def _upgrade_component(self, component: str, callback: Optional[Callable] = None) -> None:
        """执行组件升级（内部方法）"""
        if component not in self.upgrade_durations:
            raise ValueError(f"未知组件: {component}")
            
        if self.upgrade_status[component]:
            print(f"警告: 组件 '{component}' 已经在升级中")
            return
            
        # 获取版本信息
        original = self.available_versions[component][0]
        target = self.upgrade_candidates[component]
        
        print(f"开始升级 {component} 从 {original} 到 {target} (预计耗时: {self.upgrade_durations[component]}秒)...")
        
        self.upgrade_status[component] = True
        self.start_times[component] = time.time()  # 记录开始时间
        
        # 创建计时器线程
        timer = threading.Timer(
            interval=self.upgrade_durations[component],
            function=self._complete_upgrade,
            args=(component, original, target, callback, self.start_times[component])
        )
        timer.start()
        
    def _complete_upgrade(self, 
                         component: str, 
                         original: str, 
                         target: str,
                         callback: Optional[Callable],
                         start_time: float) -> None:
        """升级完成处理（内部方法）"""
        # 计算实际用时
        actual_duration = time.time() - start_time
        self.upgrade_times[component] = actual_duration  # 记录用时
        
        # 检查升级是否成功
        def judge_success():
            self.success = random.randint(0, 1)
            # return(self.success)# 这里设置了随机01


#_________________________________________________________________________________________________
        # 由HCS提供
        # success = judge_success()
        judge_success()
        versions = self.available_versions[component]
        # 更新版本库
        if self.success:
            target_idx = versions.index(target)
            self.available_versions[component] = versions[target_idx:]
            
            print(f"升级成功。{component} 的可用版本已更新为: {self.available_versions[component]}")
        else:
            print(f"升级失败。{component} 的可用版本保持不变。")
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(self.available_versions, f, ensure_ascii=False, indent=4)
  
        # success = self.available_versions[component][0] == target
        
        # 打印用时信息
        time_diff = actual_duration - self.upgrade_durations[component]
        time_info = (
            f" (提前{-time_diff:.2f}秒)" if time_diff < 0 
            else f" (延迟{time_diff:.2f}秒)" if time_diff > 0 
            else " (准时完成)"
        )
        print(f"{component} 升级{'成功' if self.success else '失败'} - "
              f"实际用时: {actual_duration:.2f}秒{time_info}")
        
        # 记录版本历史
        if self.success:
            if component not in self.version_history:
                self.version_history[component] = []
            self.version_history[component].append((original, target))
        
        self.upgrade_status[component] = False
        
        if callback:
            callback(component, original, target, actual_duration)

    #_________________________________________________________________________________________________ 
    
    def get_upgrade_times(self, component: Optional[str] = None) -> Dict[str, float]:
        """获取升级用时统计"""
        if component:
            return {component: self.upgrade_times.get(component, 0.0)}
        return self.upgrade_times.copy()
            
    def create_upgrade_function(self, component: str) -> Callable:
        """
        为指定组件创建升级函数
        
        :param component: 组件名称
        :return: 升级函数
        """
        def upgrade(callback: Callable = None) -> None:
            self._upgrade_component(component, callback)
        return upgrade
    
    def get_upgrade_status(self, component: str = None) -> Dict[str, bool]:
        """
        获取升级状态
        
        :param component: 可选，指定组件名。如果为None则返回所有状态
        :return: 升级状态字典
        """
        if component:
            return {component: self.upgrade_status.get(component, False)}
        return self.upgrade_status.copy()


