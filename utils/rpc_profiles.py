"""
多鏈 RPC 設定載入器 — 可複製到各專案使用（搭配 utils/console.py 風格）。

預設讀取與本檔同目錄的 `rpc.toml`（即 `utils/rpc.toml`；複製整個 `utils/` 即可帶走）。
若要改用其他檔案，請對 `load_chain_profiles` / `get_chain_profile` / `pick_first_healthy_rpc`
傳入 `path="/絕對路徑/自訂.toml"`。

欄位說明（每條 [chains.<key>]）：
- name          人類可讀鏈名稱
- chain_id      預期鏈 ID（測試時會與節點回傳比對）
- urls          RPC URL 清單（依序嘗試）
- default       可選，會插入 urls 最前面（若尚未出現在 urls）
- native_symbol 可選，原生 gas 代幣符號（顯示用，預設 ETH）
- explorer_tx_url 可選，交易瀏覽器 URL 模板，使用 {tx_hash} 占位
- poa           可選，是否為 POA 鏈（web3 需注入 ExtraDataToPOAMiddleware）

為何用 TOML：註解友善、多段落清楚、無括號地獄；若團隊偏好 YAML/JSON 也可只換載入層。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

# 與本模組同目錄的 rpc.toml（複製 utils 時請一併複製）
DEFAULT_RPC_TOML_PATH = str((Path(__file__).resolve().parent / "rpc.toml"))


@dataclass(frozen=True)
class ChainProfile:
    """單一鏈設定（由 TOML [chains.<key>] 解析）。"""

    key: str
    name: str
    chain_id: int
    urls: Tuple[str, ...]
    native_symbol: str = "ETH"
    explorer_tx_url: Optional[str] = None
    poa: bool = False


def load_chain_profiles(path: str = DEFAULT_RPC_TOML_PATH) -> Dict[str, ChainProfile]:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    chains = raw.get("chains", {})
    profiles: Dict[str, ChainProfile] = {}
    for key, val in chains.items():
        name = str(val.get("name", key)).strip()
        chain_id = int(val["chain_id"])
        default = str(val.get("default", "")).strip()
        urls_list: List[str] = [str(u).strip() for u in val.get("urls", []) if str(u).strip()]
        if default:
            if default not in urls_list:
                urls_list.insert(0, default)
        native_symbol = str(val.get("native_symbol", "ETH")).strip() or "ETH"
        explorer_raw = val.get("explorer_tx_url")
        explorer_tx_url = str(explorer_raw).strip() if explorer_raw else None
        poa = bool(val.get("poa", False))
        profiles[key] = ChainProfile(
            key=key,
            name=name,
            chain_id=chain_id,
            urls=tuple(urls_list),
            native_symbol=native_symbol,
            explorer_tx_url=explorer_tx_url or None,
            poa=poa,
        )
    return profiles


def get_chain_profile(chain_key: str, path: str = DEFAULT_RPC_TOML_PATH) -> ChainProfile:
    profiles = load_chain_profiles(path)
    if chain_key not in profiles:
        raise ValueError(f"設定檔找不到鏈 key: {chain_key}（檔案: {path}）")
    return profiles[chain_key]


def make_web3(rpc_url: str, profile: ChainProfile, *, timeout_seconds: float = 5.0) -> Web3:
    """依 profile 建立 Web3（POA 鏈會自動注入 middleware）。"""
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": timeout_seconds}))
    if profile.poa:
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def pick_first_healthy_rpc(
    chain_key: str,
    path: str = DEFAULT_RPC_TOML_PATH,
    *,
    timeout_seconds: float = 5.0,
) -> str:
    """依序嘗試該鏈 urls，回傳第一個可連線且 chain_id 相符的 RPC。"""
    profile = get_chain_profile(chain_key, path)
    if not profile.urls:
        raise ValueError(f"{chain_key} 沒有設定任何 RPC url")

    last_error: Optional[Exception] = None
    for url in profile.urls:
        try:
            w3 = make_web3(url, profile, timeout_seconds=timeout_seconds)
            start = time.time()
            if not w3.is_connected():
                raise RuntimeError("is_connected=False")
            node_chain_id = int(w3.eth.chain_id)
            if node_chain_id != profile.chain_id:
                raise RuntimeError(
                    f"chain_id 不符：節點={node_chain_id} 設定={profile.chain_id}"
                )
            _ = w3.eth.block_number
            _ = int((time.time() - start) * 1000)
            return url
        except Exception as e:  # noqa: BLE001
            last_error = e
            continue

    raise RuntimeError(f"鏈 {chain_key} 所有 RPC 皆失敗，最後錯誤: {last_error}")


def format_explorer_tx(profile: ChainProfile, tx_hash: str) -> Optional[str]:
    """將交易哈希代入 explorer_tx_url；未設定則回傳 None。"""
    if not profile.explorer_tx_url:
        return None
    h = tx_hash.strip()
    if h.startswith("0x"):
        h_no0x = h[2:]
    else:
        h_no0x = h
        h = "0x" + h if h else h
    return (
        profile.explorer_tx_url.replace("{tx_hash}", h).replace("{tx_hash_no0x}", h_no0x)
    )
