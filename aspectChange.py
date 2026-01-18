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
    
        rect = self.crop_rect.rect()
        pos0 = self.crop_rect.pos()
        img_rect = self.pixmap_item.boundingRect()
    
        new_x = pos0.x() + delta.x()
        new_y = pos0.y() + delta.y()
    
        # clamp
        new_x = max(0, min(new_x, img_rect.width() - rect.width()))
        new_y = max(0, min(new_y, img_rect.height() - rect.height()))
    
        self.crop_rect.setPos(new_x, new_y)
        self.last_pos = pos


    def mouseReleaseEvent(self, event):
        self.dragging = False


    def wheelEvent(self, event):
        if self.crop_rect is None or self.pixmap_item is None:
            return

        delta = event.angleDelta().y()
        if delta == 0:
            return

        scale_step = 20 if delta > 0 else -20  # 拡大・縮小量（調整可）

        self.resize_crop_rect(scale_step)



    def resize_crop_rect(self, delta):
        rect = self.crop_rect.rect()
        img_rect = self.pixmap_item.boundingRect()

        # 現在の中心
        center = self.crop_rect.mapToScene(rect.center())

        # 現在サイズ
        cur_w = rect.width()
        cur_h = rect.height()

        # 4:5 固定
        new_w = cur_w + delta
        new_h = new_w * 5 / 4

        # サイズ制限
        min_size = min(img_rect.width(), img_rect.height()) / 2
        max_size = min(img_rect.width(), img_rect.height())

        if new_w < min_size or new_w > max_size:
            return

        # 新しい rect
        new_rect = QRectF(0, 0, new_w, new_h)
        self.crop_rect.setRect(new_rect)

        # 中心を維持
        self.crop_rect.setPos(
            center.x() - new_w / 2,
            center.y() - new_h / 2
        )

        # はみ出し防止
        self.clamp_crop_rect()


    def clamp_crop_rect(self):
        rect = self.crop_rect.rect()
        pos = self.crop_rect.pos()
        img_rect = self.pixmap_item.boundingRect()

        x = pos.x()
        y = pos.y()

        if x < 0:
            x = 0
        if y < 0:
            y = 0
        if x + rect.width() > img_rect.width():
            x = img_rect.width() - rect.width()
        if y + rect.height() > img_rect.height():
            y = img_rect.height() - rect.height()

        self.crop_rect.setPos(x, y)



class FontFamilyDialog(QDialog):
    def __init__(self, italic, parent = None):
        super().__init__(parent)
        self.setWindowTitle("フォント選択")

        self.list = QListWidget()
        for family in QFontDatabase.families():
            self.list.addItem(family)

        self.italic = QCheckBox("斜体（イタリック）")
        self.italic.setChecked(italic)

        ok = QPushButton("OK")
        ok.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        layout.addWidget(self.italic)
        layout.addWidget(ok)

    def selected_family(self):
        item = self.list.currentItem()
        return item.text() if item else None

    def selected_italic(self):
        item = self.italic.isChecked()
        return item
    
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
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, pixmap, crop_rect, text, family, save_path, comment, filepath, backgroundColor, fontColor, fontItalic):
        super().__init__()
        self.pixmap = pixmap
        self.crop_rect = crop_rect
        self.text = text
        self.font_family = family
        self.save_path = save_path
        self.comment = comment
        self.filepath = filepath
        self.backgroundColor = backgroundColor
        self.fontColor = fontColor
        self.fontItalic = fontItalic

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
            pen = QPen(self.backgroundColor, border)
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
                font.setItalic(self.fontItalic)
                painter.setFont(font)
                painter.setPen(QPen(self.fontColor))

                # 余白計算
                left_margin = 100
                top_margin = font_size * 2.5       # 上に2行分余白（見た目調整用）

                # 描画 y座標 = キャンバス高さ - 下余白
                y_pos = border + crop_h + top_margin
                painter.drawText(left_margin, y_pos, text)


            painter.end()

            if self.save_path:
                canvas.save(self.save_path)
            
            # --- 余白付き（非トリミング）画像 ---
            padded = self.make_padded_pixmap(self.pixmap, self.backgroundColor)

            base, ext = os.path.splitext(self.save_path)
            padded_path = base + "_padded" + ext

            padded.save(padded_path)

            self.copy_exif(self.filepath, self.save_path)
            self.copy_exif(self.filepath, padded_path)


        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit(self.save_path)

    def make_padded_pixmap(self, pixmap: QPixmap, bg_color: QColor):
        w = pixmap.width()
        h = pixmap.height()

        target_ratio = 4 / 5

        if w / h > target_ratio:
            # 横が長い → 縦を伸ばす
            new_w = w
            new_h = int(w / target_ratio)
        else:
            # 縦が長い → 横を伸ばす
            new_h = h
            new_w = int(h * target_ratio)

        canvas = QPixmap(new_w, new_h)
        canvas.fill(bg_color)

        painter = QPainter(canvas)
        x = (new_w - w) // 2
        y = (new_h - h) // 2
        painter.drawPixmap(x, y, pixmap)
        painter.end()

        return canvas
    

    def copy_exif(self, src_path, dst_path):
        try:
            src = Image.open(src_path)
            exif = src.getexif()

            if not exif:
                return
            
            exif[0x0131] = "aspectChange"        # Software

            dst = Image.open(dst_path)
            dst.save(dst_path, exif=exif)
        except Exception as e:
            print("EXIF コピー失敗:", e)





class MainWindow(QMainWindow):
    def __init__(self, File = None, parent=None):
        # 親クラスの初期化
        super().__init__(parent)
        self.settings = QSettings("HoshiYakiImo", "aspectChange")

        self.textContent = self.settings.value("textContent", "%year%.%month%.%day% %comment%")
        self.backgroundColor = self.settings.value("backgroundColor", QColor(244,235,255))
        self.fontColor = self.settings.value("fontColor", QColor(0,0,10))
        self.fontItalic = self.settings.value("fontItalic", False, bool)
        self.viewExportCompletedDialog = self.settings.value("viewExportCompletedDialog", True, bool)
        self.currentOpenFileDir = self.settings.value("currentOpenFileDir", "", str)
        self.lockOpenFileDir = self.settings.value("lockOpenFileDir", False, bool)

        self.Makewindow()

        self.view.fileDropped.connect(self.loadedFile)

        if File == None:
            self.No_file()
            #self.file_open()
        else:
            self.loadedFile(File)

    def Makewindow(self):
        self.setWindowTitle("aspectChange")
        self.resize(800,600)
        self.MainWinMainLayout = QVBoxLayout()
        self.underLayout = QHBoxLayout()

        self.statusBar = self.statusBar()
        self.setStatusBar(self.statusBar)

        MenuBar = self.menuBar()
        mFile = MenuBar.addMenu("ファイル")
        mSetting = MenuBar.addMenu("設定")
        self.acOpenFile = QAction("開く", self)
        self.acOpenFile.triggered.connect(self.file_open)
        self.acSetExportFolder = QAction("出力フォルダの選択", self)
        self.acSetExportFolder.triggered.connect(self.set_export_folder)
        self.acSetFont = QAction("フォントの選択", self)
        self.acSetFont.triggered.connect(self.set_font)
        self.acSetTextTemplete = QAction("文字列フォーマットの変更", self)
        self.acSetTextTemplete.triggered.connect(self.set_text_template)
        self.acSetBackgroundColor = QAction("背景色の変更")
        self.acSetBackgroundColor.triggered.connect(self.set_background_color)
        self.acSetFontColor = QAction("文字色の変更", self)
        self.acSetFontColor.triggered.connect(self.set_font_color)
        self.acViewExportCompletedDialog = QAction("出力完了時のダイアログ表示")
        self.acViewExportCompletedDialog.setCheckable(True)
        self.acViewExportCompletedDialog.triggered.connect(self.view_export_completed_dialog)
        self.aclockOpenFileDir = QAction("選択フォルダのロック")
        self.acViewExportCompletedDialog.setChecked(self.viewExportCompletedDialog)
        mFile.addAction(self.acOpenFile)
        mSetting.addAction(self.acSetExportFolder)
        mSetting.addAction(self.acSetFont)
        mSetting.addAction(self.acSetTextTemplete)
        mSetting.addAction(self.acSetBackgroundColor)
        mSetting.addAction(self.acSetFontColor)
        mSetting.addAction(self.acViewExportCompletedDialog)

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

        self.statusBar.showMessage("正常に起動しました")

    def file_open(self):
        try:
            Filename, tmp = QFileDialog.getOpenFileName(self,"ファイルを開く",self.currentOpenFileDir,"Image File (*.jpeg *.jpg *.png *.bmp)")
            self.currentOpenFileDir = os.path.dirname(Filename)
            self.settings.setValue("currentOpenFileDir", self.currentOpenFileDir)
        except FileNotFoundError:
            self.statusBar.showMessage("ファイルが選択されませんでした")
            return
        if Filename == "":
            return
        self.loadedFile(Filename)

    def loadedFile(self, Filename):
        self.view.load_image(Filename)
        self.currentWindowTitle = f"aspectChange - {os.path.basename(Filename)}"
        self.setWindowTitle(self.currentWindowTitle)
        self.statusBar.showMessage(f"ファイルが開かれました - {Filename}")
        self.export.setDisabled(False)

    def set_export_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "出力フォルダを選択", "", QFileDialog.ShowDirsOnly)

        if folder:
            self.settings.setValue("exportFolder", folder)
            self.statusBar.showMessage(f"出力フォルダを{folder}に設定しました")

    def set_font(self):
        italic = False if str(self.fontItalic) == "False" else True
        print(self.fontItalic)
        dlg = FontFamilyDialog(italic, self)
        if dlg.exec():
            family = dlg.selected_family()
            italic = dlg.selected_italic()
            if family:
                self.settings.setValue("fontFamily", family)
                self.fontFamily = family
                self.settings.setValue("fontItalic", bool(italic))
                self.fontItalic = italic
                self.statusBar.showMessage(f"フォントを{family}に、イタリックを{italic}に設定しました")

    def set_text_template(self):
        dlg = TextTemplateDialog(self.textContent, self)
        if dlg.exec():
            self.textContent = dlg.text()
            self.settings.setValue("textContent", self.textContent)


    def set_background_color(self):
        tmpColor = QColorDialog.getColor(initial = self.backgroundColor, title = "背景色を選択")
        if tmpColor.isValid():
            self.backgroundColor = tmpColor
            self.statusBar.showMessage(f"背景色を変更しました")
            self.settings.setValue("backgroundColor", tmpColor)

    def set_font_color(self):
        tmpColor = QColorDialog.getColor(initial = self.fontColor, title = "文字色を選択")
        if tmpColor.isValid():
            self.fontColor = tmpColor
            self.statusBar.showMessage(f"文字色を変更しました")
            self.settings.setValue("fontColor", tmpColor)

    def view_export_completed_dialog(self, checked):
        self.viewExportCompletedDialog = checked
        self.settings.setValue("viewExportCompletedDialog", self.viewExportCompletedDialog)


    def Export(self):
        self.statusBar.showMessage("出力準備中")
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
        self.worker = ExportWorker(pixmap, crop_rect, text, family, save_path, comment, filepath, self.backgroundColor, self.fontColor, self.fontItalic)

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.error.connect(self.error_export)
        self.exportError = False

        self.export.setDisabled(True)
        self.worker.finished.connect(self.finish_export)
        self.setEnabled(False)
        self.statusBar.showMessage("出力中……")
        self.setWindowTitle(f"出力中…… - {save_path}")

        self.thread.start()


    def finish_export(self, save_path):
        if not self.exportError:
            self.export.setDisabled(False)
            self.statusBar.showMessage(f"出力完了 - {save_path}")
            if self.viewExportCompletedDialog:
                QMessageBox.information(self, "出力完了", f"保存が完了しました\n- {save_path}")
        else:
            self.statusBar.showMessage(f"エラーが発生しました({self.errorDetail})")
        self.setEnabled(True)
        self.setWindowTitle(self.currentWindowTitle)

    def error_export(self, detail):
        self.exportError = True
        self.errorDetail = detail

    def No_file(self):
        self.export.setDisabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)    # PySide6の実行
    app.setWindowIcon(QIcon("icon.ico"))
    window = None
    if len(sys.argv) > 1:
        window = MainWindow(sys.argv[1])
    else:
        window = MainWindow()

    window.show()                   # PySide6のウィンドウを表示
    sys.exit(app.exec())            # PySide6の終了