import time
from datetime import datetime, timezone

from eth_account import Account
from eth_account.messages import encode_typed_data
from web3 import Web3

from utils.console import print_success, print_warn

PERMIT_ABI = [
    {
        "inputs": [],
        "name": "name",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "version",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "owner", "type": "address"}],
        "name": "nonces",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "address", "name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
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
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "value", "type": "uint256"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"},
            {"internalType": "uint8", "name": "v", "type": "uint8"},
            {"internalType": "bytes32", "name": "r", "type": "bytes32"},
            {"internalType": "bytes32", "name": "s", "type": "bytes32"},
        ],
        "name": "permit",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "from", "type": "address"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "value", "type": "uint256"},
        ],
        "name": "transferFrom",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


def supports_permit(w3: Web3, token_addr: str, owner_addr: str) -> bool:
    contract = w3.eth.contract(address=Web3.to_checksum_address(token_addr), abi=PERMIT_ABI)
    try:
        _ = contract.functions.nonces(Web3.to_checksum_address(owner_addr)).call()
        return True
    except Exception:  # noqa: BLE001
        return False


def execute_permit(
    cfg,
    w3: Web3,
    compromised,
    safe_a,
    compromised_key: str,
    safe_wallet_a_key: str,
    parse_amount_to_base_units,
) -> dict:
    token_addr = Web3.to_checksum_address(cfg.token_address)
    token = w3.eth.contract(address=token_addr, abi=PERMIT_ABI)

    decimals = int(token.functions.decimals().call())
    try:
        symbol = token.functions.symbol().call()
    except Exception:  # noqa: BLE001
        symbol = "TOKEN"

    transfer_amount = parse_amount_to_base_units(cfg.transfer_amount_raw, decimals)
    if transfer_amount == -1:
        transfer_amount = int(token.functions.balanceOf(compromised.address).call())
        if transfer_amount <= 0:
            raise RuntimeError("被盜錢包 token 餘額為 0，無法 all 轉移")

    owner = Web3.to_checksum_address(compromised.address)
    spender = Web3.to_checksum_address(safe_a.address)
    receiver = Web3.to_checksum_address(cfg.safe_wallet_b_address)
    nonce = int(token.functions.nonces(owner).call())
    deadline = int(time.time()) + cfg.valid_window_seconds

    name = token.functions.name().call()
    try:
        version = token.functions.version().call()
    except Exception:  # noqa: BLE001
        version = "1"

    print_warn("📍 策略：EIP-2612 permit + transferFrom\n")
    print(f"🪙 代幣: {symbol} ({token_addr})")
    print(f"🔢 decimals: {decimals}")
    print(f"💰 轉移數量(最小單位): {transfer_amount}")
    print(f"🧾 nonce: {nonce}")
    print(f"⏰ deadline: {deadline}\n")

    typed_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Permit": [
                {"name": "owner", "type": "address"},
                {"name": "spender", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "nonce", "type": "uint256"},
                {"name": "deadline", "type": "uint256"},
            ],
        },
        "primaryType": "Permit",
        "domain": {
            "name": name,
            "version": version,
            "chainId": cfg.chain_id,
            "verifyingContract": token_addr,
        },
        "message": {
            "owner": owner,
            "spender": spender,
            "value": transfer_amount,
            "nonce": nonce,
            "deadline": deadline,
        },
    }

    signable = encode_typed_data(full_message=typed_data)
    signed = Account.sign_message(signable, private_key=compromised_key)
    v, r, s = signed.v, signed.r, signed.s

    gas_price = w3.eth.gas_price
    tx_nonce = w3.eth.get_transaction_count(safe_a.address)
    permit_tx = token.functions.permit(owner, spender, transfer_amount, deadline, v, r, s).build_transaction(
        {
            "from": safe_a.address,
            "chainId": cfg.chain_id,
            "nonce": tx_nonce,
            "gas": cfg.gas_limit,
            "gasPrice": gas_price,
        }
    )
    signed_permit_tx = Account.sign_transaction(permit_tx, safe_wallet_a_key)
    permit_hash = w3.eth.send_raw_transaction(signed_permit_tx.raw_transaction)
    permit_receipt = w3.eth.wait_for_transaction_receipt(permit_hash, timeout=180)
    if permit_receipt.status != 1:
        raise RuntimeError("permit 交易失敗")

    transfer_tx = token.functions.transferFrom(owner, receiver, transfer_amount).build_transaction(
        {
            "from": safe_a.address,
            "chainId": cfg.chain_id,
            "nonce": tx_nonce + 1,
            "gas": cfg.gas_limit,
            "gasPrice": gas_price,
        }
    )
    signed_transfer_tx = Account.sign_transaction(transfer_tx, safe_wallet_a_key)
    transfer_hash = w3.eth.send_raw_transaction(signed_transfer_tx.raw_transaction)
    transfer_receipt = w3.eth.wait_for_transaction_receipt(transfer_hash, timeout=180)
    if transfer_receipt.status != 1:
        raise RuntimeError("transferFrom 交易失敗")

    permit_hash_hex = permit_hash.hex()
    transfer_hash_hex = transfer_hash.hex()
    print_success("✅ permit + transferFrom 完成")
    print(f"📍 permit tx: {permit_hash_hex}")
    print(f"📍 transfer tx: {transfer_hash_hex}\n")

    return {
        "success": True,
        "strategy": "permit",
        "tx_hash": transfer_hash_hex,
        "permit_tx_hash": permit_hash_hex,
        "block_number": transfer_receipt.blockNumber,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }

