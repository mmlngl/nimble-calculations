import math
from dataclasses import dataclass

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="FeedFast – Scheduled Meals Business Case Explorer",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("FeedFast – Scheduled Repeat Meals Business Case Explorer")
st.caption(
    "Exploratory model for comparing scenarios. "
    "This is not a forecast; outputs are highly sensitive to adoption, cannibalisation, "
    "completion rate, and contribution margin assumptions."
)


# -----------------------------
# Scenario presets
# -----------------------------
@dataclass
class Scenario:
    adoption_pct: int
    baseline_orders_per_user_per_week: float
    gross_additional_orders_per_scheduler: float
    cannibalisation_pct: int
    failure_pct: int
    monthly_retention_uplift_pct: float
    variable_cost_per_incremental_order: float
    avg_order_value: float
    platform_take_rate_pct: float
    annual_feature_cost: int


SCENARIOS = {
    "Conservative": Scenario(
        adoption_pct=10,
        baseline_orders_per_user_per_week=1.0,
        gross_additional_orders_per_scheduler=1.0,
        cannibalisation_pct=70,
        failure_pct=15,
        monthly_retention_uplift_pct=1.0,
        variable_cost_per_incremental_order=2.5,
        avg_order_value=200.0,
        platform_take_rate_pct=18.0,
        annual_feature_cost=250_000,
    ),
    "Base Case": Scenario(
        adoption_pct=20,
        baseline_orders_per_user_per_week=1.0,
        gross_additional_orders_per_scheduler=2.0,
        cannibalisation_pct=50,
        failure_pct=10,
        monthly_retention_uplift_pct=2.0,
        variable_cost_per_incremental_order=2.0,
        avg_order_value=300.0,
        platform_take_rate_pct=20.0,
        annual_feature_cost=400_000,
    ),
    "Aggressive": Scenario(
        adoption_pct=35,
        baseline_orders_per_user_per_week=1.0,
        gross_additional_orders_per_scheduler=3.0,
        cannibalisation_pct=30,
        failure_pct=5,
        monthly_retention_uplift_pct=3.0,
        variable_cost_per_incremental_order=1.5,
        avg_order_value=500.0,
        platform_take_rate_pct=22.0,
        annual_feature_cost=600_000,
    ),
}


# -----------------------------
# Sidebar controls
# -----------------------------
st.sidebar.header("Configuration")

scenario_name = st.sidebar.selectbox(
    "Scenario Preset",
    options=list(SCENARIOS.keys()),
    index=1,
)

preset = SCENARIOS[scenario_name]

num_active_users = st.sidebar.number_input(
    "Active Users",
    min_value=1_000,
    max_value=5_000_000,
    value=50_000,
    step=1_000,
)

months_to_model = st.sidebar.slider(
    "Months to Model",
    min_value=3,
    max_value=24,
    value=12,
    step=1,
)

st.sidebar.subheader("Adoption & Behaviour")

adoption_pct = st.sidebar.slider(
    "Scheduled Meals Adoption (%)",
    min_value=0,
    max_value=100,
    value=preset.adoption_pct,
    step=1,
    help="Share of active users who adopt scheduled repeat meals.",
)

baseline_orders_per_user_per_week = st.sidebar.number_input(
    "Baseline Orders / User / Week",
    min_value=0.1,
    max_value=10.0,
    value=preset.baseline_orders_per_user_per_week,
    step=0.1,
)

gross_additional_orders_per_scheduler = st.sidebar.number_input(
    "Gross Additional Orders / Scheduling User / Week",
    min_value=0.0,
    max_value=10.0,
    value=preset.gross_additional_orders_per_scheduler,
    step=0.25,
    help=(
        "Gross uplift before accounting for orders that would have happened anyway "
        "and before accounting for failed scheduled orders."
    ),
)

cannibalisation_pct = st.sidebar.slider(
    "Cannibalisation (%)",
    min_value=0,
    max_value=100,
    value=preset.cannibalisation_pct,
    step=1,
    help="Share of scheduled orders that replace orders users would have placed anyway.",
)

failure_pct = st.sidebar.slider(
    "Scheduled Order Failure / Cancellation (%)",
    min_value=0,
    max_value=100,
    value=preset.failure_pct,
    step=1,
    help="Failed, cancelled, or otherwise unrealised scheduled orders.",
)

monthly_retention_uplift_pct = st.sidebar.slider(
    "Monthly Retention Uplift for Scheduling Users (%)",
    min_value=0.0,
    max_value=10.0,
    value=float(preset.monthly_retention_uplift_pct),
    step=0.25,
    help=(
        "Additional monthly active-user retention for the scheduling cohort. "
        "Applied over time, not as instant same-week uplift."
    ),
)

st.sidebar.subheader("Economics")

avg_order_value = st.sidebar.number_input(
    "Average Order Value (฿)",
    min_value=5.0,
    max_value=2000.0,
    value=float(preset.avg_order_value),
    step=1.0,
)

platform_take_rate_pct = st.sidebar.slider(
    "Platform Take Rate (%)",
    min_value=1.0,
    max_value=50.0,
    value=float(preset.platform_take_rate_pct),
    step=0.5,
    help="Revenue FeedFast keeps as platform revenue, not full GMV.",
)

variable_cost_per_incremental_order = st.sidebar.number_input(
    "Variable Cost per Incremental Order (฿)",
    min_value=0.0,
    max_value=20.0,
    value=float(preset.variable_cost_per_incremental_order),
    step=0.25,
    help="Support, incentives, discounts, ops, and other variable costs on incremental orders.",
)

annual_feature_cost = st.sidebar.number_input(
    "Annual Feature Cost (฿)",
    min_value=0,
    max_value=10_000_000,
    value=int(preset.annual_feature_cost),
    step=50_000,
    help="Build + maintenance + rollout cost estimate.",
)


# -----------------------------
# Core model
# -----------------------------
def monthly_decay_factor_from_uplift(uplift_pct: float) -> float:
    """Convert monthly uplift percentage to a multiplicative factor."""
    return 1 + uplift_pct / 100.0


def build_projection_df() -> pd.DataFrame:
    """
    Model two cohorts:
    - non-scheduling users
    - scheduling users

    Scheduling users generate:
    - baseline orders they would already place
    - gross additional scheduled orders
    Then gross uplift is reduced by:
    - cannibalisation
    - failure/cancellation

    Retention uplift is applied to scheduling cohort size over time.
    """
    scheduling_users_month_1 = num_active_users * (adoption_pct / 100.0)
    regular_users_month_1 = num_active_users - scheduling_users_month_1

    monthly_factor = monthly_decay_factor_from_uplift(monthly_retention_uplift_pct)

    rows = []
    current_scheduling_users = scheduling_users_month_1
    current_regular_users = regular_users_month_1

    for month in range(1, months_to_model + 1):
        weeks = 4.33

        # Baseline orders if feature did not exist
        baseline_total_orders = (
            num_active_users * baseline_orders_per_user_per_week * weeks
        )

        # Cohort orders with feature
        regular_orders = (
            current_regular_users * baseline_orders_per_user_per_week * weeks
        )
        scheduler_baseline_orders = (
            current_scheduling_users * baseline_orders_per_user_per_week * weeks
        )

        gross_additional_orders = (
            current_scheduling_users * gross_additional_orders_per_scheduler * weeks
        )

        cannibalised_orders = gross_additional_orders * (cannibalisation_pct / 100.0)
        failed_orders = gross_additional_orders * (failure_pct / 100.0)

        net_incremental_orders = max(
            0.0,
            gross_additional_orders - cannibalised_orders - failed_orders,
        )

        total_orders_with_feature = (
            regular_orders + scheduler_baseline_orders + net_incremental_orders
        )

        # Economics
        baseline_gmv = baseline_total_orders * avg_order_value
        gmv_with_feature = total_orders_with_feature * avg_order_value
        incremental_gmv = gmv_with_feature - baseline_gmv

        incremental_platform_revenue = incremental_gmv * (
            platform_take_rate_pct / 100.0
        )
        incremental_variable_cost = (
            net_incremental_orders * variable_cost_per_incremental_order
        )
        monthly_feature_cost = annual_feature_cost / 12.0
        incremental_contribution = (
            incremental_platform_revenue
            - incremental_variable_cost
            - monthly_feature_cost
        )

        rows.append(
            {
                "Month": month,
                "Scheduling Users": current_scheduling_users,
                "Regular Users": current_regular_users,
                "Baseline Orders": baseline_total_orders,
                "Orders With Feature": total_orders_with_feature,
                "Gross Additional Orders": gross_additional_orders,
                "Cannibalised Orders": cannibalised_orders,
                "Failed Orders": failed_orders,
                "Net Incremental Orders": net_incremental_orders,
                "Baseline GMV": baseline_gmv,
                "GMV With Feature": gmv_with_feature,
                "Incremental GMV": incremental_gmv,
                "Incremental Platform Revenue": incremental_platform_revenue,
                "Incremental Variable Cost": incremental_variable_cost,
                "Monthly Feature Cost": monthly_feature_cost,
                "Incremental Contribution": incremental_contribution,
            }
        )

        # Apply retention uplift only to scheduling cohort for next month
        current_scheduling_users *= monthly_factor

    return pd.DataFrame(rows)


df = build_projection_df()

month_1 = df.iloc[0]
last_month = df.iloc[-1]

baseline_weekly_orders = num_active_users * baseline_orders_per_user_per_week
feature_weekly_orders_month_1 = month_1["Orders With Feature"] / 4.33
net_new_weekly_orders_month_1 = month_1["Net Incremental Orders"] / 4.33

month_1_multiplier = (
    feature_weekly_orders_month_1 / baseline_weekly_orders
    if baseline_weekly_orders > 0
    else 0
)

annual_net_incremental_orders = df["Net Incremental Orders"].sum()
annual_incremental_platform_revenue = df["Incremental Platform Revenue"].sum()
annual_incremental_contribution = df["Incremental Contribution"].sum()


# -----------------------------
# Summary / executive view
# -----------------------------
st.subheader("Executive Summary")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Month 1 Weekly Order Multiplier",
        f"{month_1_multiplier:.2f}x",
        delta=f"{((month_1_multiplier - 1) * 100):.1f}%",
    )

with col2:
    st.metric(
        "Month 1 Net New Weekly Orders",
        f"{net_new_weekly_orders_month_1:,.0f}",
    )

with col3:
    st.metric(
        "12-Month Incremental Platform Revenue",
        f"฿{annual_incremental_platform_revenue:,.0f}",
    )

with col4:
    contribution_delta_color = (
        "normal" if annual_incremental_contribution >= 0 else "inverse"
    )
    st.metric(
        "12-Month Incremental Contribution",
        f"฿{annual_incremental_contribution:,.0f}",
        delta=f"฿{annual_incremental_contribution:,.0f}",
        delta_color=contribution_delta_color,
    )

st.info(
    "Critical thinking built into the model: "
    "gross uplift is reduced by cannibalisation and failure, "
    "and retention is treated as a cohort effect over time rather than same-week uplift."
)


# -----------------------------
# Assumptions table
# -----------------------------
st.subheader("Assumptions")

assumptions_df = pd.DataFrame(
    [
        {"Assumption": "Active Users", "Value": f"{num_active_users:,.0f}"},
        {"Assumption": "Scheduled Meals Adoption", "Value": f"{adoption_pct}%"},
        {
            "Assumption": "Baseline Orders / User / Week",
            "Value": f"{baseline_orders_per_user_per_week:.2f}",
        },
        {
            "Assumption": "Gross Additional Orders / Scheduler / Week",
            "Value": f"{gross_additional_orders_per_scheduler:.2f}",
        },
        {"Assumption": "Cannibalisation", "Value": f"{cannibalisation_pct}%"},
        {"Assumption": "Failure / Cancellation", "Value": f"{failure_pct}%"},
        {
            "Assumption": "Monthly Retention Uplift (Scheduling Cohort)",
            "Value": f"{monthly_retention_uplift_pct:.2f}%",
        },
        {"Assumption": "Average Order Value", "Value": f"฿{avg_order_value:.2f}"},
        {"Assumption": "Platform Take Rate", "Value": f"{platform_take_rate_pct:.1f}%"},
        {
            "Assumption": "Variable Cost / Incremental Order",
            "Value": f"฿{variable_cost_per_incremental_order:.2f}",
        },
        {"Assumption": "Annual Feature Cost", "Value": f"฿{annual_feature_cost:,.0f}"},
    ]
)

st.dataframe(assumptions_df, use_container_width=True, hide_index=True)


# -----------------------------
# Waterfall style breakdown for month 1
# -----------------------------
st.subheader("Month 1 Order Bridge")

bridge_labels = [
    "Baseline Orders",
    "Gross Additional Orders",
    "- Cannibalised",
    "- Failed",
    "Net Orders With Feature",
]

bridge_values = [
    month_1["Baseline Orders"],
    month_1["Gross Additional Orders"],
    -month_1["Cannibalised Orders"],
    -month_1["Failed Orders"],
    0,  # placeholder for total
]

fig_bridge = go.Figure(
    go.Waterfall(
        name="Month 1",
        orientation="v",
        measure=["absolute", "relative", "relative", "relative", "total"],
        x=bridge_labels,
        y=bridge_values,
        connector={"line": {"color": "rgb(63, 63, 63)"}},
    )
)
fig_bridge.update_layout(height=420, margin=dict(l=20, r=20, t=40, b=20))
st.plotly_chart(fig_bridge, use_container_width=True)


# -----------------------------
# Monthly trends
# -----------------------------
st.subheader("Monthly Trend")

trend_df = df[
    [
        "Month",
        "Baseline Orders",
        "Orders With Feature",
        "Net Incremental Orders",
        "Scheduling Users",
        "Incremental Contribution",
    ]
].copy()

metric_choice = st.radio(
    "Trend View",
    options=[
        "Orders",
        "Net Incremental Orders",
        "Scheduling Users",
        "Incremental Contribution",
    ],
    horizontal=True,
)

if metric_choice == "Orders":
    fig_trend = px.line(
        trend_df,
        x="Month",
        y=["Baseline Orders", "Orders With Feature"],
        markers=True,
        title="Monthly Orders: Baseline vs With Feature",
    )
elif metric_choice == "Net Incremental Orders":
    fig_trend = px.bar(
        trend_df,
        x="Month",
        y="Net Incremental Orders",
        title="Monthly Net Incremental Orders",
    )
elif metric_choice == "Scheduling Users":
    fig_trend = px.line(
        trend_df,
        x="Month",
        y="Scheduling Users",
        markers=True,
        title="Scheduling Cohort Size Over Time",
    )
else:
    fig_trend = px.bar(
        trend_df,
        x="Month",
        y="Incremental Contribution",
        title="Monthly Incremental Contribution",
    )

fig_trend.update_layout(height=420, margin=dict(l=20, r=20, t=40, b=20))
st.plotly_chart(fig_trend, use_container_width=True)


# -----------------------------
# Sensitivity analysis
# -----------------------------
st.subheader("Sensitivity Analysis")

base_inputs = {
    "Adoption": adoption_pct,
    "Cannibalisation": cannibalisation_pct,
    "Failure": failure_pct,
    "Gross Additional Orders": gross_additional_orders_per_scheduler,
}

sensitivity_rows = []


def calculate_annual_contribution(
    adoption_override=None,
    cannibalisation_override=None,
    failure_override=None,
    gross_orders_override=None,
) -> float:
    local_adoption = adoption_pct if adoption_override is None else adoption_override
    local_cannibalisation = (
        cannibalisation_pct
        if cannibalisation_override is None
        else cannibalisation_override
    )
    local_failure = failure_pct if failure_override is None else failure_override
    local_gross_orders = (
        gross_additional_orders_per_scheduler
        if gross_orders_override is None
        else gross_orders_override
    )

    scheduling_users_month_1 = num_active_users * (local_adoption / 100.0)
    regular_users_month_1 = num_active_users - scheduling_users_month_1
    monthly_factor = monthly_decay_factor_from_uplift(monthly_retention_uplift_pct)

    current_scheduling_users = scheduling_users_month_1
    current_regular_users = regular_users_month_1
    total_contribution = 0.0

    for _month in range(1, months_to_model + 1):
        weeks = 4.33
        baseline_total_orders = (
            num_active_users * baseline_orders_per_user_per_week * weeks
        )
        regular_orders = (
            current_regular_users * baseline_orders_per_user_per_week * weeks
        )
        scheduler_baseline_orders = (
            current_scheduling_users * baseline_orders_per_user_per_week * weeks
        )

        gross_additional_orders = current_scheduling_users * local_gross_orders * weeks
        cannibalised_orders = gross_additional_orders * (local_cannibalisation / 100.0)
        failed_orders = gross_additional_orders * (local_failure / 100.0)
        net_incremental_orders = max(
            0.0,
            gross_additional_orders - cannibalised_orders - failed_orders,
        )

        total_orders_with_feature = (
            regular_orders + scheduler_baseline_orders + net_incremental_orders
        )

        baseline_gmv = baseline_total_orders * avg_order_value
        gmv_with_feature = total_orders_with_feature * avg_order_value
        incremental_gmv = gmv_with_feature - baseline_gmv
        incremental_platform_revenue = incremental_gmv * (
            platform_take_rate_pct / 100.0
        )
        incremental_variable_cost = (
            net_incremental_orders * variable_cost_per_incremental_order
        )
        monthly_feature_cost = annual_feature_cost / 12.0

        total_contribution += (
            incremental_platform_revenue
            - incremental_variable_cost
            - monthly_feature_cost
        )

        current_scheduling_users *= monthly_factor

    return total_contribution


# Low / high bands around each key variable
sensitivity_specs = [
    ("Adoption", max(0, adoption_pct - 5), min(100, adoption_pct + 5)),
    (
        "Cannibalisation",
        max(0, cannibalisation_pct - 10),
        min(100, cannibalisation_pct + 10),
    ),
    ("Failure", max(0, failure_pct - 5), min(100, failure_pct + 5)),
    (
        "Gross Additional Orders",
        max(0.0, gross_additional_orders_per_scheduler - 0.5),
        gross_additional_orders_per_scheduler + 0.5,
    ),
]

base_contribution = calculate_annual_contribution()

for metric, low_val, high_val in sensitivity_specs:
    if metric == "Adoption":
        low_contribution = calculate_annual_contribution(adoption_override=low_val)
        high_contribution = calculate_annual_contribution(adoption_override=high_val)
    elif metric == "Cannibalisation":
        low_contribution = calculate_annual_contribution(
            cannibalisation_override=high_val
        )
        high_contribution = calculate_annual_contribution(
            cannibalisation_override=low_val
        )
    elif metric == "Failure":
        low_contribution = calculate_annual_contribution(failure_override=high_val)
        high_contribution = calculate_annual_contribution(failure_override=low_val)
    else:
        low_contribution = calculate_annual_contribution(gross_orders_override=low_val)
        high_contribution = calculate_annual_contribution(
            gross_orders_override=high_val
        )

    sensitivity_rows.append(
        {
            "Driver": metric,
            "Low Case Contribution": low_contribution,
            "Base Case Contribution": base_contribution,
            "High Case Contribution": high_contribution,
            "Swing": abs(high_contribution - low_contribution),
        }
    )

sensitivity_df = pd.DataFrame(sensitivity_rows).sort_values("Swing", ascending=True)

fig_sensitivity = go.Figure()
fig_sensitivity.add_trace(
    go.Bar(
        y=sensitivity_df["Driver"],
        x=sensitivity_df["Low Case Contribution"]
        - sensitivity_df["Base Case Contribution"],
        name="Low Case vs Base",
        orientation="h",
    )
)
fig_sensitivity.add_trace(
    go.Bar(
        y=sensitivity_df["Driver"],
        x=sensitivity_df["High Case Contribution"]
        - sensitivity_df["Base Case Contribution"],
        name="High Case vs Base",
        orientation="h",
    )
)
fig_sensitivity.update_layout(
    barmode="relative",
    height=380,
    title="Which Assumptions Matter Most?",
    xaxis_title="Contribution Impact vs Base Case (฿)",
    yaxis_title="",
    margin=dict(l=20, r=20, t=40, b=20),
)
st.plotly_chart(fig_sensitivity, use_container_width=True)


# -----------------------------
# Critical thinking / conclusion
# -----------------------------
st.subheader("Decision Framing")

col_a, col_b = st.columns(2)

with col_a:
    st.markdown(
        """
**Why this model is more decision-useful**
- Separates **gross uplift** from **net new orders**
- Accounts for **cannibalisation**
- Accounts for **failure / cancellation**
- Treats retention as a **cohort effect over time**
- Uses **platform revenue**, not full GMV, for business value
"""
    )

with col_b:
    breakeven = "Yes" if annual_incremental_contribution > 0 else "No"
    st.markdown(
        f"""
**Current read**
- Month 1 order uplift: **{((month_1_multiplier - 1) * 100):.1f}%**
- 12-month net incremental orders: **{annual_net_incremental_orders:,.0f}**
- 12-month incremental contribution: **฿{annual_incremental_contribution:,.0f}**
- Feature economically positive under current assumptions: **{breakeven}**
"""
    )

with st.expander("Model Notes"):
    st.markdown(
        """
- This tool is meant to compare scenarios, not predict exact business outcomes.
- It intentionally avoids assuming all scheduled orders are net new.
- It highlights which assumptions matter most so the product team can de-risk them first.
- In a real product discovery process, the next step would be to validate:
  - scheduler adoption intent
  - likely cannibalisation
  - completion / cancellation rate
  - operational impact on support and fulfillment
"""
    )
