from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
import sys
from PIL import Image, ExifTags


class CropView(QGraphicsView):
    def __init__(self):
        super().__init__()

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.pixmap_item = None
        self.dragging = None
        self.crop_rect = None
        self.last_pos = None
        self.current_file = None

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if self.pixmap_item is None:
            return

        self.fitInView(
            self.sceneRect(),
            Qt.KeepAspectRatio
        )

    def load_image(self, filename):
        pixmap = QPixmap(filename)
        self.current_file = filename
        self.scene.clear()
        
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)
        
        self.setSceneRect(self.pixmap_item.boundingRect())
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

        img_rect = self.pixmap_item.boundingRect()

        # 枠サイズは短辺固定の4:5
        crop_w = img_rect.width()
        crop_h = crop_w * 5 / 4
        if crop_h > img_rect.height():
            crop_h = img_rect.height()
            crop_w = crop_h * 4 / 5

        self.crop_rect = QGraphicsRectItem(0, 0, crop_w, crop_h)
        self.crop_rect.setPen(QPen(QColor(180, 160, 255), 5))  # 薄紫
        self.crop_rect.setBrush(Qt.NoBrush)
        self.scene.addItem(self.crop_rect)

        # 長辺方向だけ動く
        self.move_axis = "x" if img_rect.width() > img_rect.height() else "y"

    def mousePressEvent(self, event):
        if self.crop_rect is None:
            return
        self.dragging = True
        self.last_pos = self.mapToScene(event.position().toPoint())

    def mouseMoveEvent(self, event):
        if not self.dragging or self.crop_rect is None:
            return

        pos = self.mapToScene(event.pos())
        delta = pos - self.last_pos

        crop_rect_rect = self.crop_rect.rect()
        crop_pos = self.crop_rect.pos()
        img_rect = self.pixmap_item.boundingRect()

        if self.move_axis == "x":  # 横移動
            new_x = crop_pos.x() + delta.x()
            new_x = max(0, min(new_x, img_rect.width() - crop_rect_rect.width()))
            self.crop_rect.setX(new_x)
        else:  # 縦移動
            new_y = crop_pos.y() + delta.y()
            new_y = max(0, min(new_y, img_rect.height() - crop_rect_rect.height()))
            self.crop_rect.setY(new_y)

        self.last_pos = pos


    def mouseReleaseEvent(self, event):
        self.dragging = False




class MainWindow(QMainWindow):
    def __init__(self, File = None, parent=None):
        # 親クラスの初期化
        super().__init__(parent)
        self.settings = QSettings("HoshiYakiImo", "aspectChange")
        self.Makewindow()

        if File == None:
            self.No_file()

    def Makewindow(self):
        self.setWindowTitle("aspectChange")
        self.resize(800,600)
        self.MainWinMainLayout = QVBoxLayout()
        self.underLayout = QHBoxLayout()

        MenuBar = self.menuBar()
        mFile = MenuBar.addMenu("ファイル")
        mSetting = MenuBar.addMenu("設定")
        self.acOpenFile = QAction("開く", self)
        self.acOpenFile.triggered.connect(self.file_open)
        self.acSetExportFolder = QAction("出力フォルダ", self)
        self.acSetExportFolder.triggered.connect(self.set_export_folder)
        mFile.addAction(self.acOpenFile)
        mSetting.addAction(self.acSetExportFolder)

        # Makewindow 内
        self.comment_input = QLineEdit()
        self.comment_input.setPlaceholderText("～にて")


        self.export = QPushButton("出力")
        self.export.clicked.connect(self.Export)

        self.view = CropView()

        self.MainWinMainLayout.addWidget(self.view)
        self.MainWinMainLayout.addLayout(self.underLayout)
        self.underLayout.addWidget(self.comment_input)
        self.underLayout.addWidget(self.export)
        centralWidget = QWidget()
        centralWidget.setLayout(self.MainWinMainLayout)
        self.setCentralWidget(centralWidget)

    def file_open(self):
        try:
            Filename, tmp = QFileDialog.getOpenFileName(self,"ファイルを開く","","Image File (*.jpeg *.jpg *.png *.bmp)")
        except FileNotFoundError:
            self.StatusBar.showMessage("ファイルが選択されませんでした")
            return
        if Filename == "":
            return
        self.export.setDisabled(False)
        self.view.load_image(Filename)

    def set_export_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "出力フォルダを選択", "", QFileDialog.ShowDirsOnly)

        if folder:
            self.settings.setValue("exportFolder", folder)

    def Export(self):
        if self.view.pixmap_item is None or self.view.crop_rect is None:
            return

        pixmap = self.view.pixmap_item.pixmap()

        crop_rect = self.view.crop_rect
        rect = crop_rect.rect()
        pos = self.mapToScene(event.position().toPoint())
        crop_x = int(pos.x())
        crop_y = int(pos.y())
        crop_w = int(rect.width())
        crop_h = int(rect.height())

        cropped = pixmap.copy(crop_x, crop_y, crop_w, crop_h)

        border = max(50, crop_w // 8)
        canvas = QPixmap(crop_w + border*2, crop_h + border*2)
        canvas.fill(Qt.transparent)

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.drawPixmap(border, border, cropped)

        # 枠
        pen = QPen(QColor(244,235,255), border)
        pen.setJoinStyle(Qt.MiterJoin)
        pen.setCapStyle(Qt.SquareCap)
        painter.setPen(pen)
        painter.drawRect(border//2, border//2, crop_w + border - 1, crop_h + border - 1)

        # 日付取得
        date_str = ""
        try:
            img = Image.open(self.view.current_file)
            exif_data = img._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = ExifTags.TAGS.get(tag_id)
                    if tag == "DateTimeOriginal":
                        # YYYY:MM:DD HH:MM:SS → MM月DD日
                        date_parts = value.split()[0].split(":")
                        date_str = f"{int(date_parts[0])}.{int(date_parts[1])}.{int(date_parts[2])}"
                        break
        except Exception as e:
            print("EXIF 読み込み失敗:", e)

        # コメント取得（QLineEdit から）
        comment = self.comment_input.text() if hasattr(self, "comment_input") else ""
        text = f"{date_str} {comment}".strip()

        # 左下に文字描画
        if text:
            font_size = max(18, crop_h //30)
            font = QFont("みかちゃん", font_size)
            painter.setFont(font)
            painter.setPen(QPen(QColor(0,0,10)))  # 黒

            # 余白計算
            left_margin = 100
            top_margin = font_size * 2.5       # 上に2行分余白（見た目調整用）

            # 描画 y座標 = キャンバス高さ - 下余白
            y_pos = border + crop_h + top_margin
            painter.drawText(left_margin, y_pos, text)


        painter.end()

        export_dir = self.settings.value("exportFolder", "")

        save_path, _ = QFileDialog.getSaveFileName(self, "保存先を選択", export_dir, "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg)")

        if save_path:
            canvas.save(save_path)



    def No_file(self):
        self.export.setDisabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)    # PySide6の実行
    app.setWindowIcon(QIcon("icon.ico"))
    window = MainWindow()           # ユーザがコーディングしたクラス
    if len(sys.argv) > 1:
        window.view.load_imange(sys.argv[1])
        window.export.setDisabled(False)
    window.show()                   # PySide6のウィンドウを表示
    sys.exit(app.exec())            # PySide6の終了