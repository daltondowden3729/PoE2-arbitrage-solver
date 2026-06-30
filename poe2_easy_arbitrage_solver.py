
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

def ratio_df(df):
    rows = []
    for _, r in df.iterrows():
        base = r["Using 1"]
        target = r["You can buy"]
        amount = r["Amount"]
        rows.append([base, target, amount, f"1 {base} = {reciprocal_display(amount, target)}"])
    return pd.DataFrame(rows, columns=["Using 1", "You can buy", "Amount", "Ratio Calculated"])

def save_state(rates_df, start_currency, bankroll, max_trades):
    data = {
        "rates": rates_df[["Using 1", "You can buy", "Amount"]].values.tolist(),
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
                start_currency = data.get("start_currency", "Exalted")
                bankroll = float(data.get("bankroll", 548.0))
                max_trades = int(data.get("max_trades", 5))
                return rates, start_currency, bankroll, max_trades
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
    # Supports "Divine ... Using 1 Divine..." style blocks and simple rows:
    # Divine Exalted 410
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
        if len(parts) >= 2 and parts[0] in CURRENCIES and parts[1] in CURRENCIES:
            try:
                rows.append([parts[0], parts[1], float(parts[2])])
            except Exception:
                pass
            continue
        if current and parts:
            # Examples: "410 Exalted" or "1/400 Divine"
            try:
                if "/" in parts[0]:
                    n, d = parts[0].split("/")
                    val = float(n) / float(d)
                else:
                    val = float(parts[0])
                target = parts[1] if len(parts) > 1 else None
                if target in CURRENCIES and target != current:
                    rows.append([current, target, val])
            except Exception:
                pass
    return rows

st.title("PoE2 Easy Arbitrage Solver")
st.caption("Rule: each row means **Using 1 currency, you can buy X of another currency.**")

if "rates" not in st.session_state:
    saved_rates, saved_start, saved_bankroll, saved_max_trades = load_state()
    st.session_state.rates = saved_rates
    st.session_state.start_currency = saved_start
    st.session_state.bankroll = saved_bankroll
    st.session_state.max_trades = saved_max_trades

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

tab1, tab2 = st.tabs(["Manual Table", "Paste Import"])

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

    edited = st.data_editor(
        st.session_state.rates,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Using 1": st.column_config.SelectboxColumn("Using 1", options=CURRENCIES, disabled=True),
            "You can buy": st.column_config.SelectboxColumn("You can buy", options=CURRENCIES, disabled=True),
            "Amount": st.column_config.NumberColumn("Amount", min_value=0.0, step=0.0001, format="%.4f"),
        },
    )
    st.session_state.rates = edited.copy()
    save_state(st.session_state.rates, start_currency, bankroll, max_trades)

    st.markdown("#### Ratio Calculated")
    st.dataframe(
        ratio_df(st.session_state.rates),
        use_container_width=True,
        hide_index=True,
    )

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
