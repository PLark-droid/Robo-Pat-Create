#!/usr/bin/env python3
"""
Script Exporter - YAMLスクリプトを様々な形式でエクスポート

- Markdown手順書: Robo-Pat DX で手動作成するための詳細手順
- HTML: ブラウザで見れる形式
- JSON: プログラム連携用
"""

import yaml
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


class ScriptExporter:
    """スクリプトを様々な形式でエクスポート"""

    # コマンドの日本語名
    COMMAND_NAMES = {
        'open_chrome': 'Chromeを開く',
        'click': 'クリック',
        'input_text': 'テキスト入力',
        'input_password': 'パスワード入力',
        'input_calendar': 'カレンダー入力',
        'select': 'ドロップダウン選択',
        'get_text': 'テキスト取得',
        'get_attribute': '属性取得',
        'execute_script': 'JavaScript実行',
        'navigate_back': '戻る',
        'close_tab': 'タブを閉じる',
        'check': 'チェックボックス',
        'if': '条件分岐 (IF)',
        'else_if': '条件分岐 (ELSE IF)',
        'else': '条件分岐 (ELSE)',
        'end_if': '条件分岐終了',
        'while': 'ループ (WHILE)',
        'end_while': 'ループ終了',
        'loop': '回数ループ',
        'end_loop': 'ループ終了',
        'break': 'ループ中断',
        'try': '例外処理開始 (TRY)',
        'catch': '例外処理 (CATCH)',
        'end_try': '例外処理終了',
        'switch_window': 'ウィンドウ切替',
        'go_to_tab': 'タブ切替',
        'send_keys': 'キー送信',
        'paste': 'ペースト',
        'type': 'タイプ入力',
        'find': '画像/テキスト検索',
        'wait_for_screen_calms': '画面安定待機',
        'comment': 'コメント',
        'script_exit': 'スクリプト終了',
        'send_mail': 'メール送信',
        'screen_record_start': '画面録画開始',
        'screen_record_end': '画面録画終了',
    }

    # Robo-Pat DX のメニュー位置
    MENU_LOCATIONS = {
        'open_chrome': 'ブラウザ操作 > Chromeを開く',
        'click': 'ブラウザ操作 > クリック',
        'input_text': 'ブラウザ操作 > テキスト入力',
        'input_password': 'ブラウザ操作 > パスワード入力',
        'select': 'ブラウザ操作 > ドロップダウン選択',
        'get_text': 'ブラウザ操作 > テキスト取得',
        'get_attribute': 'ブラウザ操作 > 属性取得',
        'execute_script': 'ブラウザ操作 > JavaScript実行',
        'close_tab': 'ブラウザ操作 > タブを閉じる',
        'if': 'フロー制御 > 条件分岐',
        'else_if': 'フロー制御 > 条件分岐',
        'else': 'フロー制御 > 条件分岐',
        'end_if': 'フロー制御 > 条件分岐終了',
        'while': 'フロー制御 > 繰り返し',
        'end_while': 'フロー制御 > 繰り返し終了',
        'try': 'フロー制御 > 例外処理',
        'catch': 'フロー制御 > 例外処理',
        'end_try': 'フロー制御 > 例外処理終了',
        'wait_for_screen_calms': '待機 > 画面安定待機',
        'send_keys': '入力 > キー送信',
        'comment': 'その他 > コメント',
        'script_exit': 'フロー制御 > スクリプト終了',
    }

    def __init__(self, yaml_content: str):
        self.config = yaml.safe_load(yaml_content)
        self.project = self.config.get('project', {})
        self.variables = self.config.get('variables', [])
        self.steps = self.config.get('steps', [])

    def to_markdown(self) -> str:
        """Markdown形式の手順書を生成"""
        lines = []

        # ヘッダー
        lines.append(f"# {self.project.get('name', 'Robo-Pat スクリプト')}")
        lines.append("")
        lines.append(f"> {self.project.get('description', '')}")
        lines.append("")
        lines.append(f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 変数一覧
        if self.variables:
            lines.append("## 変数設定")
            lines.append("")
            lines.append("Robo-Pat DX で以下の変数を作成してください：")
            lines.append("")
            lines.append("| 変数名 | 型 | デフォルト値 |")
            lines.append("|--------|-----|-------------|")
            for var in self.variables:
                lines.append(f"| `{var.get('name', '')}` | {var.get('type', 'STRING')} | {var.get('default', '')} |")
            lines.append("")

        # ステップ一覧
        lines.append("## 手順")
        lines.append("")

        indent_level = 0
        for step in self.steps:
            cmd = step.get('command', '')
            cmd_name = self.COMMAND_NAMES.get(cmd, cmd)
            menu = self.MENU_LOCATIONS.get(cmd, '')
            comment = step.get('comment', '')
            options = step.get('options', {})

            # インデント調整
            if cmd in ['end_if', 'end_while', 'end_try', 'end_loop', 'catch', 'else', 'else_if']:
                indent_level = max(0, indent_level - 1)

            indent = "  " * indent_level

            # ステップ番号と名前
            step_id = step.get('id', '')
            lines.append(f"{indent}### ステップ {step_id}: {cmd_name}")
            lines.append("")

            if comment:
                lines.append(f"{indent}**説明**: {comment}")
                lines.append("")

            if menu:
                lines.append(f"{indent}**メニュー**: `{menu}`")
                lines.append("")

            # オプション詳細
            if options:
                lines.append(f"{indent}**設定内容**:")
                lines.append("")
                for key, value in options.items():
                    if isinstance(value, str) and len(value) > 50:
                        lines.append(f"{indent}- **{key}**:")
                        lines.append(f"{indent}  ```")
                        lines.append(f"{indent}  {value}")
                        lines.append(f"{indent}  ```")
                    else:
                        lines.append(f"{indent}- **{key}**: `{value}`")
                lines.append("")

            # インデント増加
            if cmd in ['if', 'else_if', 'else', 'while', 'try', 'catch', 'loop']:
                indent_level += 1

            lines.append("---")
            lines.append("")

        # フッター
        lines.append("## 備考")
        lines.append("")
        lines.append("- セレクタは実際の画面に合わせて調整してください")
        lines.append("- 待機時間は環境に応じて調整してください")
        lines.append("- 変数は実行前に適切な値を設定してください")
        lines.append("")
        lines.append("---")
        lines.append("*Generated by Robo-Pat AI*")

        return "\n".join(lines)

    def to_html(self) -> str:
        """HTML形式で出力"""
        md_content = self.to_markdown()

        html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.project.get('name', 'Robo-Pat スクリプト')}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        h3 {{ color: #2980b9; background: #ecf0f1; padding: 10px; border-radius: 5px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background: #3498db; color: white; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        code {{ background: #2c3e50; color: #ecf0f1; padding: 2px 6px; border-radius: 3px; }}
        pre {{ background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        blockquote {{ border-left: 4px solid #3498db; margin: 0; padding-left: 15px; color: #666; }}
        hr {{ border: none; border-top: 1px solid #eee; margin: 20px 0; }}
        .step {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .step:hover {{ border-color: #3498db; }}
        ul {{ margin: 10px 0; }}
        li {{ margin: 5px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{self.project.get('name', 'Robo-Pat スクリプト')}</h1>
        <blockquote>{self.project.get('description', '')}</blockquote>
        <p>生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
"""

        # 変数セクション
        if self.variables:
            html += """
        <h2>変数設定</h2>
        <p>Robo-Pat DX で以下の変数を作成してください：</p>
        <table>
            <tr><th>変数名</th><th>型</th><th>デフォルト値</th></tr>
"""
            for var in self.variables:
                html += f"            <tr><td><code>{var.get('name', '')}</code></td><td>{var.get('type', 'STRING')}</td><td>{var.get('default', '')}</td></tr>\n"
            html += "        </table>\n"

        # ステップセクション
        html += "        <h2>手順</h2>\n"

        for step in self.steps:
            cmd = step.get('command', '')
            cmd_name = self.COMMAND_NAMES.get(cmd, cmd)
            menu = self.MENU_LOCATIONS.get(cmd, '')
            comment = step.get('comment', '')
            options = step.get('options', {})
            step_id = step.get('id', '')

            html += f"""
        <div class="step">
            <h3>ステップ {step_id}: {cmd_name}</h3>
"""
            if comment:
                html += f"            <p><strong>説明</strong>: {comment}</p>\n"
            if menu:
                html += f"            <p><strong>メニュー</strong>: <code>{menu}</code></p>\n"

            if options:
                html += "            <p><strong>設定内容</strong>:</p>\n            <ul>\n"
                for key, value in options.items():
                    html += f"                <li><strong>{key}</strong>: <code>{value}</code></li>\n"
                html += "            </ul>\n"

            html += "        </div>\n"

        html += """
        <h2>備考</h2>
        <ul>
            <li>セレクタは実際の画面に合わせて調整してください</li>
            <li>待機時間は環境に応じて調整してください</li>
            <li>変数は実行前に適切な値を設定してください</li>
        </ul>
        <hr>
        <p><em>Generated by Robo-Pat AI</em></p>
    </div>
</body>
</html>
"""
        return html

    def to_json(self) -> str:
        """JSON形式で出力"""
        return json.dumps(self.config, ensure_ascii=False, indent=2)


def export_script(yaml_content: str, output_path: str, format: str = 'markdown'):
    """
    スクリプトをエクスポート

    Args:
        yaml_content: YAML形式のスクリプト
        output_path: 出力先パス
        format: 'markdown', 'html', 'json'
    """
    exporter = ScriptExporter(yaml_content)

    if format == 'html':
        content = exporter.to_html()
    elif format == 'json':
        content = exporter.to_json()
    else:
        content = exporter.to_markdown()

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Exported: {output_path}")


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("Usage: python script_exporter.py <input.yaml> <output> [format]")
        print("  format: markdown (default), html, json")
        sys.exit(1)

    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        yaml_content = f.read()

    output_path = sys.argv[2]
    fmt = sys.argv[3] if len(sys.argv) > 3 else 'markdown'

    export_script(yaml_content, output_path, fmt)
