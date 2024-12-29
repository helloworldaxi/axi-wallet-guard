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
import base58

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
            "transaction_count": 0,
            "suspicious_transfers": []  # Track potentially suspicious transfers
        })
        self.transaction_details = []
        self.output_file = 'pool_flows.json'

    def save_progress(self):
        """Save current progress to JSON file"""
        output = {
            "wallet_flows": dict(self.wallet_flows),  # Convert defaultdict to regular dict
            "transaction_details": self.transaction_details,
            "last_updated": datetime.now().isoformat()
        }
        with open(self.output_file, 'w') as f:
            json.dump(output, f, indent=2)
        print(colored("[INFO] Progress saved to pool_flows.json", "green"))

    def get_signatures_paginated(self, limit_per_page=1000):
        """Fetch all transaction signatures for the pool"""
        print(colored("Fetching signatures for the Raydium pool...", "cyan"))
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
                resp = requests.post(self.rpc_url, json=payload, headers=self.headers)
                data = resp.json()

                if "result" not in data or not data["result"]:
                    break

                page_sigs = data["result"]
                all_signatures.extend(page_sigs)
                before_sig = page_sigs[-1]["signature"]
                print(colored(f"  Fetched {len(page_sigs)} signatures", "green"))

            except Exception as e:
                print(colored(f"Error fetching signatures: {e}", "red"))
                traceback.print_exc()
                break

        return all_signatures

    def get_transaction_details(self, signature):
        """Fetch detailed transaction information"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [
                signature,
                {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
            ]
        }

        try:
            resp = requests.post(self.rpc_url, json=payload, headers=self.headers)
            data = resp.json()
            return data.get("result")
        except Exception as e:
            print(colored(f"Error fetching transaction details: {e}", "red"))
            return None

    def analyze_transaction(self, tx_data, signature):
        """Analyze transaction data for token transfers and sales"""
        if not tx_data or "transaction" not in tx_data:
            return

        timestamp = datetime.fromtimestamp(tx_data["blockTime"]).isoformat()
        
        # Track token transfers
        transfer_info = {
            "signature": signature,
            "timestamp": timestamp,
            "transfers": []
        }

        for instruction in tx_data["transaction"]["message"]["instructions"]:
            if "parsed" in instruction:
                parsed = instruction["parsed"]
                
                if parsed["type"] == "transfer" or parsed["type"] == "transferChecked":
                    source = parsed["info"]["source"]
                    destination = parsed["info"]["destination"]
                    amount = float(parsed["info"].get("amount", 0))
                    
                    # Update wallet flows
                    if source in self.flagged_addresses:
                        self.wallet_flows[source]["outgoing"][destination] += amount
                        self.wallet_flows[source]["total_sent"] += amount
                        self.wallet_flows[destination]["incoming"][source] += amount
                        self.wallet_flows[destination]["total_received"] += amount
                        
                        # Mark as suspicious if from flagged to new wallet
                        transfer_info["transfers"].append({
                            "type": "suspicious_transfer",
                            "from": source,
                            "to": destination,
                            "amount": amount
                        })

                    # Update first/last seen timestamps
                    for wallet in [source, destination]:
                        if not self.wallet_flows[wallet]["first_seen"]:
                            self.wallet_flows[wallet]["first_seen"] = timestamp
                        self.wallet_flows[wallet]["last_seen"] = timestamp
                        self.wallet_flows[wallet]["transaction_count"] += 1

        if transfer_info["transfers"]:
            self.transaction_details.append(transfer_info)

    def generate_report(self):
        """Generate comprehensive transaction report"""
        sigs = self.get_signatures_paginated()
        if not sigs:
            print(colored("No transactions found for this Raydium pool. Exiting.", "red"))
            return

        print(colored(f"\nAnalyzing {len(sigs)} transactions...", "cyan"))
        
        for sig_info in tqdm(sigs, desc="Processing transactions"):
            signature = sig_info["signature"]
            tx_data = self.get_transaction_details(signature)
            
            if tx_data:
                self.analyze_transaction(tx_data, signature)
            
            # Save progress periodically
            if len(self.transaction_details) % 100 == 0:
                self.save_progress()
                
            time.sleep(0.1)  # Rate limiting
        
        # Final save
        self.save_progress()
        
        # Print summary
        print(colored("\nAnalysis Summary:", "green"))
        print(f"Total transactions processed: {len(sigs)}")
        print(f"Suspicious transfers detected: {len(self.transaction_details)}")
        print(f"Unique wallets tracked: {len(self.wallet_flows)}")
        
        # Identify most active wallets
        active_wallets = sorted(
            self.wallet_flows.items(),
            key=lambda x: x[1]["transaction_count"],
            reverse=True
        )[:5]
        
        print("\nMost active wallets:")
        for wallet, data in active_wallets:
            print(f"{wallet}: {data['transaction_count']} transactions")

def main():
    tracker = RaydiumPoolTracker()
    tracker.generate_report()

if __name__ == "__main__":
    main()