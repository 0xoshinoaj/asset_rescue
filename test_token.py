try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib
from web3 import Web3

from utils.rpc_profiles import get_chain_profile, make_web3, pick_first_healthy_rpc
from strategies import supports_eip3009, supports_permit
from utils.console import print_error, print_success, print_warn


ERC20_MIN_ABI = [
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
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
]


def main() -> int:
    with open("config.toml", "rb") as f:
        cfg = tomllib.load(f)
    network = cfg["network"]
    chain_key = str(network["chain"]).strip()
    profile = get_chain_profile(chain_key)
    token_address = str(network.get("token_address", "")).strip()
    chain_id = profile.chain_id

    if not token_address:
        print_error("❌ config.toml 缺少 token_address")
        return 1

    rpc_url = pick_first_healthy_rpc(chain_key)
    w3 = make_web3(rpc_url, profile, timeout_seconds=6.0)
    node_chain_id = w3.eth.chain_id
    if node_chain_id != chain_id:
        print_warn(f"⚠️ config chain_id={chain_id}，但 RPC chain_id={node_chain_id}")

    token_addr = Web3.to_checksum_address(token_address)
    owner_probe_addr = "0x0000000000000000000000000000000000000001"
    token = w3.eth.contract(address=token_addr, abi=ERC20_MIN_ABI)

    try:
        symbol = token.functions.symbol().call()
    except Exception:  # noqa: BLE001
        symbol = "UNKNOWN"
    try:
        decimals = int(token.functions.decimals().call())
    except Exception:  # noqa: BLE001
        decimals = -1

    eip3009 = supports_eip3009(w3, token_addr, owner_probe_addr)
    permit = supports_permit(w3, token_addr, owner_probe_addr)

    print_warn("🔎 Token 能力檢測")
    print(f"token: {token_addr}")
    print(f"chain: {chain_key} ({profile.name}) native={profile.native_symbol}")
    print(f"symbol: {symbol}")
    print(f"decimals: {decimals}")
    print(f"rpc: {rpc_url}")
    print(f"EIP-3009: {'yes' if eip3009 else 'no'}")
    print(f"permit: {'yes' if permit else 'no'}")

    if eip3009:
        strategy = "eip3009"
        advice = "可用 transferWithAuthorization（優先）"
    elif permit:
        strategy = "permit"
        advice = "可用 permit + transferFrom"
    else:
        strategy = "transfer"
        advice = "僅建議一般 transfer/approve+transferFrom（高風險）"

    if strategy == "eip3009":
        print_success(f"\n建議策略: {strategy}")
    elif strategy == "permit":
        print_warn(f"\n建議策略: {strategy}")
    else:
        print_error(f"\n建議策略: {strategy}")
    print(f"說明: {advice}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
