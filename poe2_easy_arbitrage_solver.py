
import streamlit as st
import pandas as pd
import json
from pathlib import Path
from itertools import permutations

st.set_page_config(page_title="PoE2 Easy Arbitrage Solver", layout="wide")

CURRENCIES = ["Exalted", "Divine", "Chaos", "Chance", "Annulment", "Vaal"]
SAVE_FILE = Path("saved_rates.json")

# Default rows from your uploaded CSV.
# Columns are: Using 1, You can buy, Buy, Sell
DEFAULT_ROWS = [['Exalted', 'Divine', 0.002, 1.0], ['Exalted', 'Chaos', 0.022, 1.0], ['Exalted', 'Chance', 0.0588, 1.0], ['Exalted', 'Annulment', 0.0036, 1.0], ['Exalted', 'Vaal', 0.2, 1.0], ['Divine', 'Exalted', 498.0, 1.0], ['Divine', 'Chaos', 9.34, 1.0], ['Divine', 'Chance', 46.0, 1.0], ['Divine', 'Annulment', 1.68, 1.0], ['Divine', 'Vaal', 134.0, 1.0], ['Chaos', 'Exalted', 52.0, 1.0], ['Chaos', 'Divine', 0.1064, 1.0], ['Chaos', 'Chance', 4.74, 1.0], ['Chaos', 'Annulment', 0.1724, 1.0], ['Chaos', 'Vaal', 8.5, 1.0], ['Chance', 'Exalted', 0.1666, 1.0], ['Chance', 'Divine', 0.0158, 1.0], ['Chance', 'Chaos', 0.1666, 1.0], ['Chance', 'Annulment', 0.0188, 1.0], ['Chance', 'Vaal', 2.0, 1.0], ['Annulment', 'Exalted', 195.5, 1.0], ['Annulment', 'Divine', 0.5405, 1.0], ['Annulment', 'Chaos', 5.5, 1.0], ['Annulment', 'Chance', 3.33, 1.0], ['Annulment', 'Vaal', 29.0, 1.0], ['Vaal', 'Exalted', 3.75, 1.0], ['Vaal', 'Divine', 0.0059, 1.0], ['Vaal', 'Chaos', 0.054, 1.0], ['Vaal', 'Chance', 0.1111, 1.0], ['Vaal', 'Annulment', 0.01, 1.0]]

def fmt(x):
    try:
        x = float(x)
    except Exception:
        return str(x)
    if abs(x - round(x)) < 0.00005:
        return f"{int(round(x)):,}"
    return f"{x:,.4f}"

def reciprocal_display(rate, target):
    rate = float(rate)
    if rate >= 1:
        return f"{fmt(rate)} {target}"
    if rate <= 0:
        return f"0 {target}"
    denom = 1 / rate
    return f"{fmt(rate)} {target}  (1/{fmt(denom)})"

def default_df():
    return pd.DataFrame(DEFAULT_ROWS, columns=["Using 1", "You can buy", "Buy", "Sell"])

def clean_df(df):
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]

    # Backwards compatibility with older files
    if "Buy" not in out.columns and "Amount" in out.columns:
        out["Buy"] = pd.to_numeric(out["Amount"], errors="coerce").fillna(0.0)
    if "Sell" not in out.columns:
        out["Sell"] = 1.0

    out = out[["Using 1", "You can buy", "Buy", "Sell"]].copy()
    out["Using 1"] = out["Using 1"].astype(str).str.strip()
    out["You can buy"] = out["You can buy"].astype(str).str.strip()
    out["Buy"] = pd.to_numeric(out["Buy"], errors="coerce").fillna(0.0)
    out["Sell"] = pd.to_numeric(out["Sell"], errors="coerce").fillna(0.0)
    out = out[out["Using 1"].isin(CURRENCIES)]
    out = out[out["You can buy"].isin(CURRENCIES)]
    out = out[out["Using 1"] != out["You can buy"]]
    return out.reset_index(drop=True)

def amount_from_buy_sell(buy, sell):
    try:
        buy = float(buy)
        sell = float(sell)
        if sell <= 0:
            return 0.0
        return buy / sell
    except Exception:
        return 0.0

def add_calculated_columns(df):
    out = clean_df(df)

    # Spreadsheet-style formula:
    # Amount always equals Buy divided by Sell.
    out["Amount"] = out.apply(
        lambda r: amount_from_buy_sell(r["Buy"], r["Sell"]),
        axis=1
    )

    # Ratio is based on the calculated Amount.
    out["Ratio Calculated"] = out.apply(
        lambda r: f"1 {r['Using 1']} = {reciprocal_display(r['Amount'], r['You can buy'])}",
        axis=1
    )

    return out[["Using 1", "You can buy", "Buy", "Sell", "Amount", "Ratio Calculated"]]

def save_state(rates_df, start_currency, bankroll, max_trades):
    rates = clean_df(rates_df)
    data = {
        "rates": rates[["Using 1", "You can buy", "Buy", "Sell"]].values.tolist(),
        "start_currency": start_currency,
        "bankroll": float(bankroll),
        "max_trades": int(max_trades),
    }
    SAVE_FILE.write_text(json.dumps(data, indent=2))

def load_state():
    if SAVE_FILE.exists():
        try:
            data = json.loads(SAVE_FILE.read_text())
            raw = data.get("rates", [])
            if raw:
                # Supports old 3-column saves and new 4-column saves.
                if len(raw[0]) == 3:
                    rates = pd.DataFrame(raw, columns=["Using 1", "You can buy", "Amount"])
                    rates["Buy"] = pd.to_numeric(rates["Amount"], errors="coerce").fillna(0.0)
                    rates["Sell"] = 1.0
                    rates = rates[["Using 1", "You can buy", "Buy", "Sell"]]
                else:
                    rates = pd.DataFrame(raw, columns=["Using 1", "You can buy", "Buy", "Sell"])
                return (
                    clean_df(rates),
                    data.get("start_currency", "Exalted"),
                    float(data.get("bankroll", 548.0)),
                    int(data.get("max_trades", 5)),
                )
        except Exception:
            pass
    return default_df(), "Exalted", 548.0, 5

def build_edges(df):
    edges = {}
    calc = add_calculated_columns(df)
    for _, r in calc.iterrows():
        a = str(r["Using 1"])
        b = str(r["You can buy"])
        rate = float(r["Amount"])
        if a != b and rate > 0:
            edges[(a, b)] = rate
    return edges

def eval_path(path, start_amount, edges):
    amount = start_amount
    steps = []
    for a, b in zip(path, path[1:]):
        if (a, b) not in edges:
            return None
        rate = edges[(a, b)]
        new_amount = amount * rate
        if a == "Exalted":
            line = f"Buy **{fmt(new_amount)} {b}** with **{fmt(amount)} {a}**."
        elif b == "Exalted":
            line = f"Sell **{fmt(amount)} {a}** for **{fmt(new_amount)} {b}**."
        else:
            line = f"Trade **{fmt(amount)} {a}** for **{fmt(new_amount)} {b}**."
        steps.append({
            "line": line,
            "reason": f"Ratio: 1 {a} = {reciprocal_display(rate, b)}",
            "math": f"Math: {fmt(amount)} × {fmt(rate)} = {fmt(new_amount)}"
        })
        amount = new_amount
    profit = amount - start_amount
    roi = (profit / start_amount * 100) if start_amount else 0
    return {"path": path, "final": amount, "profit": profit, "roi": roi, "steps": steps, "ratio": amount/start_amount if start_amount else 0}

def solve(df, start_currency, bankroll, max_trades):
    edges = build_edges(df)
    results = []
    others = [c for c in CURRENCIES if c != start_currency]
    for trades in range(2, max_trades + 1):
        for middle in permutations(others, trades - 1):
            path = [start_currency] + list(middle) + [start_currency]
            r = eval_path(path, bankroll, edges)
            if r:
                results.append(r)
    return sorted(results, key=lambda r: r["profit"], reverse=True)

def parse_paste(text):
    rows = []
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line in CURRENCIES:
            current = line
            continue
        if line.startswith("Using 1 "):
            for c in CURRENCIES:
                if f"Using 1 {c}" in line:
                    current = c
                    break
            continue
        parts = line.replace(":", " ").replace(",", " ").split()

        # Using1 YouCanBuy Buy Sell
        if len(parts) >= 4 and parts[0] in CURRENCIES and parts[1] in CURRENCIES:
            try:
                rows.append([parts[0], parts[1], float(parts[2]), float(parts[3])])
            except Exception:
                pass
            continue

        # Using1 YouCanBuy Amount
        if len(parts) >= 3 and parts[0] in CURRENCIES and parts[1] in CURRENCIES:
            try:
                amount = float(parts[2])
                rows.append([parts[0], parts[1], amount, 1.0])
            except Exception:
                pass
            continue

        # Block style: amount target
        if current and len(parts) >= 2:
            try:
                if "/" in parts[0]:
                    n, d = parts[0].split("/")
                    val = float(n) / float(d)
                else:
                    val = float(parts[0])
                target = parts[1]
                if target in CURRENCIES and target != current:
                    rows.append([current, target, val, 1.0])
            except Exception:
                pass
    return rows

def normalize_imported_df(uploaded_df):
    df = uploaded_df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # New preferred CSV format
    if {"Using 1", "You can buy", "Buy", "Sell"}.issubset(set(df.columns)):
        out = df[["Using 1", "You can buy", "Buy", "Sell"]].copy()
        return clean_df(out)

    # Uploaded file format with Amount only
    if {"Using 1", "You can buy", "Amount"}.issubset(set(df.columns)):
        out = df[["Using 1", "You can buy", "Amount"]].copy()
        out["Buy"] = pd.to_numeric(out["Amount"], errors="coerce").fillna(0.0)
        out["Sell"] = 1.0
        out = out[["Using 1", "You can buy", "Buy", "Sell"]]
        return clean_df(out)

    # Old 4-column market format
    if {"Currency", "Trade To", "Buy", "Sell"}.issubset(set(df.columns)):
        rows = []
        for _, r in df.iterrows():
            currency = str(r["Currency"]).strip()
            trade_to = str(r["Trade To"]).strip()
            try:
                buy = float(r["Buy"])
                sell = float(r["Sell"])
            except Exception:
                continue
            if currency in CURRENCIES and trade_to in CURRENCIES and currency != trade_to and buy > 0 and sell > 0:
                # This means: Buy amount of Trade To = Sell amount of Currency.
                # So Using 1 Trade To buys Sell/Buy Currency.
                rows.append([trade_to, currency, sell, buy])
        return clean_df(pd.DataFrame(rows, columns=["Using 1", "You can buy", "Buy", "Sell"]))

    raise ValueError("CSV needs either: Using 1, You can buy, Buy, Sell OR Using 1, You can buy, Amount.")

def transfer_to_manual(current_df, imported_df):
    df = clean_df(current_df)
    imported = clean_df(imported_df)
    updated = 0
    added = 0
    skipped = 0
    changes = []
    for _, row in imported.iterrows():
        base = str(row["Using 1"]).strip()
        target = str(row["You can buy"]).strip()
        try:
            buy = float(row["Buy"])
            sell = float(row["Sell"])
        except Exception:
            skipped += 1
            continue
        if base not in CURRENCIES or target not in CURRENCIES or base == target or sell <= 0:
            skipped += 1
            continue
        mask = (df["Using 1"] == base) & (df["You can buy"] == target)
        new_amount = amount_from_buy_sell(buy, sell)
        if mask.any():
            old_amount = amount_from_buy_sell(df.loc[mask, "Buy"].iloc[0], df.loc[mask, "Sell"].iloc[0])
            df.loc[mask, "Buy"] = buy
            df.loc[mask, "Sell"] = sell
            updated += 1
            changes.append([base, target, old_amount, new_amount])
        else:
            df.loc[len(df)] = [base, target, buy, sell]
            added += 1
            changes.append([base, target, None, new_amount])
    return df, updated, added, skipped, changes

st.title("PoE2 Easy Arbitrage Solver")
st.caption("Enter **Buy** and **Sell**. The app calculates **Amount = Buy ÷ Sell** and updates the ratio automatically.")

if "rates" not in st.session_state:
    saved_rates, saved_start, saved_bankroll, saved_max_trades = load_state()
    st.session_state.rates = saved_rates
    st.session_state.start_currency = saved_start
    st.session_state.bankroll = saved_bankroll
    st.session_state.max_trades = saved_max_trades

if "imported_csv" not in st.session_state:
    st.session_state.imported_csv = None

if "last_csv_import_changes" not in st.session_state:
    st.session_state.last_csv_import_changes = []

top1, top2, top3 = st.columns(3)
with top1:
    start_currency = st.selectbox(
        "Start / End Currency",
        CURRENCIES,
        index=CURRENCIES.index(st.session_state.start_currency) if st.session_state.start_currency in CURRENCIES else 0,
    )
with top2:
    bankroll = st.number_input(f"Current {start_currency}", min_value=0.0, value=float(st.session_state.bankroll), step=1.0)
with top3:
    max_trades = st.slider("Max trades", 2, 5, int(st.session_state.max_trades))

st.session_state.start_currency = start_currency
st.session_state.bankroll = bankroll
st.session_state.max_trades = max_trades

tab1, tab2, tab3 = st.tabs(["Manual Table", "Paste Import", "Imported CSV"])

with tab1:
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Save values"):
            save_state(st.session_state.rates, start_currency, bankroll, max_trades)
            st.success("Saved.")
    with c2:
        if st.button("Reset values"):
            st.session_state.rates = default_df()
            save_state(st.session_state.rates, start_currency, bankroll, max_trades)
            st.rerun()

    st.info("Formula: **Amount = Buy ÷ Sell**. Only **Buy** and **Sell** are editable.")

    editor_df = add_calculated_columns(st.session_state.rates)

    edited = st.data_editor(
        editor_df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Using 1": st.column_config.SelectboxColumn("Using 1", options=CURRENCIES, disabled=True),
            "You can buy": st.column_config.SelectboxColumn("You can buy", options=CURRENCIES, disabled=True),
            "Buy": st.column_config.NumberColumn("Buy", min_value=0.0, step=0.0001, format="%.4f"),
            "Sell": st.column_config.NumberColumn("Sell", min_value=0.0001, step=0.0001, format="%.4f"),
            "Amount": st.column_config.NumberColumn("Amount = Buy ÷ Sell", disabled=True, format="%.4f", help="Formula: Buy divided by Sell"),
            "Ratio Calculated": st.column_config.TextColumn("Ratio Calculated", disabled=True),
        },
    )

    # Only save the editable source columns.
    # Amount and Ratio are never saved as manual values; they are recalculated every run.
    st.session_state.rates = clean_df(edited)
    save_state(st.session_state.rates, start_currency, bankroll, max_trades)

    if st.session_state.last_csv_import_changes:
        with st.expander("Last CSV transfer changes", expanded=False):
            change_df = pd.DataFrame(
                st.session_state.last_csv_import_changes,
                columns=["Using 1", "You can buy", "Old Amount", "New Amount"]
            )
            st.dataframe(change_df, use_container_width=True, hide_index=True)

with tab2:
    paste = st.text_area("Paste rates here", height=250)
    if st.button("Transfer paste to manual table"):
        rows = parse_paste(paste)
        if not rows:
            st.error("Could not read the paste.")
        else:
            imported = pd.DataFrame(rows, columns=["Using 1", "You can buy", "Buy", "Sell"])
            df, updated, added, skipped, changes = transfer_to_manual(st.session_state.rates, imported)
            st.session_state.rates = df
            save_state(st.session_state.rates, start_currency, bankroll, max_trades)
            st.success(f"Updated and saved {updated} row(s). Added {added} row(s). Skipped {skipped}.")
            st.rerun()

with tab3:
    st.markdown("### Imported CSV")
    st.caption("Upload a CSV from Google Sheets or Excel. Review it here, then transfer it to the Manual Table.")

    uploaded_file = st.file_uploader("Import CSV file", type=["csv"])

    if uploaded_file is not None:
        try:
            raw_csv = pd.read_csv(uploaded_file)
            imported = normalize_imported_df(raw_csv)
            st.session_state.imported_csv = imported
            st.success(f"CSV loaded: {len(imported)} valid row(s).")
        except Exception as e:
            st.error(f"Could not read CSV: {e}")

    if st.session_state.imported_csv is not None:
        st.markdown("#### Imported CSV Table")
        st.dataframe(add_calculated_columns(st.session_state.imported_csv), use_container_width=True, hide_index=True)

        if st.button("Transfer Imported CSV to Manual Table"):
            new_df, updated, added, skipped, changes = transfer_to_manual(
                st.session_state.rates,
                st.session_state.imported_csv
            )
            st.session_state.rates = new_df
            st.session_state.last_csv_import_changes = changes
            save_state(st.session_state.rates, start_currency, bankroll, max_trades)
            st.success(f"Transferred and saved: {updated} updated, {added} added, {skipped} skipped.")
            st.info("Open Manual Table to review the updated values.")

    csv_export = add_calculated_columns(st.session_state.rates).to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export Manual Table as CSV",
        csv_export,
        file_name="poe2_currency_rates.csv",
        mime="text/csv"
    )

st.subheader("Easy View")
calc_rates = add_calculated_columns(st.session_state.rates)
for base in CURRENCIES:
    with st.expander(base, expanded=(base == start_currency)):
        st.markdown(f"**Using 1 {base}, you can buy:**")
        sub = calc_rates[calc_rates["Using 1"] == base]
        for _, r in sub.iterrows():
            st.write(f"- {reciprocal_display(r['Amount'], r['You can buy'])}")

st.subheader("Best Trade Instructions")
results = solve(st.session_state.rates, start_currency, bankroll, max_trades)
shown = [r for r in results if r["profit"] > 0][:10] or results[:10]

if not shown:
    st.error("No loops found.")
else:
    for i, r in enumerate(shown, 1):
        good = r["profit"] > 0
        icon = "🟢" if good else "🔴"
        with st.expander(f"{icon} #{i} Profit: {fmt(r['profit'])} {start_currency} | ROI: {r['roi']:.2f}% | Final: {fmt(r['final'])}", expanded=i==1):
            st.markdown(f"### Start with **{fmt(bankroll)} {start_currency}**")
            for n, step in enumerate(r["steps"], 1):
                st.markdown(f"**Step {n}:** {step['line']}")
                st.caption(step["reason"])
                st.caption(step["math"])
            st.markdown("---")
            st.markdown(f"**Finish with:** {fmt(r['final'])} {start_currency}")
            st.markdown(f"**Overall ratio:** 1 {start_currency} becomes **{fmt(r['ratio'])} {start_currency}**")
            st.markdown(f"**ROI reason:** ({fmt(r['final'])} - {fmt(bankroll)}) ÷ {fmt(bankroll)} × 100 = **{r['roi']:.2f}%**")
            (st.success if good else st.error)(f"{'Profit' if good else 'Loss'}: {fmt(r['profit'])} {start_currency}")
