
import streamlit as st
import pandas as pd
import json
from pathlib import Path
from itertools import permutations

st.set_page_config(page_title="PoE2 Easy Arbitrage Solver", layout="wide")

CURRENCIES = ["Exalted", "Divine", "Chaos", "Chance", "Annulment", "Vaal"]
SAVE_FILE = Path("saved_rates.json")

DEFAULT_RATES = {
    "Divine": {"Exalted": 410.0, "Chaos": 10.23, "Chance": 45.0, "Annulment": 1.75, "Vaal": 127.0},
    "Exalted": {"Divine": 1/400, "Chaos": 1/45, "Chance": 8.0, "Annulment": 1/200, "Vaal": 4.0},
    "Chaos": {"Divine": 1/10.35, "Exalted": 1/38.5, "Chance": 2.76, "Annulment": 1/5.8, "Vaal": 8.5},
    "Chance": {"Divine": 1/63, "Exalted": 1/6, "Chaos": 1/6, "Annulment": 1/53, "Vaal": 2.0},
    "Annulment": {"Divine": 1/1.85, "Exalted": 195.5, "Chaos": 5.5, "Chance": 3.33, "Vaal": 29.0},
    "Vaal": {"Divine": 1/168, "Exalted": 3.75, "Chaos": 1/18.49, "Chance": 1/9, "Annulment": 1/100},
}

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
    rows = []
    for base in CURRENCIES:
        for target in CURRENCIES:
            if base != target:
                rows.append([base, target, DEFAULT_RATES.get(base, {}).get(target, 0.0)])
    return pd.DataFrame(rows, columns=["Using 1", "You can buy", "Amount"])

def add_ratio_column(df):
    out = df[["Using 1", "You can buy", "Amount"]].copy()
    out["Calculated Ratio"] = out.apply(
        lambda r: f"1 {r['Using 1']} = {reciprocal_display(r['Amount'], r['You can buy'])}",
        axis=1
    )
    return out

def add_sell_buy_column(df):
    out = df[["Using 1", "You can buy", "Amount"]].copy()
    out["Calculated Ratio"] = out.apply(
        lambda r: f"1 {r['Using 1']} = {reciprocal_display(r['Amount'], r['You can buy'])}",
        axis=1
    )
    out["Sell ÷ Buy"] = out.apply(
        lambda r: fmt(r["Sell"] / r["Buy"]) if "Sell" in out.columns and "Buy" in out.columns and r["Buy"] else "",
        axis=1
    )
    return out

def make_profit_ratio_text(sell_value, buy_value):
    try:
        sell_value = float(sell_value)
        buy_value = float(buy_value)
        if buy_value <= 0:
            return "Enter a buy value above 0"
        ratio = sell_value / buy_value
        profit_pct = (ratio - 1) * 100
        return f"Sell ÷ Buy = {fmt(ratio)} | Profit % = {profit_pct:.2f}%"
    except Exception:
        return "Enter valid numbers"

def save_state(rates_df, start_currency, bankroll, max_trades):
    rates_only = rates_df[["Using 1", "You can buy", "Amount"]].copy()
    data = {
        "rates": rates_only.values.tolist(),
        "start_currency": start_currency,
        "bankroll": float(bankroll),
        "max_trades": int(max_trades),
    }
    SAVE_FILE.write_text(json.dumps(data, indent=2))

def load_state():
    if SAVE_FILE.exists():
        try:
            data = json.loads(SAVE_FILE.read_text())
            rates = pd.DataFrame(data.get("rates", []), columns=["Using 1", "You can buy", "Amount"])
            if len(rates) > 0:
                return (
                    rates,
                    data.get("start_currency", "Exalted"),
                    float(data.get("bankroll", 548.0)),
                    int(data.get("max_trades", 5)),
                )
        except Exception:
            pass
    return default_df(), "Exalted", 548.0, 5

def build_edges(df):
    edges = {}
    for _, r in df.iterrows():
        a = str(r["Using 1"])
        b = str(r["You can buy"])
        try:
            rate = float(r["Amount"])
        except Exception:
            rate = 0
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
        if len(parts) >= 3 and parts[0] in CURRENCIES and parts[1] in CURRENCIES:
            try:
                rows.append([parts[0], parts[1], float(parts[2])])
            except Exception:
                pass
            continue
        if current and len(parts) >= 2:
            try:
                if "/" in parts[0]:
                    n, d = parts[0].split("/")
                    val = float(n) / float(d)
                else:
                    val = float(parts[0])
                target = parts[1]
                if target in CURRENCIES and target != current:
                    rows.append([current, target, val])
            except Exception:
                pass
    return rows

def normalize_imported_df(uploaded_df):
    df = uploaded_df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if {"Using 1", "You can buy", "Amount"}.issubset(set(df.columns)):
        out = df[["Using 1", "You can buy", "Amount"]].copy()
        out["Using 1"] = out["Using 1"].astype(str).str.strip()
        out["You can buy"] = out["You can buy"].astype(str).str.strip()
        out["Amount"] = pd.to_numeric(out["Amount"], errors="coerce")
        out = out[out["Using 1"].isin(CURRENCIES)]
        out = out[out["You can buy"].isin(CURRENCIES)]
        out = out[out["Using 1"] != out["You can buy"]]
        out = out[out["Amount"].notna() & (out["Amount"] > 0)]
        return out.reset_index(drop=True)

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
            if currency not in CURRENCIES or trade_to not in CURRENCIES or currency == trade_to:
                continue
            if buy > 0 and sell > 0:
                rows.append([trade_to, currency, sell / buy])
        return pd.DataFrame(rows, columns=["Using 1", "You can buy", "Amount"])

    raise ValueError("CSV must include either: Using 1, You can buy, Amount OR Currency, Trade To, Buy, Sell.")

def transfer_to_manual(current_df, imported_df):
    df = current_df.copy()
    updated = 0
    added = 0
    skipped = 0
    changes = []
    for _, row in imported_df.iterrows():
        base = str(row["Using 1"]).strip()
        target = str(row["You can buy"]).strip()
        try:
            amount = float(row["Amount"])
        except Exception:
            skipped += 1
            continue
        if base not in CURRENCIES or target not in CURRENCIES or base == target or amount <= 0:
            skipped += 1
            continue
        mask = (df["Using 1"] == base) & (df["You can buy"] == target)
        if mask.any():
            old_amount = float(df.loc[mask, "Amount"].iloc[0])
            df.loc[mask, "Amount"] = amount
            updated += 1
            changes.append([base, target, old_amount, amount])
        else:
            df.loc[len(df)] = [base, target, amount]
            added += 1
            changes.append([base, target, None, amount])
    return df, updated, added, skipped, changes

st.title("PoE2 Easy Arbitrage Solver")
st.caption("Rule: each row means **Using 1 currency, you can buy X of another currency.**")

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


st.subheader("Quick Ratio Calculator")
st.caption("Use this when you have a buy number and sell number. It calculates Sell ÷ Buy.")

calc1, calc2, calc3 = st.columns(3)
with calc1:
    quick_buy = st.number_input("Buy number", min_value=0.0, value=1.0, step=0.01, key="quick_buy")
with calc2:
    quick_sell = st.number_input("Sell number", min_value=0.0, value=1.0, step=0.01, key="quick_sell")
with calc3:
    if quick_buy > 0:
        quick_ratio = quick_sell / quick_buy
        quick_profit_pct = (quick_ratio - 1) * 100
        st.metric("Sell ÷ Buy", fmt(quick_ratio), f"{quick_profit_pct:.2f}%")
    else:
        st.metric("Sell ÷ Buy", "—")

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

    editor_df = add_ratio_column(st.session_state.rates)

    edited = st.data_editor(
        editor_df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Using 1": st.column_config.SelectboxColumn("Using 1", options=CURRENCIES, disabled=True),
            "You can buy": st.column_config.SelectboxColumn("You can buy", options=CURRENCIES, disabled=True),
            "Amount": st.column_config.NumberColumn("Amount", min_value=0.0, step=0.0001, format="%.4f"),
            "Calculated Ratio": st.column_config.TextColumn("Calculated Ratio", disabled=True),
        },
    )

    st.session_state.rates = edited[["Using 1", "You can buy", "Amount"]].copy()
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
            df = st.session_state.rates.copy()
            updated = 0
            for base, target, amount in rows:
                mask = (df["Using 1"] == base) & (df["You can buy"] == target)
                if mask.any():
                    df.loc[mask, "Amount"] = amount
                    updated += 1
            st.session_state.rates = df
            save_state(st.session_state.rates, start_currency, bankroll, max_trades)
            st.success(f"Updated and saved {updated} row(s). Open Manual Table to review.")
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
        st.dataframe(add_ratio_column(st.session_state.imported_csv), use_container_width=True, hide_index=True)

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

    csv_export = st.session_state.rates.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export Manual Table as CSV",
        csv_export,
        file_name="poe2_currency_rates.csv",
        mime="text/csv"
    )

st.subheader("Easy View")
for base in CURRENCIES:
    with st.expander(base, expanded=(base == start_currency)):
        st.markdown(f"**Using 1 {base}, you can buy:**")
        sub = st.session_state.rates[st.session_state.rates["Using 1"] == base]
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
