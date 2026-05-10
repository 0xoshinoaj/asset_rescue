# Changelog

## [0.2.2] - 2026-05-10

### Changed

- 核心檔名由 `fast_escape.py` 重新命名為 `asset_rescue.py`，`main.py` 匯入路徑與 README 執行指令同步更新。

## [0.2.1] - 2026-05-10

### Added

- 新增 `main.py` 互動式入口：可檢視 `config.toml`、互動修改後儲存、或直接啟動主流程。

### Changed

- `README.md` 新增互動式啟動方式（`python main.py`）與非互動模式說明（`python asset_rescue.py`）。

## [0.2.0] - 2026-05-10

### Added

- `utils/rpc_profiles.py`：多鏈 RPC 載入（`ChainProfile`）、`make_web3`（自動注入 POA middleware）、`pick_first_healthy_rpc`（依序 fallback 並校驗 `chain_id`）、`format_explorer_tx`、`DEFAULT_RPC_TOML_PATH`（預設為與模組同目錄的 `rpc.toml`）。
- `utils/rpc.toml`：共用鏈設定範本（含 `eth_mainnet`、`bsc_mainnet`、`base_mainnet`、`op_mainnet`、`polygon_mainnet`），支援 `native_symbol`、`explorer_tx_url`、`poa`、`urls`／`default`。
- `strategies/`：`eip3009.py`、`permit.py`、`native.py`，主程式依序嘗試 EIP-3009 → EIP-2612 permit → 不支援時提示僅能走一般 transfer（不自動執行）。
- `test_rpc.py`：測試 `utils/rpc.toml` 內各 URL 連線、延遲與 `chain_id` 一致性。
- `test_token.py`：依 `config.toml` 檢測代幣是否支援 EIP-3009／permit／否則為 transfer 類。
- `tomli` 依賴條件式安裝（Python 3.10 及以下解析 TOML 時需要）。

### Changed

- `config.toml`：`network.chain` 對應 `utils/rpc.toml` 的 `[chains.<key>]`；僅保留 `network.token_address`（移除 `usdc_address` 相容欄位）；RPC 不再寫在業務設定檔。
- `fast_escape.py`：`AppConfig` 帶入 `rpc_profile`；連線使用 `make_web3` 以正確支援 BSC／Polygon 等 POA 鏈。
- `test_rpc.py`／`test_token.py`：輸出改用 `utils/console.py` 色彩。
- `README.md`：反映多鏈設定、策略流程與工具腳本。

### Removed

- `fast-escape.js`（主流程以 Python 為準）。
- 根目錄 `rpc_utils.py`，職責併入 `utils/rpc_profiles.py`。

## [0.1.1] - 2026-05-08

### Changed

- 將 CLI 色彩工具由 `utils/colors.py` 調整為 `utils/console.py`，對齊參考倉庫命名風格。
- 私鑰改由 `.env` 載入，不再放在 `config.toml`。
- 更新 `README.md` 配置教學，加入 `.env` 建立步驟。

### Added

- 新增 `.env.example` 作為環境變數範本。
- 新增 `.gitignore`，避免提交 `.env` 與虛擬環境檔案。
- 新增 `python-dotenv` 依賴。

## [0.1.0] - 2026-05-08

### Added

- 新增 `fast_escape.py`，將原始 JS 版邏輯轉為 Python 執行。
- 新增 `config.toml`，集中配置 RPC、錢包、轉帳與交易參數。
- 新增 `utils/colors.py` 與 `utils/__init__.py`，提供 CLI 色彩輸出工具。
- 新增 `README.md`，補齊安裝、配置與執行說明。
- 新增 `requirements.txt`，管理 Python 依賴。
