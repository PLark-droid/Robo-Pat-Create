#!/usr/bin/env python3
"""
BWNP Packager - .bwn と画像を .bwnp (ZIP) にパッケージング
"""

import zipfile
import os
from pathlib import Path
from typing import List, Optional
import shutil
import tempfile


class BWNPPackager:
    """
    .bwnp ファイル（ZIP形式）を作成
    """

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.images: List[tuple] = []  # (image_path, internal_name)

    def add_image(self, image_path: str, internal_name: Optional[str] = None):
        """
        画像を追加

        Args:
            image_path: 画像ファイルパス
            internal_name: ZIP内の名前（省略時は自動生成）
        """
        if internal_name is None:
            internal_name = Path(image_path).name
        self.images.append((image_path, internal_name))

    def package(self, bwn_path: str, output_path: str):
        """
        .bwnp ファイルを作成

        Args:
            bwn_path: .bwn ファイルパス
            output_path: 出力 .bwnp ファイルパス
        """
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # メインの .bwn ファイル
            bwn_name = f"{self.project_name}.bwn"
            zf.write(bwn_path, bwn_name)

            # 画像ファイル
            image_folder = self.project_name
            for img_path, internal_name in self.images:
                arcname = f"{image_folder}/{internal_name}"
                zf.write(img_path, arcname)

        print(f"Packaged: {output_path}")
        print(f"  - {bwn_name}")
        for _, internal_name in self.images:
            print(f"  - {self.project_name}/{internal_name}")


def create_bwnp(
    project_name: str,
    bwn_path: str,
    output_path: str,
    image_paths: Optional[List[str]] = None
):
    """
    .bwnp ファイルを作成

    Args:
        project_name: プロジェクト名
        bwn_path: .bwn ファイルパス
        output_path: 出力 .bwnp ファイルパス
        image_paths: 画像ファイルパスのリスト（オプション）
    """
    packager = BWNPPackager(project_name)

    if image_paths:
        for i, img_path in enumerate(image_paths):
            packager.add_image(img_path, f"bwn-{i+1}.png")

    packager.package(bwn_path, output_path)


def extract_bwnp(bwnp_path: str, output_dir: str) -> dict:
    """
    .bwnp ファイルを展開

    Args:
        bwnp_path: .bwnp ファイルパス
        output_dir: 出力ディレクトリ

    Returns:
        展開されたファイル情報
    """
    os.makedirs(output_dir, exist_ok=True)

    result = {
        'bwn_file': None,
        'images': []
    }

    with zipfile.ZipFile(bwnp_path, 'r') as zf:
        for name in zf.namelist():
            # エンコーディング問題を回避
            try:
                # CP932 でエンコードされている場合がある
                decoded_name = name.encode('cp437').decode('utf-8')
            except:
                decoded_name = name

            if decoded_name.endswith('.bwn'):
                ext = 'bwn'
                output_name = 'main.bwn'
                result['bwn_file'] = os.path.join(output_dir, output_name)
            elif decoded_name.endswith('.png'):
                ext = 'png'
                output_name = Path(decoded_name).name
                result['images'].append(os.path.join(output_dir, output_name))
            else:
                continue

            with zf.open(name) as src:
                output_file = os.path.join(output_dir, output_name)
                with open(output_file, 'wb') as dst:
                    dst.write(src.read())

    return result


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  Pack:   python bwnp_packager.py pack <project_name> <bwn_file> <output.bwnp> [images...]")
        print("  Unpack: python bwnp_packager.py unpack <file.bwnp> <output_dir>")
        sys.exit(1)

    action = sys.argv[1]

    if action == 'pack':
        if len(sys.argv) < 5:
            print("Error: Not enough arguments for pack")
            sys.exit(1)

        project_name = sys.argv[2]
        bwn_path = sys.argv[3]
        output_path = sys.argv[4]
        image_paths = sys.argv[5:] if len(sys.argv) > 5 else None

        create_bwnp(project_name, bwn_path, output_path, image_paths)

    elif action == 'unpack':
        if len(sys.argv) < 4:
            print("Error: Not enough arguments for unpack")
            sys.exit(1)

        bwnp_path = sys.argv[2]
        output_dir = sys.argv[3]

        result = extract_bwnp(bwnp_path, output_dir)
        print(f"Extracted to: {output_dir}")
        print(f"  BWN file: {result['bwn_file']}")
        print(f"  Images: {len(result['images'])}")

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)
