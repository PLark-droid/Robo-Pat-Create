#!/usr/bin/env python3
"""
AI Generator - 自然言語からRobo-Patスクリプトを生成

Claude API を使用して、自然言語の指示をRobo-PatのYAMLスクリプトに変換します。
"""

import os
import yaml
import json
from typing import Optional, Dict, Any
from pathlib import Path

# .env ファイルから環境変数を読み込み
try:
    from dotenv import load_dotenv
    # このファイルの親ディレクトリ（src）の親（robopat-ai）にある .env を読み込む
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass

# Anthropic SDK (optional, falls back to template-based generation)
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


# システムプロンプト
SYSTEM_PROMPT = """あなたはRobo-Pat DX（RPA自動化ツール）のスクリプト生成AIです。

ユーザーの自然言語指示を、Robo-PatのYAML形式スクリプトに変換してください。

## 出力形式

必ず以下のYAML形式で出力してください：

```yaml
project:
  name: "スクリプト名"
  description: "説明"

variables:
  - name: 変数名
    type: STRING  # STRING, INTEGER, BOOLEAN, LIST, FILE
    default: デフォルト値

steps:
  - id: 1
    command: コマンド名
    comment: "このステップの説明"
    options:
      オプション名: 値
```

## 利用可能なコマンド

### ブラウザ操作
- `open_chrome`: Chromeを開く
  - options: url, profile, headless
- `click`: クリック
  - options: selector, selector_type (CSS/XPATH/ID), click_type (SINGLE/DOUBLE/RIGHT), wait_timeout
- `input_text`: テキスト入力
  - options: selector, selector_type, text, clear_first
- `input_password`: パスワード入力
  - options: selector, selector_type, password
- `select`: ドロップダウン選択
  - options: selector, selector_type, value, by (VALUE/TEXT/INDEX)
- `get_text`: テキスト取得
  - options: selector, selector_type, variable
- `get_attribute`: 属性取得
  - options: selector, selector_type, attribute, variable
- `execute_script`: JavaScript実行
  - options: script, variable
- `navigate_back`: 戻る
- `close_tab`: タブを閉じる
  - options: type (CURRENT/ALL_EXCEPT_FIRST)

### フロー制御
- `if`: 条件分岐開始
  - options: condition, operator (EQUALS/NOT_EQUALS/CONTAINS/GREATER/LESS)
- `else_if`: 追加条件
  - options: condition
- `else`: それ以外
- `end_if`: 条件分岐終了
- `while`: ループ開始
  - options: condition, max_iterations
- `end_while`: ループ終了
- `loop`: 回数ループ
  - options: count, variable
- `break`: ループ中断
- `try`: 例外処理開始
- `catch`: 例外ハンドラ
  - options: error_variable
- `end_try`: 例外処理終了

### ウィンドウ・入力
- `switch_window`: ウィンドウ切替
  - options: title, match_type (EXACT/CONTAINS/REGEX)
- `go_to_tab`: タブ切替
  - options: index
- `send_keys`: キー送信
  - options: keys ({ENTER}, {TAB}, {CTRL+A}, etc.)
- `paste`: ペースト
  - options: text
- `type`: タイプ入力
  - options: text, delay

### その他
- `comment`: コメント
  - options: text
- `wait_for_screen_calms`: 画面安定待機
  - options: timeout
- `script_exit`: スクリプト終了
  - options: status (SUCCESS/ERROR), message
- `send_mail`: メール送信
  - options: to, subject, body, attachments

## 変数の使用

変数は `${変数名}` の形式で参照できます。

例：
```yaml
variables:
  - name: USERNAME
    type: STRING
    default: "user@example.com"

steps:
  - id: 1
    command: input_text
    options:
      selector: "#email"
      selector_type: CSS
      text: "${USERNAME}"
```

## 重要なルール

1. セレクタは具体的に指定してください（#id, .class, xpath等）
2. 適切な待機時間を設定してください（wait_timeout）
3. エラーハンドリングを考慮してください（try/catch）
4. コメントで各ステップを説明してください
5. 変数を活用して再利用性を高めてください

YAMLのみを出力し、説明文は含めないでください。
"""


class AIGenerator:
    """
    自然言語からRobo-Patスクリプトを生成
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        self.client = None

        if HAS_ANTHROPIC and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)

    def generate(self, instruction: str, context: Optional[str] = None) -> str:
        """
        自然言語指示からYAMLスクリプトを生成

        Args:
            instruction: 自然言語の指示
            context: 追加コンテキスト（オプション）

        Returns:
            YAML形式のスクリプト
        """
        if self.client:
            return self._generate_with_api(instruction, context)
        else:
            return self._generate_with_template(instruction, context)

    def _generate_with_api(self, instruction: str, context: Optional[str] = None) -> str:
        """Claude API を使用して生成"""
        user_message = instruction
        if context:
            user_message = f"コンテキスト:\n{context}\n\n指示:\n{instruction}"

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

        # YAMLブロックを抽出
        content = response.content[0].text
        if "```yaml" in content:
            yaml_start = content.find("```yaml") + 7
            yaml_end = content.find("```", yaml_start)
            return content[yaml_start:yaml_end].strip()
        elif "```" in content:
            yaml_start = content.find("```") + 3
            yaml_end = content.find("```", yaml_start)
            return content[yaml_start:yaml_end].strip()
        return content.strip()

    def _generate_with_template(self, instruction: str, context: Optional[str] = None) -> str:
        """テンプレートベースで生成（API なしの場合）"""
        # 簡易的なテンプレートマッチング
        instruction_lower = instruction.lower()

        steps = []
        step_id = 1

        # URL検出
        import re
        urls = re.findall(r'https?://[^\s]+', instruction)

        # ブラウザを開く
        if any(word in instruction_lower for word in ['開く', 'アクセス', 'ブラウザ', 'chrome', 'url']):
            url = urls[0] if urls else "https://example.com"
            steps.append({
                'id': step_id,
                'command': 'open_chrome',
                'comment': 'ブラウザを開く',
                'options': {'url': url}
            })
            step_id += 1

        # ログイン関連
        if any(word in instruction_lower for word in ['ログイン', 'login', 'サインイン']):
            steps.append({
                'id': step_id,
                'command': 'input_text',
                'comment': 'ユーザー名を入力',
                'options': {
                    'selector': '#username',
                    'selector_type': 'CSS',
                    'text': '${USERNAME}',
                    'clear_first': True
                }
            })
            step_id += 1

            steps.append({
                'id': step_id,
                'command': 'input_password',
                'comment': 'パスワードを入力',
                'options': {
                    'selector': '#password',
                    'selector_type': 'CSS',
                    'password': '${PASSWORD}'
                }
            })
            step_id += 1

            steps.append({
                'id': step_id,
                'command': 'click',
                'comment': 'ログインボタンをクリック',
                'options': {
                    'selector': 'button[type="submit"]',
                    'selector_type': 'CSS',
                    'click_type': 'SINGLE',
                    'wait_timeout': 10
                }
            })
            step_id += 1

        # クリック操作
        if 'クリック' in instruction_lower or 'click' in instruction_lower:
            steps.append({
                'id': step_id,
                'command': 'click',
                'comment': '要素をクリック',
                'options': {
                    'selector': '#target-element',
                    'selector_type': 'CSS',
                    'click_type': 'SINGLE',
                    'wait_timeout': 10
                }
            })
            step_id += 1

        # データ取得
        if any(word in instruction_lower for word in ['取得', '抽出', 'csv', 'データ']):
            steps.append({
                'id': step_id,
                'command': 'get_text',
                'comment': 'データを取得',
                'options': {
                    'selector': '.data-container',
                    'selector_type': 'CSS',
                    'variable': 'extracted_data'
                }
            })
            step_id += 1

        # 待機
        if any(word in instruction_lower for word in ['待つ', '待機', 'wait']):
            steps.append({
                'id': step_id,
                'command': 'wait_for_screen_calms',
                'comment': '画面が安定するまで待機',
                'options': {'timeout': 10}
            })
            step_id += 1

        # デフォルトのスクリプト
        if not steps:
            steps = [
                {
                    'id': 1,
                    'command': 'comment',
                    'comment': '自動生成されたスクリプト',
                    'options': {'text': instruction}
                },
                {
                    'id': 2,
                    'command': 'open_chrome',
                    'comment': 'ブラウザを開く',
                    'options': {'url': 'https://example.com'}
                }
            ]

        # プロジェクト名を生成
        project_name = self._extract_project_name(instruction)

        script = {
            'project': {
                'name': project_name,
                'description': instruction
            },
            'variables': [
                {'name': 'USERNAME', 'type': 'STRING', 'default': ''},
                {'name': 'PASSWORD', 'type': 'STRING', 'default': ''}
            ],
            'steps': steps
        }

        return yaml.dump(script, allow_unicode=True, sort_keys=False, default_flow_style=False)

    def _extract_project_name(self, instruction: str) -> str:
        """指示からプロジェクト名を抽出"""
        # 最初の20文字程度をプロジェクト名に
        name = instruction[:30].replace('\n', ' ').strip()
        if len(instruction) > 30:
            name += '...'
        return name


def generate_robopat_script(instruction: str, api_key: Optional[str] = None) -> str:
    """
    自然言語指示からRobo-Patスクリプトを生成

    Args:
        instruction: 自然言語の指示
        api_key: Anthropic API キー（オプション）

    Returns:
        YAML形式のスクリプト
    """
    generator = AIGenerator(api_key=api_key)
    return generator.generate(instruction)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ai_generator.py <instruction>")
        print("       python ai_generator.py --interactive")
        print("")
        print("Examples:")
        print('  python ai_generator.py "SUUMOにログインして反響データを取得する"')
        sys.exit(1)

    if sys.argv[1] == '--interactive':
        generator = AIGenerator()
        print("Robo-Pat AI Generator (対話モード)")
        print("終了するには 'quit' または 'exit' を入力")
        print("-" * 50)

        while True:
            try:
                instruction = input("\n指示> ").strip()
                if instruction.lower() in ['quit', 'exit', 'q']:
                    break
                if not instruction:
                    continue

                print("\n生成中...")
                yaml_output = generator.generate(instruction)
                print("\n--- 生成されたスクリプト ---")
                print(yaml_output)
                print("--- ここまで ---")

            except KeyboardInterrupt:
                print("\n終了します。")
                break
    else:
        instruction = ' '.join(sys.argv[1:])
        yaml_output = generate_robopat_script(instruction)
        print(yaml_output)
