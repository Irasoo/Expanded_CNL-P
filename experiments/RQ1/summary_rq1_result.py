# ========= 修正与增强收集：重新遍历并覆盖时间列表 =========
import re
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# 清空并重建（覆盖先前误判的结果）
group1_risen_time_spent = []
group1_cnlp_time_spent = []
group2_risen_time_spent = []
group2_cnlp_time_spent = []
risen_time_spent = []
cnlp_time_spent = []

group1_rating_dfs = []
group2_rating_dfs = []

def extract_prompt_type_and_time_robust(py_path):
    """
    从 dietary_advice_assistant.py 提取:
      - 类型: "RISEN" / "CNL-P" / None
      - time_spent: int / None
    更鲁棒的正则，支持三引号与单/双引号。
    """
    try:
        with open(py_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return None, None

    # 三引号或单/双引号内容
    qpat = r'(?P<q>"""|\'\'\'|"|\')(?P<txt>.*?)(?P=q)'

    cnlp_match = re.search(r'cnlp_prompt\s*=\s*' + qpat, content, re.S)
    risen_match = re.search(r'risen_prompt\s*=\s*' + qpat, content, re.S)

    # time_spent: 允许有/无注解
    time_match = re.search(r'time_spent\s*:?\s*int?\s*=\s*(\d+)', content)
    time_val = int(time_match.group(1)) if time_match else None

    # 类型判定（按你原先规则：若两者都有，取更长）
    if cnlp_match and not risen_match:
        ttype = "CNL-P"
    elif risen_match and not cnlp_match:
        ttype = "RISEN"
    elif cnlp_match and risen_match:
        cnlp_len = len(cnlp_match.group("txt"))
        risen_len = len(risen_match.group("txt"))
        ttype = "RISEN" if risen_len >= cnlp_len else "CNL-P"
    else:
        ttype = None

    return ttype, time_val

def extract_time_robust(py_path):
    """从任一 assistant.py 中提取 time_spent（宽松匹配）"""
    try:
        with open(py_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return None
    m = re.search(r'time_spent\s*:?\s*int?\s*=\s*(\d+)', content)
    return int(m.group(1)) if m else None

BASE_DIR = "user_study_result"

for group_name in ["group1", "group2"]:
    group_path = os.path.join(BASE_DIR, group_name)
    for root, dirs, files in os.walk(group_path):
        files_set = set(files)

        # 读取 rating（兼容变体文件名）
        for f in files:
            if re.match(r'rating_scale.*\.csv$', f, re.I):
                csv_path = os.path.join(root, f)
                try:
                    df = pd.read_csv(csv_path)
                    if group_name == "group1":
                        group1_rating_dfs.append(df)
                    else:
                        group2_rating_dfs.append(df)
                except Exception:
                    pass  # 忽略坏文件

        if {"dietary_advice_assistant.py", "travel_advice_assistant.py"}.issubset(files_set):
            dietary_path = os.path.join(root, "dietary_advice_assistant.py")
            travel_path  = os.path.join(root, "travel_advice_assistant.py")

            ttype, t_diet = extract_prompt_type_and_time_robust(dietary_path)
            t_trav = extract_time_robust(travel_path)

            # 如果两个时间都拿到了，但类型不明确，则用“一致性约束”分配：
            if t_diet is not None and t_trav is not None and ttype is None:
                # 大者为 CNL-P，小者为 RISEN（相等时约定 travel 归 CNL-P）
                if t_trav > t_diet:
                    risen_t, cnlp_t = t_diet, t_trav
                elif t_trav < t_diet:
                    risen_t, cnlp_t = t_trav, t_diet
                else:
                    risen_t, cnlp_t = t_diet, t_trav  # 相等：让 travel 当 CNL-P 也可，这里保持一致（都相等影响不大）
            elif t_diet is not None and t_trav is not None and ttype is not None:
                # 有类型时，按“dietary 的类型 + travel 为另一类”
                if ttype == "RISEN":
                    risen_t, cnlp_t = t_diet, t_trav
                else:  # CNL-P
                    risen_t, cnlp_t = t_trav, t_diet

                # 一致性约束：若不满足 CNL-P ≥ RISEN，则交换
                if cnlp_t is not None and risen_t is not None and cnlp_t < risen_t:
                    risen_t, cnlp_t = cnlp_t, risen_t
            else:
                # 只有一个 time 或全无
                risen_t = cnlp_t = None
                if ttype == "RISEN" and t_diet is not None:
                    risen_t = t_diet
                elif ttype == "CNL-P" and t_diet is not None:
                    cnlp_t = t_diet
                # 若只拿到 travel 的 time，但没有类型，无法可靠分配 -> 跳过

            # 将结果塞入列表
            if risen_t is not None:
                if group_name == "group1":
                    group1_risen_time_spent.append(risen_t)
                else:
                    group2_risen_time_spent.append(risen_t)
                risen_time_spent.append(risen_t)

            if cnlp_t is not None:
                if group_name == "group1":
                    group1_cnlp_time_spent.append(cnlp_t)
                else:
                    group2_cnlp_time_spent.append(cnlp_t)
                cnlp_time_spent.append(cnlp_t)

# 合并 rating

group1_rating_df = pd.concat(group1_rating_dfs, ignore_index=True) if group1_rating_dfs else pd.DataFrame()
print(group1_rating_df.head(20))
group2_rating_df = pd.concat(group2_rating_dfs, ignore_index=True) if group2_rating_dfs else pd.DataFrame()
print(group2_rating_df.head(30))
all_rating_df = pd.concat([group1_rating_df, group2_rating_df], ignore_index=True) if not (group1_rating_df.empty and group2_rating_df.empty) else pd.DataFrame()

# ===== 打印核对（可选）=====
print("\n[Rebuilt] group1_risen_time_spent:", group1_risen_time_spent)
print("[Rebuilt] group1_cnlp_time_spent:", group1_cnlp_time_spent)
print("[Rebuilt] group2_risen_time_spent:", group2_risen_time_spent)
print("[Rebuilt] group2_cnlp_time_spent:", group2_cnlp_time_spent)

# ========= 统计与绘图 =========

def remove_zeros_and_mean(lst):
    arr = np.array([x for x in lst if (x is not None and x != 0)])
    return arr.mean() if len(arr) > 0 else float('nan')

# 1) time spent: 计算均值（去 0）
mean_g1_risen = remove_zeros_and_mean(group1_risen_time_spent)
mean_g1_cnlp = remove_zeros_and_mean(group1_cnlp_time_spent)
mean_g2_risen = remove_zeros_and_mean(group2_risen_time_spent)
mean_g2_cnlp = remove_zeros_and_mean(group2_cnlp_time_spent)
mean_risen   = remove_zeros_and_mean(risen_time_spent)
mean_cnlp    = remove_zeros_and_mean(cnlp_time_spent)

print("\n=== Time Spent (去 0 后均值) ===")
print(f"Group1 RISEN: {mean_g1_risen:.2f}")
print(f"Group1 CNL-P: {mean_g1_cnlp:.2f}")
print(f"Group2 RISEN: {mean_g2_risen:.2f}")
print(f"Group2 CNL-P: {mean_g2_cnlp:.2f}")
print(f"ALL  RISEN:   {mean_risen:.2f}")
print(f"ALL  CNL-P:   {mean_cnlp:.2f}")

# ======= 绘图（雷达：两组并排；箱线：按类型各一张，六个箱子 D1-D6，合并两组数据） =======
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

def plot_radar_two_groups(df1, df2):
    categories = ["D1","D2","D3","D4","D5","D6"]
    N = len(categories)
    angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    fig, axes = plt.subplots(1, 2, subplot_kw=dict(polar=True), figsize=(12,6))

    # 先计算全局最大值（两个 group 的所有均值）
    all_vals = []
    for df in [df1, df2]:
        if not df.empty:
            for t in ["RISEN", "CNL-P"]:
                if t in df["type"].unique():
                    vals = df[df["type"] == t][categories].mean().tolist()
                    all_vals.extend(vals)
    global_max = max(all_vals) if all_vals else 0
    ylim = int(np.ceil(global_max))  # 向上取整为整数

    for ax, df, title in zip(axes, [df1, df2], ["Group1", "Group2"]):
        if df.empty:
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(categories)
            ax.set_title(title)
            continue

        df_use = df[["type"] + categories].copy()

        for t, style in zip(["RISEN", "CNL-P"], ["black", "dimgray"]):
            if t in df_use["type"].unique():
                vals = df_use[df_use["type"] == t][categories].mean().tolist()
                vals += vals[:1]
                ax.plot(angles, vals, label=t, color=style)
                ax.fill(angles, vals, alpha=0.25, color=style)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories)
        ax.set_title(title)
        ax.legend(loc='upper right')

        # === 统一刻度 ===
        ax.set_ylim(0, ylim)
        ax.set_yticks(range(0, ylim+1, 1))  # 强制间隔为 1

    plt.tight_layout()
    plt.show()

# ====== 调用：先雷达（两个子图），再两张按类型的箱线图（每张 6 个箱子 D1-D6，合并两组） ======
plot_radar_two_groups(group1_rating_df, group2_rating_df)   # 第一幅：两个雷达图（Group1 / Group2）

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle


import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle


def plot_stacked_bars(df1, df2, ncols=3, nrows=2, figsize=(16, 8),
                      bar_height=0.10, y_gap=0.05, xtick_step=2,
                      group_colors=None):
    """
    Plot a grid of stacked horizontal bar charts for categories D1 to D6.
    - Y-axis: Scores 1 to 5
    - Right: CNL-P (positive, Group2 bottom, Group1 top)
    - Left: RISEN (negative, but labels show positive values)
    - bar_height: thickness of bars
    - y_gap: spacing between bars (independent of bar_height)
    """

    # 默认颜色
    if group_colors is None:
        group_colors = {"Group1": "#D3D3D3", "Group2": "#696969"}  # 浅灰和深灰

    # 类别列表
    categories = ["D1", "D2", "D3", "D4", "D5", "D6"]

    # 输入验证
    def validate_df(df, name):
        if df is None or df.empty:
            raise ValueError(f"{name} is empty or not provided")
        if "type" not in df.columns:
            raise ValueError(f"{name} missing 'type' column")
        for cat in categories:
            if cat not in df.columns:
                raise ValueError(f"{name} missing column {cat}")

    validate_df(df1, "df1")
    validate_df(df2, "df2")

    # 计算频次
    def get_count(df, t, col, score):
        return df[(df["type"] == t) & (df[col] == score)].shape[0]

    # 确定横轴最大值
    max_count = 0
    for cat in categories:
        for score in range(1, 6):
            counts = [
                get_count(df1, "CNL-P", cat, score) + get_count(df2, "CNL-P", cat, score),
                get_count(df1, "RISEN", cat, score) + get_count(df2, "RISEN", cat, score)
            ]
            max_count = max(max_count, max(counts))

    max_count = max(max_count, xtick_step * 2)  # 最小范围
    max_tick = int(np.ceil(max_count / xtick_step) * xtick_step)
    xticks = np.arange(-max_tick, max_tick + 1, xtick_step)

    # 创建画布和子图
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, sharey=False)
    axes = axes.flatten()

    # 绘制每个子图
    for idx, cat in enumerate(categories):
        ax = axes[idx]
        scores = range(1, 6)

        # 重新计算每个score的y坐标
        y_positions = [i * (bar_height + y_gap) for i in range(len(scores))]

        for y, score in zip(y_positions, scores):
            # CNL-P (右侧)
            g2_cnlp = get_count(df2, "CNL-P", cat, score)
            g1_cnlp = get_count(df1, "CNL-P", cat, score)
            if g2_cnlp > 0:
                ax.barh(y, g2_cnlp, height=bar_height, left=0,
                        color=group_colors["Group2"], edgecolor="black", linewidth=0.5)
            if g1_cnlp > 0:
                ax.barh(y, g1_cnlp, height=bar_height, left=g2_cnlp,
                        color=group_colors["Group1"], edgecolor="black", linewidth=0.5)

            # RISEN (左侧)
            g2_risen = get_count(df2, "RISEN", cat, score)
            g1_risen = get_count(df1, "RISEN", cat, score)
            if g2_risen > 0:
                ax.barh(y, -g2_risen, height=bar_height, left=0,
                        color=group_colors["Group2"], edgecolor="black", linewidth=0.5)
            if g1_risen > 0:
                ax.barh(y, -g1_risen, height=bar_height, left=-g2_risen,
                        color=group_colors["Group1"], edgecolor="black", linewidth=0.5)

        # 设置y轴
        ax.set_yticks(y_positions)
        ax.set_yticklabels(scores, fontsize=10)
        ax.set_ylim(-bar_height, max(y_positions) + bar_height + y_gap)

        # 设置x轴
        ax.set_xlim(-max_tick, max_tick)
        ax.set_xticks(xticks)
        ax.set_xticklabels([str(abs(int(x))) for x in xticks], fontsize=10)

        ax.set_xlabel(cat, fontsize=11)
        ax.axvline(0, color="black", linewidth=0.8)
        ax.grid(axis="x", linestyle="--", linewidth=0.4, alpha=0.7)

    # 关闭多余子图
    for j in range(len(categories), nrows * ncols):
        axes[j].axis("off")

    # 全局轴标签
    fig.text(0.5, 0.02, "Count", ha="center", va="center", fontsize=12)
    fig.text(0.04, 0.5, "Score", ha="center", va="center", rotation="vertical", fontsize=12)

    # 图例
    handles = [
        Rectangle((0, 0), 1, 1, color=group_colors["Group1"], edgecolor="black", label="Group1"),
        Rectangle((0, 0), 1, 1, color=group_colors["Group2"], edgecolor="black", label="Group2")
    ]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.98, 0.98),
               frameon=True, fontsize=10, edgecolor="black")

    # 调整布局
    plt.subplots_adjust(left=0.08, right=0.92, top=0.95, bottom=0.08, wspace=0.15, hspace=0.25)
    plt.show()


plot_stacked_bars(group1_rating_df, group2_rating_df)




