
import streamlit as st
import re
from itertools import permutations

st.set_page_config(page_title="PoE2 Easy Arbitrage Solver", layout="wide")

CURRENCIES = ["Exalted", "Divine", "Chaos", "Chance", "Annulment", "Vaal"]

st.title("PoE2 Easy Arbitrage Solver")
st.write("Paste your rates, enter your Exalted balance, and get simple steps like: **Buy 137 Vaal with 548 Exalted.**")

bankroll = st.number_input("Starting Exalted", min_value=0.0, value=548.0, step=1.0)

sample = """Divine	Trade To	Buy	Sell
	Exalted	405	1
	Chaos	135	1
	Chance	30	1
	Annulment	1.75	1
	Vaal	124	1

Exalted	Trade To	Buy	Sell
	Divine	1	400
	Chaos	1	40
	Chance	1	10
	Annulment	1	207
	Vaal	1	4

Chaos	Trade To	Buy	Sell
	Divine	1	10.32
	Exalted	36.94	1
	Chance	3.86	1
	Annulment	1	5.7
	Vaal	11.61	1

Chance	Trade To	Buy	Sell
	Divine	1	55
	Exalted	6.5	1
	Chaos	1	6.5
	Annulment	1	53
	Vaal	2	1

Annulment	Trade To	Buy	Sell
	Divine	1	1.85
	Exalted	196.5	1
	Chaos	5.5	1
	Chance	3.33	1
	Vaal	30	1

Vaal	Trade To	Buy	Sell
	Divine	1	150
	Exalted	3.5	1
	Chaos	1	18.99
	Chance	1	9
	Annulment	1	90"""

raw = st.text_area("Paste your currency table here", value=sample, height=420)

def parse_table(text):
    """
    Reads pasted table format:
    Base Trade To Buy Sell
         Target buy sell

    Interpretation:
    - Buy column: cost in Target to buy 1 Base. This creates edge Target -> Base at cost buy.
    - Sell column: amount of Target received for selling 1 Base. This creates edge Base -> Target at rate sell.
    """
    edges = {}
    current_base = None
    for line in text.splitlines():
        parts = [p.strip() for p in re.split(r"\t+|\s{2,}", line.strip()) if p.strip()]
        if not parts:
            continue

        if parts[0] in CURRENCIES and ("Trade To" in line or len(parts) == 1):
            current_base = parts[0]
            continue

        if current_base and len(parts) >= 3:
            target = parts[0]
            if target not in CURRENCIES:
                continue
            try:
                buy = float(parts[1])
                sell = float(parts[2])
            except ValueError:
                continue

            if buy > 0:
                # Pay buy TARGET to receive 1 BASE
                edges[(target, current_base)] = {
                    "cost_per_one": buy,
                    "action": "buy",
                    "from": target,
                    "to": current_base,
                    "text": f"Buy 1 {current_base} with {buy:g} {target}"
                }

            if sell > 0:
                # Pay 1 BASE to receive sell TARGET
                # Equivalent cost per 1 TARGET = 1/sell BASE
                edges[(current_base, target)] = {
                    "cost_per_one": 1 / sell,
                    "action": "sell",
                    "from": current_base,
                    "to": target,
                    "sell_receive": sell,
                    "text": f"Sell 1 {current_base} for {sell:g} {target}"
                }
    return edges

edges = parse_table(raw)

def convert(amount, frm, to):
    e = edges.get((frm, to))
    if not e:
        return None
    return amount / e["cost_per_one"]

def step_text(amount, frm, to):
    e = edges[(frm, to)]
    out = convert(amount, frm, to)
    if e["action"] == "buy":
        return out, f"Buy **{out:,.2f} {to}** with **{amount:,.2f} {frm}**."
    else:
        return out, f"Sell **{amount:,.2f} {frm}** for **{out:,.2f} {to}**."

def evaluate_path(path):
    amount = bankroll
    steps = []
    for frm, to in zip(path, path[1:]):
        if (frm, to) not in edges:
            return None
        amount, text = step_text(amount, frm, to)
        steps.append(text)
    profit = amount - bankroll
    roi = profit / bankroll * 100 if bankroll else 0
    return {"path": path, "final": amount, "profit": profit, "roi": roi, "steps": steps}

results = []
start = "Exalted"
others = [c for c in CURRENCIES if c != start]

for trades in range(2, 6):
    for middle in permutations(others, trades - 1):
        path = [start] + list(middle) + [start]
        res = evaluate_path(path)
        if res:
            results.append(res)

results.sort(key=lambda r: r["profit"], reverse=True)

st.subheader("Best Trade Instructions")

if not results:
    st.error("No valid trade loops found. Check the pasted table.")
else:
    profitable = [r for r in results if r["profit"] > 0]
    show = profitable[:10] if profitable else results[:10]

    if not profitable:
        st.warning("No profitable loops found. Showing the least-bad options.")

    for i, r in enumerate(show, 1):
        color = "🟢" if r["profit"] > 0 else "🔴"
        with st.expander(f"{color} #{i} {' → '.join(r['path'])} | Profit: {r['profit']:,.2f} Ex | ROI: {r['roi']:.2f}%", expanded=(i == 1)):
            st.markdown(f"### Start with **{bankroll:,.2f} Exalted**")
            for n, step in enumerate(r["steps"], 1):
                st.markdown(f"**Step {n}:** {step}")
            st.markdown("---")
            st.markdown(f"**Final:** {r['final']:,.2f} Exalted")
            if r["profit"] > 0:
                st.success(f"Profit: +{r['profit']:,.2f} Exalted")
            else:
                st.error(f"Loss: {r['profit']:,.2f} Exalted")

st.subheader("Parsed Trades")
st.write("These are the trade directions the app understood from your table.")
parsed_rows = []
for (frm, to), e in sorted(edges.items()):
    parsed_rows.append({
        "From": frm,
        "To": to,
        "Simple Meaning": e["text"]
    })
st.dataframe(parsed_rows, use_container_width=True)
