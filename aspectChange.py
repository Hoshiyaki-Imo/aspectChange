from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
import sys
from PIL import Image, ExifTags
import os


class CropView(QGraphicsView):
    # シグナルを定義 (読み込んだファイルのパスを渡す)
    fileDropped = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.pixmap_item = None
        self.dragging = None
        self.crop_rect = None
        self.last_pos = None
        self.current_file = None

    # ... (resizeEvent, load_image, mouse系イベントはそのまま) ...

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    # 【重要】これを追加しないとQGraphicsViewではドロップできない場合がある
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return

        path = urls[0].toLocalFile()
        if path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
            # ここで直接 load_image せず、シグナルを送るか、
            # load_imageした後にシグナルを送る
            
            # 今回はView側で表示更新しつつ、親に通知する形にします
            self.load_image(path)
            
            # メインウィンドウに通知
            self.fileDropped.emit(path)

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
        self.crop_rect.setPen(QPen(QColor(0, 255, 0), 5))  # 薄紫
        self.crop_rect.setBrush(Qt.NoBrush)
        self.scene.addItem(self.crop_rect)

        # 長辺方向だけ動く
        self.move_axis = "x" if img_rect.width() >= img_rect.height() else "y"

    def mousePressEvent(self, event):
        if self.crop_rect is None:
            return
        self.dragging = True
        self.last_pos = self.mapToScene(event.position().toPoint())

    def mouseMoveEvent(self, event):
        if not self.dragging or self.crop_rect is None:
            return

        pos = self.mapToScene(event.position().toPoint())
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


class FontFamilyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("フォント選択")

        self.list = QListWidget()
        for family in QFontDatabase.families():
            self.list.addItem(family)

        ok = QPushButton("OK")
        ok.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        layout.addWidget(ok)

    def selected_family(self):
        item = self.list.currentItem()
        return item.text() if item else None
    
class TextTemplateDialog(QDialog):
    def __init__(self, current, parent=None):
        super().__init__(parent)
        self.setWindowTitle("テキスト形式の設定")

        self.edit = QTextEdit()
        self.edit.setPlainText(current)

        help = QLabel("使用可能な変数:\n%year% : 撮影された年\n%month% : 撮影された月\n%day% : 撮影日\n%comment% : ボックスに入力した内容")

        ok = QPushButton("OK")
        cancel = QPushButton("キャンセル")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)

        btn = QHBoxLayout()
        btn.addStretch()
        btn.addWidget(ok)
        btn.addWidget(cancel)

        layout = QVBoxLayout(self)
        layout.addWidget(self.edit)
        layout.addWidget(help)
        layout.addLayout(btn)

    def text(self):
        return self.edit.toPlainText()



class ExportWorker(QObject):
    finished = Signal()
    error = Signal(str)

    def __init__(self, pixmap, crop_rect, text, family, save_path, comment, filepath):
        super().__init__()
        self.pixmap = pixmap
        self.crop_rect = crop_rect
        self.text = text
        self.font_family = family
        self.save_path = save_path
        self.comment = comment
        self.filepath = filepath

    def run(self):
        try:
            rect = self.crop_rect.rect()
            pos = self.crop_rect.pos()
            crop_x = int(pos.x())
            crop_y = int(pos.y())
            crop_w = int(rect.width())
            crop_h = int(rect.height())

            cropped = self.pixmap.copy(crop_x, crop_y, crop_w, crop_h)

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
            text = self.text
            try:
                img = Image.open(self.filepath)
                exif_data = img._getexif()
                if exif_data:
                    for tag_id, value in exif_data.items():
                        tag = ExifTags.TAGS.get(tag_id)
                        if tag == "DateTimeOriginal":
                            # YYYY:MM:DD HH:MM:SS → MM月DD日
                            date_parts = value.split()[0].split(":")
                            mapping = {
                                r"%year%": date_parts[0],
                                r"%month%": date_parts[1],
                                r"%day%": date_parts[2],
                                r"%comment%": self.comment
                            }

                            for k, v in mapping.items():
                                text = text.replace(k, v)
                            break
            except Exception as e:
                print("EXIF 読み込み失敗:", e)

            #前後の空白を削除
            text = text.strip()

            # 左下に文字描画
            if text:
                font_size = max(18, crop_h //30)
                font = QFont(self.font_family, font_size)
                painter.setFont(font)
                painter.setPen(QPen(QColor(0,0,10)))  # 黒

                # 余白計算
                left_margin = 100
                top_margin = font_size * 2.5       # 上に2行分余白（見た目調整用）

                # 描画 y座標 = キャンバス高さ - 下余白
                y_pos = border + crop_h + top_margin
                painter.drawText(left_margin, y_pos, text)


            painter.end()

            if self.save_path:
                canvas.save(self.save_path)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()



class MainWindow(QMainWindow):
    def __init__(self, File = None, parent=None):
        # 親クラスの初期化
        super().__init__(parent)
        self.settings = QSettings("HoshiYakiImo", "aspectChange")

        self.textContent = self.settings.value("textContent", "%year%.%month%.%day% %comment%")
        self.Makewindow()

        self.view.fileDropped.connect(self.loadedFile)

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
        self.acSetFont = QAction("フォントの選択", self)
        self.acSetFont.triggered.connect(self.set_font)
        self.acSetTextTemplete = QAction("挿入する文字列の変更", self)
        self.acSetTextTemplete.triggered.connect(self.set_text_template)
        mFile.addAction(self.acOpenFile)
        mSetting.addAction(self.acSetExportFolder)
        mSetting.addAction(self.acSetFont)
        mSetting.addAction(self.acSetTextTemplete)

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
        self.loadedFile(Filename)

    def loadedFile(self, Filename):
        self.export.setDisabled(False)
        self.view.load_image(Filename)
        self.setWindowTitle(f"aspectChange - {os.path.basename(Filename)}")

    def set_export_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "出力フォルダを選択", "", QFileDialog.ShowDirsOnly)

        if folder:
            self.settings.setValue("exportFolder", folder)

    def set_font(self):
        dlg = FontFamilyDialog(self)
        if dlg.exec():
            family = dlg.selected_family()
            if family:
                self.settings.setValue("fontFamily", family)

    def set_text_template(self):
        dlg = TextTemplateDialog(self.textContent, self)
        if dlg.exec():
            self.textContent = dlg.text()
            self.settings.setValue("textContent", self.textContent)


    def Export(self):
        if self.view.pixmap_item is None or self.view.crop_rect is None:
            return

        pixmap = self.view.pixmap_item.pixmap()
        crop_rect = self.view.crop_rect
        text = self.textContent
        family = self.settings.value("fontFamily", "Arial")
        export_dir = self.settings.value("exportFolder", "")
        save_path, _ = QFileDialog.getSaveFileName(self, "保存先を選択", export_dir, "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg)")
        comment = self.comment_input.text() if hasattr(self, "comment_input") else ""
        filepath = self.view.current_file
        self.thread = QThread()
        self.worker = ExportWorker(pixmap, crop_rect, text, family, save_path, comment, filepath)

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()



    def No_file(self):
        self.export.setDisabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)    # PySide6の実行
    app.setWindowIcon(QIcon("icon.ico"))
    window = MainWindow()           # ユーザがコーディングしたクラス
    if len(sys.argv) > 1:
        file = sys.argv[1]
        if os.path.exists(file):
            window.view.load_image(file)
            window.loadedFile(file)
    window.show()                   # PySide6のウィンドウを表示
    sys.exit(app.exec())            # PySide6の終了