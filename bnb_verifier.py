import os, json, requests
from datetime import datetime

BSCSCAN_API_KEY = "8PZBAW6EVWU6MMQQ48NIW2NDFECT44EH7R"
WALLET = "0xb06B2dAfD41f83F032375A03C33C09c8d3D9A77c"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-1003715758888")
STATE_FILE = "verifier_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f: return json.load(f)
    return {"last_block_bnb": 0, "last_block_token": 0, "processed_txs": []}

def save_state(state):
    with open(STATE_FILE, "w") as f: json.dump(state, f, indent=2)

def check_bnb(start_block):
    r = requests.get("https://api.bscscan.com/api", params={"module":"account","action":"txlist","address":WALLET,"startblock":start_block,"endblock":999999999,"sort":"desc","apikey":BSCSCAN_API_KEY}, timeout=15)
    d = r.json()
    return d.get("result", []) if d.get("status") == "1" else []

def check_token(start_block):
    r = requests.get("https://api.bscscan.com/api", params={"module":"account","action":"tokentx","address":WALLET,"startblock":start_block,"endblock":999999999,"sort":"desc","apikey":BSCSCAN_API_KEY}, timeout=15)
    d = r.json()
    return d.get("result", []) if d.get("status") == "1" else []

def send_tg(msg):
    if not TELEGRAM_BOT_TOKEN: return
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json={"chat_id":TELEGRAM_CHAT_ID,"text":msg,"parse_mode":"Markdown"}, timeout=10)

def process():
    state = load_state()
    new = []
    for tx in check_bnb(state["last_block_bnb"]):
        if tx["hash"] in state["processed_txs"] or tx["to"].lower() != WALLET.lower(): continue
        v = int(tx["value"])/1e18
        if v <= 0: continue
        new.append({"type":"BNB","hash":tx["hash"],"from":tx["from"],"value":v,"time":datetime.fromtimestamp(int(tx["timeStamp"])).strftime("%Y-%m-%d %H:%M:%S")})
        if int(tx["blockNumber"]) > state["last_block_bnb"]: state["last_block_bnb"] = int(tx["blockNumber"])
    for tx in check_token(state["last_block_token"]):
        if tx["hash"] in state["processed_txs"] or tx["to"].lower() != WALLET.lower(): continue
        v = int(tx["value"])/(10**int(tx["tokenDecimal"]))
        if v <= 0: continue
        new.append({"type":tx["tokenSymbol"],"hash":tx["hash"],"from":tx["from"],"value":v,"time":datetime.fromtimestamp(int(tx["timeStamp"])).strftime("%Y-%m-%d %H:%M:%S")})
        if int(tx["blockNumber"]) > state["last_block_token"]: state["last_block_token"] = int(tx["blockNumber"])
    for tx in new:
        print(f"NEW PAYMENT: {tx['value']} {tx['type']} from {tx['from'][:10]}...")
        send_tg(f"\U0001f680 *\u0648\u0627\u0631\u06cc\u0632\u06cc \u062c\u062f\u06cc\u062f!*\n\U0001f4b0 `{tx['value']} {tx['type']}`\n\U0001f464 `{tx['from'][:10]}...`\n\U0001f517 [BscScan](https://bscscan.com/tx/{tx['hash']})")
        state["processed_txs"].append(tx["hash"])
    if len(state["processed_txs"]) > 1000: state["processed_txs"] = state["processed_txs"][-500:]
    save_state(state)
    print(f"Checked. New: {len(new)}")

if __name__ == "__main__":
    process()
