#!/usr/bin/env python3
"""
BWN Compiler V2 - 完全なJavaシリアライズ形式のBWNファイルを生成

このコンパイラは、Robo-Pat DXで読み込み可能な.bwnファイルを生成します。
"""

import struct
import io
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field


# =============================================================================
# Java Serialization Protocol Constants
# =============================================================================

STREAM_MAGIC = 0xACED
STREAM_VERSION = 5

TC_NULL = 0x70
TC_REFERENCE = 0x71
TC_CLASSDESC = 0x72
TC_OBJECT = 0x73
TC_STRING = 0x74
TC_ARRAY = 0x75
TC_CLASS = 0x76
TC_BLOCKDATA = 0x77
TC_ENDBLOCKDATA = 0x78
TC_RESET = 0x79
TC_BLOCKDATALONG = 0x7A
TC_EXCEPTION = 0x7B
TC_LONGSTRING = 0x7C
TC_PROXYCLASSDESC = 0x7D
TC_ENUM = 0x7E

BASE_WIRE_HANDLE = 0x7E0000

SC_WRITE_METHOD = 0x01
SC_SERIALIZABLE = 0x02
SC_EXTERNALIZABLE = 0x04
SC_BLOCK_DATA = 0x08
SC_ENUM = 0x10


# =============================================================================
# Known Serial Version UIDs (extracted from existing .bwn file)
# =============================================================================

SERIAL_UIDS = {
    'java.util.HashMap': 362498820763181265,
    'java.util.AbstractMap': 4828766684233562441,
    'java.util.ArrayList': 8683452581122892189,
    'java.util.AbstractList': 4083306618545678451,
    'java.util.AbstractCollection': 8925815256423158682,
    'java.util.concurrent.CopyOnWriteArrayList': 8673264195747942595,
    'java.util.Collections$SynchronizedMap': 1978198479659022715,
    'java.util.Collections$SynchronizedCollection': 3053995032091335093,
    'java.util.Collections$SynchronizedList': -1472766899164520507,

    # Robo-Pat command classes (extracted from dump)
    'com.asirrera.brownie.ide.command.Argument': -8244499117953890091,
    'com.asirrera.brownie.ide.command.BrownieCommand': -416088768,
    'com.asirrera.brownie.ide.command.FlowCommand': 1,
    'com.asirrera.brownie.ide.command.Comment': 1,
    'com.asirrera.brownie.ide.command.GoToTab': 1,
    'com.asirrera.brownie.ide.command.OpenFlow': 1,
    'com.asirrera.brownie.ide.command.CloseFlow': 1,
    'com.asirrera.brownie.ide.command.OpenLoop': 1,
    'com.asirrera.brownie.ide.command.Try': 1,
    'com.asirrera.brownie.ide.command.Catch': 1,
    'com.asirrera.brownie.ide.command.EndTry': 1,
    'com.asirrera.brownie.ide.command.Break': 1,
    'com.asirrera.brownie.ide.command.SwitchWindow': 1,
    'com.asirrera.brownie.ide.command.SendKeys': 1,
    'com.asirrera.brownie.ide.command.Paste': 1,
    'com.asirrera.brownie.ide.command.Type': 1,
    'com.asirrera.brownie.ide.command.Find': 1,
    'com.asirrera.brownie.ide.command.WaitForScreenCalms': 1,
    'com.asirrera.brownie.ide.command.ScriptExit': 1,
    'com.asirrera.brownie.ide.command.SendMailV2': 1,
    'com.asirrera.brownie.ide.command.Metadata': 1,
    'com.asirrera.brownie.ide.command.Arguments': 1,
    'com.asirrera.brownie.ide.command.screen.record.ScreenRecordStart': 1,
    'com.asirrera.brownie.ide.command.screen.record.ScreenRecordEnd': 1,
    'com.asirrera.brownie.ide.command.evaluate.EvaluateBranchStart': 1,
    'com.asirrera.brownie.ide.command.evaluate.EvaluateBranchEnd': 1,
    'com.asirrera.brownie.ide.command.evaluate.EvaluateElse': 1,
    'com.asirrera.brownie.ide.command.evaluate.EvaluateElseIf': 1,
    'com.asirrera.brownie.ide.command.evaluate.EvaluateWhileStart': 1,
    'com.asirrera.brownie.ide.command.evaluate.EvaluateWhileEnd': 1,

    # Web commands
    'com.asirrera.brownie.ide.web.command.WebCommand': 1,
    'com.asirrera.brownie.ide.web.command.FindElementCommand': 1,
    'com.asirrera.brownie.ide.web.command.openChrome.OpenChrome': 1,
    'com.asirrera.brownie.ide.web.command.click.Click': 1,
    'com.asirrera.brownie.ide.web.command.inputText.InputText': 1,
    'com.asirrera.brownie.ide.web.command.inputPassword.InputPassword': 1,
    'com.asirrera.brownie.ide.web.command.select.Select': 1,
    'com.asirrera.brownie.ide.web.command.getText.GetText': 1,
    'com.asirrera.brownie.ide.web.command.getAttribute.GetAttribute': 1,
    'com.asirrera.brownie.ide.web.command.executeScript.ExecuteScript': 1,
    'com.asirrera.brownie.ide.web.command.closeTab.CloseTab': 1,
    'com.asirrera.brownie.ide.web.command.navigateBack.NavigateBack': 1,
    'com.asirrera.brownie.ide.web.command.check.Check': 1,
}


# =============================================================================
# Java Object Output Stream
# =============================================================================

class JavaObjectOutputStream:
    """Java互換のオブジェクトシリアライザ"""

    def __init__(self):
        self.buffer = io.BytesIO()
        self.handle_counter = BASE_WIRE_HANDLE
        self.object_handles: Dict[int, int] = {}  # id(obj) -> handle
        self.class_handles: Dict[str, int] = {}   # class_name -> handle
        self.string_handles: Dict[str, int] = {}  # string value -> handle

        # Write stream header
        self.buffer.write(struct.pack('>H', STREAM_MAGIC))
        self.buffer.write(struct.pack('>H', STREAM_VERSION))

    def _next_handle(self) -> int:
        handle = self.handle_counter
        self.handle_counter += 1
        return handle

    def _write_byte(self, v: int):
        self.buffer.write(bytes([v & 0xFF]))

    def _write_short(self, v: int):
        self.buffer.write(struct.pack('>h', v))

    def _write_ushort(self, v: int):
        self.buffer.write(struct.pack('>H', v))

    def _write_int(self, v: int):
        self.buffer.write(struct.pack('>i', v))

    def _write_long(self, v: int):
        if v < 0:
            v = v & 0xFFFFFFFFFFFFFFFF
        self.buffer.write(struct.pack('>Q', v))

    def _write_float(self, v: float):
        self.buffer.write(struct.pack('>f', v))

    def _write_double(self, v: float):
        self.buffer.write(struct.pack('>d', v))

    def _write_bool(self, v: bool):
        self._write_byte(1 if v else 0)

    def _write_utf(self, s: str):
        encoded = s.encode('utf-8')
        self._write_ushort(len(encoded))
        self.buffer.write(encoded)

    def write_null(self):
        self._write_byte(TC_NULL)

    def write_reference(self, handle: int):
        self._write_byte(TC_REFERENCE)
        self._write_int(handle)

    def write_string(self, s: str) -> int:
        """Write a string, using reference if already written"""
        if s in self.string_handles:
            self.write_reference(self.string_handles[s])
            return self.string_handles[s]

        self._write_byte(TC_STRING)
        handle = self._next_handle()
        self.string_handles[s] = handle
        self._write_utf(s)
        return handle

    def write_class_desc(
        self,
        class_name: str,
        serial_uid: int,
        flags: int,
        fields: List[Tuple],
        super_class: Optional[Tuple] = None,
        skip_if_exists: bool = True
    ) -> int:
        """
        Write a class descriptor

        fields: List of (type_char, field_name) or (type_char, field_name, type_string)
        """
        if skip_if_exists and class_name in self.class_handles:
            self.write_reference(self.class_handles[class_name])
            return self.class_handles[class_name]

        self._write_byte(TC_CLASSDESC)
        self._write_utf(class_name)
        self._write_long(serial_uid)

        handle = self._next_handle()
        self.class_handles[class_name] = handle

        self._write_byte(flags)
        self._write_short(len(fields))

        for f in fields:
            type_char = f[0]
            field_name = f[1]
            self._write_byte(ord(type_char))
            self._write_utf(field_name)
            if type_char in ('L', '['):
                type_string = f[2] if len(f) > 2 else 'Ljava/lang/Object;'
                self.write_string(type_string)

        self._write_byte(TC_ENDBLOCKDATA)

        if super_class:
            self.write_class_desc(*super_class)
        else:
            self.write_null()

        return handle

    def write_hashmap(self, data: Dict, load_factor: float = 0.75) -> int:
        """Write a HashMap"""
        obj_id = id(data)
        if obj_id in self.object_handles:
            self.write_reference(self.object_handles[obj_id])
            return self.object_handles[obj_id]

        self._write_byte(TC_OBJECT)

        size = len(data)
        capacity = 16
        while capacity * load_factor < size:
            capacity *= 2
        threshold = int(capacity * load_factor)

        # HashMap class desc
        self.write_class_desc(
            'java.util.HashMap',
            SERIAL_UIDS['java.util.HashMap'],
            SC_SERIALIZABLE | SC_WRITE_METHOD,
            [('F', 'loadFactor'), ('I', 'threshold')],
            ('java.util.AbstractMap', SERIAL_UIDS['java.util.AbstractMap'],
             SC_SERIALIZABLE, [], None)
        )

        handle = self._next_handle()
        self.object_handles[obj_id] = handle

        # Fields
        self._write_float(load_factor)
        self._write_int(threshold)

        # writeObject data: capacity, size, then key-value pairs
        block = struct.pack('>ii', capacity, size)
        self._write_byte(TC_BLOCKDATA)
        self._write_byte(len(block))
        self.buffer.write(block)

        for key, value in data.items():
            self.write_object(key)
            self.write_object(value)

        self._write_byte(TC_ENDBLOCKDATA)

        return handle

    def write_arraylist(self, data: List) -> int:
        """Write an ArrayList"""
        obj_id = id(data)
        if obj_id in self.object_handles:
            self.write_reference(self.object_handles[obj_id])
            return self.object_handles[obj_id]

        self._write_byte(TC_OBJECT)

        size = len(data)

        # ArrayList class desc
        self.write_class_desc(
            'java.util.ArrayList',
            SERIAL_UIDS['java.util.ArrayList'],
            SC_SERIALIZABLE | SC_WRITE_METHOD,
            [('I', 'size')],
            ('java.util.AbstractList', SERIAL_UIDS['java.util.AbstractList'],
             SC_SERIALIZABLE, [],
             ('java.util.AbstractCollection', SERIAL_UIDS['java.util.AbstractCollection'],
              SC_SERIALIZABLE, [], None))
        )

        handle = self._next_handle()
        self.object_handles[obj_id] = handle

        # Field: size
        self._write_int(size)

        # writeObject: capacity + elements
        block = struct.pack('>i', size)
        self._write_byte(TC_BLOCKDATA)
        self._write_byte(len(block))
        self.buffer.write(block)

        for item in data:
            self.write_object(item)

        self._write_byte(TC_ENDBLOCKDATA)

        return handle

    def write_copyonwritearraylist(self, data: List) -> int:
        """Write a CopyOnWriteArrayList"""
        obj_id = id(data)
        if obj_id in self.object_handles:
            self.write_reference(self.object_handles[obj_id])
            return self.object_handles[obj_id]

        self._write_byte(TC_OBJECT)

        # CopyOnWriteArrayList class desc
        self.write_class_desc(
            'java.util.concurrent.CopyOnWriteArrayList',
            SERIAL_UIDS['java.util.concurrent.CopyOnWriteArrayList'],
            SC_SERIALIZABLE | SC_WRITE_METHOD,
            [],  # No serializable fields
            None
        )

        handle = self._next_handle()
        self.object_handles[obj_id] = handle

        # writeObject: length + elements
        size = len(data)
        block = struct.pack('>i', size)
        self._write_byte(TC_BLOCKDATA)
        self._write_byte(len(block))
        self.buffer.write(block)

        for item in data:
            self.write_object(item)

        self._write_byte(TC_ENDBLOCKDATA)

        return handle

    def write_synchronized_map(self, inner_map: Dict) -> int:
        """Write a Collections.SynchronizedMap wrapping a HashMap"""
        self._write_byte(TC_OBJECT)

        # SynchronizedMap class desc
        self.write_class_desc(
            'java.util.Collections$SynchronizedMap',
            SERIAL_UIDS['java.util.Collections$SynchronizedMap'],
            SC_SERIALIZABLE,
            [
                ('L', 'm', 'Ljava/util/Map;'),
                ('L', 'mutex', 'Ljava/lang/Object;'),
            ],
            None
        )

        handle = self._next_handle()

        # Write the inner HashMap
        inner_handle = self.write_hashmap(inner_map)

        # mutex = this (reference to this SynchronizedMap)
        self.write_reference(handle)

        return handle

    def write_synchronized_list(self, inner_list: List) -> int:
        """Write a Collections.SynchronizedList wrapping an ArrayList"""
        self._write_byte(TC_OBJECT)

        # SynchronizedList class desc
        self.write_class_desc(
            'java.util.Collections$SynchronizedList',
            SERIAL_UIDS['java.util.Collections$SynchronizedList'],
            SC_SERIALIZABLE,
            [('L', 'list', 'Ljava/util/List;')],
            ('java.util.Collections$SynchronizedCollection',
             SERIAL_UIDS['java.util.Collections$SynchronizedCollection'],
             SC_SERIALIZABLE,
             [
                 ('L', 'c', 'Ljava/util/Collection;'),
                 ('L', 'mutex', 'Ljava/lang/Object;'),
             ],
             None)
        )

        handle = self._next_handle()

        # Fields from SynchronizedCollection: c, mutex
        inner_handle = self.write_arraylist(inner_list)
        self.write_reference(handle)  # mutex = this

        # Field from SynchronizedList: list (same as c, so reference)
        self.write_reference(inner_handle)

        return handle

    def write_object(self, obj: Any) -> Optional[int]:
        """Write any supported object"""
        if obj is None:
            self.write_null()
            return None

        if isinstance(obj, str):
            return self.write_string(obj)
        elif isinstance(obj, bool):
            # For primitive boolean in object context, we need Boolean wrapper
            # But for field values, we write raw bytes
            raise ValueError("Boolean objects not supported, use primitive")
        elif isinstance(obj, int):
            # Would need Integer wrapper
            raise ValueError("Integer objects not supported, use primitive")
        elif isinstance(obj, float):
            raise ValueError("Float objects not supported, use primitive")
        elif isinstance(obj, dict):
            return self.write_hashmap(obj)
        elif isinstance(obj, list):
            return self.write_arraylist(obj)
        else:
            raise ValueError(f"Unsupported type: {type(obj)}")

    def get_bytes(self) -> bytes:
        return self.buffer.getvalue()

    def save(self, path: str):
        with open(path, 'wb') as f:
            f.write(self.get_bytes())


# =============================================================================
# BWN Script Builder
# =============================================================================

class BWNScriptBuilder:
    """
    Robo-Pat BWNスクリプトを構築するビルダー
    """

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.tabs: List[Dict] = []

    def add_tab(self, title: str, commands: List[Dict]):
        """
        タブを追加

        Args:
            title: タブタイトル（例: "実行タブ"）
            commands: コマンドリスト
        """
        self.tabs.append({
            'tabTitle': title,
            'commands': commands,
        })

    def build(self) -> bytes:
        """BWNバイト列を生成"""
        writer = JavaObjectOutputStream()

        # Build script data structure
        script_data = []
        for tab in self.tabs:
            script_data.append(tab)

        # Root HashMap
        root = {
            'projectName': self.project_name,
            'scriptData': script_data,
        }

        # Write as custom structure
        self._write_root(writer, root)

        return writer.get_bytes()

    def _write_root(self, writer: JavaObjectOutputStream, root: Dict):
        """Write root HashMap with custom structure"""
        writer._write_byte(TC_OBJECT)

        # HashMap class desc
        writer.write_class_desc(
            'java.util.HashMap',
            SERIAL_UIDS['java.util.HashMap'],
            SC_SERIALIZABLE | SC_WRITE_METHOD,
            [('F', 'loadFactor'), ('I', 'threshold')],
            ('java.util.AbstractMap', SERIAL_UIDS['java.util.AbstractMap'],
             SC_SERIALIZABLE, [], None)
        )

        handle = writer._next_handle()

        # Fields
        writer._write_float(0.75)
        writer._write_int(12)

        # writeObject: capacity, size, then entries
        size = 2  # projectName and scriptData
        capacity = 16
        block = struct.pack('>ii', capacity, size)
        writer._write_byte(TC_BLOCKDATA)
        writer._write_byte(len(block))
        writer.buffer.write(block)

        # Entry 1: projectName
        writer.write_string('projectName')
        writer.write_string(root['projectName'])

        # Entry 2: scriptData
        writer.write_string('scriptData')
        self._write_script_data(writer, root['scriptData'])

        writer._write_byte(TC_ENDBLOCKDATA)

    def _write_script_data(self, writer: JavaObjectOutputStream, tabs: List):
        """Write scriptData as CopyOnWriteArrayList of SynchronizedMaps"""
        writer._write_byte(TC_OBJECT)

        writer.write_class_desc(
            'java.util.concurrent.CopyOnWriteArrayList',
            SERIAL_UIDS['java.util.concurrent.CopyOnWriteArrayList'],
            SC_SERIALIZABLE | SC_WRITE_METHOD,
            [],
            None
        )

        handle = writer._next_handle()

        # writeObject: length + elements
        block = struct.pack('>i', len(tabs))
        writer._write_byte(TC_BLOCKDATA)
        writer._write_byte(len(block))
        writer.buffer.write(block)

        for tab in tabs:
            self._write_tab(writer, tab)

        writer._write_byte(TC_ENDBLOCKDATA)

    def _write_tab(self, writer: JavaObjectOutputStream, tab: Dict):
        """Write a tab as SynchronizedMap"""
        writer._write_byte(TC_OBJECT)

        writer.write_class_desc(
            'java.util.Collections$SynchronizedMap',
            SERIAL_UIDS['java.util.Collections$SynchronizedMap'],
            SC_SERIALIZABLE,
            [
                ('L', 'm', 'Ljava/util/Map;'),
                ('L', 'mutex', 'Ljava/lang/Object;'),
            ],
            None
        )

        sync_handle = writer._next_handle()

        # Inner HashMap
        self._write_tab_hashmap(writer, tab, sync_handle)

        # mutex = this SynchronizedMap
        writer.write_reference(sync_handle)

    def _write_tab_hashmap(self, writer: JavaObjectOutputStream, tab: Dict, sync_handle: int):
        """Write inner HashMap for tab"""
        writer._write_byte(TC_OBJECT)

        writer.write_class_desc(
            'java.util.HashMap',
            SERIAL_UIDS['java.util.HashMap'],
            SC_SERIALIZABLE | SC_WRITE_METHOD,
            [('F', 'loadFactor'), ('I', 'threshold')],
            ('java.util.AbstractMap', SERIAL_UIDS['java.util.AbstractMap'],
             SC_SERIALIZABLE, [], None)
        )

        handle = writer._next_handle()

        writer._write_float(0.75)
        writer._write_int(12)

        # 3 entries: MergeInfoData, tabTitle, commandData
        block = struct.pack('>ii', 16, 3)
        writer._write_byte(TC_BLOCKDATA)
        writer._write_byte(len(block))
        writer.buffer.write(block)

        # MergeInfoData
        writer.write_string('MergeInfoData')
        writer.write_arraylist([])  # Empty ArrayList

        # tabTitle
        writer.write_string('tabTitle')
        writer.write_string(tab['tabTitle'])

        # commandData
        writer.write_string('commandData')
        commands = tab.get('commands', tab.get('commandData', []))
        self._write_command_data(writer, commands, sync_handle)

        writer._write_byte(TC_ENDBLOCKDATA)

    def _write_command_data(self, writer: JavaObjectOutputStream, commands: List, sync_handle: int):
        """Write commandData as SynchronizedList"""
        writer._write_byte(TC_OBJECT)

        writer.write_class_desc(
            'java.util.Collections$SynchronizedList',
            SERIAL_UIDS['java.util.Collections$SynchronizedList'],
            SC_SERIALIZABLE,
            [('L', 'list', 'Ljava/util/List;')],
            ('java.util.Collections$SynchronizedCollection',
             SERIAL_UIDS['java.util.Collections$SynchronizedCollection'],
             SC_SERIALIZABLE,
             [
                 ('L', 'c', 'Ljava/util/Collection;'),
                 ('L', 'mutex', 'Ljava/lang/Object;'),
             ],
             None)
        )

        list_handle = writer._next_handle()

        # Field c: inner ArrayList
        inner = self._write_command_arraylist(writer, commands)

        # Field mutex: reference to containing SynchronizedMap
        writer.write_reference(sync_handle)

        # Field list: same as c
        writer.write_reference(inner)

    def _write_command_arraylist(self, writer: JavaObjectOutputStream, commands: List) -> int:
        """Write ArrayList of commands"""
        writer._write_byte(TC_OBJECT)

        writer.write_class_desc(
            'java.util.ArrayList',
            SERIAL_UIDS['java.util.ArrayList'],
            SC_SERIALIZABLE | SC_WRITE_METHOD,
            [('I', 'size')],
            ('java.util.AbstractList', SERIAL_UIDS['java.util.AbstractList'],
             SC_SERIALIZABLE, [],
             ('java.util.AbstractCollection', SERIAL_UIDS['java.util.AbstractCollection'],
              SC_SERIALIZABLE, [], None))
        )

        handle = writer._next_handle()

        writer._write_int(len(commands))

        block = struct.pack('>i', len(commands))
        writer._write_byte(TC_BLOCKDATA)
        writer._write_byte(len(block))
        writer.buffer.write(block)

        # Write each command (simplified - just Comment for now)
        for cmd in commands:
            self._write_comment_command(writer, cmd.get('comment', ''))

        writer._write_byte(TC_ENDBLOCKDATA)

        return handle

    def _write_comment_command(self, writer: JavaObjectOutputStream, comment_text: str):
        """Write a Comment command (simplest command type)"""
        writer._write_byte(TC_OBJECT)

        # Comment extends FlowCommand extends BrownieCommand extends Argument
        writer.write_class_desc(
            'com.asirrera.brownie.ide.command.Comment',
            1,  # serialVersionUID
            SC_SERIALIZABLE,
            [],  # Comment has no additional fields
            ('com.asirrera.brownie.ide.command.FlowCommand', 1, SC_SERIALIZABLE,
             [
                 ('Z', 'isRetriable'),
                 ('L', 'comment', 'Ljava/lang/String;'),
             ],
             ('com.asirrera.brownie.ide.command.BrownieCommand', -416088768, SC_SERIALIZABLE,
              [
                  ('Z', 'enabled'),
                  ('Z', 'isAddTableCommandIconSelected'),
                  ('Z', 'isChangeWaitTime'),
                  ('D', 'privateWaitTimeSecond'),
                  ('L', 'arguments', 'Lcom/asirrera/brownie/ide/command/Arguments;'),
                  ('L', 'findModelOfOption', 'Lcom/asirrera/brownie/ide/command/option/model/FindOptionModel;'),
                  ('L', 'metadata', 'Ljava/util/HashMap;'),
                  ('L', 'object', 'Ljava/lang/Object;'),
                  ('L', 'retryIf', 'Lcom/asirrera/brownie/ide/command/RetryIf;'),
              ],
              ('com.asirrera.brownie.ide.command.Argument', -8244499117953890091, SC_SERIALIZABLE,
               [
                   ('L', 'object', 'Ljava/lang/Object;'),
                   ('L', 'sourceCode', 'Ljava/lang/String;'),
               ],
               None)))
        )

        writer._next_handle()

        # Argument fields
        writer.write_null()  # object
        writer.write_null()  # sourceCode

        # BrownieCommand fields
        writer._write_bool(True)   # enabled
        writer._write_bool(False)  # isAddTableCommandIconSelected
        writer._write_bool(False)  # isChangeWaitTime
        writer._write_double(0.0)  # privateWaitTimeSecond
        writer.write_null()  # arguments
        writer.write_null()  # findModelOfOption
        writer.write_null()  # metadata
        writer.write_null()  # object
        writer.write_null()  # retryIf

        # FlowCommand fields
        writer._write_bool(False)  # isRetriable
        writer.write_string(comment_text)  # comment

    def save(self, path: str):
        """Save to file"""
        data = self.build()
        with open(path, 'wb') as f:
            f.write(data)


def create_simple_bwn(project_name: str, comments: List[str], output_path: str):
    """
    シンプルなBWNファイルを作成（コメントコマンドのみ）

    Args:
        project_name: プロジェクト名
        comments: コメントテキストのリスト
        output_path: 出力パス
    """
    builder = BWNScriptBuilder(project_name)

    commands = [{'comment': c} for c in comments]
    builder.add_tab('実行タブ', commands)

    builder.save(output_path)
    print(f"Created: {output_path}")


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("Usage: python bwn_compiler_v2.py <project_name> <output.bwn>")
        print("Example: python bwn_compiler_v2.py 'テストスクリプト' test.bwn")
        sys.exit(1)

    project_name = sys.argv[1]
    output_path = sys.argv[2]

    # Create simple test script
    create_simple_bwn(
        project_name,
        ['ステップ1: 開始', 'ステップ2: 処理中', 'ステップ3: 完了'],
        output_path
    )
