#!/usr/bin/env python3

import requests
import json
from datetime import datetime
import time
from collections import defaultdict
from tqdm import tqdm
import traceback
from decimal import Decimal
from termcolor import colored

class RaydiumPoolTracker:
    def __init__(self):
        # Token and Pool Configuration
        self.token_address = "9tLUnDz6G2dUGVhiLEEEpfM8e1YBiXnWrdT4xVeopump"
        self.pool_address = "ATq5UNL1z3ZgpBbvasqbqtC1Ei8rz3rdxbmgeiPwhrrE"

        self.flagged_addresses = [
            "Brcd3wmuHFd5bTdufdsCjAT8pD8huhpg36F2Gjiuq8ZZ",
            "5hj7njCVTnih6gksibPoZbX5ppYJyy1xU8ZM17fg5yXi",
            "HpMSqpsv6i8owHqQeZzUiVpGv4iRB5yJrPeGsbPFx1nD",
            "DHGhJZTCBSEN9PY34f6uaZSSU23Ducg3BtCYye67gzWK",
            "BUwUJ9iWS5DQVvLMVrZftEuKJxBGsmiMiVnFoBejEjgD",
            "735DNS2peaNEaG6zTAJkqXwCiHQyBceyCuhwXwTgYbKj",
            "5nKsdRoCogUgSKYgUZebC8F7MZQvGteabSpgTKyoxvdy",
            "Gbv8ttscCkYsnU5Fv3wbwSoFSN1p7rXLX5AqCsAUNV8Q",
            "93RGVyzVYFaKM53mxhpgqkmKRtVkmp8JEcDuceB4DdfJ",
            "0xf3fe2776f58e7882eee122544bf1b0bddd2ee8d2",
            "2aAHrfotnDbraTFErzAuqeVM665YVLxrvNmg1PnNp47F",
            "HvvHaDdmDDcek8zGMXwUiNsXzBYX6DvRtCqvsYK93Dya",
            "752Nn2PDQYsJCZAPDZ26Y84waWki9f6UAmm1jny88Pdy"
        ]

        # RPC Configuration
        self.rpc_url = "https://api.mainnet-beta.solana.com"
        self.headers = {"Content-Type": "application/json"}

        # Wallet flow and transaction details
        self.wallet_flows = defaultdict(lambda: {
            "incoming": defaultdict(float),
            "outgoing": defaultdict(float),
            "total_received": 0.0,
            "total_sent": 0.0,
            "first_seen": None,
            "last_seen": None,
            "transaction_count": 0
        })
        self.transaction_details = []
        self.output_file = 'pool_flows.json'

    def save_progress(self):
        output = {
            "wallet_flows": self.wallet_flows,
            "transaction_details": self.transaction_details
        }
        with open(self.output_file, 'w') as f:
            json.dump(output, f, indent=2)
        print(colored("[INFO] Progress saved to pool_flows.json", "green"))

    def get_signatures_paginated(self, limit_per_page=1000):
        print(colored("Fetching signatures for the Raydium pool with debugging...", "cyan"))
        all_signatures = []
        before_sig = None

        while True:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [
                    self.pool_address,
                    {"limit": limit_per_page}
                ]
            }
            if before_sig:
                payload["params"][1]["before"] = before_sig

            try:
                print(colored("[DEBUG] Requesting signatures with payload:", "yellow"))
                print(json.dumps(payload, indent=2))
                resp = requests.post(self.rpc_url, json=payload, headers=self.headers)
                data = resp.json()

                if "result" not in data or not data["result"]:
                    break

                page_sigs = data["result"]
                all_signatures.extend(page_sigs)
                before_sig = page_sigs[-1]["signature"]
                print(colored(f"  Fetched {len(page_sigs)} sigs", "green"))

            except Exception as e:
                print(colored(f"Error fetching signatures: {e}", "red"))
                traceback.print_exc()
                break

        print(colored(f"Total signatures fetched overall: {len(all_signatures)}", "cyan"))
        return all_signatures

    def generate_report(self):
        sigs = self.get_signatures_paginated()
        if not sigs:
            print(colored("No transactions found for this Raydium pool. Exiting.", "red"))
            return

        for s in tqdm(sigs, desc="Parsing transactions"):
            print(colored(f"Analyzing transaction: {s['signature']}", "blue"))
            time.sleep(0.05)

        print(colored("[INFO] Final data saved to pool_flows.json.", "green"))

def main():
    tracker = RaydiumPoolTracker()
    tracker.generate_report()

if __name__ == "__main__":
    main()
