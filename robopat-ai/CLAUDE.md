# Robo-Pat AI プロジェクト

## プロジェクト概要
自然言語からRobo-Pat DXのスクリプトファイル(.bwnp)を生成するツール

## 現在の状態
- パッチ方式コンパイラ: **完成**
- Robo-Pat DXで開けるファイル生成: **成功確認済み**

## 主要ファイル
- `robopat_ai.py` - メインCLI
- `src/bwn_patcher.py` - BWNパッチャー（核心）
- `src/ai_generator.py` - AI生成

## 使い方
```bash
# テンプレートから新規作成（推奨）
python robopat_ai.py template "プロジェクト名" output.bwnp --base template.bwnp

# パッチJSONで変更
python robopat_ai.py patch template.bwnp patch.json output.bwnp

# 分析
python robopat_ai.py analyze existing.bwnp
```

## テンプレートファイル
`/Users/hiroki-matsui/Robo-Pat/Robo-Pat-Create/script/SUUMO反響記録ロボット.bwnp`

## 技術メモ
- .bwnpはZIP形式（.bwn + PNG画像）
- .bwnはJava Object Serialization形式（magic: 0xACED）
- TC_STRING (0x74) + 長さ(2byte BE) + UTF-8文字列
