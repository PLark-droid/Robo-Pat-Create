#!/usr/bin/env python3
"""
BWN Template Patcher - 既存の.bwnpをテンプレートとして使用し、
プロジェクト名のみを変更する方式

完全な互換性を保証するため、Javaシリアライズを直接生成するのではなく、
既存ファイルをベースに最小限の変更を行う
"""

import zipfile
import os
import re
import tempfile
import shutil
from pathlib import Path
from typing import Optional


class BWNTemplatePatcher:
    """
    既存の .bwnp ファイルをテンプレートとして使用し、
    プロジェクト名を変更して新しいファイルを生成
    """

    def __init__(self, template_path: str):
        """
        Args:
            template_path: テンプレートとなる .bwnp ファイルのパス
        """
        self.template_path = Path(template_path)
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

    def create_from_template(
        self,
        output_path: str,
        new_project_name: str,
        description: Optional[str] = None
    ):
        """
        テンプレートから新しい .bwnp を作成

        Args:
            output_path: 出力先パス
            new_project_name: 新しいプロジェクト名
            description: 説明（オプション）
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            # テンプレートを展開
            self._extract_template(tmp_dir)

            # .bwn ファイルを探してプロジェクト名を変更
            bwn_files = list(Path(tmp_dir).glob('*.bwn'))
            if not bwn_files:
                raise ValueError("No .bwn file found in template")

            old_bwn = bwn_files[0]
            new_bwn_name = f"{new_project_name}.bwn"
            new_bwn = Path(tmp_dir) / new_bwn_name

            # プロジェクト名をバイナリレベルで置換
            self._patch_project_name(old_bwn, new_bwn, new_project_name)

            # 画像フォルダをリネーム
            old_folder = None
            for item in Path(tmp_dir).iterdir():
                if item.is_dir():
                    old_folder = item
                    break

            new_folder = Path(tmp_dir) / new_project_name
            if old_folder and old_folder != new_folder:
                old_folder.rename(new_folder)

            # 古い .bwn を削除（リネーム後の場合のみ）
            if old_bwn.exists() and old_bwn != new_bwn:
                old_bwn.unlink()

            # 新しい .bwnp を作成
            self._create_bwnp(tmp_dir, output_path, new_project_name)

        print(f"Created: {output_path}")

    def _extract_template(self, output_dir: str):
        """テンプレートを展開"""
        with zipfile.ZipFile(self.template_path, 'r') as zf:
            for name in zf.namelist():
                # ファイル名のエンコーディング問題を処理
                try:
                    decoded_name = name.encode('cp437').decode('utf-8')
                except:
                    decoded_name = name

                # 出力先パスを決定
                if decoded_name.endswith('.bwn'):
                    out_name = 'template.bwn'
                elif '/' in decoded_name:
                    # フォルダ内のファイル
                    folder = decoded_name.split('/')[0]
                    filename = decoded_name.split('/')[-1]
                    out_folder = Path(output_dir) / 'template_folder'
                    out_folder.mkdir(exist_ok=True)
                    out_name = str(out_folder / filename)
                else:
                    out_name = decoded_name

                if decoded_name.endswith('/'):
                    continue

                with zf.open(name) as src:
                    out_path = Path(output_dir) / out_name if '/' not in out_name else Path(out_name)
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(out_path, 'wb') as dst:
                        dst.write(src.read())

    def _patch_project_name(self, old_path: Path, new_path: Path, new_name: str):
        """
        .bwn ファイル内のプロジェクト名を置換

        Java シリアライズ形式では、文字列は length (2 bytes) + UTF-8 bytes
        """
        with open(old_path, 'rb') as f:
            data = f.read()

        # projectName の後の文字列を探して置換
        # パターン: 'projectName' の後に続く文字列を置換
        new_name_bytes = new_name.encode('utf-8')
        new_name_length = len(new_name_bytes)

        # 簡易的なアプローチ: 既存のプロジェクト名部分を探して置換
        # より堅牢な実装が必要な場合は、完全なJavaシリアライズパーサーが必要

        # プロジェクト名は 'projectName' の直後にある
        project_name_marker = b'projectName'
        idx = data.find(project_name_marker)

        if idx != -1:
            # projectName の後の文字列を探す
            # t (0x74) + length (2 bytes) + string
            search_start = idx + len(project_name_marker)
            if data[search_start] == 0x74:  # TC_STRING
                old_length = (data[search_start + 1] << 8) | data[search_start + 2]
                old_string_end = search_start + 3 + old_length

                # 新しいデータを構築
                new_data = (
                    data[:search_start + 1] +
                    bytes([(new_name_length >> 8) & 0xFF, new_name_length & 0xFF]) +
                    new_name_bytes +
                    data[old_string_end:]
                )
                data = new_data

        with open(new_path, 'wb') as f:
            f.write(data)

    def _create_bwnp(self, source_dir: str, output_path: str, project_name: str):
        """新しい .bwnp を作成"""
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            source = Path(source_dir)

            # .bwn ファイル
            for bwn in source.glob('*.bwn'):
                arcname = f"{project_name}.bwn"
                zf.write(bwn, arcname)

            # 画像フォルダ
            for folder in source.iterdir():
                if folder.is_dir():
                    for img in folder.glob('*.png'):
                        arcname = f"{project_name}/{img.name}"
                        zf.write(img, arcname)


def create_from_template(
    template_path: str,
    output_path: str,
    new_project_name: str
):
    """
    テンプレートから新しい .bwnp を作成

    Args:
        template_path: テンプレート .bwnp ファイルパス
        output_path: 出力先パス
        new_project_name: 新しいプロジェクト名
    """
    patcher = BWNTemplatePatcher(template_path)
    patcher.create_from_template(output_path, new_project_name)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 4:
        print("Usage: python bwn_template_patcher.py <template.bwnp> <output.bwnp> <new_project_name>")
        sys.exit(1)

    create_from_template(sys.argv[1], sys.argv[2], sys.argv[3])
