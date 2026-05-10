"""
測試 utils/rpc.toml 內各鏈 RPC 連線與 chain_id。

請放在專案根目錄執行：`python test_rpc.py`
（需與 `utils/rpc_profiles.py`、`utils/rpc.toml` 並存；路徑由 rpc_profiles 依 __file__ 解析，不必改這支檔里的 rpc.toml 路徑。）
"""

import time

from utils.console import print_error, print_success, print_warn
from utils.rpc_profiles import DEFAULT_RPC_TOML_PATH, load_chain_profiles, make_web3


def main() -> int:
    profiles = load_chain_profiles()
    if not profiles:
        print_error(f"❌ {DEFAULT_RPC_TOML_PATH} 沒有任何鏈設定")
        return 1

    print_warn(f"🔎 測試 RPC 設定檔：{DEFAULT_RPC_TOML_PATH}\n")
    total_ok = 0
    total_count = 0
    for chain_key, profile in profiles.items():
        extra = f" gas={profile.native_symbol}"
        if profile.poa:
            extra += " POA"
        if profile.explorer_tx_url:
            extra += " explorer=✓"
        print_warn(
            f"=== {chain_key} ({profile.name}) "
            f"chain_id={profile.chain_id}{extra} ==="
        )
        candidates = list(profile.urls)
        if not candidates:
            print_error("❌ 無 RPC 清單\n")
            continue
        ok = 0
        for idx, url in enumerate(candidates, start=1):
            total_count += 1
            start = time.time()
            try:
                w3 = make_web3(url, profile, timeout_seconds=6.0)
                if not w3.is_connected():
                    raise RuntimeError("is_connected=False")
                node_chain_id = int(w3.eth.chain_id)
                block = w3.eth.block_number
                latency_ms = int((time.time() - start) * 1000)
                if node_chain_id != profile.chain_id:
                    raise RuntimeError(
                        f"chain_id 不符：節點={node_chain_id} 設定={profile.chain_id}"
                    )
                print_success(f"[{idx}] ✅ {url}")
                print(
                    f"    chain_id={node_chain_id} block={block} latency={latency_ms}ms"
                )
                ok += 1
                total_ok += 1
            except Exception as e:  # noqa: BLE001
                latency_ms = int((time.time() - start) * 1000)
                print_error(f"[{idx}] ❌ {url}")
                print(f"    error={e} latency={latency_ms}ms")
        if ok == len(candidates):
            print_success(f"小計：{ok}/{len(candidates)} 可用\n")
        elif ok > 0:
            print_warn(f"小計：{ok}/{len(candidates)} 可用\n")
        else:
            print_error(f"小計：{ok}/{len(candidates)} 可用\n")

    if total_ok == total_count:
        print_success(f"總計：{total_ok}/{total_count} 可用")
    elif total_ok > 0:
        print_warn(f"總計：{total_ok}/{total_count} 可用")
    else:
        print_error(f"總計：{total_ok}/{total_count} 可用")
    return 0 if total_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
