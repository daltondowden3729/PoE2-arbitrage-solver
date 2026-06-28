
import streamlit as st
import pandas as pd
from itertools import permutations

st.set_page_config(page_title="PoE2 Easy Arbitrage Solver", layout="wide")

CURRENCIES = ["Divine", "Exalted", "Chaos", "Chance", "Annulment", "Vaal"]

DEFAULT_RATES = {
    "Divine": {
        "Exalted": 410.0,
        "Chaos": 10.23,
        "Chance": 45.0,
        "Annulment": 1.75,
        "Vaal": 127.0,
    },
    "Exalted": {
        "Divine": 1/400,
        "Chaos": 45.0,
        "Chance": 8.0,
        "Annulment": 1/200,
        "Vaal": 4.0,
    },
    "Chaos": {
        "Divine": 1/10.35,
        "Exalted": 1/38.5,
        "Chance": 2.76,
        "Annulment": 1/5.8,
        "Vaal": 8.5,
    },
    "Chance": {
        "Divine": 1/63,
        "Exalted": 1/6,
        "Chaos": 1/6,
        "Annulment": 1/53,
        "Vaal": 2.0,
    },
    "Annulment": {
        "Divine": 1/1.85,
        "Exalted": 195.5,
        "Chaos": 5.5,
        "Chance": 3.33,
        "Vaal": 29.0,
    },
    "Vaal": {
        "Divine": 1/168,
        "Exalted": 3.75,
        "Chaos": 1/18.49,
        "Chance": 1/9,
        "Annulment": 1/100,
    },
}

def fmt(value):
    try:
        value = float(value)
    except Exception:
        return str(value)
    if abs(value - round(value)) < 0.005:
        return f"{int(round(value)):,}"
    return f"{value:,.2f}"

def decimal_to_display(value, target):
    value = float(value)
    if value >= 1:
        return f"{fmt(value)} {target}"
    if value > 0:
        denom = 1 / value
        return f"1/{fmt(denom)} {target} ({fmt(denom)} needed for 1 {target})"
    return f"0 {target}"

def rates_to_df(rates):
    rows = []
    for base in CURRENCIES:
        for target in CURRENCIES:
            if base == target:
                continue
            rows.append([base, target, float(rates.get(base, {}).get(target, 0.0))])
    return pd.DataFrame(rows, columns=["Using 1", "You can buy", "Amount"])

def df_to_rates(df):
    rates = {}
    for _, row in df.iterrows():
        base = str(row["Using 1"])
        target = str(row["You can buy"])
        try:
            amount = float(row["Amount"])
        except Exception:
            amount = 0.0
        if base != target and amount > 0:
            rates.setdefault(base, {})[target] = amount
    return rates

def build_edges(df):
    edges = {}
    for _, row in df.iterrows():
        base = str(row["Using 1"])
        target = str(row["You can buy"])
        try:
            amount = float(row["Amount"])
        except Exception:
            amount = 0.0
        if base != target and amount > 0:
            edges[(base, target)] = amount
    return edges

def make_step(amount, frm, to, edges):
    rate = edges[(frm, to)]
    out = amount * rate

    if frm == "Exalted":
        text = f"Buy **{fmt(out)} {to}** with **{fmt(amount)} Exalted**."
    elif to == "Exalted":
        text = f"Sell **{fmt(amount)} {frm}** for **{fmt(out)} Exalted**."
    else:
        text = f"Trade **{fmt(amount)} {frm}** for **{fmt(out)} {to}**."

    reason = f"Reason: 1 {frm} = {decimal_to_display(rate, to)}"
    math = f"Math: {fmt(amount)} × {fmt(rate)} = {fmt(out)}"
    return out, text, reason, math

def evaluate_path(path, bankroll, edges):
    amount = bankroll
    steps = []

    for frm, to in zip(path, path[1:]):
        if (frm, to) not in edges:
            return None
        amount, text, reason, math = make_step(amount, frm, to, edges)
        steps.append({"text": text, "reason": reason, "math": math})

    profit = amount - bankroll
    roi = (profit / bankroll * 100) if bankroll else 0
    return {
        "path": path,
        "final": amount,
        "profit": profit,
        "roi": roi,
        "steps": steps,
        "overall_ratio": (amount / bankroll) if bankroll else 0,
    }

def solve(df, start_currency, bankroll, max_trades):
    edges = build_edges(df)
    results = []
    others = [c for c in CURRENCIES if c != start_currency]

    for trade_count in range(2, max_trades + 1):
        for middle in permutations(others, trade_count - 1):
            path = [start_currency] + list(middle) + [start_currency]
            res = evaluate_path(path, bankroll, edges)
            if res:
                results.append(res)

    results.sort(key=lambda r: r["profit"], reverse=True)
    return results

st.title("PoE2 Easy Arbitrage Solver")
st.write("New format: **Using 1 currency, how much of another currency can you buy?** Edit the Amount values directly.")

if "rate_df" not in st.session_state:
    st.session_state.rate_df = rates_to_df(DEFAULT_RATES)

col_a, col_b, col_c = st.columns(3)
with col_a:
    start_currency = st.selectbox("Start / End Currency", CURRENCIES, index=CURRENCIES.index("Exalted"))
with col_b:
    bankroll = st.number_input(f"Current {start_currency}", min_value=0.0, value=548.0, step=1.0)
with col_c:
    max_trades = st.slider("Max trades to check", min_value=2, max_value=5, value=5)

st.subheader("1) Currency Rates")

st.caption("Example: If 1 Divine sells for 410 Exalted, enter 410 on Divine → Exalted. If 400 Exalted = 1 Divine, enter 0.0025 on Exalted → Divine.")

if st.button("Reset to default values"):
    st.session_state.rate_df = rates_to_df(DEFAULT_RATES)
    st.rerun()

edited = st.data_editor(
    st.session_state.rate_df,
    use_container_width=True,
    num_rows="fixed",
    hide_index=True,
    column_config={
        "Using 1": st.column_config.SelectboxColumn("Using 1", options=CURRENCIES, disabled=True),
        "You can buy": st.column_config.SelectboxColumn("You can buy", options=CURRENCIES, disabled=True),
        "Amount": st.column_config.NumberColumn(
            "Amount bought with 1",
            min_value=0.0,
            step=0.01,
            format="%.6f",
            help="How many of the target currency you receive for 1 of the base currency.",
        ),
    },
)
st.session_state.rate_df = edited.copy()

st.subheader("2) Easy View")

for base_cur in CURRENCIES:
    with st.expander(base_cur, expanded=(base_cur == start_currency)):
        st.markdown(f"**Using 1 {base_cur}, you can buy:**")
        small = edited[edited["Using 1"] == base_cur]
        for _, row in small.iterrows():
            target = row["You can buy"]
            amount = float(row["Amount"])
            st.write(f"- **{decimal_to_display(amount, target)}**")

st.subheader("3) Best Trade Instructions")

results = solve(edited, start_currency, bankroll, max_trades)
profitable = [r for r in results if r["profit"] > 0]
shown = profitable[:10] if profitable else results[:10]

if not shown:
    st.error("No loops found. Check the table values.")
elif profitable:
    st.success(f"Found {len(profitable)} profitable loop(s).")
else:
    st.warning("No profitable loops found. Showing the least-bad options.")

for rank, r in enumerate(shown, 1):
    icon = "🟢" if r["profit"] > 0 else "🔴"
    with st.expander(
        f"{icon} #{rank} | Profit: {fmt(r['profit'])} {start_currency} | ROI: {r['roi']:.2f}% | Final: {fmt(r['final'])} {start_currency}",
        expanded=(rank == 1),
    ):
        st.markdown(f"### Start with **{fmt(bankroll)} {start_currency}**")
        for i, step in enumerate(r["steps"], 1):
            st.markdown(f"**Step {i}:** {step['text']}")
            st.caption(step["reason"])
            st.caption(step["math"])

        st.markdown("---")
        st.markdown(f"**Finish with:** {fmt(r['final'])} {start_currency}")
        st.markdown(f"**Overall ratio:** 1 {start_currency} becomes **{fmt(r['overall_ratio'])} {start_currency}**")
        st.markdown(f"**ROI reason:** ({fmt(r['final'])} - {fmt(bankroll)}) ÷ {fmt(bankroll)} × 100 = **{r['roi']:.2f}%**")

        if r["profit"] > 0:
            st.success(f"Profit: +{fmt(r['profit'])} {start_currency}")
            st.markdown("### Recommendation: 🟢 Do this trade if the rates are still available.")
        else:
            st.error(f"Loss: {fmt(r['profit'])} {start_currency}")
            st.markdown("### Recommendation: 🔴 Do not do this trade.")
