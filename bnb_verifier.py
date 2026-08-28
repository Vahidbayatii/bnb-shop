"""
BNB Shop Transaction Verification Bot
======================================
Checks BSC blockchain for incoming payments to wallet,
sends Telegram notification, logs to Google Sheets.

Setup:
1. Get BscScan API key: https://bscscan.com/myapikey
2. Set environment variables or edit config below
3. Run: python bnb_verifier.py

Recommended: Run every 60 seconds via cron/systemd timer
"""

import os
import json
import time
import requests
from datetime import datetime

# ===== CONFIGURATION =====
BSCSCAN_API_KEY = os.environ.get("BSCSCAN_API_KEY", "YOUR_BSCSCAN_API_KEY")
WALLET_ADDRESS = "0xb06B2dAfD41f83F032375A03C33C09c8d3D9A77c"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-1003715758888")
GOOGLE_SHEET_ID = "1hx2WeT4Kg_thUH9vF6C0jmotn6kJLLH_W7T1KkXOD7A"

USDT_BSC = "0x55d398326f99059fF775485246999027B3197955"
STATE_FILE = "verifier_state.json"


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_block_bnb": 0, "last_block_token": 0, "processed_txs": []}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def check_bnb_transactions(start_block):
    url = "https://api.bscscan.com/api"
    params = {
        "module": "account",
        "action": "txlist",
        "address": WALLET_ADDRESS,
        "startblock": start_block,
        "endblock": 999999999,
        "sort": "desc",
        "apikey": BSCSCAN_API_KEY
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if data.get("status") == "1":
            return data.get("result", [])
    except Exception as e:
        print(f"BNB check error: {e}")
    return []


def check_token_transfers(start_block):
    url = "https://api.bscscan.com/api"
    params = {
        "module": "account",
        "action": "tokentx",
        "address": WALLET_ADDRESS,
        "startblock": start_block,
        "endblock": 999999999,
        "sort": "desc",
        "apikey": BSCSCAN_API_KEY
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if data.get("status") == "1":
            return data.get("result", [])
    except Exception as e:
        print(f"Token check error: {e}")
    return []


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN:
        print(f"[Telegram disabled] Would send: {message}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json().get("ok", False)
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


def log_to_sheet(tx_data):
    print(f"[Sheet] Would log: {json.dumps(tx_data, indent=2)}")


def process_transactions():
    state = load_state()
    new_txs = []

    bnb_txs = check_bnb_transactions(state["last_block_bnb"])
    for tx in bnb_txs:
        tx_hash = tx["hash"]
        if tx_hash in state["processed_txs"]:
            continue
        if tx["to"].lower() != WALLET_ADDRESS.lower():
            continue
        value_bnb = int(tx["value"]) / 1e18
        if value_bnb <= 0:
            continue
        new_txs.append({
            "type": "BNB", "hash": tx_hash, "from": tx["from"],
            "value": value_bnb, "block": int(tx["blockNumber"]),
            "time": datetime.fromtimestamp(int(tx["timeStamp"])).strftime("%Y-%m-%d %H:%M:%S"),
            "confirmations": int(tx.get("confirmations", 0))
        })
        if int(tx["blockNumber"]) > state["last_block_bnb"]:
            state["last_block_bnb"] = int(tx["blockNumber"])

    token_txs = check_token_transfers(state["last_block_token"])
    for tx in token_txs:
        tx_hash = tx["hash"]
        if tx_hash in state["processed_txs"]:
            continue
        if tx["to"].lower() != WALLET_ADDRESS.lower():
            continue
        value = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
        if value <= 0:
            continue
        new_txs.append({
            "type": tx["tokenSymbol"], "hash": tx_hash, "from": tx["from"],
            "value": value, "block": int(tx["blockNumber"]),
            "time": datetime.fromtimestamp(int(tx["timeStamp"])).strftime("%Y-%m-%d %H:%M:%S"),
            "confirmations": int(tx.get("confirmations", 0))
        })
        if int(tx["blockNumber"]) > state["last_block_token"]:
            state["last_block_token"] = int(tx["blockNumber"])

    for tx in new_txs:
        tx_hash = tx["hash"]
        if tx_hash in state["processed_txs"]:
            continue
        print(f"\n{'='*50}")
        print(f"\U0001f680 NEW PAYMENT DETECTED!")
        print(f"{'='*50}")
        print(f"Token:    {tx['type']}")
        print(f"Amount:   {tx['value']}")
        print(f"From:     {tx['from']}")
        print(f"TxHash:   {tx['hash']}")
        print(f"Time:     {tx['time']}")
        print(f"Block:    {tx['block']}")

        msg = (
            f"\U0001f680 *واریزی جدید!*\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"\U0001f4b0 مقدار: `{tx['value']} {tx['type']}`\n"
            f"\U0001f464 از: `{tx['from'][:10]}...{tx['from'][-6:]}`\n"
            f"\U0001f517 [مشاهده در BscScan](https://bscscan.com/tx/{tx['hash']})\n"
            f"\u23f0 {tx['time']}"
        )
        send_telegram(msg)
        log_to_sheet(tx)
        state["processed_txs"].append(tx_hash)

    if len(state["processed_txs"]) > 1000:
        state["processed_txs"] = state["processed_txs"][-500:]

    save_state(state)

    if new_txs:
        print(f"\n\u2705 Processed {len(new_txs)} new transaction(s)")
    else:
        print(f"\u23f3 No new transactions (last BNB block: {state['last_block_bnb']})")


if __name__ == "__main__":
    print(f"BNB Shop Verifier - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Wallet: {WALLET_ADDRESS}")
    process_transactions()
