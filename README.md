# PoE2 Easy Arbitrage Solver

This app is built to output plain-English trade steps.

Example output:

1. Buy **137 Vaal** with **548 Exalted**.
2. Buy **1 Divine** with **124 Vaal**.
3. Sell **1 Divine** for **10 Chaos**.
4. Sell **10 Chaos** for **400 Exalted**.

## Run it

```bash
pip install -r requirements.txt
streamlit run poe2_easy_arbitrage_solver.py
```

## How to use

Paste your in-game exchange table into the text box, enter your Exalted balance, and the app will rank the best trade loops.
