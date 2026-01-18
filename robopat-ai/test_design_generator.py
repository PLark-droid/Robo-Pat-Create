#!/usr/bin/env python3
"""
DesignGenerator 実運用テスト

実際のAIを使って設計生成をテストします。
"""

import os
import sys
import json
from pathlib import Path

# .envから環境変数を読み込む（スクリプトと同じディレクトリ）
script_dir = Path(__file__).resolve().parent
env_path = script_dir / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from design_generator import DesignGenerator

# テスト用要件
TEST_REQUIREMENT = """
毎朝9時に、SUUMOの管理画面にログインして、
新着の反響データ（問い合わせ）を取得し、
Excelファイルに追記保存する。

対象システム: SUUMO 業務支援サイト
ログイン情報: 環境変数から取得
出力先: C:/RoboPat/反響データ.xlsx
"""


def main():
    print("=" * 60)
    print("  DesignGenerator 実運用テスト")
    print("=" * 60)
    print("")

    # 初期化
    generator = DesignGenerator()

    if not generator.client:
        print("ERROR: ANTHROPIC_API_KEY が設定されていません")
        print("       robopat-ai/.env を確認してください")
        return 1

    print(f"要件:\n{TEST_REQUIREMENT}")
    print("")

    # Step 1: 基本設計生成
    print("-" * 60)
    print("【Step 1】基本設計を生成中...")
    print("-" * 60)

    try:
        basic_design = generator.generate_basic_design(TEST_REQUIREMENT)
        print("")
        print(generator.format_basic_design())
        print("")
    except Exception as e:
        print(f"ERROR: 基本設計生成失敗 - {e}")
        return 1

    # Step 2: 詳細設計生成
    print("-" * 60)
    print("【Step 2】詳細設計を生成中...")
    print("-" * 60)

    try:
        detailed_design = generator.generate_detailed_design()
        print("")
        print(generator.format_detailed_design())
        print("")
    except Exception as e:
        print(f"ERROR: 詳細設計生成失敗 - {e}")
        return 1

    # Step 3: 手順書生成
    print("-" * 60)
    print("【Step 3】設定手順書を生成中...")
    print("-" * 60)

    try:
        manual = generator.generate_manual()
        print("")
        # 表示用に短縮（保存は全文）
        display_manual = manual[:2000] + "..." if len(manual) > 2000 else manual
        print(display_manual)
        print("")
    except Exception as e:
        print(f"ERROR: 手順書生成失敗 - {e}")
        return 1

    # Step 4: YAML生成
    print("-" * 60)
    print("【Step 4】YAMLスクリプトを生成中...")
    print("-" * 60)

    try:
        yaml_script = generator.generate_yaml_script()
        print("")
        print(yaml_script[:1500] + "..." if len(yaml_script) > 1500 else yaml_script)
        print("")
    except Exception as e:
        print(f"ERROR: YAML生成失敗 - {e}")
        return 1

    # 成果物を保存
    output_dir = Path(__file__).parent / "output" / "test"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 設計データ
    design_path = output_dir / "test_design.json"
    with open(design_path, "w", encoding="utf-8") as f:
        json.dump({
            "requirement": TEST_REQUIREMENT,
            "basic_design": basic_design,
            "detailed_design": detailed_design
        }, f, ensure_ascii=False, indent=2)

    # YAML
    yaml_path = output_dir / "test_script.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_script)

    # 手順書
    manual_path = output_dir / "test_manual.md"
    with open(manual_path, "w", encoding="utf-8") as f:
        f.write(manual)

    print("=" * 60)
    print("  テスト完了！")
    print("=" * 60)
    print("")
    print("成果物:")
    print(f"  - 設計データ: {design_path}")
    print(f"  - YAMLスクリプト: {yaml_path}")
    print(f"  - 設定手順書: {manual_path}")
    print("")

    return 0


if __name__ == "__main__":
    sys.exit(main())
