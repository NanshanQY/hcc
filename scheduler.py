# sjx可运行版本
# 目前是不连续显示的时间窗
from gurobipy import Model, GRB, quicksum
import json
import matplotlib.pyplot as plt
from upgrader import AppUpgrader
from visualizer import AppUpgradeVisualizer
import time
from controller import goon
from copy import deepcopy
# Load data
from optimizer import optimize
with open('data copy.json', 'r') as f:
    data = json.load(f)

data1 = deepcopy(data)  # 使用 deepcopy 确保不会修改原始数据


services = list(data['available_versions'].keys())
available_versions = data1['available_versions']

incompatible_pairs = data['incompatible_pairs']
upgrade_duration = data['upgrade_duration']


#___________________________________________________________________________________________


total_time = 20
 
while available_versions:
    # 初始化时间窗的开始时间
    start_time = time.time()
    current_time = start_time
    print("当前时间:", start_time)

    # 嵌套循环：在当前时间窗内调度
    while (current_time - start_time) < total_time:
        print("当前时间:", start_time)
        rest_time = total_time - (current_time - start_time)  # 计算当前时间窗的剩余时间
        print(f"当前时间窗剩余时间: {start_time:.1f} ,{rest_time:.1f}秒")
        if rest_time <= 0:
            print("当前时间窗已用尽")
            break
# 
        # 在每次升级前询问用户是否继续
        user_input = goon(rest_time)
        if user_input != "1":
            print("结束当前时间窗")
            break
        current_time = time.time()  # 重置开始时间
        rest_time = total_time - (current_time - start_time)  # 计算当前时间窗的剩余时间

        # 调用优化器选择升级服务
        selected_services, upgrade_candidates = optimize(available_versions, incompatible_pairs, upgrade_duration, rest_time)
        if not selected_services:
            print("没有可升级组件")
            break

        # 创建 AppUpgrader
        upgrade_durations = {s: upgrade_duration[s] for s in selected_services}
        upgrader = AppUpgrader(upgrade_durations, available_versions, upgrade_candidates)

        # 调用可视化函数，传递 start_time
        services = list(available_versions.keys())  # 所有组件作为纵轴
        visualizer = AppUpgradeVisualizer(upgrader, services, total_time, start_time)
#—————————————————————————————————————————————————————————————————————————————————————————————————————
        # 启动升级
        for key in selected_services:
            upgrade = upgrader.create_upgrade_function(key)
            upgrade()

        visualizer.animate()
#—————————————————————————————————————————————————————————————————————————————————————————————————————
        # 等待所有升级完成
        while any(upgrader.get_upgrade_status().values()):
            time.sleep(0.1)
            current_time = time.time()  # 更新当前时间

        # 更新当前时间
        current_time = time.time()

        # 更新版本
        for component in selected_services:
            # original = available_versions[component][0]
            # target = upgrade_candidates[component]
            available_versions = data1['available_versions']

        print("更新后的 available_versions:", available_versions)

    print("进入下一个时间窗")