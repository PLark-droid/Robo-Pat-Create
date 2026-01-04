#!/usr/bin/env python3
"""
BWN Compiler - YAML から Robo-Pat .bwn ファイルを生成

注意: Java シリアライズ形式は複雑なため、テンプレートベースのアプローチを使用
"""

import struct
import yaml
import json
import io
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, BinaryIO
from pathlib import Path
import hashlib


# Java シリアライズ定数
STREAM_MAGIC = 0xaced
STREAM_VERSION = 5
TC_NULL = 0x70
TC_OBJECT = 0x73
TC_CLASS = 0x76
TC_CLASSDESC = 0x72
TC_ENDBLOCKDATA = 0x78
TC_STRING = 0x74
TC_ARRAY = 0x75
TC_REFERENCE = 0x71
TC_BLOCKDATA = 0x77


@dataclass
class JavaString:
    """Java String オブジェクト"""
    value: str

    def serialize(self, stream: BinaryIO, handles: Dict) -> int:
        """シリアライズ"""
        encoded = self.value.encode('utf-8')
        if len(encoded) <= 0xFFFF:
            stream.write(bytes([TC_STRING]))
            stream.write(struct.pack('>H', len(encoded)))
            stream.write(encoded)
        else:
            # Long string
            stream.write(bytes([0x7c]))  # TC_LONGSTRING
            stream.write(struct.pack('>Q', len(encoded)))
            stream.write(encoded)
        return len(handles) + 1


class BWNCompiler:
    """
    YAML から .bwn ファイルを生成するコンパイラ
    """

    # YAML コマンド -> Java クラス名のマッピング
    COMMAND_CLASS_MAP = {
        'open_chrome': 'com.asirrera.brownie.ide.web.command.openChrome.OpenChrome',
        'click': 'com.asirrera.brownie.ide.web.command.click.Click',
        'input_text': 'com.asirrera.brownie.ide.web.command.inputText.InputText',
        'input_password': 'com.asirrera.brownie.ide.web.command.inputPassword.InputPassword',
        'input_calendar': 'com.asirrera.brownie.ide.web.command.inputCalendar.InputCalendar',
        'select': 'com.asirrera.brownie.ide.web.command.select.Select',
        'get_text': 'com.asirrera.brownie.ide.web.command.getText.GetText',
        'get_attribute': 'com.asirrera.brownie.ide.web.command.getAttribute.GetAttribute',
        'execute_script': 'com.asirrera.brownie.ide.web.command.executeScript.ExecuteScript',
        'navigate_back': 'com.asirrera.brownie.ide.web.command.navigateBack.NavigateBack',
        'close_tab': 'com.asirrera.brownie.ide.web.command.closeTab.CloseTab',
        'check': 'com.asirrera.brownie.ide.web.command.check.Check',
        'if': 'com.asirrera.brownie.ide.command.evaluate.EvaluateBranchStart',
        'else_if': 'com.asirrera.brownie.ide.command.evaluate.EvaluateElseIf',
        'else': 'com.asirrera.brownie.ide.command.evaluate.EvaluateElse',
        'end_if': 'com.asirrera.brownie.ide.command.evaluate.EvaluateBranchEnd',
        'while': 'com.asirrera.brownie.ide.command.evaluate.EvaluateWhileStart',
        'end_while': 'com.asirrera.brownie.ide.command.evaluate.EvaluateWhileEnd',
        'loop': 'com.asirrera.brownie.ide.command.OpenLoop',
        'end_loop': 'com.asirrera.brownie.ide.command.CloseFlow',
        'break': 'com.asirrera.brownie.ide.command.Break',
        'try': 'com.asirrera.brownie.ide.command.Try',
        'catch': 'com.asirrera.brownie.ide.command.Catch',
        'end_try': 'com.asirrera.brownie.ide.command.EndTry',
        'switch_window': 'com.asirrera.brownie.ide.command.SwitchWindow',
        'go_to_tab': 'com.asirrera.brownie.ide.command.GoToTab',
        'send_keys': 'com.asirrera.brownie.ide.command.SendKeys',
        'paste': 'com.asirrera.brownie.ide.command.Paste',
        'type': 'com.asirrera.brownie.ide.command.Type',
        'find': 'com.asirrera.brownie.ide.command.Find',
        'wait_for_screen_calms': 'com.asirrera.brownie.ide.command.WaitForScreenCalms',
        'comment': 'com.asirrera.brownie.ide.command.Comment',
        'script_exit': 'com.asirrera.brownie.ide.command.ScriptExit',
        'send_mail': 'com.asirrera.brownie.ide.command.SendMailV2',
        'screen_record_start': 'com.asirrera.brownie.ide.command.screen.record.ScreenRecordStart',
        'screen_record_end': 'com.asirrera.brownie.ide.command.screen.record.ScreenRecordEnd',
    }

    def __init__(self, yaml_path: Optional[str] = None, yaml_content: Optional[str] = None):
        if yaml_path:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        elif yaml_content:
            self.config = yaml.safe_load(yaml_content)
        else:
            raise ValueError("yaml_path or yaml_content required")

        self.handle_count = 0
        self.handles: Dict[int, Any] = {}

    def compile(self, output_path: str):
        """YAMLを.bwnにコンパイル"""
        with open(output_path, 'wb') as f:
            self._write_stream(f)

    def compile_to_bytes(self) -> bytes:
        """YAMLをバイト列にコンパイル"""
        stream = io.BytesIO()
        self._write_stream(stream)
        return stream.getvalue()

    def _write_stream(self, stream: BinaryIO):
        """Java シリアライズストリームを書き込み"""
        # Magic number and version
        stream.write(struct.pack('>H', STREAM_MAGIC))
        stream.write(struct.pack('>H', STREAM_VERSION))

        # Root HashMap object
        self._write_hashmap(stream)

    def _write_string(self, stream: BinaryIO, value: str):
        """文字列を書き込み"""
        encoded = value.encode('utf-8')
        stream.write(bytes([TC_STRING]))
        stream.write(struct.pack('>H', len(encoded)))
        stream.write(encoded)

    def _write_hashmap(self, stream: BinaryIO):
        """HashMap オブジェクトを書き込み"""
        # HashMap class descriptor
        stream.write(bytes([TC_OBJECT]))
        stream.write(bytes([TC_CLASSDESC]))

        # Class name: java.util.HashMap
        class_name = b'java.util.HashMap'
        stream.write(struct.pack('>H', len(class_name)))
        stream.write(class_name)

        # Serial version UID
        stream.write(struct.pack('>q', 362498820763181265))  # HashMap's serialVersionUID

        # Class flags: SC_SERIALIZABLE | SC_WRITE_METHOD
        stream.write(bytes([0x03]))

        # Fields count
        stream.write(struct.pack('>H', 2))

        # Field 1: float loadFactor
        stream.write(bytes([ord('F')]))  # Float type
        field_name = b'loadFactor'
        stream.write(struct.pack('>H', len(field_name)))
        stream.write(field_name)

        # Field 2: int threshold
        stream.write(bytes([ord('I')]))  # Int type
        field_name = b'threshold'
        stream.write(struct.pack('>H', len(field_name)))
        stream.write(field_name)

        # No class annotations
        stream.write(bytes([TC_ENDBLOCKDATA]))

        # No superclass
        stream.write(bytes([TC_NULL]))

        # Field values
        stream.write(struct.pack('>f', 0.75))  # loadFactor = 0.75
        stream.write(struct.pack('>i', 12))    # threshold = 12

        # Block data for HashMap entries
        stream.write(bytes([TC_BLOCKDATA]))
        stream.write(bytes([8]))  # 8 bytes follow

        # HashMap internal: capacity and size
        stream.write(struct.pack('>i', 16))  # capacity
        stream.write(struct.pack('>i', 3))   # size (3 entries)

        # Entry 1: projectName
        self._write_string(stream, 'projectName')
        self._write_string(stream, self.config.get('project', {}).get('name', 'RoboPat Script'))

        # Entry 2: tabTitle
        self._write_string(stream, 'tabTitle')
        self._write_string(stream, self.config.get('project', {}).get('tab_title', '実行タブ'))

        # Entry 3: commandData (placeholder - simplified)
        self._write_string(stream, 'commandData')
        self._write_command_list(stream)

        stream.write(bytes([TC_ENDBLOCKDATA]))

    def _write_command_list(self, stream: BinaryIO):
        """コマンドリストを書き込み"""
        steps = self.config.get('steps', [])

        # ArrayList wrapper
        stream.write(bytes([TC_OBJECT]))
        stream.write(bytes([TC_CLASSDESC]))

        class_name = b'java.util.ArrayList'
        stream.write(struct.pack('>H', len(class_name)))
        stream.write(class_name)

        # ArrayList serialVersionUID
        stream.write(struct.pack('>q', 8683452581122892189))

        # Flags
        stream.write(bytes([0x03]))

        # Fields count: 1 (size)
        stream.write(struct.pack('>H', 1))

        # Field: int size
        stream.write(bytes([ord('I')]))
        field_name = b'size'
        stream.write(struct.pack('>H', len(field_name)))
        stream.write(field_name)

        stream.write(bytes([TC_ENDBLOCKDATA]))
        stream.write(bytes([TC_NULL]))

        # Size value
        stream.write(struct.pack('>i', len(steps)))

        # Array data
        stream.write(bytes([TC_BLOCKDATA]))
        stream.write(bytes([4]))
        stream.write(struct.pack('>i', len(steps)))

        # Write each command (simplified - just the class reference)
        for step in steps:
            cmd_type = step.get('command', 'comment')
            class_name = self.COMMAND_CLASS_MAP.get(cmd_type, 'com.asirrera.brownie.ide.command.Comment')

            stream.write(bytes([TC_OBJECT]))
            stream.write(bytes([TC_CLASSDESC]))

            class_bytes = class_name.encode('utf-8')
            stream.write(struct.pack('>H', len(class_bytes)))
            stream.write(class_bytes)

            # Placeholder serial UID
            stream.write(struct.pack('>q', 1))
            stream.write(bytes([0x02]))  # SC_SERIALIZABLE
            stream.write(struct.pack('>H', 0))  # No fields
            stream.write(bytes([TC_ENDBLOCKDATA]))
            stream.write(bytes([TC_NULL]))

        stream.write(bytes([TC_ENDBLOCKDATA]))


def compile_yaml_to_bwn(yaml_path: str, output_path: str):
    """
    YAMLファイルを.bwnにコンパイル

    Args:
        yaml_path: 入力YAMLファイルパス
        output_path: 出力.bwnファイルパス
    """
    compiler = BWNCompiler(yaml_path=yaml_path)
    compiler.compile(output_path)
    print(f"Compiled: {yaml_path} -> {output_path}")


def compile_yaml_string_to_bwn(yaml_content: str, output_path: str):
    """
    YAML文字列を.bwnにコンパイル

    Args:
        yaml_content: YAML文字列
        output_path: 出力.bwnファイルパス
    """
    compiler = BWNCompiler(yaml_content=yaml_content)
    compiler.compile(output_path)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("Usage: python bwn_compiler.py <input.yaml> <output.bwn>")
        sys.exit(1)

    compile_yaml_to_bwn(sys.argv[1], sys.argv[2])
