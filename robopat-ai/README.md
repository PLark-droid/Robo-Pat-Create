# Robo-Pat AI

自然言語から Robo-Pat DX のスクリプトファイル（.bwnp）を生成するツール。

## 概要

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│ 自然言語指示     │ ──→ │ YAML スクリプト │ ──→ │ .bwnp ファイル │
│ "SUUMOにログイン" │     │               │     │  (Robo-Pat)  │
└─────────────────┘     └──────────────┘     └─────────────┘
      ↑                       ↑                    ↑
   AI Generator           Compiler            Packager
```

## インストール

```bash
# 必要なパッケージ
pip install pyyaml

# オプション: Claude API を使用する場合
pip install anthropic
export ANTHROPIC_API_KEY="your-api-key"
```

## 使用方法

### 1. 対話モード（推奨）

```bash
python robopat_ai.py interactive
```

対話モードでは、自然言語で指示を入力すると、リアルタイムでスクリプトが生成されます。

```
指示> SUUMOにログインして反響データをCSVに出力する

--- 生成されたスクリプト ---
project:
  name: "SUUMO反響データ取得"
...

'save script.yaml' で保存, 'export script.bwnp' で .bwnp 出力
```

### 2. ワンショット生成

自然言語から直接 .bwnp ファイルを生成:

```bash
python robopat_ai.py create "SUUMOにログインして反響データを取得" output.bwnp
```

### 3. 段階的な生成

#### YAML 生成
```bash
python robopat_ai.py generate "指示" -o script.yaml
```

#### YAML → .bwnp コンパイル
```bash
python robopat_ai.py compile script.yaml output.bwnp
```

### 4. 既存スクリプトの解析

```bash
python robopat_ai.py parse existing.bwnp -o parsed.yaml
```

## YAML スクリプト形式

```yaml
project:
  name: "スクリプト名"
  description: "説明"

variables:
  - name: USERNAME
    type: STRING
    default: ""

steps:
  - id: 1
    command: open_chrome
    comment: "ブラウザを開く"
    options:
      url: "https://example.com"

  - id: 2
    command: input_text
    options:
      selector: "#email"
      selector_type: CSS
      text: "${USERNAME}"
```

## 利用可能なコマンド

### ブラウザ操作
| コマンド | 説明 | 主なオプション |
|---------|------|---------------|
| `open_chrome` | Chrome を開く | url, profile, headless |
| `click` | クリック | selector, selector_type, click_type |
| `input_text` | テキスト入力 | selector, text, clear_first |
| `input_password` | パスワード入力 | selector, password |
| `select` | ドロップダウン選択 | selector, value, by |
| `get_text` | テキスト取得 | selector, variable |
| `execute_script` | JavaScript実行 | script, variable |
| `close_tab` | タブを閉じる | type |

### フロー制御
| コマンド | 説明 |
|---------|------|
| `if` / `else_if` / `else` / `end_if` | 条件分岐 |
| `while` / `end_while` | ループ |
| `loop` / `end_loop` | 回数ループ |
| `try` / `catch` / `end_try` | 例外処理 |
| `break` | ループ中断 |

### その他
| コマンド | 説明 |
|---------|------|
| `comment` | コメント |
| `wait_for_screen_calms` | 画面安定待機 |
| `send_keys` | キー送信 |
| `switch_window` | ウィンドウ切替 |
| `script_exit` | スクリプト終了 |

## ファイル構成

```
robopat-ai/
├── robopat_ai.py          # メイン CLI
├── schema.yaml            # YAML スキーマ定義
├── README.md              # このファイル
├── src/
│   ├── ai_generator.py    # AI 生成エンジン
│   ├── bwn_compiler.py    # YAML → .bwn コンパイラ
│   ├── bwn_parser.py      # .bwn → YAML パーサー
│   └── bwnp_packager.py   # .bwnp パッケージャー
├── examples/
│   └── suumo_login.yaml   # サンプルスクリプト
└── templates/             # テンプレート（将来拡張用）
```

## 技術詳細

### .bwnp ファイル形式

```
.bwnp (ZIP アーカイブ)
├── プロジェクト名.bwn    # Java シリアライズ形式のスクリプト
└── プロジェクト名/
    ├── bwn-1.png         # スクリーンショット（画像マッチング用）
    ├── bwn-2.png
    └── ...
```

### .bwn ファイル形式

- Java シリアライズ形式 (`java.io.Serializable`)
- パッケージ: `com.asirrera.brownie.ide.*`
- 主なクラス: `HashMap`, `ArrayList`, `BrownieCommand`

## 制限事項

- 画像マッチング（Find コマンド）はスクリーンショットが必要
- 一部の高度なコマンドは手動調整が必要な場合があります
- 生成されたスクリプトは Robo-Pat DX で動作確認することを推奨

## ライセンス

MIT License

## 関連

- [Robo-Pat DX](https://www.fcrlabo.co.jp/) - RPA ツール
- [Miyabi](https://github.com/...) - GitHub 自動化フレームワーク
