import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# Page configuration
st.set_page_config(
    page_title="Weekly Scheduling Impact Analysis",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🍽️ Food Delivery: Weekly Scheduling Feature Impact")
st.markdown(
    "**Business Proposition**: Enable users to schedule their food orders for the entire week in advance"
)

# Sidebar configuration
st.sidebar.header("⚙️ Configuration Parameters")

# Main parameters
num_users = st.sidebar.number_input(
    "Number of Users",
    min_value=1000,
    max_value=1000000,
    value=50000,
    step=1000,
    help="Total number of active users on the platform",
)

scheduling_adoption = st.sidebar.slider(
    "% of Users Who Use Weekly Scheduling",
    min_value=5,
    max_value=80,
    value=25,
    step=5,
    help="Percentage of users expected to adopt the weekly scheduling feature",
)

baseline_orders_per_week = st.sidebar.number_input(
    "Average Orders per User per Week (Current)",
    min_value=0.5,
    max_value=10.0,
    value=2.3,
    step=0.1,
    help="Current average weekly orders per user",
)

# Advanced parameters
st.sidebar.subheader("📈 Feature Impact Modeling")

scheduling_frequency_boost = st.sidebar.slider(
    "Weekly Scheduling Users Order Boost",
    min_value=1.0,
    max_value=3.0,
    value=1.7,
    step=0.1,
    help="Multiplier for how much more frequently scheduling users order",
)

planning_effect = st.sidebar.slider(
    "Planning Effect Bonus (%)",
    min_value=0,
    max_value=40,
    value=15,
    step=5,
    help="Additional orders due to better meal planning and reduced decision fatigue",
)

convenience_retention = st.sidebar.slider(
    "User Retention Improvement (%)",
    min_value=0,
    max_value=30,
    value=10,
    step=5,
    help="Improvement in user retention due to convenience",
)


# Calculations
def calculate_impact():
    # Baseline scenario
    baseline_total_orders = num_users * baseline_orders_per_week

    # User segments
    scheduling_users = int(num_users * (scheduling_adoption / 100))
    non_scheduling_users = num_users - scheduling_users

    # Orders calculation
    non_scheduling_orders = non_scheduling_users * baseline_orders_per_week

    # Scheduling users benefit from multiple factors
    scheduling_base = (
        scheduling_users * baseline_orders_per_week * scheduling_frequency_boost
    )
    planning_bonus = scheduling_base * (planning_effect / 100)
    retention_bonus = scheduling_base * (convenience_retention / 100)

    scheduling_orders = scheduling_base + planning_bonus + retention_bonus

    total_orders_with_feature = non_scheduling_orders + scheduling_orders

    return {
        "baseline_total": baseline_total_orders,
        "total_with_feature": total_orders_with_feature,
        "scheduling_users": scheduling_users,
        "non_scheduling_users": non_scheduling_users,
        "non_scheduling_orders": non_scheduling_orders,
        "scheduling_orders": scheduling_orders,
        "additional_orders": total_orders_with_feature - baseline_total_orders,
        "multiplier": total_orders_with_feature / baseline_total_orders,
        "percentage_increase": (
            (total_orders_with_feature - baseline_total_orders) / baseline_total_orders
        )
        * 100,
    }


results = calculate_impact()

# Hero section - Large multiplier display
st.markdown("### 🎯 **ORDER VOLUME IMPACT**")
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    multiplier_color = (
        "#FF4B4B"
        if results["multiplier"] >= 2.0
        else "#FF8700"
        if results["multiplier"] >= 1.5
        else "#00D4AA"
    )
    st.markdown(
        f"""
        <div style='text-align: center; padding: 40px; background: linear-gradient(90deg, {multiplier_color}20, {multiplier_color}10); border-radius: 20px; margin: 30px 0;'>
            <div style='font-size: 80px; font-weight: bold; color: {multiplier_color}; margin-bottom: 10px;'>
                {results["multiplier"]:.1f}x
            </div>
            <div style='font-size: 28px; color: #666; margin-bottom: 20px;'>
                Order Volume Increase
            </div>
            <div style='font-size: 24px; color: {multiplier_color}; font-weight: 600;'>
                +{results["percentage_increase"]:.1f}% More Orders Weekly
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Key metrics
st.markdown("---")
st.subheader("📊 Key Impact Metrics")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Current Weekly Orders",
        f"{results['baseline_total']:,.0f}",
        help="Total orders per week in current state",
    )

with col2:
    st.metric(
        "Orders with Feature",
        f"{results['total_with_feature']:,.0f}",
        delta=f"+{results['additional_orders']:,.0f}",
        delta_color="normal",
    )

with col3:
    st.metric(
        "Weekly Scheduling Users",
        f"{results['scheduling_users']:,.0f}",
        delta=f"{scheduling_adoption}% adoption",
    )

with col4:
    st.metric(
        "Additional Weekly Orders",
        f"+{results['additional_orders']:,.0f}",
        delta=f"+{results['percentage_increase']:.1f}%",
    )

# Charts section
st.markdown("---")
st.subheader("📈 Visual Analysis")

# Create comparison charts
fig = make_subplots(
    rows=1,
    cols=3,
    subplot_titles=(
        "Before vs After Orders",
        "User Segmentation",
        "Order Distribution",
    ),
    specs=[[{"type": "bar"}, {"type": "pie"}, {"type": "bar"}]],
)

# Before/After comparison
fig.add_trace(
    go.Bar(
        x=["Current State", "With Weekly Scheduling"],
        y=[results["baseline_total"], results["total_with_feature"]],
        marker_color=["#B0BEC5", "#FF4B4B"],
        text=[
            f"{results['baseline_total']:,.0f}",
            f"{results['total_with_feature']:,.0f}",
        ],
        textposition="auto",
        name="Weekly Orders",
    ),
    row=1,
    col=1,
)

# User segmentation pie chart
fig.add_trace(
    go.Pie(
        labels=["Regular Users", "Weekly Scheduling Users"],
        values=[results["non_scheduling_users"], results["scheduling_users"]],
        marker_colors=["#B0BEC5", "#00D4AA"],
        name="User Types",
    ),
    row=1,
    col=2,
)

# Order distribution by user type
fig.add_trace(
    go.Bar(
        x=["Regular Users", "Scheduling Users"],
        y=[results["non_scheduling_orders"], results["scheduling_orders"]],
        marker_color=["#B0BEC5", "#00D4AA"],
        text=[
            f"{results['non_scheduling_orders']:,.0f}",
            f"{results['scheduling_orders']:,.0f}",
        ],
        textposition="auto",
        name="Orders by User Type",
    ),
    row=1,
    col=3,
)

fig.update_layout(height=400, showlegend=False)
st.plotly_chart(fig, width="stretch")

# Monthly projection
st.markdown("---")
st.subheader("📅 12-Month Growth Projection")

months = list(range(1, 13))
weeks_per_month = 4.33

baseline_monthly = [
    results["baseline_total"] * weeks_per_month * month for month in months
]
feature_monthly = [
    results["total_with_feature"] * weeks_per_month * month for month in months
]

projection_df = pd.DataFrame(
    {
        "Month": months,
        "Current Trajectory": baseline_monthly,
        "With Weekly Scheduling": feature_monthly,
    }
)

fig_projection = px.line(
    projection_df,
    x="Month",
    y=["Current Trajectory", "With Weekly Scheduling"],
    title="Cumulative Orders: Current vs With Weekly Scheduling",
    labels={"value": "Cumulative Orders", "variable": "Scenario"},
    color_discrete_map={
        "Current Trajectory": "#B0BEC5",
        "With Weekly Scheduling": "#FF4B4B",
    },
)

fig_projection.update_layout(height=400)
st.plotly_chart(fig_projection, width="stretch")

# Revenue impact
st.markdown("---")
st.subheader("💰 Revenue Impact Analysis")

col1, col2 = st.columns([1, 2])

with col1:
    avg_order_value = st.number_input(
        "Average Order Value ($)", min_value=10, max_value=100, value=32, step=5
    )

with col2:
    # Revenue calculations
    weekly_baseline_revenue = results["baseline_total"] * avg_order_value
    weekly_feature_revenue = results["total_with_feature"] * avg_order_value
    additional_weekly_revenue = weekly_feature_revenue - weekly_baseline_revenue
    annual_additional_revenue = additional_weekly_revenue * 52

    col2a, col2b, col2c = st.columns(3)

    with col2a:
        st.metric("Weekly Revenue (Current)", f"${weekly_baseline_revenue:,.0f}")

    with col2b:
        st.metric("Weekly Revenue (With Feature)", f"${weekly_feature_revenue:,.0f}")

    with col2c:
        st.metric("Additional Annual Revenue", f"${annual_additional_revenue:,.0f}")

# Business case summary
st.markdown("---")
st.subheader("💡 Business Case Summary")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    **🚀 Why Weekly Scheduling Drives Growth:**

    - **Reduced Friction**: Users don't need to decide what to order each day
    - **Better Planning**: Users order more when planning meals in advance
    - **Habit Formation**: Regular scheduling creates consistent ordering patterns
    - **Increased Basket Size**: Planning ahead leads to more thoughtful, larger orders
    - **Higher Retention**: Convenience keeps users engaged longer
    """)

with col2:
    st.markdown(f"""
    **📈 Expected Business Impact:**

    - **{results["multiplier"]:.1f}x** increase in total weekly orders
    - **{results["scheduling_users"]:,}** users ({scheduling_adoption}%) adopt feature
    - **+{results["additional_orders"]:,.0f}** additional weekly orders
    - **${annual_additional_revenue:,.0f}** additional annual revenue
    - **{results["percentage_increase"]:.1f}%** growth in order volume

    *ROI depends on implementation costs and user acquisition*
    """)

# Implementation considerations
with st.expander("🎯 Implementation Considerations"):
    st.markdown("""
    **Feature Requirements:**
    - Weekly meal planning interface
    - Flexible scheduling and modification options
    - Smart recommendations based on user preferences
    - Integration with restaurant availability

    **Success Factors:**
    - User-friendly planning interface
    - Reliable delivery scheduling
    - Easy modification/cancellation process
    - Incentives for early adoption

    **Key Metrics to Track:**
    - Weekly scheduling adoption rate
    - Order frequency among scheduling users
    - User retention improvement
    - Average order value changes
    """)

# Footer
st.markdown("---")
st.markdown(
    "*💡 **Tip**: Adjust the parameters in the sidebar to model different scenarios and adoption rates for your business case.*"
)
