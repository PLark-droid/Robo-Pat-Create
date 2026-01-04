#!/usr/bin/env python3
"""
BWN Patcher - 元ファイルをベースに新しいスクリプトを生成

このツールは既存の.bwnファイルをテンプレートとして使用し、
プロジェクト名やコマンドを変更した新しいファイルを生成します。

使用方法:
  - analyze: .bwnpファイルの構造を分析
  - create: テンプレートから新しいスクリプトを作成
  - patch: 複数の文字列を一括置換
"""

import struct
import zipfile
import io
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class StringLocation:
    """バイナリ内の文字列位置"""
    offset: int      # TC_STRING (0x74) の位置
    length: int      # 文字列長
    value: str       # 文字列値
    end_offset: int  # 文字列終了位置


@dataclass
class CommandInfo:
    """コマンド情報"""
    offset: int           # コマンド開始位置
    command_type: str     # コマンドタイプ
    comment: str = ""     # コメント
    enabled: bool = True  # 有効/無効


class BWNPatcher:
    """
    BWNファイルのパッチャー

    既存ファイルをベースに、特定の文字列を置換して新しいファイルを生成
    """

    def __init__(self, template_bwnp_path: str):
        """
        Args:
            template_bwnp_path: テンプレートとなる.bwnpファイルのパス
        """
        self.template_path = Path(template_bwnp_path)
        self.bwn_data: bytearray = bytearray()
        self.images: Dict[str, bytes] = {}
        self.original_project_name: str = ""

        self._load_template()

    def _load_template(self):
        """テンプレートファイルを読み込み"""
        with zipfile.ZipFile(self.template_path, 'r') as zf:
            for name in zf.namelist():
                try:
                    # エンコーディング問題を回避
                    decoded_name = name.encode('cp437').decode('utf-8')
                except:
                    decoded_name = name

                data = zf.read(name)

                if decoded_name.endswith('.bwn'):
                    self.bwn_data = bytearray(data)
                    # プロジェクト名を抽出
                    self.original_project_name = self._find_project_name()
                elif decoded_name.endswith('.png'):
                    img_name = decoded_name.split('/')[-1] if '/' in decoded_name else decoded_name
                    self.images[img_name] = data

        print(f"Loaded template: {self.template_path}")
        print(f"  BWN size: {len(self.bwn_data)} bytes")
        print(f"  Images: {len(self.images)}")
        print(f"  Original project name: {self.original_project_name}")

    def _find_string(self, data: bytes, search_after: bytes) -> Optional[StringLocation]:
        """
        特定のマーカー後の文字列を検索

        Args:
            data: 検索対象のバイト列
            search_after: このバイト列の後にある文字列を検索

        Returns:
            StringLocation or None
        """
        idx = data.find(search_after)
        if idx == -1:
            return None

        str_offset = idx + len(search_after)

        # TC_STRING (0x74) を確認
        if data[str_offset] != 0x74:
            return None

        # 文字列長を読み取り
        length = struct.unpack('>H', data[str_offset+1:str_offset+3])[0]
        value = data[str_offset+3:str_offset+3+length].decode('utf-8')

        return StringLocation(
            offset=str_offset,
            length=length,
            value=value,
            end_offset=str_offset + 3 + length
        )

    def _find_project_name(self) -> str:
        """プロジェクト名を検索"""
        loc = self._find_string(bytes(self.bwn_data), b'projectName')
        return loc.value if loc else ""

    def _replace_string(self, marker: bytes, new_value: str) -> bool:
        """
        マーカー後の文字列を置換

        Args:
            marker: 検索マーカー
            new_value: 新しい文字列値

        Returns:
            成功したかどうか
        """
        loc = self._find_string(bytes(self.bwn_data), marker)
        if not loc:
            return False

        new_bytes = new_value.encode('utf-8')
        new_length = struct.pack('>H', len(new_bytes))

        # 新しいデータを構築
        self.bwn_data = bytearray(
            bytes(self.bwn_data[:loc.offset + 1]) +  # TC_STRING まで
            new_length +                               # 新しい長さ
            new_bytes +                                # 新しい文字列
            bytes(self.bwn_data[loc.end_offset:])     # 残り
        )

        return True

    def set_project_name(self, new_name: str):
        """
        プロジェクト名を変更

        Args:
            new_name: 新しいプロジェクト名
        """
        if self._replace_string(b'projectName', new_name):
            print(f"Project name changed: {self.original_project_name} -> {new_name}")
        else:
            print("Warning: Could not find project name to replace")

    def find_all_strings(self) -> List[StringLocation]:
        """全ての文字列を検索（デバッグ用）"""
        strings = []
        data = bytes(self.bwn_data)
        i = 0

        while i < len(data) - 3:
            if data[i] == 0x74:  # TC_STRING
                try:
                    length = struct.unpack('>H', data[i+1:i+3])[0]
                    if 1 <= length <= 500 and i + 3 + length <= len(data):
                        value = data[i+3:i+3+length].decode('utf-8')
                        if value.isprintable() or any('\u3000' <= c <= '\u9fff' for c in value):
                            strings.append(StringLocation(
                                offset=i,
                                length=length,
                                value=value,
                                end_offset=i + 3 + length
                            ))
                except:
                    pass
            i += 1

        return strings

    def find_tab_titles(self) -> List[Tuple[int, str]]:
        """タブタイトルを検索"""
        titles = []
        data = bytes(self.bwn_data)

        marker = b'tabTitle'
        idx = 0
        while True:
            idx = data.find(marker, idx)
            if idx == -1:
                break

            loc = self._find_string(data, marker)
            if loc:
                titles.append((idx, loc.value))
            idx += len(marker)

        return titles

    def find_comments(self) -> List[Tuple[int, str]]:
        """コメントを検索"""
        comments = []
        data = bytes(self.bwn_data)

        # FlowCommand の comment フィールドを検索
        # パターン: isRetriable (boolean) の後に comment (String)
        strings = self.find_all_strings()

        for s in strings:
            # コメントっぽい文字列を探す（日本語を含むなど）
            if len(s.value) > 5 and any('\u3000' <= c <= '\u9fff' for c in s.value):
                comments.append((s.offset, s.value))

        return comments

    def set_tab_title(self, old_title: str, new_title: str) -> bool:
        """
        タブタイトルを変更

        Args:
            old_title: 現在のタブタイトル
            new_title: 新しいタブタイトル

        Returns:
            成功したかどうか
        """
        data = bytes(self.bwn_data)
        marker = b'tabTitle'
        idx = 0

        while True:
            idx = data.find(marker, idx)
            if idx == -1:
                break

            loc = self._find_string(data, marker)
            if loc and loc.value == old_title:
                # この位置から直接置換
                self._replace_string_at_offset(loc.offset, new_title)
                print(f"Tab title changed: {old_title} -> {new_title}")
                return True
            idx += len(marker)

        print(f"Warning: Tab title '{old_title}' not found")
        return False

    def _replace_string_at_offset(self, offset: int, new_value: str) -> bool:
        """
        指定オフセットの文字列を置換

        Args:
            offset: TC_STRING (0x74) の位置
            new_value: 新しい文字列値

        Returns:
            成功したかどうか
        """
        data = bytes(self.bwn_data)

        if data[offset] != 0x74:
            return False

        old_length = struct.unpack('>H', data[offset+1:offset+3])[0]
        old_end = offset + 3 + old_length

        new_bytes = new_value.encode('utf-8')
        new_length = struct.pack('>H', len(new_bytes))

        self.bwn_data = bytearray(
            bytes(self.bwn_data[:offset + 1]) +
            new_length +
            new_bytes +
            bytes(self.bwn_data[old_end:])
        )

        return True

    def replace_string(self, old_value: str, new_value: str, count: int = 1) -> int:
        """
        文字列を置換（複数可）

        Args:
            old_value: 置換対象の文字列
            new_value: 新しい文字列
            count: 置換回数（-1で全て）

        Returns:
            置換した回数
        """
        replaced = 0
        strings = self.find_all_strings()

        # オフセット順にソート（後ろから置換しないとオフセットがずれる）
        matching = [s for s in strings if s.value == old_value]
        matching.sort(key=lambda x: x.offset, reverse=True)

        for s in matching:
            if count != -1 and replaced >= count:
                break
            if self._replace_string_at_offset(s.offset, new_value):
                replaced += 1
                # データが変わったので再スキャンが必要
                strings = self.find_all_strings()
                matching = [s for s in strings if s.value == old_value]
                matching.sort(key=lambda x: x.offset, reverse=True)

        if replaced > 0:
            print(f"Replaced '{old_value}' -> '{new_value}' ({replaced} times)")

        return replaced

    def batch_replace(self, replacements: Dict[str, str]) -> Dict[str, int]:
        """
        複数の文字列を一括置換

        Args:
            replacements: {old_value: new_value} の辞書

        Returns:
            {old_value: 置換回数} の辞書
        """
        results = {}
        for old_val, new_val in replacements.items():
            results[old_val] = self.replace_string(old_val, new_val, count=-1)
        return results

    def get_script_structure(self) -> Dict[str, Any]:
        """
        スクリプトの構造情報を取得

        Returns:
            プロジェクト名、タブ、コマンドの情報
        """
        structure = {
            'project_name': self.original_project_name,
            'tabs': [],
            'total_strings': 0,
            'bwn_size': len(self.bwn_data),
            'image_count': len(self.images)
        }

        strings = self.find_all_strings()
        structure['total_strings'] = len(strings)

        # タブタイトルを取得
        for offset, title in self.find_tab_titles():
            structure['tabs'].append({
                'title': title,
                'offset': offset
            })

        return structure

    def export_structure_json(self, output_path: str):
        """
        構造情報をJSONでエクスポート

        Args:
            output_path: 出力ファイルパス
        """
        structure = self.get_script_structure()
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(structure, f, ensure_ascii=False, indent=2)
        print(f"Exported structure to: {output_path}")

    def save(self, output_path: str, project_name: Optional[str] = None):
        """
        パッチ済みファイルを保存

        Args:
            output_path: 出力パス（.bwnp）
            project_name: プロジェクト名（省略時はテンプレートから取得）
        """
        if project_name:
            self.set_project_name(project_name)
            folder_name = project_name
        else:
            folder_name = self.original_project_name

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # BWN ファイル
            zf.writestr(f'{folder_name}.bwn', bytes(self.bwn_data))

            # 画像ファイル
            for img_name, img_data in self.images.items():
                zf.writestr(f'{folder_name}/{img_name}', img_data)

        print(f"Saved: {output_path}")
        print(f"  BWN size: {len(self.bwn_data)} bytes")
        print(f"  Images: {len(self.images)}")


def create_from_template(
    template_path: str,
    output_path: str,
    project_name: str
):
    """
    テンプレートから新しいスクリプトを作成

    Args:
        template_path: テンプレート.bwnpファイル
        output_path: 出力.bwnpファイル
        project_name: 新しいプロジェクト名
    """
    patcher = BWNPatcher(template_path)
    patcher.save(output_path, project_name)


def analyze_bwnp(bwnp_path: str):
    """
    BWNPファイルを分析

    Args:
        bwnp_path: 分析対象の.bwnpファイル
    """
    patcher = BWNPatcher(bwnp_path)

    print("\n=== String Analysis ===")
    strings = patcher.find_all_strings()
    print(f"Total strings: {len(strings)}")

    print("\n=== Tab Titles ===")
    for offset, title in patcher.find_tab_titles():
        print(f"  [{offset}] {title}")

    print("\n=== Sample Strings (first 50) ===")
    for s in strings[:50]:
        if len(s.value) > 3:
            print(f"  [{s.offset}] ({s.length}) {s.value[:60]}{'...' if len(s.value) > 60 else ''}")


def patch_with_json(template_path: str, patch_file: str, output_path: str):
    """
    JSONパッチファイルで.bwnpを変更

    Args:
        template_path: テンプレート.bwnpファイル
        patch_file: パッチ定義JSONファイル
        output_path: 出力.bwnpファイル

    JSON形式:
    {
        "project_name": "新しいプロジェクト名",
        "tab_titles": {"古い名前": "新しい名前"},
        "replacements": {"古い文字列": "新しい文字列"}
    }
    """
    patcher = BWNPatcher(template_path)

    with open(patch_file, 'r', encoding='utf-8') as f:
        patch_data = json.load(f)

    # プロジェクト名の変更
    project_name = patch_data.get('project_name')
    if project_name:
        patcher.set_project_name(project_name)

    # タブタイトルの変更
    tab_titles = patch_data.get('tab_titles', {})
    for old_title, new_title in tab_titles.items():
        patcher.set_tab_title(old_title, new_title)

    # 一般的な文字列置換
    replacements = patch_data.get('replacements', {})
    if replacements:
        patcher.batch_replace(replacements)

    patcher.save(output_path, project_name)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("BWN Patcher - Robo-Pat スクリプトパッチツール")
        print()
        print("Usage:")
        print("  Create:   python bwn_patcher.py create <template.bwnp> <output.bwnp> <project_name>")
        print("  Analyze:  python bwn_patcher.py analyze <file.bwnp>")
        print("  Patch:    python bwn_patcher.py patch <template.bwnp> <patch.json> <output.bwnp>")
        print("  Export:   python bwn_patcher.py export <file.bwnp> <output.json>")
        print()
        print("Patch JSON format:")
        print('  {')
        print('    "project_name": "新しいプロジェクト名",')
        print('    "tab_titles": {"古いタブ名": "新しいタブ名"},')
        print('    "replacements": {"古い文字列": "新しい文字列"}')
        print('  }')
        sys.exit(1)

    action = sys.argv[1]

    if action == 'create':
        if len(sys.argv) < 5:
            print("Error: create requires template, output, and project_name")
            sys.exit(1)
        create_from_template(sys.argv[2], sys.argv[3], sys.argv[4])

    elif action == 'analyze':
        if len(sys.argv) < 3:
            print("Error: analyze requires file path")
            sys.exit(1)
        analyze_bwnp(sys.argv[2])

    elif action == 'patch':
        if len(sys.argv) < 5:
            print("Error: patch requires template, patch.json, and output")
            sys.exit(1)
        patch_with_json(sys.argv[2], sys.argv[3], sys.argv[4])

    elif action == 'export':
        if len(sys.argv) < 4:
            print("Error: export requires file.bwnp and output.json")
            sys.exit(1)
        patcher = BWNPatcher(sys.argv[2])
        patcher.export_structure_json(sys.argv[3])

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)
