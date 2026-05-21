import networkx as nx
import plotly.graph_objects as go
import pandas as pd


def build_distribution_network():
    """
    构建配电网图模型
    功能：根据IEEE33节点系统的拓扑结构，创建NetworkX有向图
    """
    G = nx.DiGraph()

    # 添加所有节点（0-32，共33个节点）
    for node in range(33):
        G.add_node(node)

    # 定义支路连接关系 (from, to, resistance, reactance)
    branch_data = [
        (0, 1, 0.0922, 0.0470), (1, 2, 0.4930, 0.2511), (2, 3, 0.3660, 0.1864),
        (3, 4, 0.3811, 0.1941), (4, 5, 0.8190, 0.7070), (5, 6, 0.1872, 0.6188),
        (6, 7, 0.7114, 0.2351), (7, 8, 1.0300, 0.7400), (8, 9, 1.0440, 0.7400),
        (9, 10, 0.1966, 0.0650), (10, 11, 0.3744, 0.1238), (11, 12, 1.4680, 1.1550),
        (12, 13, 0.5416, 0.7129), (13, 14, 0.5910, 0.5260), (14, 15, 0.7463, 0.5450),
        (15, 16, 1.2890, 1.7210), (16, 17, 0.3720, 0.5740), (1, 18, 0.1640, 0.1565),
        (18, 19, 1.5042, 1.3554), (19, 20, 0.4095, 0.4784), (20, 21, 0.7089, 0.9373),
        (2, 22, 0.4512, 0.3083), (22, 23, 0.8980, 0.7091), (23, 24, 0.8960, 0.7011),
        (5, 25, 0.2030, 0.1034), (25, 26, 0.2842, 0.1447), (26, 27, 1.0590, 0.9337),
        (27, 28, 0.8042, 0.7006), (28, 29, 0.5075, 0.2585), (29, 30, 0.9744, 0.9630),
        (30, 31, 0.3105, 0.3619), (31, 32, 0.3410, 0.5302),(7,20,2,2),(8,14,2,2),
        (11,21,2,2),(17,32,0.5,0.5),(24,28,0.5,0.5)
    ]

    for from_node, to_node, r, x in branch_data:
        G.add_edge(from_node, to_node, weight=r + x, resistance=r, reactance=x)

    return G


network = build_distribution_network()

def compute_node_positions(G):
    """
     严格遵循IEEE 33节点配电网标准接线图结构的硬编码坐标
     """
    pos = {
        # 主干线 (0-17) - 水平排列
        ** {i: (i, 0) for i in range(18)},
        # 节点1分支 (18-21) - 垂直向下
        18: (1, 0.5), 19: (2, 0.5),  20: (3, 0.5),21: (4, 0.5),

        # 节点2分支 (22-24) - 垂直向下
        22: (2, -1),23: (3, -1), 24: (4, -1),
        # 节点5分支 (25-32) - 垂直向下
        25: (5, -0.5), 26: (6, -0.5), 27: (7, -0.5),
        28: (8, -0.5), 29: (9, -0.5), 30: (10, -0.5),
        31: (11, -0.5), 32: (12, -0.5)
    }
    return pos


def extract_plotly_coordinates(G, pos):
    """提取用于Plotly绘图的坐标数组"""
    # 提取节点坐标
    node_x = [pos[node][0] for node in G.nodes()]
    node_y = [pos[node][1] for node in G.nodes()]

    # 提取边坐标（每条边由起点(x0,y0)和终点(x1,y1)两个点组成）
    edge_x = []
    edge_y = []
    for u, v in G.edges():
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        # 使用None分隔不同的边
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    return node_x, node_y, edge_x, edge_y


def plot_carbon_intensity_topology(G, pos, carbon_intensity_data, threshold=0.5):
    """
    功能：生成交互式配电网拓扑图，用颜色表示节点碳势高低
    参数：
    - carbon_intensity_data: Dictionary {node: carbon_intensity_value}
    - threshold: 碳势分级阈值，用于颜色映射类
    """
    node_x, node_y, edge_x, edge_y = extract_plotly_coordinates(G, pos)

    # 为每个节点确定颜色（基于碳势值实现色彩映射）
    node_colors = []
    for node in G.nodes():
        ci = carbon_intensity_data.get(node, 0)
        # 使用plotly内置的色阶 (0→绿，0.5→黄，1→红)
        node_colors.append(ci)

    # 构建Edge trace
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        mode='lines',
        line=dict(width=1.5, color='#888'),
        hoverinfo='none',
        name='输电线路'
    )

    # 构建Node trace
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        marker=dict(
            size=20,
            color=node_colors,  # 颜色由碳势数据驱动
            colorscale='Viridis',  # 可换为 'RdYlGn' 红绿渐变
            colorbar=dict(title='碳势 (kgCO₂/kWh)'),
            showscale=True,
            line_width=2
        ),
        text=[f"节点 {node}<br>碳势: {carbon_intensity_data.get(node, 0):.3f}" for node in G.nodes()],
        textposition="top center",
        hoverinfo='text',
        name='电网节点'
    )

    # 合并创建图形
    fig = go.Figure(data=[edge_trace, node_trace])

    # 布局设置
    fig.update_layout(
        title='配电网节点碳势分布图',
        showlegend=False,
        hovermode='closest',
        margin=dict(b=20, l=5, r=5, t=40),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
    )

    return fig

if __name__ == "__main__":
      # 生成示例碳势数据
      carbon_intensity_data = {node: 0.2 + 0.6 * (node % 5) / 4 for node in range(33)}
      # 计算节点位置
      pos = compute_node_positions(network)
      # 生成并显示图表（注意：这里调用的是已定义的函数）
      fig = plot_carbon_intensity_topology(network, pos, carbon_intensity_data)
      fig.show()
