# from typing import Dict, List, Tuple

# class VersionManager:
#     def update_version(self, 
#                       component: str, 
#                       success: bool, 
#                       original: str, 
#                       target: str, 
#                       available_versions: Dict[str, List[str]], 
#                       version_history: Dict[str, List[Tuple[str, str]]]) -> None:
#         """
#         处理组件的版本更新。

#         :param component: 升级的组件
#         :param success: 升级是否成功
#         :param original: 组件的原始版本
#         :param target: 升级的目标版本
#         :param available_versions: 组件的可用版本字典
#         :param version_history: 版本历史字典
#         """
#         versions = available_versions[component]

#         if success:
#             target_idx = versions.index(target)
#             available_versions[component] = versions[target_idx:]
#             # print(f"升级成功。{component} 的可用版本已更新为: {available_versions[component]}")
            
#             # 记录版本历史
#             if component not in version_history:
#                 version_history[component] = []
#             version_history[component].append((original, target))
#         # else:
#             # print(f"升级失败。{component} 的可用版本保持不变。")