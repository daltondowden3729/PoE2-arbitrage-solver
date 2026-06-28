
import streamlit as st
import pandas as pd
import re
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

def fmt(value):
    try:
        value = float(value)
    except Exception:
        return str(value)
    if abs(value - round(value)) < 0.005:
        return f"{int(round(value)):,}"
    return f"{value:,.2f}"

def make_default_df():
    return pd.DataFrame(DEFAULT_ROWS, columns=["Currency", "Trade To", "Buy", "Sell"])

def parse_pasted_table(text):
    """
    Supports pasted text like:

    Divine    Trade To    Buy    Sell
              Exalted     405    1
              Chaos       135    1

    It returns rows:
    Currency, Trade To, Buy, Sell
    """
    rows = []
    current_currency = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = [p.strip() for p in re.split(r"\t+|\s{2,}", line) if p.strip()]
        if not parts:
            continue

        # Header line: "Divine Trade To Buy Sell"
        if parts[0] in CURRENCIES and any("Trade To" in p for p in parts):
            current_currency = parts[0]
            continue

        # Single currency line
        if len(parts) == 1 and parts[0] in CURRENCIES:
            current_currency = parts[0]
            continue

        # Data line under a current currency
        if current_currency and len(parts) >= 3:
            trade_to = parts[0]
            if trade_to not in CURRENCIES:
                continue
            try:
                buy = float(parts[1])
                sell = float(parts[2])
            except Exception:
                continue
            rows.append([current_currency, trade_to, buy, sell])

        # Sometimes pasted rows may include all four fields directly
        elif len(parts) >= 4 and parts[0] in CURRENCIES and parts[1] in CURRENCIES:
            try:
                buy = float(parts[2])
                sell = float(parts[3])
            except Exception:
                continue
            rows.append([parts[0], parts[1], buy, sell])

    if not rows:
        return None

    # Merge with the full default structure so missing rows still exist.
    df = make_default_df()
    pasted = pd.DataFrame(rows, columns=["Currency", "Trade To", "Buy", "Sell"])

    for _, row in pasted.iterrows():
        mask = (df["Currency"] == row["Currency"]) & (df["Trade To"] == row["Trade To"])
        if mask.any():
            df.loc[mask, "Buy"] = row["Buy"]
            df.loc[mask, "Sell"] = row["Sell"]
        else:
            df.loc[len(df)] = row

    return df

def build_edges(df):
    """
    For each row:
    Currency = base currency
    Trade To = target currency

    Buy means:
      Buy 1 Currency with Buy amount of Trade To.
      Example: Divine / Exalted / Buy 405
      = Buy 1 Divine with 405 Exalted.
      Edge: Exalted -> Divine

    Sell means:
      Sell 1 Currency for Sell amount of Trade To.
      Example: Divine / Chaos / Sell 10
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
            edges[(target, base)] = {
                "type": "buy",
                "cost_per_one": buy,
                "base": base,
                "target": target,
            }

        if sell > 0:
            edges[(base, target)] = {
                "type": "sell",
                "cost_per_one": 1 / sell,
                "base": base,
                "target": target,
                "sell_amount": sell,
            }

    return edges

def convert(amount, frm, to, edges):
    edge = edges.get((frm, to))
    if edge is None:
        return None
    return amount / edge["cost_per_one"]

def make_step(amount, frm, to, edges):
    edge = edges[(frm, to)]
    out = convert(amount, frm, to, edges)

    if edge["type"] == "buy":
        text = f"Buy **{fmt(out)} {to}** with **{fmt(amount)} {frm}**."
        reason = f"Reason: {fmt(amount)} ÷ {fmt(edge['cost_per_one'])} = {fmt(out)}"
    else:
        text = f"Sell **{fmt(amount)} {frm}** for **{fmt(out)} {to}**."
        reason = f"Reason: {fmt(amount)} × {fmt(edge['sell_amount'])} = {fmt(out)}"

    return out, text, reason

def evaluate_path(path, bankroll, edges):
    amount = bankroll
    steps = []

    for frm, to in zip(path, path[1:]):
        if (frm, to) not in edges:
            return None
        amount, text, reason = make_step(amount, frm, to, edges)
        steps.append({"text": text, "reason": reason})

    profit = amount - bankroll
    roi = (profit / bankroll * 100) if bankroll else 0

    return {
        "path": path,
        "final": amount,
        "profit": profit,
        "roi": roi,
        "steps": steps,
    }

# ---------------- APP ----------------

st.title("PoE2 Easy Arbitrage Solver")
st.write("Manual table stays. Paste table is added. Output stays simple: **Buy X Vaal with X Exalted.**")

if "rates_df" not in st.session_state:
    st.session_state.rates_df = make_default_df()

bankroll = st.number_input("Current Exalted", min_value=0.0, value=548.0, step=1.0)

st.subheader("1) Update Rates")

tab_manual, tab_paste = st.tabs(["Manual Table", "Paste Table"])

with tab_manual:
    st.caption("Click any Buy or Sell cell to update it manually.")
    if st.button("Reset manual table to default values"):
        st.session_state.rates_df = make_default_df()

    edited_df = st.data_editor(
        st.session_state.rates_df,
        num_rows="fixed",
        use_container_width=True,
        column_config={
            "Currency": st.column_config.SelectboxColumn("Currency", options=CURRENCIES, disabled=True),
            "Trade To": st.column_config.SelectboxColumn("Trade To", options=CURRENCIES, disabled=True),
            "Buy": st.column_config.NumberColumn("Buy", min_value=0.0, step=0.01, format="%.2f"),
            "Sell": st.column_config.NumberColumn("Sell", min_value=0.0, step=0.01, format="%.2f"),
        },
        hide_index=True,
    )
    st.session_state.rates_df = edited_df.copy()

with tab_paste:
    st.caption("Paste your table here, then click Apply. This updates the manual table.")
    pasted = st.text_area("Paste currency table", height=280, placeholder="Paste your copied table here...")
    if st.button("Apply pasted table"):
        parsed = parse_pasted_table(pasted)
        if parsed is None:
            st.error("I could not read that table. Try copying it again with Currency / Trade To / Buy / Sell.")
        else:
            st.session_state.rates_df = parsed
            st.success("Table updated from pasted data. Go back to Manual Table to check it.")

st.subheader("2) Best Trade Instructions")

edges = build_edges(st.session_state.rates_df)

results = []
start = "Exalted"
others = [c for c in CURRENCIES if c != start]

max_trades = st.slider("Max number of trades to check", min_value=2, max_value=5, value=5)

for trade_count in range(2, max_trades + 1):
    for middle in permutations(others, trade_count - 1):
        path = [start] + list(middle) + [start]
        res = evaluate_path(path, bankroll, edges)
        if res is not None:
            results.append(res)

results.sort(key=lambda r: r["profit"], reverse=True)

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
    with st.expander(f"{icon} #{rank} | Profit: {fmt(r['profit'])} Ex | ROI: {r['roi']:.2f}%", expanded=(rank == 1)):
        st.markdown(f"### Start with **{fmt(bankroll)} Exalted**")

        for idx, step in enumerate(r["steps"], 1):
            st.markdown(f"**Step {idx}:** {step['text']}")
            with st.caption(step["reason"]):
                pass

        st.markdown("---")
        st.markdown(f"**Finish with:** {fmt(r['final'])} Exalted")

        if r["profit"] > 0:
            st.success(f"Profit: +{fmt(r['profit'])} Exalted")
            st.markdown("### Recommendation: 🟢 Do this trade if the rates are still available.")
        else:
            st.error(f"Loss: {fmt(r['profit'])} Exalted")
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
