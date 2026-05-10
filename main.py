import sys

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib
from web3.exceptions import ContractLogicError

from asset_rescue import fast_escape, load_config
from utils.console import print_error, print_success, print_warn
from utils.rpc_profiles import load_chain_profiles


def _read_raw_config(path: str = "config.toml") -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _write_config(raw: dict, path: str = "config.toml") -> None:
    network = raw["network"]
    transfer = raw["transfer"]
    tx = raw["tx"]
    content = (
        "[network]\n"
        "# 鏈設定鍵值，對應 utils/rpc.toml 的 [chains.<key>]\n"
        f'chain = "{network["chain"]}"\n'
        "# token 模式：ERC-20 合約地址\n"
        f'token_address = "{network["token_address"]}"\n'
        "\n"
        "[transfer]\n"
        "# kind: token 或 native\n"
        f'kind = "{transfer["kind"]}"\n'
        '# 可填十進位字串（例如 "1.25"），或 "all" 全轉\n'
        f'amount = "{transfer["amount"]}"\n'
        "\n"
        "# 授權有效秒數（建議短，但要能被鏈上打包）\n"
        f'valid_window_seconds = {int(transfer["valid_window_seconds"])}\n'
        "\n"
        "# 安全錢包 B（最終接收地址）\n"
        "# 可由 .env 的 SAFE_WALLET_B_ADDRESS 覆蓋\n"
        f'safe_wallet_b_address = "{transfer["safe_wallet_b_address"]}"\n'
        "\n"
        "[tx]\n"
        "# gas_limit 是「最多可消耗」而非固定花費\n"
        f'gas_limit = {int(tx["gas_limit"])}\n'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _show_config(raw: dict) -> None:
    print_warn("\n目前設定：")
    print(f'- network.chain = "{raw["network"]["chain"]}"')
    print(f'- network.token_address = "{raw["network"]["token_address"]}"')
    print(f'- transfer.kind = "{raw["transfer"]["kind"]}"')
    print(f'- transfer.amount = "{raw["transfer"]["amount"]}"')
    print(f'- transfer.valid_window_seconds = {raw["transfer"]["valid_window_seconds"]}')
    print(f'- transfer.safe_wallet_b_address = "{raw["transfer"]["safe_wallet_b_address"]}"')
    print(f'- tx.gas_limit = {raw["tx"]["gas_limit"]}\n')


def _modify_config(raw: dict, path: str = "config.toml") -> None:
    chains = load_chain_profiles()
    while True:
        _show_config(raw)
        print("修改項目：")
        print("1) chain")
        print("2) token_address")
        print("3) kind (token/native)")
        print("4) amount")
        print("5) valid_window_seconds")
        print("6) safe_wallet_b_address")
        print("7) gas_limit")
        print("8) 儲存並返回")
        print("9) 放棄修改並返回")
        choice = input("> ").strip()

        if choice == "1":
            print("可用 chain：")
            for key, profile in chains.items():
                print(f"- {key} ({profile.name})")
            v = input("新的 chain key: ").strip()
            if v in chains:
                raw["network"]["chain"] = v
                print_success("已更新 chain")
            else:
                print_error("無效 chain key")
        elif choice == "2":
            v = input("新的 token_address: ").strip()
            raw["network"]["token_address"] = v
            print_success("已更新 token_address")
        elif choice == "3":
            v = input('新的 kind (token/native): ').strip().lower()
            if v in {"token", "native"}:
                raw["transfer"]["kind"] = v
                print_success("已更新 kind")
            else:
                print_error("kind 只支援 token/native")
        elif choice == "4":
            v = input('新的 amount (例如 "1.25" 或 all): ').strip()
            raw["transfer"]["amount"] = v
            print_success("已更新 amount")
        elif choice == "5":
            v = input("新的 valid_window_seconds: ").strip()
            try:
                raw["transfer"]["valid_window_seconds"] = int(v)
                print_success("已更新 valid_window_seconds")
            except ValueError:
                print_error("請輸入整數")
        elif choice == "6":
            v = input("新的 safe_wallet_b_address: ").strip()
            raw["transfer"]["safe_wallet_b_address"] = v
            print_success("已更新 safe_wallet_b_address")
        elif choice == "7":
            v = input("新的 gas_limit: ").strip()
            try:
                raw["tx"]["gas_limit"] = int(v)
                print_success("已更新 gas_limit")
            except ValueError:
                print_error("請輸入整數")
        elif choice == "8":
            _write_config(raw, path)
            print_success("已儲存 config.toml")
            return
        elif choice == "9":
            print_warn("已放棄本次修改")
            return
        else:
            print_error("無效選項")


def _run_escape() -> int:
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


def main() -> int:
    while True:
        print_warn("\n=== 互動式入口 ===")
        print("1) 顯示目前設定")
        print("2) 修改設定")
        print("3) 直接啟動")
        print("4) 離開")
        choice = input("> ").strip()

        if choice == "1":
            raw = _read_raw_config("config.toml")
            _show_config(raw)
        elif choice == "2":
            raw = _read_raw_config("config.toml")
            _modify_config(raw, "config.toml")
        elif choice == "3":
            return _run_escape()
        elif choice == "4":
            print_warn("已離開")
            return 0
        else:
            print_error("無效選項")


if __name__ == "__main__":
    sys.exit(main())
