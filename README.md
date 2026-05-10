# 資產救援工具（asset_rescue）

在私鑰已外洩的情境下，盡快把資產從被盜地址轉到安全地址：ERC-20 優先使用 **EIP-3009**（`transferWithAuthorization`，由安全錢包 A 付 Gas）；若不支援則嘗試 **EIP-2612 permit**；兩者皆無則程式會**中止並提示**只能走一般 `transfer`／`approve`（高風險，需自行評估）。亦可選 **原生幣** 轉移模式。

## 功能摘要

- **策略順序（token 模式）**：EIP-3009 → permit → 不支援則錯誤提示（不自動送 transfer）。
- **native 模式**：由被盜錢包自行付 Gas 轉出原生幣。
- **多鏈**：鏈與 RPC 清單集中在 `utils/rpc.toml`，業務參數在 `config.toml` 的 `network.chain` 等。
- **POA 鏈**：透過 `utils/rpc_profiles.py` 的 `make_web3` 自動處理（如 BSC、Polygon）。
- 私鑰僅從 `.env` 載入；CLI 色彩見 `utils/console.py`。

## 目錄與可複製套件

若要在其他專案重用 RPC 設定與載入邏輯，可複製整個 **`utils/`** 資料夾（含 `console.py`、`rpc_profiles.py`、`rpc.toml`、`__init__.py`）。根目錄的 `test_rpc.py` 可依需求一併複製。

## 環境

- Python **3.11+** 建議（內建 `tomllib`）；若為 **3.10 及以下**，依賴會安裝 `tomli`。
- 安裝（macOS 範例）：

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

編輯 `.env` 填入私鑰（見下節）。

## 配置

### `config.toml`

| 欄位 | 說明 |
|------|------|
| `network.chain` | 對應 `utils/rpc.toml` 的 `[chains.<key>]`（例如 `bsc_mainnet`） |
| `network.token_address` | ERC-20 合約地址（token 模式必填） |
| `transfer.kind` | `token` 或 `native` |
| `transfer.amount` | 十進位字串或 `"all"` |
| `transfer.valid_window_seconds` | 簽名／permit 有效窗口（秒） |
| `transfer.safe_wallet_b_address` | 接收地址（可被 `.env` 覆蓋） |
| `tx.gas_limit` | Gas 上限 |

### `utils/rpc.toml`

每條鏈可設定：`name`、`chain_id`、`urls`、`default`（可選，插入為首選）、`native_symbol`、`explorer_tx_url`（模板 `{tx_hash}`）、`poa`（POA 鏈為 `true`）。

### `.env`

- `COMPROMISED_PRIVATE_KEY`：被盜錢包私鑰（簽名用）
- `SAFE_WALLET_A_PRIVATE_KEY`：安全錢包 A（提交交易、付 Gas；token 策略用）
- `SAFE_WALLET_B_ADDRESS`（可選）：覆蓋 `config.toml` 的接收地址

## 執行

### 互動式入口（建議）

```bash
python main.py
```

可在介面中：
- 檢視目前 `config.toml` 設定
- 互動修改設定後直接儲存
- 不修改就直接啟動主流程

### 直接執行主流程（非互動）

```bash
python asset_rescue.py
```

### 輔助腳本

```bash
python test_rpc.py    # 測試 utils/rpc.toml 內各 RPC 連線與 chain_id
python test_token.py  # 依 config 檢測代幣：3009 / permit / transfer-only
```

請在**專案根目錄**執行（需能 `import utils`，且存在 `utils/rpc.toml`）。

## 注意事項

- `valid_window_seconds` 過短可能來不及上鏈。
- 安全錢包 A 需備足該鏈 **原生 Gas**（`utils/rpc.toml` 中 `native_symbol` 僅供顯示／辨識，實際仍為該鏈原生代幣）。
- 不支援 3009／permit 的代幣只能依賴一般鏈上轉帳，請自行評估監控與搶跑風險。
- 建議先小額測試再進行大額操作。

## 變更紀錄

見 [CHANGELOG.md](CHANGELOG.md)。
