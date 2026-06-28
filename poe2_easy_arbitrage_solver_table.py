
import streamlit as st
import pandas as pd
from itertools import permutations

st.set_page_config(page_title="PoE2 Easy Arbitrage Solver", layout="wide")

CURRENCIES = ["Exalted", "Divine", "Chaos", "Chance", "Annulment", "Vaal"]

DEFAULT_ROWS = [
    ["Divine", "Exalted", 405.0, 1.0],
    ["Divine", "Chaos", 135.0, 1.0],
    ["Divine", "Chance", 30.0, 1.0],
    ["Divine", "Annulment", 1.75, 1.0],
    ["Divine", "Vaal", 124.0, 1.0],

    ["Exalted", "Divine", 1.0, 400.0],
    ["Exalted", "Chaos", 1.0, 40.0],
    ["Exalted", "Chance", 1.0, 10.0],
    ["Exalted", "Annulment", 1.0, 207.0],
    ["Exalted", "Vaal", 1.0, 4.0],

    ["Chaos", "Divine", 1.0, 10.32],
    ["Chaos", "Exalted", 36.94, 1.0],
    ["Chaos", "Chance", 3.86, 1.0],
    ["Chaos", "Annulment", 1.0, 5.7],
    ["Chaos", "Vaal", 11.61, 1.0],

    ["Chance", "Divine", 1.0, 55.0],
    ["Chance", "Exalted", 6.5, 1.0],
    ["Chance", "Chaos", 1.0, 6.5],
    ["Chance", "Annulment", 1.0, 53.0],
    ["Chance", "Vaal", 2.0, 1.0],

    ["Annulment", "Divine", 1.0, 1.85],
    ["Annulment", "Exalted", 196.5, 1.0],
    ["Annulment", "Chaos", 5.5, 1.0],
    ["Annulment", "Chance", 3.33, 1.0],
    ["Annulment", "Vaal", 30.0, 1.0],

    ["Vaal", "Divine", 1.0, 150.0],
    ["Vaal", "Exalted", 3.5, 1.0],
    ["Vaal", "Chaos", 1.0, 18.99],
    ["Vaal", "Chance", 1.0, 9.0],
    ["Vaal", "Annulment", 1.0, 90.0],
]

st.title("PoE2 Easy Arbitrage Solver")
st.write("Edit the table, enter your Exalted balance, then the app gives simple instructions like: **Buy 137 Vaal with 548 Exalted.**")

bankroll = st.number_input("Current Exalted", min_value=0.0, value=548.0, step=1.0)

st.subheader("Exchange Rate Table")
st.caption("Click any Buy or Sell cell to update it. The table uses your in-game layout.")

if "rates_df" not in st.session_state:
    st.session_state.rates_df = pd.DataFrame(DEFAULT_ROWS, columns=["Currency", "Trade To", "Buy", "Sell"])

if st.button("Reset table to default values"):
    st.session_state.rates_df = pd.DataFrame(DEFAULT_ROWS, columns=["Currency", "Trade To", "Buy", "Sell"])

edited_df = st.data_editor(
    st.session_state.rates_df,
    num_rows="fixed",
    use_container_width=True,
    column_config={
        "Currency": st.column_config.SelectboxColumn("Currency", options=CURRENCIES, disabled=True),
        "Trade To": st.column_config.SelectboxColumn("Trade To", options=CURRENCIES, disabled=True),
        "Buy": st.column_config.NumberColumn("Buy", min_value=0.0, step=0.01, format="%.6f"),
        "Sell": st.column_config.NumberColumn("Sell", min_value=0.0, step=0.01, format="%.6f"),
    },
    hide_index=True,
)

st.session_state.rates_df = edited_df.copy()

def build_edges(df):
    """
    For each row:
    Currency = base currency
    Trade To = target currency

    Buy means:
      Buy 1 Currency with Buy amount of Trade To.
      Example: Currency Divine, Trade To Exalted, Buy 405
      = Buy 1 Divine with 405 Exalted.
      Edge: Exalted -> Divine

    Sell means:
      Sell 1 Currency for Sell amount of Trade To.
      Example: Currency Divine, Trade To Chaos, Sell 10
      = Sell 1 Divine for 10 Chaos.
      Edge: Divine -> Chaos
    """
    edges = {}

    for _, row in df.iterrows():
        base = str(row["Currency"])
        target = str(row["Trade To"])

        try:
            buy = float(row["Buy"])
        except Exception:
            buy = 0.0

        try:
            sell = float(row["Sell"])
        except Exception:
            sell = 0.0

        if base == target:
            continue

        if buy > 0:
            # Pay buy target to receive 1 base
            edges[(target, base)] = {
                "type": "buy",
                "cost_per_one": buy,
                "base": base,
                "target": target,
            }

        if sell > 0:
            # Pay 1 base to receive sell target
            edges[(base, target)] = {
                "type": "sell",
                "cost_per_one": 1 / sell,
                "base": base,
                "target": target,
                "sell_amount": sell,
            }

    return edges

edges = build_edges(edited_df)

def convert(amount, frm, to):
    edge = edges.get((frm, to))
    if edge is None:
        return None
    return amount / edge["cost_per_one"]

def make_step(amount, frm, to):
    edge = edges[(frm, to)]
    out = convert(amount, frm, to)

    if edge["type"] == "buy":
        # from target to base
        text = f"Buy **{out:,.2f} {to}** with **{amount:,.2f} {frm}**."
    else:
        text = f"Sell **{amount:,.2f} {frm}** for **{out:,.2f} {to}**."

    return out, text

def evaluate_path(path):
    amount = bankroll
    steps = []

    for frm, to in zip(path, path[1:]):
        if (frm, to) not in edges:
            return None
        amount, text = make_step(amount, frm, to)
        steps.append(text)

    profit = amount - bankroll
    roi = (profit / bankroll * 100) if bankroll else 0

    return {
        "path": path,
        "final": amount,
        "profit": profit,
        "roi": roi,
        "steps": steps,
    }

results = []
start = "Exalted"
others = [c for c in CURRENCIES if c != start]

# Search loops from 2 through 5 trades.
for trade_count in range(2, 6):
    for middle in permutations(others, trade_count - 1):
        path = [start] + list(middle) + [start]
        res = evaluate_path(path)
        if res is not None:
            results.append(res)

results.sort(key=lambda r: r["profit"], reverse=True)

st.subheader("Best Trade Instructions")

profitable = [r for r in results if r["profit"] > 0]
shown = profitable[:10] if profitable else results[:10]

if not shown:
    st.error("No possible loops found. Check the exchange table.")
elif not profitable:
    st.warning("No profitable loops found. Showing the least-bad options.")
else:
    st.success(f"Found {len(profitable)} profitable loop(s).")

for rank, r in enumerate(shown, 1):
    icon = "🟢" if r["profit"] > 0 else "🔴"
    route = " → ".join(r["path"])
    with st.expander(f"{icon} #{rank}: {route} | Profit: {r['profit']:,.2f} Ex | ROI: {r['roi']:.2f}%", expanded=(rank == 1)):
        st.markdown(f"### Start with **{bankroll:,.2f} Exalted**")
        for idx, step in enumerate(r["steps"], 1):
            st.markdown(f"**Step {idx}:** {step}")

        st.markdown("---")
        st.markdown(f"**Finish with:** {r['final']:,.2f} Exalted")

        if r["profit"] > 0:
            st.success(f"Profit: +{r['profit']:,.2f} Exalted")
            st.markdown("### Recommendation: 🟢 Do this trade if the rates are still available.")
        else:
            st.error(f"Loss: {r['profit']:,.2f} Exalted")
            st.markdown("### Recommendation: 🔴 Do not do this trade.")

st.subheader("How to Read the Table")
st.markdown("""
Example row:

| Currency | Trade To | Buy | Sell |
|---|---:|---:|---:|
| Divine | Exalted | 405 | 400 |

Means:

- **Buy 1 Divine with 405 Exalted**
- **Sell 1 Divine for 400 Exalted**
""")
