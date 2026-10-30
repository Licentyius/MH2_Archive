"""
MakeHuman 2 Community Archive Downloader V3.1 - Elvaerwyn_MH2 2026
Completely Independent Visual Content Browser, Search Engine, Cart & Favorites Matrix
"""

import os
import json
import urllib.request
import shutil
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QLabel, QTextEdit, QProgressBar, QScrollArea, QGridLayout, 
    QFrame, QComboBox, QApplication, QMessageBox, QGroupBox, 
    QStyle, QDockWidget
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
        self.error = None

class AssetDownloadWorker(QThread):
    progress_signal = Signal(int)
    log_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, asset_entry, local_target_base, repo_path):
        super().__init__()
        self.asset_entry = asset_entry
        self.local_target_base = local_target_base
        self.repo_path = repo_path
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
                elif "releases/download/" in clean_rel_path:

                    source_url = f"https://github.com/{clean_rel_path}".replace(" ", "%20")
                else:
                    source_url = f"https://raw.githubusercontent.com/{self.repo_path}/main/{clean_rel_path}".replace(" ", "%20")

                    
                destination_path = os.path.normpath(os.path.join(self.local_target_base, os.path.basename(clean_rel_path)))
                os.makedirs(os.path.dirname(destination_path), exist_ok=True)
                
                req = urllib.request.Request(source_url, headers={"User-Agent": "MH2_Archive_Downloader/3.0"})
                with urllib.request.urlopen(req, timeout=25) as response:
                    with open(destination_path, "wb") as output_file:
                        output_file.write(response.read())
                
                self.progress_signal.emit(int(((index + 1) / total_files) * 100))
            except Exception as e:
                self.error = f"Download failure: {str(e)}\nTarget URL: {source_url}"
                self.finished_signal.emit(False, self.error)
                return
        self.finished_signal.emit(True, "Asset package safely pulled and staged!")

# ==========================================
# SECTION 2: STANDALONE CARD DISP COMPONENT
# ==========================================
class MH2AssetCard(QFrame):
    def __init__(self, key, data, mode, browser_panel):
        super().__init__()
        self.key = str(key)          
        self.data = data        
        self.mode = mode        
        self.browser = browser_panel
        
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(1)
        self.setFixedSize(145, 235)

        self.setStyleSheet("QFrame:hover { border: 1px solid #D35400; }")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Header Controls: Star/Favorite Button Strip Overlay
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        
        self.fav_btn = QPushButton("☆")
        self.fav_btn.setFixedSize(22, 20)
        self.fav_btn.setToolTip("Toggle Favorite")
        self.fav_btn.setStyleSheet("font-weight: bold; background-color: transparent; border: none; color: #FFA000; font-size: 14px;")
        self.fav_btn.clicked.connect(self.toggle_favorite_status)
        header_row.addWidget(self.fav_btn, 0, Qt.AlignLeft)
        header_row.addStretch()
        
        layout.addLayout(header_row)
        
        # 1. Image Thumbnail Render Screen Canvas
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(135, 100)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("background-color: #111111; border-radius: 2px; border: none;")
        
        # 1a. Scrape the manifest data for relative file path structures
        remote_thumb_url = None
        fallback_image_rel_path = None
        
        if isinstance(self.data, dict):
            files_dict = self.data.get("files")
            if "thumb" in self.data:
                remote_thumb_url = self.data.get("thumb")
            elif isinstance(files_dict, dict):
                remote_thumb_url = files_dict.get("thumb") or files_dict.get("screenshot")

        env = self.browser.mh_glob.env
        local_thumb_path = None

        # Clean up variations to find localized cached extraction handles
        clean_key_base = self.key.replace(".zip", "").replace("_unzip", "").replace("_Kit", "").replace("_kit", "").lower()
        if clean_key_base.startswith("pd_"): 
            clean_key_base = clean_key_base[3:]
            
        if "wonder_woman" in clean_key_base: clean_key_base = "ww_kit"
        if "poison_ivy" in clean_key_base: clean_key_base = "pduck_ivy"

        possible_names = [
            self.key + ".thumb", 
            self.key + ".png", 
            f"{clean_key_base}_demo.png", 
            f"{clean_key_base}.thumb"
        ]

        # Scan local disk directories instantly
        for name in possible_names:
            p1 = os.path.normpath(os.path.join(env.path_userdata, "downloads", env.basename, "render", name))
            if os.path.exists(p1): local_thumb_path = p1; break
            p2 = os.path.normpath(os.path.join(self.browser.local_install_destination, name))
            if os.path.exists(p2): local_thumb_path = p2; break

        if local_thumb_path and os.path.exists(local_thumb_path):
            pix = QPixmap(local_thumb_path)
            self.thumb_label.setPixmap(pix.scaled(125, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            # Safe local text placeholder that forces zero internet connection wait times
            self.thumb_label.setText("📦 No Local Preview\n[Ready to Sync]")
            self.thumb_label.setStyleSheet("background-color: #111111; color: #666666; font-size: 9px; text-align: center;")
            
        layout.addWidget(self.thumb_label)
        
        # 2. Meta Title String
        asset_title = str(self.data.get("title", self.key))
        if len(asset_title) > 18:
            asset_title = asset_title[:15] + "..."
            
        self.title_label = QLabel(asset_title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 11px; border: none;")
        layout.addWidget(self.title_label)
        
        # 3. Interactive Operation Buttons Row Layout
        btn_row = QHBoxLayout()
        
        self.action_btn = QPushButton("Inspect")
        self.action_btn.setStyleSheet("background-color: #2A52BE; color: white; font-weight: bold; font-size: 9px; padding: 2px; border-radius: 2px;")
        self.action_btn.clicked.connect(lambda: self.browser.highlight_asset(self))
        btn_row.addWidget(self.action_btn)
        
        self.cart_btn = QPushButton("+ Cart")
        self.cart_btn.setStyleSheet("background-color: #D35400; color: white; font-weight: bold; font-size: 9px; padding: 2px; border-radius: 2px;")
        self.cart_btn.clicked.connect(self.toggle_cart_status)
        btn_row.addWidget(self.cart_btn)
        
        layout.addLayout(btn_row)
        self.update_card_ui_states()

    def update_card_ui_states(self):
        """Refreshes button styles matching active memory array flags state."""
        # Sync Favorites Star Icon Display
        if self.key in self.browser.favorites_db["assets"]:
            self.fav_btn.setText("★")
        else:
            self.fav_btn.setText("☆")
            
        # Sync Cart Operations Action Labels Layout
        if self.key in self.browser.download_cart:
            self.cart_btn.setText("In Cart ✓")
            self.cart_btn.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; font-size: 9px; padding: 2px; border-radius: 2px;")
        else:
            self.cart_btn.setText("+ Cart")
            self.cart_btn.setStyleSheet("background-color: #D35400; color: white; font-weight: bold; font-size: 9px; padding: 2px; border-radius: 2px;")

    def toggle_favorite_status(self):
        if self.key in self.browser.favorites_db["assets"]:
            self.browser.favorites_db["assets"].remove(self.key)
        else:
            self.browser.favorites_db["assets"].append(self.key)
        self.browser.save_local_favorites_database()
        self.update_card_ui_states()
        if self.browser.current_view_mode == "FAVORITES":
            self.browser.filter_browser_grid()

    def toggle_cart_status(self):
        if self.key in self.browser.download_cart:
            self.browser.download_cart.remove(self.key)
        else:
            self.browser.download_cart.append(self.key)
        self.browser.sync_cart_label_counters()
        self.update_card_ui_states()
        if self.browser.current_view_mode == "CART":
            self.browser.filter_browser_grid()

# ==========================================================
# SECTION 3: THE MASTER DETACHED EXPLORER BACKEND PANEL
# ==========================================================
class MH2AssetBrowserPanel(QWidget):
    def __init__(self, parent_extension, mh_glob):
        super().__init__()
        self.parent_ext = parent_extension
        self.mh_glob = mh_glob
        self.selected_card = None
        
        # Core Staging Collections
        self.download_cart = []
        self.active_batch_processing_queue = []
        self.favorites_db = {"assets": []}
        self.current_view_mode = "ALL"  # Modes: ALL, FAVORITES, CART
        
        self.repositories = {
            "Creative Commons BY (Attribution)": "Makehuman-2/MH2_Asset_Repository_CC-By",
            "Creative Commons 0 (Public Domain)": "Makehuman-2/MH2_Asset_Repository_CCO",
            "AGPL (Copyleft Software Archive)": "Makehuman-2/MH2_Asset_repository_AGPL",
            "Creator Portal(Current and Recent Uploads)": "https://raw.githubusercontent.com/Makehuman-2/MH2_Creator_Portal/main/manifest.json"
                                                 
        }
        
        env = self.mh_glob.env
        base_user_data = env.path_userdata.replace("\\", "/")
        self.local_install_destination = os.path.join(base_user_data, "downloads", "staging").replace("\\\\", "/")
        self.favorites_storage_file = os.path.normpath(os.path.join(base_user_data, "downloads", "mh2_archive_favorites.json"))
        self.manifest_data = {"packs": {}}
        self.load_local_favorites_database()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        
        # Repository Controls Suite Row Layout
        layout.addWidget(QLabel("Active Repository Destination Tracker:"))
        
        repo_row = QHBoxLayout()
        self.repo_dropdown = QComboBox()
        self.repo_dropdown.addItems(list(self.repositories.keys()))
        self.repo_dropdown.currentIndexChanged.connect(self.fetch_remote_manifest)
        repo_row.addWidget(self.repo_dropdown, 1)
        
        # Restored Refresh Button (Inheriting native MH2 button styles)
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.setToolTip("Force reload the current remote repository asset manifest catalog")
        self.btn_refresh.clicked.connect(self.fetch_remote_manifest)
        repo_row.addWidget(self.btn_refresh)
        
        layout.addLayout(repo_row)
        
        # Interactive Content Filter Ribbon Layout
        ribbon = QHBoxLayout()
        self.btn_view_all = QPushButton("🗂️ All Packs")
        self.btn_view_all.setCheckable(True)
        self.btn_view_all.setChecked(True)
        self.btn_view_all.clicked.connect(lambda: self.switch_view_mode("ALL"))
        
        self.btn_view_favs = QPushButton("★ Favorites")
        self.btn_view_favs.setCheckable(True)
        self.btn_view_favs.clicked.connect(lambda: self.switch_view_mode("FAVORITES"))
        
        self.btn_view_cart = QPushButton("🛒 Cart (0)")
        self.btn_view_cart.setCheckable(True)
        self.btn_view_cart.clicked.connect(lambda: self.switch_view_mode("CART"))
        
        ribbon.addWidget(self.btn_view_all)
        ribbon.addWidget(self.btn_view_favs)
        ribbon.addWidget(self.btn_view_cart)
        layout.addLayout(ribbon)
        
        # Inline Dynamic Filter-As-You-Type Search Field Bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search registry by asset name or tags...")
        self.search_bar.textChanged.connect(lambda: self.filter_browser_grid())
        layout.addWidget(self.search_bar)

        # Main Dynamic Grid Scroll Architecture Area Window
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setMinimumHeight(240)
        # Style sheet overrides removed so it natively inherits the standard MH2 background
        
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(6)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        self.grid_scroll.setWidget(self.grid_container)
        layout.addWidget(self.grid_scroll)

        # Inspection Details Panels
        self.preview_canvas = QLabel("Select an item card to inspect properties.")
        self.preview_canvas.setAlignment(Qt.AlignCenter)
        self.preview_canvas.setStyleSheet("border: 1px solid #3A3A3A; background-color: #111111; min-height: 100px; border-radius: 4px;")
        layout.addWidget(self.preview_canvas)

        self.meta_display = QTextEdit()
        self.meta_display.setReadOnly(True)
        self.meta_display.setMaximumHeight(75)
        layout.addWidget(self.meta_display)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Standalone Direct Operations Controller Group Box Row
        ops_group = QGroupBox("Dedicated Batch Repository Actions")
        ops_layout = QVBoxLayout(ops_group)
        
        self.btn_download = QPushButton("📥 Download Selected Data")
        self.btn_download.setEnabled(False)
        self.btn_download.setStyleSheet("font-weight: bold; padding: 4px;")
        self.btn_download.clicked.connect(self.execute_download_pipeline)
        ops_layout.addWidget(self.btn_download)

        self.btn_extract = QPushButton("📦 Unpack And Sort Data Files")
        self.btn_extract.setStyleSheet("font-weight: bold; padding: 4px;")
        self.btn_extract.clicked.connect(self.execute_extraction_pipeline)
        ops_layout.addWidget(self.btn_extract)

        self.btn_cleanup = QPushButton("🧹 Clear Temporary File Cache")
        self.btn_cleanup.setStyleSheet("padding: 3px;")
        self.btn_cleanup.clicked.connect(self.execute_cleanup_pipeline)
        ops_layout.addWidget(self.btn_cleanup)
        
        layout.addWidget(ops_group)
        self.fetch_remote_manifest()

    def get_current_repo_path(self):
        """Helper to retrieve the active repo path string layout."""
        if hasattr(self, 'repo_dropdown') and self.repo_dropdown:
            active_text = self.repo_dropdown.currentText()
            return self.repositories.get(active_text, "Makehuman-2/MH2_Asset_Repository_CC-By").strip()
        return "Makehuman-2/MH2_Asset_Repository_CC-By"

    def switch_view_mode(self, mode):
        self.current_view_mode = mode
        self.btn_view_all.setChecked(mode == "ALL")
        self.btn_view_favs.setChecked(mode == "FAVORITES")
        self.btn_view_cart.setChecked(mode == "CART")
        self.filter_browser_grid()

    def sync_cart_label_counters(self):
        self.btn_view_cart.setText(f"🛒 Cart ({len(self.download_cart)})")
        if self.download_cart or self.selected_card:
            self.btn_download.setEnabled(True)
        else:
            self.btn_download.setEnabled(False)

    def load_local_favorites_database(self):
        if os.path.exists(self.favorites_storage_file):
            try:
                with open(self.favorites_storage_file, 'r') as f:
                    self.favorites_db = json.load(f)
                if "assets" not in self.favorites_db: 
                    self.favorites_db = {"assets": []}
            except Exception: 
                self.favorites_db = {"assets": []}

    def save_local_favorites_database(self):
        try:
            os.makedirs(os.path.dirname(self.favorites_storage_file), exist_ok=True)
            with open(self.favorites_storage_file, 'w') as f:
                json.dump(self.favorites_db, f, indent=4)
        except Exception as e: 
            print(f"[MH2 Archive Error] Failed to write database parameters: {str(e)}")

    def fetch_remote_manifest(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.selected_card = None
        
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget(): 
                item.widget().deleteLater()
                
        active_repo = self.repo_dropdown.currentText()
        repo_path = self.repositories.get(active_repo, "Makehuman-2/MH2_Asset_Repository_CC-By").strip()
        
        # If it's a full web address, use it directly. Otherwise, build the default community_packs URL.
        if repo_path.startswith("http"):
            manifest_url = repo_path
        else:
            manifest_url = f"https://raw.githubusercontent.com/{repo_path}/main/community_packs.json".replace(" ", "")
        
        try:
            req = urllib.request.Request(manifest_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                self.manifest_data = json.loads(response.read().decode('utf-8'))
                
            columns_limit = 2
            row, col = 0, 0
            
            if "packs" in self.manifest_data:
                packs = self.manifest_data.get("packs", {})
                for pack_key, pack_info in packs.items():
                    card = MH2AssetCard(pack_key, pack_info, "PACK_MODE", self)
                    self.grid_layout.addWidget(card, row, col)
                    col += 1
                    if col >= columns_limit: 
                        col = 0; row += 1
            else:
                assets = self.manifest_data.get("assets", [])
                for index, asset_data in enumerate(assets):
                    card = MH2AssetCard(index, asset_data, "ASSET_MODE", self)
                    self.grid_layout.addWidget(card, row, col)
                    col += 1
                    if col >= columns_limit: 
                        col = 0; row += 1
            self.filter_browser_grid()
        except Exception as e:
            if hasattr(self, 'meta_display') and self.meta_display is not None:
                self.meta_display.setText(f"Manifest synchronization failure: {str(e)}\nTarget: {manifest_url}")
        self.sync_cart_label_counters()
        QApplication.restoreOverrideCursor()

    def filter_browser_grid(self):
        """Applies layout filter algorithms to card elements dynamically across grids row maps."""
        query = self.search_bar.text().lower().strip()
        
        for i in range(self.grid_layout.count()):
            card = self.grid_layout.itemAt(i).widget()
            if isinstance(card, MH2AssetCard):
                title = str(card.data.get("title", card.key)).lower()
                descr = str(card.data.get("descr", "")).lower()
                
                # Check Ribbon View Filter
                if self.current_view_mode == "FAVORITES" and card.key not in self.favorites_db["assets"]:
                    card.hide(); continue
                if self.current_view_mode == "CART" and card.key not in self.download_cart:
                    card.hide(); continue
                    
                # Check Text Keyword Matches
                if query and (query not in title and query not in descr):
                    card.hide()
                else:
                    card.show()

    def highlight_asset(self, asset_card):
        self.selected_card = asset_card
        for i in range(self.grid_layout.count()):
            w = self.grid_layout.itemAt(i).widget()
            if isinstance(w, MH2AssetCard):
                w.update_card_ui_states()
                
        asset_card.setStyleSheet("background-color: #2E2E2E; border: 2px solid #D35400; border-radius: 4px; color: white;")
        
        if asset_card.mode == "PACK_MODE":
            pack_info = asset_card.data
            metadata_text = f"Package ID: {asset_card.key}\nDescription: {pack_info.get('descr', 'No description.')}\nSize: {pack_info.get('size', 'Unknown')} MB"
        else:
            metadata_text = f"Asset ID: {str(asset_card.data.get('id', asset_card.key))}\nFiles Tracked: {len(asset_card.data.get('files', []))}"
            
        self.meta_display.setText(metadata_text)
        self.btn_download.setEnabled(True)

    def execute_download_pipeline(self):
        """Assembles direct array processing pipelines without external layout script dependency bounds."""
        if not self.download_cart and self.selected_card:
            self.active_batch_processing_queue = [self.selected_card.key]
        else:
            self.active_batch_processing_queue = list(self.download_cart)
            
        if not self.active_batch_processing_queue:
            QMessageBox.information(self, "Queue Empty", "Please select individual items or add elements to your Cart first.")
            return
            
        self.btn_download.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.process_next_queue_element()

    def process_next_queue_element(self):
        """Processes the top element inside the active batch queue stack using precise element index selection."""
        if not self.active_batch_processing_queue:
            self.progress_bar.setVisible(False)
            self.btn_download.setEnabled(True)
            self.meta_display.setText("All pipeline package download processes finished successfully!")
            QMessageBox.information(self, "Download Complete", "Staged operations built successfully! Ready to run Extract loops.")
            return

        target_key = str(self.active_batch_processing_queue[0]).strip()

        if "packs" in self.manifest_data and target_key in self.manifest_data["packs"]:
            pack_info = self.manifest_data["packs"][target_key]
        elif "assets" in self.manifest_data and isinstance(self.manifest_data["assets"], list):
            pack_info = next((a for a in self.manifest_data["assets"] if str(a.get("id")) == target_key), None)
            if not pack_info: 
                pack_info = {"files": [target_key], "url": target_key}
        else:
            pack_info = {"files": [target_key], "url": target_key}

        self.meta_display.setText(f"Processing download pipeline task: {target_key}...")
        active_repo = self.repo_dropdown.currentText()
        repo_path = self.repositories.get(active_repo, "Makehuman-2/MH2_Asset_Repository_CC-By")

        # Extract repo path format if it's our explicit web address exception
        if repo_path.startswith("http"):
            if "://githubusercontent.com" in repo_path:
                parts = repo_path.split("://githubusercontent.com")[-1].split("/")
                repo_path = f"{parts[0]}/{parts[1]}"

        self.worker = AssetDownloadWorker(pack_info, self.local_install_destination, repo_path)

        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.log_signal.connect(self.meta_display.setText)
        self.worker.finished_signal.connect(self.pipeline_element_download_finished)
        self.worker.start()

    def pipeline_element_download_finished(self, success, message):
        if success:
            if self.active_batch_processing_queue:
                completed_key = self.active_batch_processing_queue.pop(0)
                if completed_key in self.download_cart:
                    self.download_cart.remove(completed_key)
                self.sync_cart_label_counters()
 
                try:
                    import zipfile
                    staged_zip = os.path.normpath(os.path.join(self.local_install_destination, completed_key if completed_key.endswith(".zip") else f"{completed_key}.zip"))
                    if os.path.exists(staged_zip):
                        with zipfile.ZipFile(staged_zip, 'r') as archive:
                            internal_img = next((f for f in archive.namelist() if f.lower().endswith(('.thumb', '.png', '.jpg', '.jpeg'))), None)
                            if internal_img:
                                render_cache_dir = os.path.normpath(os.path.join(self.mh_glob.env.path_userdata, "downloads", self.mh_glob.env.basename, "render"))
                                os.makedirs(render_cache_dir, exist_ok=True)
                                with archive.open(internal_img) as source_img, open(os.path.join(render_cache_dir, completed_key + ".thumb"), 'wb') as dest_file:
                                    dest_file.write(source_img.read())
                except Exception as img_err:
                    print(f"[Image Extract Error] {str(img_err)}")


                for i in range(self.grid_layout.count()):
                    w = self.grid_layout.itemAt(i).widget()
                    if isinstance(w, MH2AssetCard) and w.key == completed_key:
                        w.update_card_ui_states()
                        break
            self.process_next_queue_element()

        else:
            self.progress_bar.setVisible(False)
            self.btn_download.setEnabled(True)
            QMessageBox.critical(self, "Pipeline Error", f"Execution halted during staging phase:\n{message}")

    def pull_missing_card_thumb_on_the_fly(self, pack_key):
        """Attempts to cache companion rendering thumbnail templates dynamically upon file completion pipelines."""
        if "packs" in self.manifest_data and pack_key in self.manifest_data["packs"]:
            p_info = self.manifest_data["packs"][pack_key]
            thumb_url = p_info.get("thumb")
            if not thumb_url and "files" in p_info and p_info["files"]:
                thumb_url = next((f for f in p_info["files"] if str(f).lower().endswith(('.png', '.jpg', '.thumb'))), None)
            if thumb_url and not str(thumb_url).endswith(".zip"):
                env = self.mh_glob.env
                dest = os.path.normpath(os.path.join(env.path_userdata, "downloads", env.basename, "render", f"{pack_key}.thumb"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                urllib.request.urlretrieve(str(thumb_url), dest)

    def execute_extraction_pipeline(self):
        if not self.selected_card:
            QMessageBox.warning(self, "Error", "Please select a target card to map deployment scopes first.")
            return
            
        pack_key = str(self.selected_card.key)
        staged_zip = os.path.normpath(os.path.join(self.local_install_destination, pack_key if pack_key.endswith(".zip") else f"{pack_key}.zip"))
        
        if not os.path.exists(staged_zip):
            QMessageBox.warning(self, "Binary Error", f"Staged bundle archive not found at:\n{staged_zip}\nPlease fire download pipelines first.")
            return
            
        try:
            from core.importfiles import AssetPack
            unzipper = AssetPack()
            temp_dir, error = unzipper.unZip(staged_zip)
            if error: raise ValueError(error)

            mesh_folder = self.mh_glob.env.basename if self.mh_glob.env.basename else "hm08"
            user_data_path = self.mh_glob.env.path_sysdata.replace("\\", "/")
            
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    source_file = os.path.join(root, file)
                    file_lower = file.lower()
                    if file_lower.endswith(('.mhclo', '.obj', '.mhmat', '.mat', '.png', '.jpg', '.jpeg', '.thumb')) and not "target" in root:
                        sub_route = f"clothes/{mesh_folder}/{os.path.basename(staged_zip)[:-4]}"
                    elif file_lower.endswith(('.target', '.npz')):
                        sub_route = f"target/{mesh_folder}"
                    elif file_lower.endswith(('.mhmat', '.mat')) and "material" in root:
                        sub_route = f"skins"
                    else:
                        sub_route = os.path.relpath(root, temp_dir).replace("\\", "/").replace("data/", "")
                        
                    final_destination = os.path.join(user_data_path, sub_route, file).replace("\\", "/")
                    os.makedirs(os.path.dirname(final_destination), exist_ok=True)
                    shutil.copy2(source_file, final_destination)
                    
            unzipper.cleanupUnzip()
            self.mh_glob.MainWindow.syncRepositories()
            self.meta_display.setText("Asset package extraction complete! Files cleanly sorted into local targets.")
            QMessageBox.information(self, "Success", f"'{pack_key}' cleanly extracted and mounted onto internal meshes grids successfully!")
        except Exception as err: 
            QMessageBox.critical(self, "Deployment Error", str(err))
    def execute_cleanup_pipeline(self):
        if not os.path.exists(self.local_install_destination): return
        try:
            shutil.rmtree(self.local_install_destination)
            os.makedirs(self.local_install_destination, exist_ok=True)
            self.meta_display.setText("Staging folders cache completely cleared.")
            QMessageBox.information(self, "Cleared", "Temporary staging folders cache cleared successfully.")
        except Exception as e: 
            QMessageBox.critical(self, "Error", str(e))

# ===========================================
# SECTION 4: THE MAIN EXTENSION ANCHOR HOOKS
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
        self.dock = QDockWidget("MH2 Asset Archive Portal (Standalone Edition)", self.mainwindow)
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
