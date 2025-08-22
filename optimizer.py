from gurobipy import Model, GRB, quicksum
import json
import matplotlib.pyplot as plt
from upgrader import AppUpgrader
from visualizer import AppUpgradeVisualizer
import time
from copy import deepcopy

# Load data
with open('data copy.json', 'r') as f:
    data = json.load(f)

data1 = deepcopy(data)  # 使用 deepcopy 确保不会修改原始数据


services = list(data['available_versions'].keys())
available_versions = data1['available_versions']
parellel = data['parellel']

incompatible_pairs = data['incompatible_pairs']
upgrade_duration = data['upgrade_duration']

# 版本索引函数
def version_index(s, v):
    return available_versions[s].index(v)

# 升级函数，返回升级服务和目标版本，以及所有候选服务
def optimize(available_versions, incompatible_pairs, upgrade_duration, rest_time):
    current_versions = {s: available_versions[s][0] for s in services}  # Current version is the lowest
    # 当前版本索引
    current_idx = {s: version_index(s, current_versions[s]) for s in services}
    m = Model("Next_Batch_Upgrade_Candidates")
    # 决策变量：x[s, v] 表示是否选择将 s 升级到 v
    x = {}
    for s in services:
        for v in available_versions[s]:
            v_idx = version_index(s, v)
            # 仅当升级时长小于 rest_time 且版本索引满足条件时，添加决策变量
            if v_idx > current_idx[s] and v_idx <= current_idx[s] + 2 and upgrade_duration[s] < rest_time:
                x[s, v] = m.addVar(vtype=GRB.BINARY, name=f"x_{s}_{v}")

    # 辅助变量：表示服务 s 是否被选择升级
    selected = {s: m.addVar(vtype=GRB.BINARY, name=f"selected_{s}") for s in services}

    # 约束
    # 1. 每个服务至多选择一个目标版本
    for s in services:
        possible_v = [v for v in available_versions[s] if version_index(s, v) > current_idx[s] and version_index(s, v) <= current_idx[s] + 2]
        m.addConstr(quicksum(x[s, v] for v in possible_v if (s, v) in x) <= 1)
        m.addConstr(selected[s] == quicksum(x[s, v] for v in possible_v if (s, v) in x))

    # 2. 不兼容约束
    for s1, v1, s2, v2 in incompatible_pairs:
        # Post-upgrade compatibility: Target versions in the candidate set must not be incompatible
        if (s1, v1) in x and (s2, v2) in x:
            m.addConstr(x[s1, v1] + x[s2, v2] <= 1)
        # Mixed state compatibility: Target version vs. current version of non-upgraded service
        if (s1, v1) in x and s2 in services and v2 == current_versions[s2]:
            m.addConstr(x[s1, v1] + selected[s2] <= 1)
        if (s2, v2) in x and s1 in services and v1 == current_versions[s1]:
            m.addConstr(x[s2, v2] + selected[s1] <= 1)
        # Upgrade process compatibility: Current versions of selected services must be compatible
        if v1 == current_versions[s1] and v2 == current_versions[s2]:
            m.addConstr(selected[s1] + selected[s2] <= 1)

    # 目标：最大化升级后版本索引的和
    m.setObjective(quicksum(version_index(s, v) * x[s, v] for s in services for v in available_versions[s] if (s, v) in x), GRB.MAXIMIZE)

    m.optimize()


    if m.status == GRB.OPTIMAL:
        print("候选升级服务及其目标版本（可任意选择组合）：")
        upgrade_candidates = {}
        for s in services:
            for v in available_versions[s]:
                if (s, v) in x and x[s, v].X > 0.5:
                    upgrade_candidates[s] = v
                    print(f"{s}: {current_versions[s]} -> {v}")
        if not upgrade_candidates:
            print("未找到可升级的候选服务")
    else:
        print("未找到可行解")

    # 获取候选升级服务
    upgrade_candidates = {}
    if m.status == GRB.OPTIMAL:
        for s in services:
            for v in available_versions[s]:
                if (s, v) in x and x[s, v].X > 0.5:
                    upgrade_candidates[s] = v

    # 选择升级时间最长的3个服务
    return(sorted(upgrade_candidates.keys(), key=lambda s: upgrade_duration[s], reverse=True)[:min(parellel, len(available_versions))], upgrade_candidates)