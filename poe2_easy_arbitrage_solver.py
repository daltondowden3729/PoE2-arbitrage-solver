
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

def parse_pasted_rows(text):
    rows = []
    current_currency = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = [p.strip() for p in re.split(r"\t+|\s{2,}", line) if p.strip()]
        if not parts:
            continue

        if parts[0] in CURRENCIES and any("Trade To" in p for p in parts):
            current_currency = parts[0]
            continue

        if len(parts) == 1 and parts[0] in CURRENCIES:
            current_currency = parts[0]
            continue

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
            continue

        if len(parts) >= 4 and parts[0] in CURRENCIES and parts[1] in CURRENCIES:
            try:
                buy = float(parts[2])
                sell = float(parts[3])
            except Exception:
                continue
            rows.append([parts[0], parts[1], buy, sell])

    return rows

def import_rows_to_manual(current_df, pasted_rows):
    df = current_df.copy()
    updated = 0
    added = 0
    skipped = 0
    changes = []

    for currency, trade_to, buy, sell in pasted_rows:
        if currency not in CURRENCIES or trade_to not in CURRENCIES or currency == trade_to:
            skipped += 1
            continue

        mask = (df["Currency"] == currency) & (df["Trade To"] == trade_to)

        if mask.any():
            old_buy = float(df.loc[mask, "Buy"].iloc[0])
            old_sell = float(df.loc[mask, "Sell"].iloc[0])
            df.loc[mask, "Buy"] = buy
            df.loc[mask, "Sell"] = sell
            updated += 1
            changes.append([currency, trade_to, old_buy, buy, old_sell, sell])
        else:
            df.loc[len(df)] = [currency, trade_to, buy, sell]
            added += 1
            changes.append([currency, trade_to, None, buy, None, sell])

    return df, updated, added, skipped, changes

def build_edges(df):
    """
    Each row creates one direction:
    Buy amount of Trade To = Sell amount of Currency.

    Example:
    Currency=Divine, Trade To=Exalted, Buy=405, Sell=1
    means 405 Exalted -> 1 Divine.
    """
    edges = {}

    for _, row in df.iterrows():
        output_currency = str(row["Currency"])
        input_currency = str(row["Trade To"])

        try:
            input_amount = float(row["Buy"])
            output_amount = float(row["Sell"])
        except Exception:
            continue

        if output_currency == input_currency or input_amount <= 0 or output_amount <= 0:
            continue

        edges[(input_currency, output_currency)] = {
            "input_amount": input_amount,
            "output_amount": output_amount,
            "rate": output_amount / input_amount,
        }

    return edges

def convert(amount, frm, to, edges):
    edge = edges.get((frm, to))
    if edge is None:
        return None
    return amount * edge["rate"]

def make_step(amount, frm, to, edges):
    edge = edges[(frm, to)]
    out = convert(amount, frm, to, edges)

    if to == "Exalted":
        text = f"Sell **{fmt(amount)} {frm}** for **{fmt(out)} Exalted**."
    elif frm == "Exalted":
        text = f"Buy **{fmt(out)} {to}** with **{fmt(amount)} Exalted**."
    else:
        text = f"Trade **{fmt(amount)} {frm}** for **{fmt(out)} {to}**."

    reason = f"{fmt(edge['input_amount'])} {frm} = {fmt(edge['output_amount'])} {to}"
    ratio = f"Ratio: 1 {frm} = {fmt(edge['rate'])} {to}"
    math = f"Math: {fmt(amount)} × {fmt(edge['rate'])} = {fmt(out)}"

    return out, text, reason, ratio, math

def evaluate_path(path, bankroll, edges):
    amount = bankroll
    steps = []

    for frm, to in zip(path, path[1:]):
        if (frm, to) not in edges:
            return None
        amount, text, reason, ratio, math = make_step(amount, frm, to, edges)
        steps.append({
            "text": text,
            "reason": reason,
            "ratio": ratio,
            "math": math,
        })

    profit = amount - bankroll
    roi = (profit / bankroll * 100) if bankroll else 0

    return {
        "path": path,
        "final": amount,
        "profit": profit,
        "roi": roi,
        "steps": steps,
        "summary_ratio": (amount / bankroll) if bankroll else 0,
    }

def solve_trades(rates_df, bankroll, max_trades):
    edges = build_edges(rates_df)
    results = []
    start = "Exalted"
    others = [c for c in CURRENCIES if c != start]

    for trade_count in range(2, max_trades + 1):
        for middle in permutations(others, trade_count - 1):
            path = [start] + list(middle) + [start]
            res = evaluate_path(path, bankroll, edges)
            if res is not None:
                results.append(res)

    results.sort(key=lambda r: r["profit"], reverse=True)
    return results

def show_results(results, bankroll):
    profitable = [r for r in results if r["profit"] > 0]
    shown = profitable[:10] if profitable else results[:10]

    if not shown:
        st.error("No possible loops found. Check the exchange table.")
        return

    if not profitable:
        st.warning("No profitable loops found. Showing the least-bad options.")
    else:
        st.success(f"Found {len(profitable)} profitable loop(s).")

    for rank, r in enumerate(shown, 1):
        icon = "🟢" if r["profit"] > 0 else "🔴"
        with st.expander(
            f"{icon} #{rank} | Profit: {fmt(r['profit'])} Ex | ROI: {r['roi']:.2f}% | Final: {fmt(r['final'])} Ex",
            expanded=(rank == 1),
        ):
            st.markdown(f"### Start with **{fmt(bankroll)} Exalted**")

            for idx, step in enumerate(r["steps"], 1):
                st.markdown(f"**Step {idx}:** {step['text']}")
                st.caption(step["reason"])
                st.caption(step["ratio"])
                st.caption(step["math"])

            st.markdown("---")
            st.markdown(f"**Finish with:** {fmt(r['final'])} Exalted")
            st.markdown(f"**Overall ratio:** 1 Exalted becomes **{fmt(r['summary_ratio'])} Exalted**")
            st.markdown(f"**ROI reason:** ({fmt(r['final'])} - {fmt(bankroll)}) ÷ {fmt(bankroll)} × 100 = **{r['roi']:.2f}%**")

            if r["profit"] > 0:
                st.success(f"Profit: +{fmt(r['profit'])} Exalted")
                st.markdown("### Recommendation: 🟢 Do this trade if the rates are still available.")
            else:
                st.error(f"Loss: {fmt(r['profit'])} Exalted")
                st.markdown("### Recommendation: 🔴 Do not do this trade.")

# ---------------- APP ----------------

st.title("PoE2 Easy Arbitrage Solver")
st.write("When you update the table, the steps, ROI, reason, and ratios refresh automatically.")

if "rates_df" not in st.session_state:
    st.session_state.rates_df = make_default_df()

if "last_import_changes" not in st.session_state:
    st.session_state.last_import_changes = []

bankroll = st.number_input("Current Exalted", min_value=0.0, value=548.0, step=1.0)
max_trades = st.slider("Max number of trades to check", min_value=2, max_value=5, value=5)

st.subheader("1) Update Rates")

tab_manual, tab_paste = st.tabs(["Manual Table", "Paste Table"])

with tab_manual:
    st.caption("This is the master table. Editing any number here automatically refreshes the trade steps below.")

    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("Reset manual table"):
            st.session_state.rates_df = make_default_df()
            st.session_state.last_import_changes = []
            st.rerun()

    edited_df = st.data_editor(
        st.session_state.rates_df,
        num_rows="fixed",
        use_container_width=True,
        key="manual_rates_editor",
        column_config={
            "Currency": st.column_config.SelectboxColumn("Currency", options=CURRENCIES, disabled=True),
            "Trade To": st.column_config.SelectboxColumn("Trade To", options=CURRENCIES, disabled=True),
            "Buy": st.column_config.NumberColumn("Buy", min_value=0.0, step=0.01, format="%.2f"),
            "Sell": st.column_config.NumberColumn("Sell", min_value=0.0, step=0.01, format="%.2f"),
        },
        hide_index=True,
    )

    # The solver below uses edited_df immediately, so steps refresh as soon as the table changes.
    st.session_state.rates_df = edited_df.copy()

    if st.session_state.last_import_changes:
        with st.expander("Last paste import changes", expanded=False):
            change_df = pd.DataFrame(
                st.session_state.last_import_changes,
                columns=["Currency", "Trade To", "Old Buy", "New Buy", "Old Sell", "New Sell"]
            )
            st.dataframe(change_df, use_container_width=True, hide_index=True)

with tab_paste:
    st.caption("Paste your copied table here. Then transfer it into the Manual Table.")
    pasted = st.text_area("Paste currency table", height=280, placeholder="Paste your copied table here...")

    if st.button("Transfer Paste to Manual Table"):
        rows = parse_pasted_rows(pasted)

        if not rows:
            st.error("I could not read that table. Try copying it again with Currency / Trade To / Buy / Sell.")
        else:
            new_df, updated, added, skipped, changes = import_rows_to_manual(st.session_state.rates_df, rows)
            st.session_state.rates_df = new_df
            st.session_state.last_import_changes = changes

            st.success(f"Transfer complete: {updated} row(s) updated, {added} row(s) added, {skipped} row(s) skipped.")
            st.info("The Manual Table is now updated. The trade steps below use the new values.")

            if changes:
                change_df = pd.DataFrame(
                    changes,
                    columns=["Currency", "Trade To", "Old Buy", "New Buy", "Old Sell", "New Sell"]
                )
                st.dataframe(change_df, use_container_width=True, hide_index=True)

st.subheader("2) Best Trade Instructions")

results = solve_trades(st.session_state.rates_df, bankroll, max_trades)
show_results(results, bankroll)

st.subheader("How to Read the Table")
st.markdown("""
Example rows:

| Currency | Trade To | Buy | Sell |
|---|---:|---:|---:|
| Divine | Exalted | 405 | 1 |
| Exalted | Divine | 1 | 400 |

Means:

- **405 Exalted = 1 Divine**
- **1 Divine = 400 Exalted**
""")
