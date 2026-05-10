from datetime import datetime, timezone
import time

from eth_account import Account
from web3 import Web3

from utils.console import print_success, print_warn


def execute_native(cfg, w3: Web3, compromised, compromised_key: str, parse_amount_to_base_units) -> dict:
    print_warn("📍 原生幣模式：將由被盜錢包直接支付 Gas 與發送\n")
    balance = int(w3.eth.get_balance(compromised.address))
    gas_price = int(w3.eth.gas_price)
    gas_cost = int(cfg.gas_limit * gas_price)

    amount_base = parse_amount_to_base_units(cfg.transfer_amount_raw, 18)
    if amount_base == -1:
        transfer_amount = balance - gas_cost
    else:
        transfer_amount = amount_base

    if transfer_amount <= 0:
        raise RuntimeError("原生幣餘額不足以支付 gas 或轉移金額")
    if transfer_amount + gas_cost > balance:
        raise RuntimeError("原生幣餘額不足，請調低 amount 或改用 all")

    nonce = w3.eth.get_transaction_count(compromised.address)
    tx = {
        "from": compromised.address,
        "to": Web3.to_checksum_address(cfg.safe_wallet_b_address),
        "value": transfer_amount,
        "nonce": nonce,
        "chainId": cfg.chain_id,
        "gas": cfg.gas_limit,
        "gasPrice": gas_price,
    }

    tx_start = time.time()
    signed_tx = Account.sign_transaction(tx, compromised_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    submission_ms = int((time.time() - tx_start) * 1000)
    tx_hash_hex = tx_hash.hex()

    print_success(f"✅ 原生幣交易已提交（耗時 {submission_ms}ms）")
    print(f"📍 交易哈希: {tx_hash_hex}\n")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    print_success(f"✅ 交易確認，Gas 使用: {receipt.gasUsed}")
    print(f"🔗 鏈上查詢: {tx_hash_hex}\n")

    return {
        "success": True,
        "strategy": "native",
        "tx_hash": tx_hash_hex,
        "block_number": receipt.blockNumber,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }

