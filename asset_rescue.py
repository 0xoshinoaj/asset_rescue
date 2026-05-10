import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import os

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib
from eth_account import Account
from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import ContractLogicError

from strategies import (
    execute_eip3009,
    execute_native,
    execute_permit,
    supports_eip3009,
    supports_permit,
)
from utils.rpc_profiles import ChainProfile, get_chain_profile, make_web3, pick_first_healthy_rpc
from utils.console import print_error, print_success, print_warn


@dataclass
class AppConfig:
    rpc_profile: ChainProfile
    rpc_url: str
    chain_id: int
    transfer_kind: str
    token_address: str
    safe_wallet_b_address: str
    transfer_amount_raw: str
    valid_window_seconds: int
    gas_limit: int


def load_config(path: str = "config.toml") -> AppConfig:
    load_dotenv()
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    network = raw["network"]
    transfer = raw["transfer"]
    tx = raw["tx"]
    chain_key = str(network["chain"]).strip()
    profile = get_chain_profile(chain_key)
    rpc_url = pick_first_healthy_rpc(chain_key)

    token_address = str(network.get("token_address", "")).strip()
    if not token_address:
        raise ValueError("config.toml [network] 缺少 token_address")

    return AppConfig(
        rpc_profile=profile,
        rpc_url=rpc_url,
        chain_id=profile.chain_id,
        transfer_kind=transfer.get("kind", "token").lower(),
        token_address=token_address,
        safe_wallet_b_address=os.getenv(
            "SAFE_WALLET_B_ADDRESS", transfer.get("safe_wallet_b_address", "")
        ),
        transfer_amount_raw=str(transfer["amount"]).strip(),
        valid_window_seconds=int(transfer["valid_window_seconds"]),
        gas_limit=int(tx["gas_limit"]),
    )


def _validate_config(cfg: AppConfig) -> None:
    if not cfg.safe_wallet_b_address.startswith("0x") or len(cfg.safe_wallet_b_address) != 42:
        raise ValueError("safe_wallet_b_address 地址格式不正確")
    if cfg.transfer_kind not in {"token", "native"}:
        raise ValueError("transfer.kind 只支援 token 或 native")
    if cfg.transfer_kind == "token":
        if not cfg.token_address.startswith("0x") or len(cfg.token_address) != 42:
            raise ValueError("token_address 地址格式不正確")


def _load_private_keys() -> tuple[str, str]:
    compromised_key = os.getenv("COMPROMISED_PRIVATE_KEY", "")
    safe_wallet_a_key = os.getenv("SAFE_WALLET_A_PRIVATE_KEY", "")

    if not compromised_key or "YOUR_" in compromised_key:
        raise ValueError("COMPROMISED_PRIVATE_KEY 尚未設置於 .env")
    if not safe_wallet_a_key or "YOUR_" in safe_wallet_a_key:
        raise ValueError("SAFE_WALLET_A_PRIVATE_KEY 尚未設置於 .env")

    return compromised_key, safe_wallet_a_key


def _parse_amount_to_base_units(amount_raw: str, decimals: int) -> int:
    if amount_raw.lower() == "all":
        return -1
    try:
        value = Decimal(amount_raw)
    except InvalidOperation as e:
        raise ValueError(f"amount 格式錯誤: {amount_raw}") from e
    if value <= 0:
        raise ValueError("amount 必須大於 0，或使用 all")
    quantized = value * (Decimal(10) ** decimals)
    if quantized != quantized.to_integral_value():
        raise ValueError(f"amount 精度超過 token decimals={decimals}")
    return int(quantized)


def fast_escape(cfg: AppConfig) -> dict:
    _validate_config(cfg)
    compromised_key, safe_wallet_a_key = _load_private_keys()

    print_warn("\n" + "█" * 60)
    print_warn("█  ⚡ 快速逃脫腳本 - 被盜錢包資金遷移系統")
    print_warn("█" * 60 + "\n")

    print_success("⚡ 快速逃脫程序啟動\n")
    print_warn("=" * 60)
    print("時刻表：")
    print("T+0ms    - 開始簽名")
    print("T+500ms  - 簽名完成")
    print("T+501ms  - 開始提交")
    print("T+2s     - 提交完成")
    print(f"T+{cfg.valid_window_seconds}s   - validBefore 過期")
    print_warn("=" * 60 + "\n")

    w3 = make_web3(cfg.rpc_url, cfg.rpc_profile)
    if not w3.is_connected():
        raise RuntimeError("RPC 連線失敗，請檢查 rpc_url")

    compromised = Account.from_key(compromised_key)
    safe_a = Account.from_key(safe_wallet_a_key)

    print_warn("📍 步驟 1：初始化錢包\n")
    print_warn(f"❌ 被盜錢包（簽名）: {compromised.address}")
    print_success(f"✅ 安全錢包 A（提交）: {safe_a.address}")
    print_success(f"✅ 安全錢包 B（接收）: {cfg.safe_wallet_b_address}\n")

    if cfg.transfer_kind == "native":
        return execute_native(cfg, w3, compromised, compromised_key, _parse_amount_to_base_units)

    token_addr = Web3.to_checksum_address(cfg.token_address)
    if supports_eip3009(w3, token_addr, compromised.address):
        return execute_eip3009(
            cfg,
            w3,
            compromised,
            safe_a,
            compromised_key,
            safe_wallet_a_key,
            _parse_amount_to_base_units,
        )
    if supports_permit(w3, token_addr, compromised.address):
        print_warn("ℹ️ token 不支援 EIP-3009，改用 permit 策略")
        return execute_permit(
            cfg,
            w3,
            compromised,
            safe_a,
            compromised_key,
            safe_wallet_a_key,
            _parse_amount_to_base_units,
        )
    raise RuntimeError(
        "此 token 不支援 EIP-3009 也不支援 permit，請改用一般 transfer 或該 token 自訂授權方式"
    )


def main() -> int:
    try:
        cfg = load_config("config.toml")
        result = fast_escape(cfg)
        print_success(f"完成: {result['tx_hash']}")
        return 0
    except ContractLogicError as e:
        print_error("❌ 合約執行失敗", to_stderr=True)
        print_error(f"錯誤信息: {e}", to_stderr=True)
        return 1
    except Exception as e:  # noqa: BLE001
        print_error("❌ 執行失敗", to_stderr=True)
        print_error(f"錯誤信息: {e}", to_stderr=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
