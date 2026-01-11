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
        self.last_pos = self.mapToScene(event.pos())

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
        self.Makewindow()

        if File == None:
            self.No_file()

    def Makewindow(self):
        self.setWindowTitle("aspectChange")
        self.resize(800,600)
        self.MainWinMainLayout = QVBoxLayout()

        MenuBar = self.menuBar()
        mFile = MenuBar.addMenu("ファイル")
        self.acOpenFile = QAction("開く", self)
        self.acOpenFile.triggered.connect(self.file_open)
        self.acCloseFile = QAction("閉じる", self)
        self.acCloseFile.triggered.connect(self.file_close)
        mFile.addAction(self.acOpenFile)
        mFile.addAction(self.acCloseFile)

        self.export = QPushButton("出力")
        self.export.clicked.connect(self.Export)

        self.view = CropView()

        self.MainWinMainLayout.addWidget(self.view)
        self.MainWinMainLayout.addWidget(self.export)
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

    def file_close(self):
        pass

    def Export(self):
        if self.view.pixmap_item is None or self.view.crop_rect is None:
            return

        # 元 pixmap
        pixmap = self.view.pixmap_item.pixmap()

        # crop_rect の Scene 座標
        crop_rect = self.view.crop_rect
        rect = crop_rect.rect()
        pos = crop_rect.pos()
        crop_x = int(pos.x())
        crop_y = int(pos.y())
        crop_w = int(rect.width())
        crop_h = int(rect.height())

        # 元 pixmap から切り出す
        cropped = pixmap.copy(crop_x, crop_y, crop_w, crop_h)

        # 枠の太さと余白
        border = max(50, crop_w // 8)  # 太く
        canvas = QPixmap(crop_w + border*2, crop_h + border*2)
        canvas.fill(Qt.transparent)

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)  # 滑らかに描画

        # 元画像を中央に描く
        painter.drawPixmap(border, border, cropped)

        # 枠線描画
        pen = QPen(QColor(240, 240, 255), border)
        pen.setJoinStyle(Qt.MiterJoin)  # 角を直角に
        pen.setCapStyle(Qt.SquareCap)   # 線の端も四角

        painter.setPen(pen)
        painter.drawRect(border//2, border//2, crop_w + border - 1, crop_h + border - 1)

        # 日付取得（self.current_file に保存しておく）
        date_str = None
        try:
            from PIL import Image, ExifTags
            img = Image.open(self.view.current_file)  # ファイルパスから開く
            exif_data = img._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = ExifTags.TAGS.get(tag_id)
                    if tag == "DateTimeOriginal":
                        date_str = value
                        break
        except Exception as e:
            print("EXIF 読み込み失敗:", e)

        # 日付描画
        print(date_str)
        if date_str:
            font = QFont("Arial", max(40, crop_h // 10))
            painter.setFont(font)
            painter.setPen(QPen(QColor(255,255,255)))  # 白っぽく
            painter.drawText(border + 20, crop_h + border - 20, date_str)


        painter.end()

        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存先を選択", "", "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg)"
        )
        if save_path:
            canvas.save(save_path)


    def No_file(self):
        self.export.setDisabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)    # PySide6の実行
    app.setWindowIcon(QIcon("icon.ico"))
    window = MainWindow()           # ユーザがコーディングしたクラス
    window.show()                   # PySide6のウィンドウを表示
    sys.exit(app.exec())            # PySide6の終了