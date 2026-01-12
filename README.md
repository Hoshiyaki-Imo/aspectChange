# aspectChange

画像を 4:5 比率でトリミングし、枠線と日付テキストを追加して保存するツールです。

## Features
- 画像のドラッグ＆ドロップ対応
- 4:5 比率のトリミング枠（長辺方向のみ移動）
- 枠線カラーの変更
- 撮影日（EXIF）とコメントの描画
- 非同期処理による高速な書き出し

## Usage
1. 画像を開く、またはドラッグ＆ドロップ
2. 枠位置を調整
3. コメントを入力（任意）
4. 出力ボタンを押す

## Build
This application is built with:
- Python
    - PySide6
    - Pillow
- Nuitka

Executable file was generated using Nuitka.

## License
This project is licensed under the MIT License.

Third-party licenses:
- PySide6 (LGPL v3)
- Pillow (HPND License)
