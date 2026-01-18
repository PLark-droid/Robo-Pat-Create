#!/usr/bin/env python3
"""
Robo-Pat AI - 自然言語からRobo-Patスクリプトを生成するCLIツール

使用方法:
    # 自然言語から YAML 生成
    python robopat_ai.py generate "SUUMOにログインして反響データを取得する"

    # テンプレートから新しいスクリプト作成（推奨）
    python robopat_ai.py template "新しいプロジェクト名" output.bwnp --base template.bwnp

    # パッチファイルで複数変更
    python robopat_ai.py patch template.bwnp patch.json output.bwnp

    # 既存の .bwnp を YAML に変換
    python robopat_ai.py parse input.bwnp

    # 対話モード
    python robopat_ai.py interactive

    # ワンショット生成 (自然言語 → .bwnp)
    python robopat_ai.py create "指示" output.bwnp
"""

import sys
import os
import argparse
import tempfile
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ai_generator import AIGenerator, generate_robopat_script
from bwn_compiler import BWNCompiler, compile_yaml_to_bwn
from bwnp_packager import BWNPPackager, create_bwnp, extract_bwnp
from bwn_parser import BWNParser, parse_bwn
from script_exporter import ScriptExporter, export_script
from bwn_patcher import BWNPatcher, create_from_template, patch_with_json, analyze_bwnp
from design_generator import DesignGenerator, run_design_wizard


def cmd_generate(args):
    """自然言語から YAML を生成"""
    generator = AIGenerator()
    yaml_output = generator.generate(args.instruction)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(yaml_output)
        print(f"出力: {args.output}")
    else:
        print(yaml_output)


def cmd_compile(args):
    """YAML を .bwnp に変換"""
    import yaml

    with open(args.yaml_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    project_name = config.get('project', {}).get('name', 'RoboPatScript')

    # 一時ファイルに .bwn を生成
    with tempfile.NamedTemporaryFile(suffix='.bwn', delete=False) as tmp:
        tmp_bwn = tmp.name

    try:
        compiler = BWNCompiler(yaml_path=args.yaml_file)
        compiler.compile(tmp_bwn)

        # .bwnp にパッケージ
        create_bwnp(project_name, tmp_bwn, args.output)
        print(f"生成完了: {args.output}")
    finally:
        if os.path.exists(tmp_bwn):
            os.unlink(tmp_bwn)


def cmd_parse(args):
    """既存の .bwnp を YAML に変換"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        result = extract_bwnp(args.bwnp_file, tmp_dir)

        if result['bwn_file']:
            parser = BWNParser(result['bwn_file'])
            yaml_output = parser.to_yaml()

            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(yaml_output)
                print(f"出力: {args.output}")
            else:
                print(yaml_output)
        else:
            print("Error: .bwn ファイルが見つかりません")
            sys.exit(1)


def cmd_create(args):
    """ワンショット: 自然言語 → .bwnp"""
    import yaml

    print(f"生成中: {args.instruction}")
    print("-" * 50)

    # Step 1: AI で YAML 生成
    generator = AIGenerator()
    yaml_output = generator.generate(args.instruction)

    print("生成された YAML:")
    print(yaml_output)
    print("-" * 50)

    # Parse YAML to get project name
    config = yaml.safe_load(yaml_output)
    project_name = config.get('project', {}).get('name', 'RoboPatScript')

    # Step 2: YAML → .bwn
    with tempfile.NamedTemporaryFile(suffix='.bwn', delete=False) as tmp:
        tmp_bwn = tmp.name

    with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False, mode='w', encoding='utf-8') as tmp_yaml:
        tmp_yaml.write(yaml_output)
        tmp_yaml_path = tmp_yaml.name

    try:
        compiler = BWNCompiler(yaml_path=tmp_yaml_path)
        compiler.compile(tmp_bwn)

        # Step 3: .bwn → .bwnp
        create_bwnp(project_name, tmp_bwn, args.output)
        print(f"\n生成完了: {args.output}")

    finally:
        for f in [tmp_bwn, tmp_yaml_path]:
            if os.path.exists(f):
                os.unlink(f)


def cmd_interactive(args):
    """対話モード"""
    import yaml

    generator = AIGenerator()

    print("=" * 60)
    print("  Robo-Pat AI Generator - 対話モード")
    print("=" * 60)
    print("")
    print("コマンド:")
    print("  <自然言語指示>  - スクリプトを生成")
    print("  save <file>     - 最後のスクリプトを保存")
    print("  export <file>   - .bwnp として出力")
    print("  quit/exit       - 終了")
    print("")
    print("-" * 60)

    last_yaml = None

    while True:
        try:
            user_input = input("\n指示> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("終了します。")
                break

            if user_input.startswith('save '):
                if last_yaml:
                    filename = user_input[5:].strip()
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(last_yaml)
                    print(f"保存しました: {filename}")
                else:
                    print("保存するスクリプトがありません")
                continue

            if user_input.startswith('export '):
                if last_yaml:
                    filename = user_input[7:].strip()
                    if not filename.endswith('.bwnp'):
                        filename += '.bwnp'

                    config = yaml.safe_load(last_yaml)
                    project_name = config.get('project', {}).get('name', 'RoboPatScript')

                    with tempfile.NamedTemporaryFile(suffix='.bwn', delete=False) as tmp:
                        tmp_bwn = tmp.name
                    with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False, mode='w', encoding='utf-8') as tmp_yaml:
                        tmp_yaml.write(last_yaml)
                        tmp_yaml_path = tmp_yaml.name

                    try:
                        compiler = BWNCompiler(yaml_path=tmp_yaml_path)
                        compiler.compile(tmp_bwn)
                        create_bwnp(project_name, tmp_bwn, filename)
                        print(f"エクスポートしました: {filename}")
                    finally:
                        for f in [tmp_bwn, tmp_yaml_path]:
                            if os.path.exists(f):
                                os.unlink(f)
                else:
                    print("エクスポートするスクリプトがありません")
                continue

            # 通常の指示 - スクリプト生成
            print("\n生成中...")
            yaml_output = generator.generate(user_input)
            last_yaml = yaml_output

            print("\n--- 生成されたスクリプト ---")
            print(yaml_output)
            print("--- ここまで ---")
            print("\n'save <file>' で保存, 'export <file>' で .bwnp 出力")

        except KeyboardInterrupt:
            print("\n終了します。")
            break
        except Exception as e:
            print(f"エラー: {e}")


def cmd_guide(args):
    """自然言語から手順書を生成"""
    print(f"生成中: {args.instruction}")
    print("-" * 50)

    # AI で YAML 生成
    generator = AIGenerator()
    yaml_output = generator.generate(args.instruction)

    print("YAML 生成完了。手順書を作成中...")

    # 手順書を生成
    fmt = args.format
    if args.output.endswith('.md'):
        fmt = 'markdown'
    elif args.output.endswith('.html'):
        fmt = 'html'

    export_script(yaml_output, args.output, fmt)

    print(f"\n手順書を生成しました: {args.output}")
    print("このファイルを開いて、Robo-Pat DX でスクリプトを作成してください。")


def cmd_template(args):
    """テンプレートから新しいスクリプトを作成（推奨方法）"""
    print(f"テンプレートから作成: {args.project_name}")
    print(f"  ベース: {args.base}")
    print("-" * 50)

    create_from_template(args.base, args.output, args.project_name)

    print(f"\n作成完了: {args.output}")
    print("Robo-Pat DX で開いて確認してください。")


def cmd_patch(args):
    """パッチファイルで複数変更"""
    print(f"パッチ適用中...")
    print(f"  テンプレート: {args.template}")
    print(f"  パッチ: {args.patch_file}")
    print("-" * 50)

    patch_with_json(args.template, args.patch_file, args.output)

    print(f"\n作成完了: {args.output}")


def cmd_analyze(args):
    """既存の.bwnpを分析"""
    analyze_bwnp(args.bwnp_file)


def cmd_design(args):
    """対話型設計ウィザード（基本設計→詳細設計→承認→成果物生成）"""
    run_design_wizard()


def cmd_ai_patch(args):
    """AIを使って自然言語からパッチを生成して適用"""
    print(f"AI パッチ生成中...")
    print(f"  指示: {args.instruction}")
    print(f"  テンプレート: {args.template}")
    print("-" * 50)

    # テンプレートの構造を取得
    patcher = BWNPatcher(args.template)
    structure = patcher.get_script_structure()

    # AI でパッチを生成
    generator = AIGenerator()
    prompt = f"""
以下のRobo-Patスクリプトのテンプレート情報を元に、ユーザーの指示に基づいて変更するパッチJSONを生成してください。

テンプレート情報:
- プロジェクト名: {structure['project_name']}
- タブ: {[t['title'] for t in structure['tabs']]}
- 文字列数: {structure['total_strings']}

ユーザーの指示: {args.instruction}

出力形式（JSON）:
{{
    "project_name": "新しいプロジェクト名（変更する場合）",
    "tab_titles": {{"古いタブ名": "新しいタブ名"}},
    "replacements": {{"置換対象文字列": "新しい文字列"}}
}}

変更不要な項目は含めないでください。JSONのみを出力してください。
"""

    try:
        response = generator.generate(prompt)
        # JSONを抽出
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            patch_json = response[json_start:json_end]
            patch_data = json.loads(patch_json)

            print(f"\n生成されたパッチ:")
            print(json.dumps(patch_data, ensure_ascii=False, indent=2))
            print("-" * 50)

            # パッチを適用
            if patch_data.get('project_name'):
                patcher.set_project_name(patch_data['project_name'])

            for old_title, new_title in patch_data.get('tab_titles', {}).items():
                patcher.set_tab_title(old_title, new_title)

            if patch_data.get('replacements'):
                patcher.batch_replace(patch_data['replacements'])

            patcher.save(args.output, patch_data.get('project_name'))

            print(f"\n作成完了: {args.output}")
        else:
            print("Error: AIからの応答からJSONを抽出できませんでした")
            print(f"応答: {response}")
            sys.exit(1)

    except json.JSONDecodeError as e:
        print(f"Error: JSONパース失敗 - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Robo-Pat AI - 自然言語からRobo-Patスクリプトを生成',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # テンプレートから新しいスクリプトを作成（推奨）
  python robopat_ai.py template "新プロジェクト" output.bwnp --base template.bwnp

  # AIを使って自然言語でパッチ生成
  python robopat_ai.py ai-patch "プロジェクト名を変更" output.bwnp --template base.bwnp

  # パッチJSONで複数変更
  python robopat_ai.py patch template.bwnp patch.json output.bwnp

  # 既存の.bwnpを分析
  python robopat_ai.py analyze existing.bwnp

  # 自然言語からYAML生成
  python robopat_ai.py generate "SUUMOにログインして反響データを取得"

  # 対話モード
  python robopat_ai.py interactive
"""
    )

    subparsers = parser.add_subparsers(dest='command', help='コマンド')

    # generate
    p_generate = subparsers.add_parser('generate', help='自然言語からYAMLを生成')
    p_generate.add_argument('instruction', help='自然言語の指示')
    p_generate.add_argument('-o', '--output', help='出力ファイル（省略時は標準出力）')

    # compile
    p_compile = subparsers.add_parser('compile', help='YAMLを.bwnpに変換')
    p_compile.add_argument('yaml_file', help='入力YAMLファイル')
    p_compile.add_argument('output', help='出力.bwnpファイル')

    # parse
    p_parse = subparsers.add_parser('parse', help='既存の.bwnpをYAMLに変換')
    p_parse.add_argument('bwnp_file', help='入力.bwnpファイル')
    p_parse.add_argument('-o', '--output', help='出力ファイル（省略時は標準出力）')

    # create
    p_create = subparsers.add_parser('create', help='ワンショット生成（自然言語→.bwnp）')
    p_create.add_argument('instruction', help='自然言語の指示')
    p_create.add_argument('output', help='出力.bwnpファイル')

    # interactive
    p_interactive = subparsers.add_parser('interactive', help='対話モード')

    # guide - 手順書出力
    p_guide = subparsers.add_parser('guide', help='自然言語から手順書(HTML/Markdown)を生成')
    p_guide.add_argument('instruction', help='自然言語の指示')
    p_guide.add_argument('output', help='出力ファイル（.html または .md）')
    p_guide.add_argument('-f', '--format', choices=['html', 'markdown'], default='html',
                        help='出力形式（デフォルト: html）')

    # template - テンプレートから作成（推奨）
    p_template = subparsers.add_parser('template', help='テンプレートから新しいスクリプトを作成（推奨）')
    p_template.add_argument('project_name', help='新しいプロジェクト名')
    p_template.add_argument('output', help='出力.bwnpファイル')
    p_template.add_argument('--base', '-b', required=True, help='テンプレート.bwnpファイル')

    # patch - パッチJSONで変更
    p_patch = subparsers.add_parser('patch', help='パッチJSONで複数変更')
    p_patch.add_argument('template', help='テンプレート.bwnpファイル')
    p_patch.add_argument('patch_file', help='パッチJSONファイル')
    p_patch.add_argument('output', help='出力.bwnpファイル')

    # analyze - 分析
    p_analyze = subparsers.add_parser('analyze', help='既存の.bwnpを分析')
    p_analyze.add_argument('bwnp_file', help='分析対象の.bwnpファイル')

    # design - 対話型設計ウィザード
    p_design = subparsers.add_parser('design', help='対話型設計ウィザード（基本設計→詳細設計→成果物生成）')

    # ai-patch - AIを使って自然言語でパッチ
    p_ai_patch = subparsers.add_parser('ai-patch', help='AIを使って自然言語でパッチ生成')
    p_ai_patch.add_argument('instruction', help='変更内容の指示')
    p_ai_patch.add_argument('output', help='出力.bwnpファイル')
    p_ai_patch.add_argument('--template', '-t', required=True, help='テンプレート.bwnpファイル')

    args = parser.parse_args()

    if args.command == 'generate':
        cmd_generate(args)
    elif args.command == 'compile':
        cmd_compile(args)
    elif args.command == 'parse':
        cmd_parse(args)
    elif args.command == 'create':
        cmd_create(args)
    elif args.command == 'interactive':
        cmd_interactive(args)
    elif args.command == 'guide':
        cmd_guide(args)
    elif args.command == 'template':
        cmd_template(args)
    elif args.command == 'patch':
        cmd_patch(args)
    elif args.command == 'analyze':
        cmd_analyze(args)
    elif args.command == 'design':
        cmd_design(args)
    elif args.command == 'ai-patch':
        cmd_ai_patch(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
