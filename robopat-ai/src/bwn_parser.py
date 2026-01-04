#!/usr/bin/env python3
"""
BWN Parser - Robo-Pat .bwn ファイルを解析してYAMLに変換
"""

import struct
import re
import yaml
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path


@dataclass
class Command:
    """Robo-Pat コマンド"""
    id: int
    type: str
    class_name: str
    options: Dict[str, Any] = field(default_factory=dict)
    comment: str = ""


@dataclass
class RoboPatScript:
    """Robo-Pat スクリプト"""
    project_name: str
    tab_title: str = "実行タブ"
    commands: List[Command] = field(default_factory=list)
    variables: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BWNParser:
    """
    .bwn ファイル（Javaシリアライズ形式）をパース
    """

    # コマンドタイプマッピング
    COMMAND_MAP = {
        'OpenChrome': 'open_chrome',
        'Click': 'click',
        'InputText': 'input_text',
        'InputPassword': 'input_password',
        'InputCalendar': 'input_calendar',
        'Select': 'select',
        'GetText': 'get_text',
        'GetAttribute': 'get_attribute',
        'ExecuteScript': 'execute_script',
        'NavigateBack': 'navigate_back',
        'CloseTab': 'close_tab',
        'Check': 'check',
        'EvaluateIf': 'if',
        'EvaluateElseIf': 'else_if',
        'EvaluateElse': 'else',
        'EvaluateEndIf': 'end_if',
        'EvaluateWhile': 'while',
        'EvaluateEndWhile': 'end_while',
        'EvaluateWhileStart': 'while',
        'EvaluateWhileEnd': 'end_while',
        'OpenLoop': 'loop',
        'CloseFlow': 'end_loop',
        'Break': 'break',
        'Try': 'try',
        'Catch': 'catch',
        'EndTry': 'end_try',
        'SwitchWindow': 'switch_window',
        'GoToTab': 'go_to_tab',
        'SendKeys': 'send_keys',
        'Paste': 'paste',
        'Type': 'type',
        'Find': 'find',
        'WaitForScreenCalms': 'wait_for_screen_calms',
        'Comment': 'comment',
        'ScriptExit': 'script_exit',
        'SendMailV2': 'send_mail',
        'ScreenRecordStart': 'screen_record_start',
        'ScreenRecordEnd': 'screen_record_end',
        'MonitoringStart': 'monitoring_start',
        'MonitoringEnd': 'monitoring_end',
        'EvaluateBranchStart': 'if',
        'EvaluateBranchEnd': 'end_if',
        'OpenFlow': 'flow_start',
        'Metadata': 'metadata',
        'Error': 'error',
        'Close': 'close',
    }

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.data = b''
        self.pos = 0
        self.strings_cache: List[str] = []

    def parse(self) -> RoboPatScript:
        """メインパース処理"""
        with open(self.file_path, 'rb') as f:
            self.data = f.read()

        # Javaシリアライズのマジックナンバー確認
        if self.data[:2] != b'\xac\xed':
            raise ValueError("Not a Java serialized file")

        # 文字列を抽出
        self._extract_strings()

        # プロジェクト情報を抽出
        project_name = self._find_project_name()
        tab_title = self._find_tab_title()

        # コマンドを抽出
        commands = self._extract_commands()

        return RoboPatScript(
            project_name=project_name,
            tab_title=tab_title,
            commands=commands
        )

    def _extract_strings(self):
        """バイナリから文字列を抽出"""
        i = 0
        while i < len(self.data) - 2:
            # UTF-8文字列のプレフィックス（2バイト長）
            length = struct.unpack('>H', self.data[i:i+2])[0]
            if 1 <= length <= 500 and i + 2 + length <= len(self.data):
                try:
                    s = self.data[i+2:i+2+length].decode('utf-8')
                    if s.isprintable() or any('\u3000' <= c <= '\u9fff' for c in s):
                        self.strings_cache.append(s)
                except:
                    pass
            i += 1

    def _find_project_name(self) -> str:
        """プロジェクト名を検索"""
        for i, s in enumerate(self.strings_cache):
            if s == 'projectName' and i + 1 < len(self.strings_cache):
                return self.strings_cache[i + 1]
        return "Unknown"

    def _find_tab_title(self) -> str:
        """タブタイトルを検索"""
        for i, s in enumerate(self.strings_cache):
            if s == 'tabTitle' and i + 1 < len(self.strings_cache):
                return self.strings_cache[i + 1]
        return "実行タブ"

    def _extract_commands(self) -> List[Command]:
        """コマンドリストを抽出"""
        commands = []
        command_id = 1

        # クラス名からコマンドを検出
        for s in self.strings_cache:
            if 'com.asirrera.brownie.ide' in s:
                # クラス名からコマンドタイプを抽出
                match = re.search(r'\.([A-Z][a-zA-Z]+)$', s)
                if match:
                    class_name = match.group(1)
                    if class_name in self.COMMAND_MAP:
                        cmd_type = self.COMMAND_MAP[class_name]
                        commands.append(Command(
                            id=command_id,
                            type=cmd_type,
                            class_name=class_name
                        ))
                        command_id += 1

        return commands

    def to_yaml(self) -> str:
        """YAMLに変換"""
        script = self.parse()

        output = {
            'project': {
                'name': script.project_name,
                'description': '',
            },
            'variables': [],
            'steps': []
        }

        for cmd in script.commands:
            step = {
                'id': cmd.id,
                'command': cmd.type,
            }
            if cmd.options:
                step['options'] = cmd.options
            if cmd.comment:
                step['comment'] = cmd.comment
            output['steps'].append(step)

        return yaml.dump(output, allow_unicode=True, sort_keys=False, default_flow_style=False)

    def to_json(self) -> str:
        """JSONに変換"""
        script = self.parse()

        output = {
            'project': {
                'name': script.project_name,
                'description': '',
            },
            'variables': [],
            'steps': [
                {
                    'id': cmd.id,
                    'command': cmd.type,
                    'class_name': cmd.class_name,
                    'options': cmd.options,
                }
                for cmd in script.commands
            ]
        }

        return json.dumps(output, ensure_ascii=False, indent=2)


def parse_bwn(file_path: str, output_format: str = 'yaml') -> str:
    """
    .bwn ファイルをパースして変換

    Args:
        file_path: .bwn ファイルパス
        output_format: 'yaml' or 'json'

    Returns:
        変換された文字列
    """
    parser = BWNParser(file_path)
    if output_format == 'json':
        return parser.to_json()
    return parser.to_yaml()


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python bwn_parser.py <file.bwn> [yaml|json]")
        sys.exit(1)

    file_path = sys.argv[1]
    fmt = sys.argv[2] if len(sys.argv) > 2 else 'yaml'
    print(parse_bwn(file_path, fmt))
