import secrets
import time
from datetime import datetime, timezone

from eth_account import Account
from eth_account.messages import encode_typed_data
from web3 import Web3

from utils.console import print_success, print_warn

ERC20_METADATA_ABI = [
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

TRANSFER_WITH_AUTH_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "from", "type": "address"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "value", "type": "uint256"},
            {"internalType": "uint256", "name": "validAfter", "type": "uint256"},
            {"internalType": "uint256", "name": "validBefore", "type": "uint256"},
            {"internalType": "bytes32", "name": "nonce", "type": "bytes32"},
            {"internalType": "bytes", "name": "signature", "type": "bytes"},
        ],
        "name": "transferWithAuthorization",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

EIP3009_PROBE_ABI = [
    {
        "inputs": [],
        "name": "DOMAIN_SEPARATOR",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "authorizer", "type": "address"},
            {"internalType": "bytes32", "name": "nonce", "type": "bytes32"},
        ],
        "name": "authorizationState",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def supports_eip3009(w3: Web3, token_addr: str, owner_addr: str) -> bool:
    probe = w3.eth.contract(address=Web3.to_checksum_address(token_addr), abi=EIP3009_PROBE_ABI)
    try:
        _ = probe.functions.DOMAIN_SEPARATOR().call()
        _ = probe.functions.authorizationState(
            Web3.to_checksum_address(owner_addr), b"\x00" * 32
        ).call()
        return True
    except Exception:  # noqa: BLE001
        return False


def execute_eip3009(
    cfg,
    w3: Web3,
    compromised,
    safe_a,
    compromised_key: str,
    safe_wallet_a_key: str,
    parse_amount_to_base_units,
) -> dict:
    token_addr = Web3.to_checksum_address(cfg.token_address)
    token_meta = w3.eth.contract(address=token_addr, abi=ERC20_METADATA_ABI)
    transfer_contract = w3.eth.contract(address=token_addr, abi=TRANSFER_WITH_AUTH_ABI)

    decimals = int(token_meta.functions.decimals().call())
    try:
        symbol = token_meta.functions.symbol().call()
    except Exception:  # noqa: BLE001
        symbol = "TOKEN"

    transfer_amount = parse_amount_to_base_units(cfg.transfer_amount_raw, decimals)
    if transfer_amount == -1:
        transfer_amount = int(token_meta.functions.balanceOf(compromised.address).call())
        if transfer_amount <= 0:
            raise RuntimeError("被盜錢包 token 餘額為 0，無法 all 轉移")

    now = int(time.time())
    valid_after = now
    valid_before = now + cfg.valid_window_seconds
    nonce_bytes = secrets.token_bytes(32)
    nonce_hex = "0x" + nonce_bytes.hex()

    print_warn("📍 策略：EIP-3009 transferWithAuthorization\n")
    print(f"🪙 代幣: {symbol} ({token_addr})")
    print(f"🔢 decimals: {decimals}")
    print(f"💰 轉移數量(最小單位): {transfer_amount}")

    typed_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "primaryType": "TransferWithAuthorization",
        "domain": {
            "name": "USD Coin",
            "version": "2",
            "chainId": cfg.chain_id,
            "verifyingContract": token_addr,
        },
        "message": {
            "from": Web3.to_checksum_address(compromised.address),
            "to": Web3.to_checksum_address(cfg.safe_wallet_b_address),
            "value": transfer_amount,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce_hex,
        },
    }

    signable = encode_typed_data(full_message=typed_data)
    signed = Account.sign_message(signable, private_key=compromised_key)

    tx_start = time.time()
    nonce = w3.eth.get_transaction_count(safe_a.address)
    gas_price = w3.eth.gas_price
    tx = transfer_contract.functions.transferWithAuthorization(
        typed_data["message"]["from"],
        typed_data["message"]["to"],
        typed_data["message"]["value"],
        typed_data["message"]["validAfter"],
        typed_data["message"]["validBefore"],
        nonce_bytes,
        signed.signature,
    ).build_transaction(
        {
            "from": safe_a.address,
            "chainId": cfg.chain_id,
            "nonce": nonce,
            "gas": cfg.gas_limit,
            "gasPrice": gas_price,
        }
    )

    signed_tx = Account.sign_transaction(tx, safe_wallet_a_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    tx_hash_hex = tx_hash.hex()
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    submission_ms = int((time.time() - tx_start) * 1000)

    print_success(f"✅ EIP-3009 交易成功（耗時 {submission_ms}ms）")
    print(f"📍 交易哈希: {tx_hash_hex}\n")

    return {
        "success": True,
        "strategy": "eip3009",
        "tx_hash": tx_hash_hex,
        "block_number": receipt.blockNumber,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }

