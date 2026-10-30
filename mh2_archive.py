"""
MakeHuman 2 Community Archive Downloader V2.1 Elvaerwyn_MH2 2026
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
    QDockWidget, QApplication, QMessageBox, QComboBox
)

# ===========================================
# SECTION 1: THE BACKGROUND DOWNLOAD WORKER
# ===========================================
class AssetDownloadWorker(QThread):
    progress_signal = Signal(int)
    log_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, asset_entry, local_target_base, repo_path):
        super().__init__()
        self.asset_entry = asset_entry
        self.local_target_base = local_target_base
        self.repo_path = repo_path
        self.base_raw_url = f"https://raw.githubusercontent.com/{repo_path}/main"
        self.run_status_flag = True
        self.error = None

    def run(self):
        files = self.asset_entry.get("files", [])
        url_pack_target = self.asset_entry.get("url", "")
        
        if not files and url_pack_target:
            files = [url_pack_target]

        if not files:
            self.error = "No assets or package binaries listed in manifest."
            self.finished_signal.emit(False, self.error)
            return

        total_files = len(files)
        for index, remote_rel_path in enumerate(files):
            try:
                clean_rel_path = str(remote_rel_path).strip().lstrip("/")
                self.log_signal.emit(f"Downloading: {os.path.basename(clean_rel_path)}")
                
                if clean_rel_path.startswith("http"):
                    source_url = clean_rel_path
                else:
                    source_url = f"https://github.com/{clean_rel_path}".replace(" ", "%20")
                    
                if "/releases/download/" in source_url:
                    pass
                
                destination_path = os.path.normpath(os.path.join(self.local_target_base, os.path.basename(clean_rel_path)))
                os.makedirs(os.path.dirname(destination_path), exist_ok=True)
                
                req = urllib.request.Request(source_url, headers={"User-Agent": "MH2_Archive_Downloader/2.0"})
                with urllib.request.urlopen(req, timeout=25) as response:
                    with open(destination_path, "wb") as output_file:
                        output_file.write(response.read())
                
                self.progress_signal.emit(int(((index + 1) / total_files) * 100))
            except Exception as e:
                self.error = f"Download failure: {str(e)}"
                self.finished_signal.emit(False, self.error)
                return
        self.finished_signal.emit(True, "Asset package safely pulled and staged!")

# ================================
# SECTION 2: THE EXPLORER PANEL
# ================================
class MH2AssetBrowserPanel(QWidget):
    def __init__(self, parent_extension, mh_glob):
        super().__init__()
        self.parent_ext = parent_extension
        self.mh_glob = mh_glob
        
        self.repositories = {
            "Creative Commons BY (Attribution)": "Makehuman-2/MH2_Asset_Repository_CC-By",
            "Creative Commons 0 (Public Domain)": "Makehuman-2/MH2_Asset_Repository_CCO",
            "AGPL (Copyleft Software Archive)": "Makehuman-2/MH2_Asset_repository_AGPL"
        }
        
        env = self.mh_glob.env
        base_user_data = env.path_userdata.replace("\\", "/")
        self.local_install_destination = os.path.join(base_user_data, "downloads", "staging").replace("\\", "/")
        
        self.manifest_data = {"packs": {}}
        self.init_ui()
        self.fetch_remote_manifest()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        
        layout.addWidget(QLabel("Select Active GitHub Repository Archive:"))
        self.repo_dropdown = QComboBox()
        self.repo_dropdown.addItems(list(self.repositories.keys()))
        self.repo_dropdown.currentIndexChanged.connect(self.fetch_remote_manifest)
        layout.addWidget(self.repo_dropdown)
        
        self.btn_refresh = QPushButton("🔄 Force Sync Selected Repository")
        self.btn_refresh.clicked.connect(self.fetch_remote_manifest)
        layout.addWidget(self.btn_refresh)

        self.catalog_list = QListWidget()
        self.catalog_list.itemSelectionChanged.connect(self.handle_selection)
        layout.addWidget(self.catalog_list)

        self.preview_canvas = QLabel("Select an asset to view details.")
        self.preview_canvas.setAlignment(Qt.AlignCenter)
        self.preview_canvas.setStyleSheet("border: 1px solid #3A3A3A; background-color: #111111; min-height: 130px; border-radius: 4px;")
        layout.addWidget(self.preview_canvas)

        self.meta_display = QTextEdit()
        self.meta_display.setReadOnly(True)
        self.meta_display.setMaximumHeight(90)
        layout.addWidget(self.meta_display)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.btn_download = QPushButton("Download and Install Asset Pack")
        self.btn_download.setEnabled(False)
        self.btn_download.setStyleSheet("font-weight: bold; padding: 6px; background-color: #2A52BE; color: white;")
        self.btn_download.clicked.connect(self.execute_download)
        layout.addWidget(self.btn_download)

        # --- NEW INTEGRATED ZIP PROCESSING COMPANION SUITE ---
        self.btn_extract = QPushButton("📦 Extract & Install Staged Zip Archive")
        self.btn_extract.setStyleSheet("font-weight: bold; padding: 5px; background-color: #2E7D32; color: white;")
        self.btn_extract.clicked.connect(self.execute_extraction)
        layout.addWidget(self.btn_extract)

        self.btn_cleanup = QPushButton("🗑️ Clean Up Staging Cache")
        self.btn_cleanup.setStyleSheet("padding: 4px; background-color: #C62828; color: white;")
        self.btn_cleanup.clicked.connect(self.execute_cleanup)
        layout.addWidget(self.btn_cleanup)

    def execute_extraction(self):
        """Unzips compiled assets and routes files to their core directories natively."""
        selected_items = self.catalog_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Extraction Error", "Please select an asset bundle from the catalog list view first.")
            return

        item = selected_items[0]
        pack_key = item.data(Qt.UserRole)

        staged_zip = os.path.normpath(os.path.join(self.local_install_destination, f"{pack_key}"))
        if not os.path.exists(staged_zip):
            # Fallback check if the key is missing its suffix extension
            staged_zip = os.path.normpath(os.path.join(self.local_install_destination, pack_key if pack_key.endswith(".zip") else f"{pack_key}.zip"))

        if not os.path.exists(staged_zip):
            QMessageBox.critical(self, "Extraction Error", f"Staged bundle binary not found at:\n{staged_zip}\nPlease download the package file first.")
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.meta_display.setText(f"Extracting asset files out of archive track: {pack_key}...")
        
        try:
            # Re-use the plugin's built-in AssetPack unzipper engine to keep system actions uniform
            from core.importfiles import AssetPack
            unzipper = AssetPack()

            temp_dir, error = unzipper.unZip(staged_zip)
            if error:
                raise ValueError(error)

            import shutil
            mesh_folder = self.mh_glob.env.basename if self.mh_glob.env.basename else "hm08"

            user_data_path = self.mh_glob.env.path_sysdata.replace("\\", "/")

            
            # Sort files dynamically out of the zip tree into their correct target directories
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    source_file = os.path.join(root, file)
                    file_lower = file.lower()
                    
                    if file_lower.endswith(('.mhclo', '.obj', '.mhmat', '.mat', '.png', '.jpg', '.jpeg', '.thumb')) and not "target" in root:
                        pack_folder_name = os.path.basename(staged_zip)[:-4]
                        sub_route = f"clothes/{mesh_folder}/{pack_folder_name}"
                    elif file_lower.endswith(('.target', '.npz')):
                        sub_route = f"target/{mesh_folder}"
                    elif file_lower.endswith(('.mhmat', '.mat')) and "material" in root:
                        sub_route = f"skins"
                    else:
                        sub_route = os.path.relpath(root, temp_dir).replace("\\", "/")
                        # Clean up any generic paths if they explicitly started with data/ inside the zip
                        if sub_route.lower().startswith("data/"):
                            sub_route = sub_route[5:]
                    
                    final_destination = os.path.join(user_data_path, sub_route, file).replace("\\", "/")
                    os.makedirs(os.path.dirname(final_destination), exist_ok=True)
                    shutil.copy2(source_file, final_destination)

            unzipper.cleanupUnzip()
            self.mh_glob.MainWindow.syncRepositories() # Refresh MakeHuman's mesh grid listings
            self.meta_display.setText("Asset package extraction complete! Files cleanly sorted into your local inventory targets.")
            QMessageBox.information(self, "Success", f"'{pack_key}' has been successfully extracted and installed into your local MakeHuman directories!")
        except Exception as err:
            self.meta_display.setText(f"Extraction processing halted: {str(err)}")
            QMessageBox.critical(self, "Error", f"Failed to extract package: {str(err)}")
        finally:
            QApplication.restoreOverrideCursor()

    def execute_cleanup(self):
        """Clears out the temporary staging directory cache to free up hard drive space."""
        if not os.path.exists(self.local_install_destination):
            return
            
        try:
            import shutil
            # Deletes the temporary downloads folder contents cleanly
            for filename in os.listdir(self.local_install_destination):
                file_path = os.path.normpath(os.path.join(self.local_install_destination, filename))
                if os.path.isfile(file_path):
                    os.remove(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    
            self.meta_display.setText("Staging directory cache cleared successfully!")
            QMessageBox.information(self, "Cache Cleared", "Staging directory cache has been completely emptied.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to empty cache folders: {str(e)}")


    def get_current_repo_path(self):
        selected_text = self.repo_dropdown.currentText()
        return self.repositories.get(selected_text, "Makehuman-2/MH2_Asset_Repository_CC-By")

    def fetch_remote_manifest(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.catalog_list.clear()
        self.btn_download.setEnabled(False)
        
        active_repo = self.get_current_repo_path().strip()
        # Cleanly build and sanitize the target web URL
        manifest_url = f"https://raw.githubusercontent.com/{active_repo}/main/community_packs.json".replace(" ", "")
        
        # Log to terminal so you can double check the string structure
        print(f"[DEBUG MAP] Attempting to resolve URL: {manifest_url}")
        
        try:
            req = urllib.request.Request(manifest_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=10) as response:
                raw_bytes = response.read()
                self.manifest_data = json.loads(raw_bytes.decode('utf-8'))
                
            if "packs" in self.manifest_data:
                packs = self.manifest_data.get("packs", {})
                for pack_key, pack_info in packs.items():
                    size = pack_info.get("size", "Unknown")
                    item = QListWidgetItem(f"📦 {pack_key} ({size} MB)")
                    item.setData(Qt.UserRole, pack_key)

                    item.setData(Qt.UserRole + 1, "PACK_MODE")
                    self.catalog_list.addItem(item)
            else:
                assets = self.manifest_data.get("assets", [])
                for index, asset in enumerate(assets):
                    asset_id = str(asset.get('id', '')).strip()
                    asset_type = str(asset.get('type', 'Asset')).strip().upper()
                    item = QListWidgetItem(f"📄 {asset_id} [{asset_type}]")
                    item.setData(Qt.UserRole, index)

                    item.setData(Qt.UserRole + 1, "ASSET_MODE")
                    self.catalog_list.addItem(item)

        except Exception as e:
            self.meta_display.setText(f"Failed to connect to direct GitHub manifest:\n{str(e)}\n\nAttempted URL:\n{manifest_url}")
        QApplication.restoreOverrideCursor()

    def handle_selection(self):
        selected_items = self.catalog_list.selectedItems()
        if not selected_items:
            self.btn_download.setEnabled(False)
            return
        
        item = selected_items[0]

        mode = item.data(Qt.UserRole + 1)
        raw_user_data = item.data(Qt.UserRole)

        if mode == "PACK_MODE":
            # Process GitHub Repository Data Map
            pack_info = self.manifest_data.get("packs", {}).get(raw_user_data, {})
            descr = pack_info.get("descr", "No description provided.")
            url_target = pack_info.get("url", "")
            size = pack_info.get("size", "Unknown")
            metadata_text = f"Package ID: {raw_user_data}\nDescription: {descr}\nSize: {size} MB\n\nDestination URL: {url_target}"
        else:
            # Process Staging Upload Panel Data Map
            asset = self.manifest_data["assets"][raw_user_data]
            asset_id = str(asset.get('id', '')).strip()
            metadata_text = f"Asset ID: {asset_id}\nFiles Tracked: {len(asset.get('files', []))}\nClick download below to install staging package."
            
        self.meta_display.setText(metadata_text)
        self.btn_download.setEnabled(True)

    def execute_download(self):
        selected_items = self.catalog_list.selectedItems()
        if not selected_items: return
        
        item = selected_items[0]
        pack_key = item.data(Qt.UserRole)
        pack_info = self.manifest_data["packs"][pack_key]
        
        self.btn_download.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        
        self.worker = AssetDownloadWorker(pack_info, self.local_install_destination, self.get_current_repo_path())
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.log_signal.connect(lambda msg: self.meta_display.setText(msg))
        self.worker.finished_signal.connect(self.download_finished)
        self.worker.start()

    def download_finished(self, success, message):
        self.progress_bar.setVisible(False)
        self.btn_download.setEnabled(True)
        if success:
            QMessageBox.information(self, "Success", "Package downloaded successfully into local staging! Use the Extract tool to install assets.")
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
        self.dock = QDockWidget("MH2 Asset Archive Portal (Direct Git)", self.mainwindow)
        self.dock.setObjectName("mh2_archive_portal_dock_widget")
        self.dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
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
