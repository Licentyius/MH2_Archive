"""
MakeHuman 2 Community Archive Downloader V1.2 Elvaerwyn_MH2 2026
Standalone Asset Explorer Module for new creator studio asset upload submissions
"""

import os
import json
import urllib.request
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QListWidget, 
    QLabel, QTextEdit, QProgressBar, QListWidgetItem, 
    QDockWidget, QApplication, QMessageBox
)

# ===========================================
# SECTION 1: THE BACKGROUND DOWNLOAD WORKER
# ===========================================
class AssetDownloadWorker(QThread):
    progress_signal = Signal(int)
    log_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, asset_entry, local_target_base):
        super().__init__()
        self.asset_entry = asset_entry
        self.local_target_base = local_target_base

        domain_name = "github.com"
        repo_location = "/Makehuman-2/MH2_Creator_Portal/raw/refs/heads/main"
        
        self.base_raw_url = "https://" + domain_name + repo_location
        self.run_status_flag = True

    def run(self):
        files = self.asset_entry.get("files", [])
        if not files:
            self.finished_signal.emit(False, "No files listed in manifest.")
            return

        total_files = len(files)
        for index, remote_rel_path in enumerate(files):
            try:
                # Strip spaces from the path file references to read the strings cleanly
                clean_rel_path = str(remote_rel_path).strip()
                self.log_signal.emit(f"Downloading: {os.path.basename(clean_rel_path)}")
                
                source_url = f"{self.base_raw_url}/{clean_rel_path}".replace(" ", "%20")
                destination_path = os.path.normpath(os.path.join(self.local_target_base, clean_rel_path))
                os.makedirs(os.path.dirname(destination_path), exist_ok=True)
                
                req = urllib.request.Request(source_url, headers={"User-Agent": "MH2_Archive_Downloader/1.0"})
                with urllib.request.urlopen(req, timeout=15) as response:
                    with open(destination_path, "wb") as output_file:
                        output_file.write(response.read())
                
                self.progress_signal.emit(int(((index + 1) / total_files) * 100))
            except Exception as e:
                self.finished_signal.emit(False, f"Download failure: {str(e)}")
                return
        self.finished_signal.emit(True, "Asset installed successfully!")

# ================================
# SECTION 2: THE EXPLORER PANEL
# ================================
class MH2AssetBrowserPanel(QWidget):
    def __init__(self, parent_extension, mh_glob):
        super().__init__()
        self.parent_ext = parent_extension
        self.mh_glob = mh_glob

        domain_name = "github.com"
        repo_location = "/Makehuman-2/MH2_Creator_Portal/raw/refs/heads/main"
        
        self.manifest_url = "https://" + domain_name + repo_location + "/manifest.json"
        self.base_raw_url = "https://" + domain_name + repo_location
        
        env = self.mh_glob.env
        base_user_data = env.path_userdata.replace("\\", "/")
        self.local_install_destination = f"{base_user_data}/data" if base_user_data.endswith("/data") else f"{base_user_data}/data"
        
        self.manifest_data = {"assets": []}
        self.init_ui()
        self.fetch_remote_manifest()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        
        self.btn_refresh = QPushButton("🔄 Refresh Archive Marketplace")
        self.btn_refresh.clicked.connect(self.fetch_remote_manifest)
        layout.addWidget(self.btn_refresh)

        self.catalog_list = QListWidget()
        self.catalog_list.itemSelectionChanged.connect(self.handle_selection)
        layout.addWidget(self.catalog_list)

        self.preview_canvas = QLabel("Select an asset to view preview.")
        self.preview_canvas.setAlignment(Qt.AlignCenter)
        self.preview_canvas.setStyleSheet("border: 1px solid #3A3A3A; background-color: #111111; min-height: 130px; border-radius: 4px;")
        layout.addWidget(self.preview_canvas)

        self.meta_display = QTextEdit()
        self.meta_display.setReadOnly(True)
        self.meta_display.setMaximumHeight(80)
        layout.addWidget(self.meta_display)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.btn_download = QPushButton("Download and Install Asset")
        self.btn_download.setEnabled(False)
        self.btn_download.setStyleSheet("font-weight: bold; padding: 6px; background-color: #2A52BE; color: white;")
        self.btn_download.clicked.connect(self.execute_download)
        layout.addWidget(self.btn_download)

    def fetch_remote_manifest(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.catalog_list.clear()
        try:
            req = urllib.request.Request(self.manifest_url, headers={"User-Agent": "MH2_Archive/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                self.manifest_data = json.loads(response.read().decode('utf-8'))
            for index, asset in enumerate(self.manifest_data.get("assets", [])):
                # Strip formatting spaces out of the JSON strings safely
                asset_id = str(asset.get('id', '')).strip()
                asset_type = str(asset.get('type', 'Asset')).strip().upper()
                
                item = QListWidgetItem(f"{asset_id} [{asset_type}]")
                item.setData(Qt.UserRole, index)
                self.catalog_list.addItem(item)
        except Exception as e:
            self.meta_display.setText(f"Failed to fetch manifest:\n{str(e)}")
        QApplication.restoreOverrideCursor()

    def handle_selection(self):
        selected_items = self.catalog_list.selectedItems()
        if not selected_items:
            self.btn_download.setEnabled(False)
            return
        
        # Pull the row item widget out of the list layout selection safely
        item = selected_items[0]
        asset_index = item.data(Qt.UserRole)
        asset = self.manifest_data["assets"][asset_index]
        
        asset_id = str(asset.get('id', '')).strip()
        metadata_text = f"Asset ID: {asset_id}\nFiles Tracked: {len(asset.get('files', []))}\nClick download below to automatically write into your local MakeHuman asset storage folders."
        self.meta_display.setText(metadata_text)
        self.btn_download.setEnabled(True)

        self.preview_canvas.clear()
        self.preview_canvas.setText("Loading Thumbnail Image...")
        
        thumb_rel_path = next((f for f in asset.get("files", []) if str(f).lower().strip().endswith(('.thumb', '.png', '.jpg'))), None)
        if thumb_rel_path:
            self.fetch_preview_thumbnail(thumb_rel_path)
        else:
            self.preview_canvas.setText("No thumbnail preview available.")

    def fetch_preview_thumbnail(self, target_img_path):
        try:
            img_url = f"{self.base_raw_url}/{target_img_path.strip()}".replace(" ", "%20")
            req = urllib.request.Request(img_url, headers={"User-Agent": "MH2_Archive/1.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                img_data = response.read()
            pixmap = QPixmap()
            pixmap.loadFromData(img_data)
            if not pixmap.isNull():
                self.preview_canvas.setPixmap(pixmap.scaled(self.preview_canvas.width(), 130, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.preview_canvas.setText("Error loading thumbnail data.")
        except Exception:
            self.preview_canvas.setText("Preview image skipped.")

    def execute_download(self):
        selected_items = self.catalog_list.selectedItems()
        if not selected_items: return
        
        item = selected_items[0]
        asset_index = item.data(Qt.UserRole)
        asset = self.manifest_data["assets"][asset_index]
        
        self.btn_download.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        
        self.worker = AssetDownloadWorker(asset, self.local_install_destination)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.log_signal.connect(lambda msg: self.meta_display.setText(msg))
        self.worker.finished_signal.connect(self.download_finished)
        self.worker.start()

    def download_finished(self, success, message):
        self.progress_bar.setVisible(False)
        self.btn_download.setEnabled(True)
        if success:
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Error", message)

# ===========================================
# SECTION 3: THE MAIN EXTENSION ANCHOR HOOKS
# ===========================================
class MH2ArchiveExtension:
    def __init__(self, mh_app, mh_glob, pluginname):
        self.mh_app = mh_app
        self.mh_glob = mh_glob
        self.mainwindow = mh_glob.MainWindow
        self.repo = mh_glob.pluginRepo
        self.pluginname = pluginname
        self.dock = None

    def initialize(self):
        if self.pluginname in self.repo:
            self.shutdown()
        self.dock = QDockWidget("MH2 Asset Archive Portal", self.mainwindow)
        self.dock.setObjectName("mh2_archive_portal_dock_widget")
        self.dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        # Now Python knows exactly what MH2AssetBrowserPanel means!
        self.panel = MH2AssetBrowserPanel(self, self.mh_glob)
        self.dock.setWidget(self.panel)
        self.mainwindow.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.show()
        self.repo[self.pluginname] = self
        return True

    def shutdown(self):
        if self.dock:
            self.mainwindow.removeDockWidget(self.dock)
            self.dock.close()
            self.dock.deleteLater()
        self.dock = None

def load_extension(app, glob):
    name = os.path.abspath(__file__)
    plugin = MH2ArchiveExtension(app, glob, name)
    return plugin.initialize()

def unload_extension(glob):
    name = os.path.abspath(__file__)
    if name in glob.pluginRepo:
        glob.pluginRepo[name].shutdown()
        glob.pluginRepo.pop(name)
