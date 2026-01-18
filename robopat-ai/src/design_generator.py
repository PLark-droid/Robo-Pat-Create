#!/usr/bin/env python3
"""
Design Generator - 自動化設計支援モジュール

段階的な設計プロセスを経てRobo-Patスクリプトと設定手順書を生成します。
フロー: 要件入力 → 基本設計 → 承認 → 詳細設計 → 承認 → 成果物生成
"""

import os
import json
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


# 基本設計用プロンプト
BASIC_DESIGN_PROMPT = """あなたはRobo-Pat DX（RPA自動化ツール）の設計エキスパートです。

ユーザーの自動化要件から「基本設計書」を作成してください。

## 出力形式（JSON）

```json
{
  "project_name": "プロジェクト名",
  "overview": "自動化の概要（1-2文）",
  "target_systems": [
    {
      "name": "対象システム名",
      "type": "Web/デスクトップ/Excel等",
      "url_or_path": "URL またはパス（あれば）"
    }
  ],
  "process_flow": [
    {
      "step": 1,
      "name": "処理名",
      "description": "処理の説明",
      "input": "入力データ",
      "output": "出力データ"
    }
  ],
  "variables": [
    {
      "name": "変数名",
      "description": "用途",
      "type": "STRING/INTEGER/BOOLEAN/LIST/FILE",
      "source": "ユーザー入力/環境変数/ファイル等"
    }
  ],
  "preconditions": [
    "前提条件1",
    "前提条件2"
  ],
  "error_handling": {
    "strategy": "リトライ/スキップ/停止",
    "notification": "通知方法（メール/ログ等）"
  },
  "estimated_commands": 10
}
```

JSONのみを出力してください。
"""

# 詳細設計用プロンプト
DETAILED_DESIGN_PROMPT = """あなたはRobo-Pat DX（RPA自動化ツール）の設計エキスパートです。

基本設計を元に「詳細設計書」を作成してください。

## Robo-Pat で使用可能なコマンド

### ブラウザ操作
- open_chrome: Chromeを開く (url, profile, headless)
- click: クリック (selector, selector_type, click_type, wait_timeout)
- input_text: テキスト入力 (selector, selector_type, text, clear_first)
- input_password: パスワード入力 (selector, selector_type, password)
- select: ドロップダウン選択 (selector, value, by)
- get_text: テキスト取得 (selector, variable)
- get_attribute: 属性取得 (selector, attribute, variable)
- execute_script: JavaScript実行 (script, variable)
- navigate_back: 戻る
- close_tab: タブを閉じる

### フロー制御
- if/else_if/else/end_if: 条件分岐
- while/end_while: ループ
- loop: 回数ループ (count, variable)
- break: ループ中断
- try/catch/end_try: 例外処理

### 入力・ウィンドウ
- switch_window: ウィンドウ切替 (title, match_type)
- go_to_tab: タブ切替 (index)
- send_keys: キー送信 ({ENTER}, {TAB}, {CTRL+A}等)
- paste: ペースト (text)

### その他
- comment: コメント
- wait_for_screen_calms: 画面安定待機
- script_exit: 終了 (status, message)
- send_mail: メール送信 (to, subject, body)

## 出力形式（JSON）

```json
{
  "project_name": "プロジェクト名",
  "tabs": [
    {
      "name": "タブ名（処理グループ）",
      "description": "タブの説明",
      "steps": [
        {
          "id": 1,
          "command": "コマンド名",
          "comment": "このステップの説明",
          "options": {
            "option_name": "value"
          },
          "error_handling": "continue/retry/stop（オプション）"
        }
      ]
    }
  ],
  "variables": [
    {
      "name": "変数名",
      "type": "STRING",
      "default": "デフォルト値",
      "description": "用途"
    }
  ]
}
```

セレクタは具体例として記載し、実際の環境に合わせて調整が必要な旨を明記してください。
JSONのみを出力してください。
"""

# 手順書用プロンプト
MANUAL_GENERATION_PROMPT = """あなたはRobo-Pat DXの導入支援エキスパートです。

詳細設計を元に「設定手順書」をMarkdown形式で作成してください。

## 出力形式

```markdown
# {プロジェクト名} 設定手順書

## 1. 概要
{自動化の目的と概要}

## 2. 事前準備

### 2.1 必要な環境
- {必要なアプリケーション}
- {必要な権限}

### 2.2 対象システムの設定
{ログイン情報の準備、ブックマークの設定等}

## 3. 変数の設定

| 変数名 | 説明 | 設定値の例 |
|--------|------|-----------|
| {変数名} | {説明} | {例} |

## 4. スクリプトの実行手順

### 4.1 初回実行前の確認事項
{チェックリスト}

### 4.2 実行方法
{ステップバイステップの手順}

## 5. トラブルシューティング

### よくある問題と対処法
| 症状 | 原因 | 対処法 |
|------|------|--------|
| {症状} | {原因} | {対処法} |

## 6. 注意事項
{運用上の注意点}

## 7. 更新履歴
| 日付 | 内容 |
|------|------|
| {日付} | 初版作成 |
```

Markdown形式のみを出力してください。
"""


class DesignGenerator:
    """
    段階的設計プロセスを管理するクラス
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        self.client = None

        if HAS_ANTHROPIC and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)

        # 設計状態の保持
        self.requirement = ""
        self.basic_design = None
        self.detailed_design = None
        self.manual = ""

    def _call_api(self, system_prompt: str, user_message: str) -> str:
        """Claude API を呼び出す"""
        if not self.client:
            raise RuntimeError("Anthropic API キーが設定されていません。.env ファイルを確認してください。")

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        return response.content[0].text

    def _extract_json(self, text: str) -> dict:
        """テキストからJSONを抽出"""
        # ```json ... ``` ブロックを探す
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            json_str = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            json_str = text[start:end].strip()
        else:
            # JSONオブジェクトを直接探す
            start = text.find("{")
            end = text.rfind("}") + 1
            json_str = text[start:end]

        return json.loads(json_str)

    def generate_basic_design(self, requirement: str) -> dict:
        """
        基本設計を生成

        Args:
            requirement: 自然言語の自動化要件

        Returns:
            基本設計のdict
        """
        self.requirement = requirement
        response = self._call_api(BASIC_DESIGN_PROMPT, requirement)
        self.basic_design = self._extract_json(response)
        return self.basic_design

    def generate_detailed_design(self, feedback: Optional[str] = None) -> dict:
        """
        詳細設計を生成

        Args:
            feedback: 基本設計へのフィードバック（オプション）

        Returns:
            詳細設計のdict
        """
        if not self.basic_design:
            raise RuntimeError("先に基本設計を生成してください")

        user_message = f"""
## 自動化要件
{self.requirement}

## 基本設計
{json.dumps(self.basic_design, ensure_ascii=False, indent=2)}
"""
        if feedback:
            user_message += f"\n## 修正指示\n{feedback}"

        response = self._call_api(DETAILED_DESIGN_PROMPT, user_message)
        self.detailed_design = self._extract_json(response)
        return self.detailed_design

    def generate_manual(self) -> str:
        """
        設定手順書を生成

        Returns:
            Markdown形式の手順書
        """
        if not self.detailed_design:
            raise RuntimeError("先に詳細設計を生成してください")

        user_message = f"""
## 自動化要件
{self.requirement}

## 基本設計
{json.dumps(self.basic_design, ensure_ascii=False, indent=2)}

## 詳細設計
{json.dumps(self.detailed_design, ensure_ascii=False, indent=2)}
"""

        response = self._call_api(MANUAL_GENERATION_PROMPT, user_message)

        # Markdownブロックを抽出
        if "```markdown" in response:
            start = response.find("```markdown") + 11
            end = response.find("```", start)
            self.manual = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            self.manual = response[start:end].strip()
        else:
            self.manual = response.strip()

        return self.manual

    def generate_yaml_script(self) -> str:
        """
        詳細設計からYAMLスクリプトを生成

        Returns:
            YAML形式のスクリプト
        """
        import yaml

        if not self.detailed_design:
            raise RuntimeError("先に詳細設計を生成してください")

        # 詳細設計からYAML形式に変換
        all_steps = []
        step_id = 1

        for tab in self.detailed_design.get("tabs", []):
            # タブ開始コメント
            all_steps.append({
                "id": step_id,
                "command": "comment",
                "comment": f"=== {tab['name']} ===",
                "options": {"text": tab.get("description", "")}
            })
            step_id += 1

            for step in tab.get("steps", []):
                all_steps.append({
                    "id": step_id,
                    "command": step["command"],
                    "comment": step.get("comment", ""),
                    "options": step.get("options", {})
                })
                step_id += 1

        script = {
            "project": {
                "name": self.detailed_design.get("project_name", "RoboPatScript"),
                "description": self.requirement
            },
            "variables": [
                {
                    "name": v["name"],
                    "type": v.get("type", "STRING"),
                    "default": v.get("default", "")
                }
                for v in self.detailed_design.get("variables", [])
            ],
            "steps": all_steps
        }

        return yaml.dump(script, allow_unicode=True, sort_keys=False, default_flow_style=False)

    def format_basic_design(self) -> str:
        """基本設計を表示用にフォーマット"""
        if not self.basic_design:
            return "基本設計が生成されていません"

        bd = self.basic_design
        lines = []
        lines.append("=" * 60)
        lines.append(f"  基本設計: {bd.get('project_name', 'N/A')}")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"【概要】{bd.get('overview', 'N/A')}")
        lines.append("")

        lines.append("【対象システム】")
        for sys in bd.get("target_systems", []):
            lines.append(f"  - {sys['name']} ({sys['type']})")
            if sys.get("url_or_path"):
                lines.append(f"    {sys['url_or_path']}")
        lines.append("")

        lines.append("【処理フロー】")
        for step in bd.get("process_flow", []):
            lines.append(f"  {step['step']}. {step['name']}")
            lines.append(f"     {step['description']}")
            if step.get("input"):
                lines.append(f"     入力: {step['input']}")
            if step.get("output"):
                lines.append(f"     出力: {step['output']}")
        lines.append("")

        lines.append("【変数】")
        for var in bd.get("variables", []):
            lines.append(f"  - {var['name']} ({var['type']}): {var['description']}")
        lines.append("")

        lines.append("【前提条件】")
        for cond in bd.get("preconditions", []):
            lines.append(f"  - {cond}")
        lines.append("")

        eh = bd.get("error_handling", {})
        lines.append(f"【エラーハンドリング】{eh.get('strategy', 'N/A')} / 通知: {eh.get('notification', 'N/A')}")
        lines.append("")
        lines.append(f"【推定コマンド数】約 {bd.get('estimated_commands', 'N/A')} コマンド")
        lines.append("=" * 60)

        return "\n".join(lines)

    def format_detailed_design(self) -> str:
        """詳細設計を表示用にフォーマット"""
        if not self.detailed_design:
            return "詳細設計が生成されていません"

        dd = self.detailed_design
        lines = []
        lines.append("=" * 60)
        lines.append(f"  詳細設計: {dd.get('project_name', 'N/A')}")
        lines.append("=" * 60)
        lines.append("")

        lines.append("【変数定義】")
        for var in dd.get("variables", []):
            default = var.get("default", "")
            if default:
                lines.append(f"  - {var['name']} = \"{default}\" ({var.get('description', '')})")
            else:
                lines.append(f"  - {var['name']} ({var.get('description', '')})")
        lines.append("")

        for tab in dd.get("tabs", []):
            lines.append("-" * 60)
            lines.append(f"【タブ: {tab['name']}】{tab.get('description', '')}")
            lines.append("-" * 60)

            for step in tab.get("steps", []):
                lines.append(f"  {step['id']:3d}. [{step['command']}] {step.get('comment', '')}")
                for key, val in step.get("options", {}).items():
                    lines.append(f"        {key}: {val}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def generate_robopat_guide(self) -> str:
        """
        Robo-Pat DXでコピペしやすい詳細ガイドを生成

        Returns:
            Markdown形式のガイド
        """
        if not self.detailed_design:
            return "詳細設計が生成されていません"

        dd = self.detailed_design
        lines = []

        lines.append(f"# {dd.get('project_name', 'RoboPatScript')} - Robo-Pat DX 作成ガイド")
        lines.append("")
        lines.append("このガイドを参照しながらRobo-Pat DXでスクリプトを作成してください。")
        lines.append("各セクションの値はそのままコピペできます。")
        lines.append("")

        # 変数セクション
        lines.append("---")
        lines.append("## 1. 変数の設定")
        lines.append("")
        lines.append("Robo-Pat DX の「変数」タブで以下を設定してください：")
        lines.append("")
        lines.append("| 変数名 | 型 | 初期値 | 説明 |")
        lines.append("|--------|-----|--------|------|")

        for var in dd.get("variables", []):
            name = var.get("name", "")
            vtype = var.get("type", "STRING")
            default = var.get("default", "")
            desc = var.get("description", "")
            lines.append(f"| `{name}` | {vtype} | `{default}` | {desc} |")

        lines.append("")
        lines.append("### コピペ用（変数名）")
        lines.append("```")
        for var in dd.get("variables", []):
            lines.append(var.get("name", ""))
        lines.append("```")
        lines.append("")

        # タブとコマンドセクション
        lines.append("---")
        lines.append("## 2. コマンドの作成")
        lines.append("")

        step_num = 1
        for tab in dd.get("tabs", []):
            lines.append(f"### タブ: {tab['name']}")
            lines.append(f"> {tab.get('description', '')}")
            lines.append("")

            for step in tab.get("steps", []):
                cmd = step.get("command", "")
                comment = step.get("comment", "")
                options = step.get("options", {})

                lines.append(f"#### Step {step_num}: {cmd}")
                lines.append(f"**説明:** {comment}")
                lines.append("")

                # コマンド別の詳細
                if cmd == "open_chrome":
                    url = options.get("url", "")
                    lines.append("**操作:** `Web操作` → `Chromeを開く`")
                    lines.append("")
                    lines.append("**URL（コピペ用）:**")
                    lines.append(f"```")
                    lines.append(url)
                    lines.append(f"```")

                elif cmd == "click":
                    selector = options.get("selector", "")
                    sel_type = options.get("selector_type", "css")
                    lines.append("**操作:** `Web操作` → `クリック`")
                    lines.append("")
                    lines.append(f"**セレクタタイプ:** {sel_type.upper()}")
                    lines.append("")
                    lines.append("**セレクタ（コピペ用）:**")
                    lines.append(f"```")
                    lines.append(selector)
                    lines.append(f"```")

                elif cmd == "input_text":
                    selector = options.get("selector", "")
                    sel_type = options.get("selector_type", "css")
                    text = options.get("text", "")
                    lines.append("**操作:** `Web操作` → `テキスト入力`")
                    lines.append("")
                    lines.append(f"**セレクタタイプ:** {sel_type.upper()}")
                    lines.append("")
                    lines.append("**セレクタ（コピペ用）:**")
                    lines.append(f"```")
                    lines.append(selector)
                    lines.append(f"```")
                    lines.append("")
                    lines.append("**入力値（コピペ用）:**")
                    lines.append(f"```")
                    lines.append(text)
                    lines.append(f"```")

                elif cmd == "input_password":
                    selector = options.get("selector", "")
                    lines.append("**操作:** `Web操作` → `パスワード入力`")
                    lines.append("")
                    lines.append("**セレクタ（コピペ用）:**")
                    lines.append(f"```")
                    lines.append(selector)
                    lines.append(f"```")

                elif cmd == "get_text":
                    selector = options.get("selector", "")
                    variable = options.get("variable", "")
                    lines.append("**操作:** `Web操作` → `テキスト取得`")
                    lines.append("")
                    lines.append("**セレクタ（コピペ用）:**")
                    lines.append(f"```")
                    lines.append(selector)
                    lines.append(f"```")
                    lines.append("")
                    lines.append(f"**格納変数:** `{variable}`")

                elif cmd == "execute_script":
                    script = options.get("script", "")
                    variable = options.get("variable", "")
                    lines.append("**操作:** `Web操作` → `JavaScript実行`")
                    lines.append("")
                    lines.append("**スクリプト（コピペ用）:**")
                    lines.append(f"```javascript")
                    lines.append(script)
                    lines.append(f"```")
                    if variable:
                        lines.append("")
                        lines.append(f"**格納変数:** `{variable}`")

                elif cmd == "if":
                    condition = options.get("condition", "")
                    lines.append("**操作:** `フロー制御` → `条件分岐(IF)`")
                    lines.append("")
                    lines.append("**条件（コピペ用）:**")
                    lines.append(f"```")
                    lines.append(condition)
                    lines.append(f"```")

                elif cmd == "while":
                    condition = options.get("condition", "")
                    lines.append("**操作:** `フロー制御` → `繰り返し(WHILE)`")
                    lines.append("")
                    lines.append("**条件（コピペ用）:**")
                    lines.append(f"```")
                    lines.append(condition)
                    lines.append(f"```")

                elif cmd == "comment":
                    text = options.get("text", comment)
                    lines.append("**操作:** `基本` → `コメント`")
                    lines.append("")
                    lines.append("**コメント（コピペ用）:**")
                    lines.append(f"```")
                    lines.append(text)
                    lines.append(f"```")

                elif cmd == "send_mail":
                    to = options.get("to", "")
                    subject = options.get("subject", "")
                    body = options.get("body", "")
                    lines.append("**操作:** `基本` → `メール送信`")
                    lines.append("")
                    lines.append("**宛先（コピペ用）:**")
                    lines.append(f"```")
                    lines.append(to)
                    lines.append(f"```")
                    lines.append("")
                    lines.append("**件名（コピペ用）:**")
                    lines.append(f"```")
                    lines.append(subject)
                    lines.append(f"```")
                    lines.append("")
                    lines.append("**本文（コピペ用）:**")
                    lines.append(f"```")
                    lines.append(body)
                    lines.append(f"```")

                elif cmd == "script_exit":
                    status = options.get("status", "0")
                    message = options.get("message", "")
                    lines.append("**操作:** `フロー制御` → `スクリプト終了`")
                    lines.append("")
                    lines.append(f"**終了ステータス:** {status}")
                    lines.append("")
                    lines.append("**メッセージ（コピペ用）:**")
                    lines.append(f"```")
                    lines.append(message)
                    lines.append(f"```")

                elif cmd in ["else", "else_if", "end_if", "end_while", "try", "catch", "end_try", "break"]:
                    cmd_map = {
                        "else": "`フロー制御` → `ELSE`",
                        "else_if": "`フロー制御` → `ELSE IF`",
                        "end_if": "`フロー制御` → `END IF`",
                        "end_while": "`フロー制御` → `END WHILE`",
                        "try": "`フロー制御` → `TRY`",
                        "catch": "`フロー制御` → `CATCH`",
                        "end_try": "`フロー制御` → `END TRY`",
                        "break": "`フロー制御` → `BREAK`",
                    }
                    lines.append(f"**操作:** {cmd_map.get(cmd, cmd)}")

                elif cmd == "wait_for_screen_calms":
                    lines.append("**操作:** `基本` → `画面安定待ち`")

                elif cmd == "close_tab":
                    lines.append("**操作:** `Web操作` → `タブを閉じる`")

                else:
                    # その他のコマンド
                    lines.append(f"**操作:** `{cmd}`")
                    if options:
                        lines.append("")
                        lines.append("**オプション:**")
                        for k, v in options.items():
                            lines.append(f"- {k}: `{v}`")

                lines.append("")
                lines.append("---")
                lines.append("")
                step_num += 1

        # 補足情報
        lines.append("## 3. 注意事項")
        lines.append("")
        lines.append("- セレクタ（XPath/CSS）は実際の画面に合わせて調整が必要です")
        lines.append("- 変数名は `^変数名^` の形式で使用します")
        lines.append("- 画面遷移後は「画面安定待ち」を入れることを推奨します")
        lines.append("")

        return "\n".join(lines)


def run_design_wizard():
    """
    対話型設計ウィザードを実行
    """
    # readline有効化（入力補助）
    try:
        import readline
    except ImportError:
        pass

    generator = DesignGenerator()

    print("=" * 60)
    print("  Robo-Pat 自動化設計支援ウィザード")
    print("=" * 60)
    print("")
    print("自然言語で自動化したい業務を入力してください。")
    print("AIが基本設計 → 詳細設計 → スクリプト + 手順書 を生成します。")
    print("")
    print("-" * 60)

    # Step 1: 要件入力
    print("")
    print("【Step 1/5】自動化要件を入力してください")
    print("")

    try:
        requirement = input("要件 > ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n終了します。")
        return

    if not requirement or requirement.lower() in ['quit', 'exit', 'q']:
        print("終了します。")
        return

    # 追加入力オプション
    print("")
    print("追加情報があれば入力してください（なければそのままEnter）:")
    try:
        extra = input("追加 > ").strip()
        if extra and extra.lower() not in ['quit', 'exit', 'q']:
            requirement = f"{requirement}\n{extra}"
    except (KeyboardInterrupt, EOFError):
        pass

    # Step 2: 基本設計生成
    print("")
    print("-" * 60)
    print("【Step 2/5】基本設計を生成中...")
    print("-" * 60)

    try:
        generator.generate_basic_design(requirement)
        print("")
        print(generator.format_basic_design())
    except Exception as e:
        print(f"エラー: {e}")
        return

    # Step 3: 基本設計承認
    print("")
    print("【Step 3/5】基本設計を承認しますか？")
    print("  [Y] 承認して詳細設計へ進む")
    print("  [N] 修正指示を入力")
    print("  [Q] 終了")
    print("")

    while True:
        choice = input("選択 (Y/N/Q): ").strip().upper()
        if choice == 'Y':
            break
        elif choice == 'N':
            print("修正指示を入力してください:")
            feedback = input("> ").strip()
            if feedback:
                print("\n基本設計を修正中...")
                generator.generate_basic_design(f"{requirement}\n\n追加要件: {feedback}")
                print(generator.format_basic_design())
            print("\n承認しますか？ (Y/N/Q)")
        elif choice == 'Q':
            print("終了します。")
            return
        else:
            print("Y, N, Q のいずれかを入力してください。")

    # Step 4: 詳細設計生成
    print("")
    print("-" * 60)
    print("【Step 4/5】詳細設計を生成中...")
    print("-" * 60)

    try:
        generator.generate_detailed_design()
        print("")
        print(generator.format_detailed_design())
    except Exception as e:
        print(f"エラー: {e}")
        return

    # Step 5: 詳細設計承認
    print("")
    print("【Step 5/5】詳細設計を承認しますか？")
    print("  [Y] 承認して成果物を生成")
    print("  [N] 修正指示を入力")
    print("  [Q] 終了")
    print("")

    while True:
        choice = input("選択 (Y/N/Q): ").strip().upper()
        if choice == 'Y':
            break
        elif choice == 'N':
            print("修正指示を入力してください:")
            feedback = input("> ").strip()
            if feedback:
                print("\n詳細設計を修正中...")
                generator.generate_detailed_design(feedback)
                print(generator.format_detailed_design())
            print("\n承認しますか？ (Y/N/Q)")
        elif choice == 'Q':
            print("終了します。")
            return
        else:
            print("Y, N, Q のいずれかを入力してください。")

    # 成果物生成
    print("")
    print("=" * 60)
    print("  成果物を生成しています...")
    print("=" * 60)

    # 出力ファイル名を決定
    project_name = generator.detailed_design.get("project_name", "RoboPatScript")
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in project_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_dir = Path.cwd() / "output"
    output_dir.mkdir(exist_ok=True)

    # YAML生成
    yaml_path = output_dir / f"{safe_name}_{timestamp}.yaml"
    yaml_content = generator.generate_yaml_script()
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
    print(f"  [✓] YAML スクリプト: {yaml_path}")

    # 手順書生成
    print("  手順書を生成中...")
    manual_content = generator.generate_manual()
    manual_path = output_dir / f"{safe_name}_{timestamp}_手順書.md"
    with open(manual_path, "w", encoding="utf-8") as f:
        f.write(manual_content)
    print(f"  [✓] 設定手順書: {manual_path}")

    # 基本設計・詳細設計JSONも保存
    design_path = output_dir / f"{safe_name}_{timestamp}_設計.json"
    design_data = {
        "requirement": generator.requirement,
        "basic_design": generator.basic_design,
        "detailed_design": generator.detailed_design,
        "generated_at": timestamp
    }
    with open(design_path, "w", encoding="utf-8") as f:
        json.dump(design_data, f, ensure_ascii=False, indent=2)
    print(f"  [✓] 設計データ: {design_path}")

    # Robo-Pat DX 作成ガイド生成
    guide_content = generator.generate_robopat_guide()
    guide_path = output_dir / f"{safe_name}_{timestamp}_作成ガイド.md"
    with open(guide_path, "w", encoding="utf-8") as f:
        f.write(guide_content)
    print(f"  [✓] Robo-Pat DX 作成ガイド: {guide_path}")

    # .bwnp生成オプション
    print("")
    print("【オプション】.bwnpファイルを生成しますか？")
    print("  [Y] テンプレートから.bwnpを生成")
    print("  [N] スキップ（後で手動生成）")
    print("")

    bwnp_path = None
    choice = input("選択 (Y/N): ").strip().upper()

    if choice == 'Y':
        # テンプレートファイルのパス
        default_template = Path(__file__).parent.parent.parent / "script" / "SUUMO反響記録ロボット.bwnp"

        print(f"  テンプレート: {default_template}")

        if default_template.exists():
            try:
                # bwn_patcherを使用してテンプレートから生成
                from bwn_patcher import create_from_template

                bwnp_path = output_dir / f"{safe_name}_{timestamp}.bwnp"
                create_from_template(
                    str(default_template),
                    str(bwnp_path),
                    project_name
                )
                print(f"  [✓] Robo-Patスクリプト: {bwnp_path}")
            except Exception as e:
                print(f"  [!] .bwnp生成エラー: {e}")
                print("      後で手動生成してください。")
        else:
            print(f"  [!] テンプレートが見つかりません: {default_template}")
            print("      後で手動生成してください。")

    print("")
    print("=" * 60)
    print("  生成完了！")
    print("=" * 60)
    print("")

    print("成果物:")
    print(f"  - Robo-Pat DX 作成ガイド: {guide_path} ★メイン")
    print(f"  - 設定手順書: {manual_path}")
    print(f"  - 設計データ: {design_path}")
    print(f"  - YAML スクリプト: {yaml_path}")
    print("")
    print("次のステップ:")
    print(f"  1. {guide_path} を開く")
    print(f"  2. ガイドを見ながらRobo-Pat DXでスクリプトを作成")
    print(f"  3. 各Stepのコピペ用テキストをそのまま貼り付け")
    print(f"  4. {manual_path} を参考に設定・テスト")
    print("")


if __name__ == "__main__":
    run_design_wizard()
