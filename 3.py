import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta


# ==================== 页面配置与样式 ====================
st.set_page_config(
    page_title="基于IEEE33碳势监测系统",
    page_icon="🌿",
    layout="wide"
)

# 自定义 CSS 样式
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: #2e7d32;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #558b2f;
        margin-bottom: 0.5rem;
        font-weight: bold;
    }
    .metric-card {
        background-color: #f0f7ea;
        border-radius: 12px;
        padding: 0.8rem;
        text-align: center;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🌱 基于IEEE33碳势动态监测系统</div>', unsafe_allow_html=True)


# ==================== 色彩映射函数 ====================
def carbon_intensity_color(value):
    """
    根据碳势值返回对应的颜色代码
    """
    if isinstance(value, (int, float)):
        value = float(value)
    if value <= 200:
        return '#1b5e20'  # 深绿色
    elif value <= 400:
        return '#827717'  # 黄绿色
    elif value <= 600:
        return '#ff8f00'  # 琥珀色
    elif value <= 800:
        return '#bf360c'  # 橙色
    else:
        return '#b71c1c'  # 红色


def get_custom_colorscale():
    """
    返回Plotly可用的自定义色阶
    色阶定义：0.0-0.2 (绿), 0.2-0.4 (黄绿), 0.4-0.6 (黄), 0.6-0.8 (橙), 0.8-1.0 (红)
    """
    return [
        (0.00, '#1b5e20'),  # [0, 200] → 深绿
        (0.20, '#1b5e20'),  # 等位线重合 → 离散块
        (0.20, '#827717'),
        (0.40, '#827717'),  # [200, 400] → 黄绿
        (0.40, '#ff8f00'),
        (0.60, '#ff8f00'),  # [400, 600] → 黄
        (0.60, '#bf360c'),
        (0.80, '#bf360c'),  # [600, 800] → 橙
        (0.80, '#b71c1c'),
        (1.00, '#b71c1c'),  # [800, 1000] → 红
    ]


# ==================== 数据生成模块 ====================
def generate_mock_data(node_count=10, hours=72):
    """
    生成模拟碳势数据
    """
    np.random.seed(42)  # 保证模拟数据可重现
    end_time = datetime.now().replace(second=0, microsecond=0)
    start_time = end_time - timedelta(hours=hours)
    time_index = pd.date_range(start=start_time, end=end_time, freq='h')

    # 生成不同趋势的节点碳势
    data_dict = {'time': time_index}
    base_trend = np.linspace(350, 650, len(time_index))  # 基线趋势
    noise = np.random.normal(0, 45, len(time_index))
    base_trend = np.clip(base_trend + noise, 150, 950)

    for i in range(node_count):
        phase_shift = (i / node_count) * np.pi * 2
        daily_pattern = 150 * np.sin(2 * np.pi * np.arange(len(time_index)) / 24 + phase_shift)
        node_trend = base_trend + daily_pattern * 0.6 + np.random.normal(0, 25, len(time_index))
        data_dict[f'node_{i}'] = np.clip(node_trend, 120, 980).round(1)

    return pd.DataFrame(data_dict)


def generate_ieee33_layout():
    """
    生成IEEE 33节点示例布局坐标
    实际项目应替换为真实的地理或拓扑坐标
    """
    # 简化的双分支拓扑布局
    layout = {}
    x_coords = [
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17,
        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16
    ]
    y_coords = [
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3
    ]

    # 调整部分节点位置形成第二分支
    for i in range(18, 33):
        x_coords[i] = x_coords[i - 17] + 0.5
        y_coords[i] = y_coords[i - 17] - 1.5 if i % 2 == 0 else y_coords[i - 17] - 0.5

    for i in range(33):
        layout[f'node_{i}'] = (x_coords[i], y_coords[i])
    return layout


# ==================== 3. 热力图绘制函数 ====================
def plot_spatial_carbon_heatmap(selected_nodes, carbon_values, layout_positions):
    """
    绘制空间碳势热力图
    """
    if not layout_positions:
        # 生成默认环形布局
        n = len(selected_nodes)
        angles = np.linspace(0, 2 * np.pi, n + 1)[:-1]
        radius = 5
        x_coords = radius * np.cos(angles)
        y_coords = radius * np.sin(angles)
        layout_positions = {node: (x_coords[i], y_coords[i]) for i, node in enumerate(selected_nodes)}

    x_vals = [layout_positions[node][0] for node in selected_nodes]
    y_vals = [layout_positions[node][1] for node in selected_nodes]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=x_vals,
        y=y_vals,
        mode='markers+text',
        marker=dict(
            size=40,
            color=carbon_values,
            colorscale=get_custom_colorscale(),
            showscale=True,
            colorbar=dict(
                title="碳势 (gCO₂/kWh)",
                thickness=15,
                len=0.7,
                tickvals=[200, 400, 600, 800, 1000],
                ticktext=["≤200 (低)", "400 (中低)", "600 (中)", "800 (高)", "≥1000 (极高)"],
                tickfont=dict(size=11)
            ),
            line=dict(width=1.5, color='white'),
            opacity=0.85
        ),
        text=selected_nodes,
        textposition="middle center",
        textfont=dict(color="white", size=9, family="Arial Black"),
        hoverinfo='text',
        hovertext=[f"{node}<br>碳势: {val:.1f} gCO₂/kWh" for node, val in zip(selected_nodes, carbon_values)],
        name="碳势节点"
    ))

    fig.update_layout(
        title=dict(text="配电网络碳势热力图", x=0.5, font=dict(size=16)),
        xaxis=dict(
            title="X 坐标",
            showgrid=True,
            gridwidth=0.5,
            gridcolor='lightgray',
            zeroline=False,
            showticklabels=False
        ),
        yaxis=dict(
            title="Y 坐标",
            showgrid=True,
            gridwidth=0.5,
            gridcolor='lightgray',
            zeroline=False,
            showticklabels=False
        ),
        height=500,
        plot_bgcolor='white',
        margin=dict(l=40, r=40, t=70, b=40)
    )

    return fig


# ==================== 4. 主应用 ====================
def main():
    # 初始化 session_state
    if "last_update_time" not in st.session_state:
        st.session_state.last_update_time = datetime.now()
        st.session_state.timestamp_enabled = True

    # 配置参数
    node_list = [f'node_{i}' for i in range(33)]
    layout_positions = generate_ieee33_layout()

    # ========== 侧边栏控制面板 ==========
    with st.sidebar:
        st.markdown("## ⚙️ 控制面板")

        # 节点选择
        selected_nodes = st.multiselect(
            "📡 选择节点",
            options=node_list,
            default=node_list[:10],
            help="选择要在图表中显示的节点"
        )

        if not selected_nodes:
            st.warning("⚠️ 请至少选择一个节点")
            selected_nodes = node_list[:10]

        # 时间范围选择
        st.markdown("### ⏰ 时间范围")
        hours_back = st.slider(
            "回溯小时数",
            min_value=1,
            max_value=168,
            value=72,
            step=6,
            help="选择要显示的时间范围（小时）"
        )

        # 数据更新时间设置
        auto_update = st.checkbox("🔄 自动实时更新", value=True)
        if auto_update:
            update_interval = st.number_input("更新间隔（秒）", min_value=5, max_value=300, value=60, step=5)

            if st.button("⏰ 立即更新"):
                st.cache_data.clear()
                st.session_state.last_update_time = datetime.now()
                st.rerun()

        st.divider()

        # 指标汇总区域
        st.markdown("### 📊 实时指标")

    # ========== 数据处理 ==========
    # 生成数据
    df = generate_mock_data(len(node_list), hours=hours_back)

    # 提取当前时间碳势值
    current_carbon_vals = [df[selected_nodes[i]].iloc[-1] for i in range(len(selected_nodes))]

    # 计算关键指标
    avg_carbon = np.mean(current_carbon_vals)
    max_carbon = max(current_carbon_vals)
    max_node = selected_nodes[current_carbon_vals.index(max_carbon)]
    min_carbon = min(current_carbon_vals)
    min_node = selected_nodes[current_carbon_vals.index(min_carbon)]

    # ========== 指标卡片 ==========
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 1.2rem; color: #2e7d32;">📊 平均碳势</div>
            <div style="font-size: 2rem; font-weight: bold;">{avg_carbon:.0f}</div>
            <div style="font-size: 0.8rem;">gCO₂/kWh</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 1.2rem; color: #d32f2f;">🔥 最高碳势</div>
            <div style="font-size: 1.6rem; font-weight: bold;">{max_carbon:.0f}</div>
            <div style="font-size: 0.8rem;">{max_node}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 1.2rem; color: #2e7d32;">🍃 最低碳势</div>
            <div style="font-size: 1.6rem; font-weight: bold;">{min_carbon:.0f}</div>
            <div style="font-size: 0.8rem;">{min_node}</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # ========== 动态时序图表 ==========
    st.markdown('<div class="sub-header">📈 时序碳势变化趋势</div>', unsafe_allow_html=True)

    if df.empty or not selected_nodes:
        st.info("📭 暂无数据显示，请调整筛选条件")
    else:
        line_fig = px.line(
            df,
            x='time',
            y=selected_nodes,
            title='各节点碳势变化趋势',
            labels={'time': '时间', 'value': '碳势 (gCO₂/kWh)', 'variable': '节点'},
            color_discrete_sequence=px.colors.qualitative.Plotly
        )

        # 更新折线图样式
        for trace in line_fig.data:
            trace.update(mode='lines+markers', marker=dict(size=4))

        line_fig.update_layout(
            height=500,
            hovermode='x unified',
            xaxis_title="时间",
            yaxis_title="碳势 (gCO₂/kWh)",
            yaxis=dict(
                range=[0, 1100],
                tickvals=[200, 400, 600, 800, 1000],
                ticktext=["200 (低)", "400 (中低)", "600 (中)", "800 (高)", "1000 (极高)"]
            ),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            plot_bgcolor='white',
            xaxis=dict(showgrid=True, gridwidth=0.5, gridcolor='lightgray',
                       title_font=dict(size=12))
        )

        # 添加色彩背景区域
        line_fig.add_hrect(y0=0, y1=200, line_width=0, fillcolor="#1b5e20", opacity=0.1)
        line_fig.add_hrect(y0=200, y1=400, line_width=0, fillcolor="#827717", opacity=0.1)
        line_fig.add_hrect(y0=400, y1=600, line_width=0, fillcolor="#ff8f00", opacity=0.1)
        line_fig.add_hrect(y0=600, y1=800, line_width=0, fillcolor="#bf360c", opacity=0.1)
        line_fig.add_hrect(y0=800, y1=1100, line_width=0, fillcolor="#b71c1c", opacity=0.1)

        # 添加范围滑块
        line_fig.update_xaxes(rangeslider_visible=True, rangeslider=dict(thickness=0.05))

        st.plotly_chart(line_fig, width='stretch')

    st.divider()

    # ========== 空间碳势分布热力图 ==========
    st.markdown('<div class="sub-header">🗺️ 空间碳势分布热力图</div>', unsafe_allow_html=True)

    heatmap_col1, heatmap_col2 = st.columns([4, 1])
    with heatmap_col1:
        heatmap_fig = plot_spatial_carbon_heatmap(
            selected_nodes,
            current_carbon_vals,
            {node: layout_positions.get(node, (i % 5, i // 5)) for i, node in enumerate(selected_nodes)}
        )
        st.plotly_chart(heatmap_fig, width='stretch')

    with heatmap_col2:
        st.markdown("""
        <div style="background-color: #f5f5f5; padding: 12px; border-radius: 10px;">
            <p style="font-weight: bold; margin-bottom: 10px;">📌 色阶说明</p>
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <div style="width: 20px; height: 20px; background-color: #1b5e20; border-radius: 4px;"></div>
                <span style="margin-left: 10px;">≤ 200 → 碳势极低</span>
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <div style="width: 20px; height: 20px; background-color: #827717; border-radius: 4px;"></div>
                <span style="margin-left: 10px;">200 - 400 → 碳势较低</span>
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <div style="width: 20px; height: 20px; background-color: #ff8f00; border-radius: 4px;"></div>
                <span style="margin-left: 10px;">400 - 600 → 中度碳势</span>
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <div style="width: 20px; height: 20px; background-color: #bf360c; border-radius: 4px;"></div>
                <span style="margin-left: 10px;">600 - 800 → 碳势较高</span>
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <div style="width: 20px; height: 20px; background-color: #b71c1c; border-radius: 4px;"></div>
                <span style="margin-left: 10px;">≥ 800 → 碳势极高</span>
            </div>
        </div>

        <div style="margin-top: 16px; background-color: #e8f5e9; padding: 10px; border-radius: 8px;">
            <p style="font-weight: bold; margin-bottom: 5px;">💡 优化建议</p>
        """, unsafe_allow_html=True)

        if max_carbon > 800:
            st.error(f"🔴 节点 {max_node} 碳势过高，建议优化发电/用电策略")
        elif max_carbon > 600:
            st.warning(f"⚠️ 节点 {max_node} 碳势偏高，请关注运行状态")
        else:
            st.success("✅ 当前网络碳势处于正常范围")
        st.markdown("</div>", unsafe_allow_html=True)

    # ========== 高级统计分析 ==========
    with st.expander("📈 高级统计分析", expanded=False):
        tab1, tab2 = st.tabs(["📊 统计摘要", "📉 分布分析"])
        with tab1:
            st.dataframe(df[selected_nodes].describe().round(2))
        with tab2:
            # 箱线图 - 碳势分布
            box_fig = px.box(
                df[selected_nodes].melt(var_name='节点', value_name='碳势'),
                x='节点',
                y='碳势',
                title='各节点碳势分布箱线图',
                color='节点',
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            box_fig.update_layout(height=400, xaxis=dict(tickangle=45))
            st.plotly_chart(box_fig, width='stretch')

            # 相关性矩阵
            st.markdown("#### 🔗 节点碳势相关性矩阵")
            corr_matrix = df[selected_nodes].corr()
            corr_fig = px.imshow(
                corr_matrix,
                text_auto='.2f',
                title="节点碳势相关性热力图",
                color_continuous_scale='RdBu_r',
                zmin=-1,
                zmax=1
            )
            corr_fig.update_layout(height=500, xaxis=dict(tickangle=45))
            st.plotly_chart(corr_fig, width='stretch')

    # ========== 页脚 ==========
    st.divider()
    st.caption(
        f"🕒 最后更新: {st.session_state.last_update_time.strftime('%Y-%m-%d %H:%M:%S')} | 若开启自动更新，页面将根据设定间隔刷新")

if __name__ == "__main__":
    main()