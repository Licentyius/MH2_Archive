"""
MakeHuman 2 Community Archive Downloader V4.1 - Elvaerwyn_MH2 2026
Completely Independent Visual Content Browser, Search Engine, Cart & Favorites Matrix
"""

import os
import json
import urllib.request
import shutil
import zipfile
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QLabel, QTextEdit, QProgressBar, QScrollArea, QGridLayout, 
    QFrame, QComboBox, QApplication, QMessageBox, QGroupBox, 
    QStyle, QDockWidget, QTabWidget
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
                
                req = urllib.request.Request(source_url, headers={"User-Agent": "MH2_Archive_Downloader/3.2"})
                with urllib.request.urlopen(req, timeout=25) as response:
                    with open(destination_path, "wb") as output_file:
                        output_file.write(response.read())
                
                self.progress_signal.emit(int(((index + 1) / total_files) * 100))
            except Exception as e:
                self.error = f"Download failure: {str(e)}\nTarget URL: {source_url}"
                self.finished_signal.emit(False, self.error)
                return
        self.finished_signal.emit(True, "Asset package safely pulled and staged!")

# =============================================
# SECTION 2: STANDALONE CARD DISPLAY COMPONENT
# =============================================
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
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        
        # Header Controls: Star / Favorite Button Strip
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
        
        # Image Thumbnail Canvas
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(133, 100)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.thumb_label)
        
        # Meta Title String Display Label
        asset_title = str(self.data.get("title", self.key))
        if len(asset_title) > 18:
            asset_title = asset_title[:15] + "..."
            
        self.title_label = QLabel(asset_title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        layout.addWidget(self.title_label)
        
        # Interactive Grid Action Row Buttons
        btn_row = QHBoxLayout()
        self.action_btn = QPushButton("Inspect")
        self.action_btn.clicked.connect(lambda: self.browser.highlight_asset(self))
        btn_row.addWidget(self.action_btn)
        
        self.cart_btn = QPushButton("+ Cart")
        self.cart_btn.clicked.connect(self.toggle_cart_status)
        btn_row.addWidget(self.cart_btn)
        
        layout.addLayout(btn_row)
        
        # Initialize thumbnail pipeline
        self.refresh_thumbnail_preview()
        self.update_card_ui_states()

    def refresh_thumbnail_preview(self):
        """Locates cached thumbnails, falls back to direct live raw image downloads."""
        env = self.browser.mh_glob.env
        
        # 1. Clean up key base names for standard file name checking matches
        clean_key_base = self.key.replace(".zip", "").replace("_unzip", "").replace("_Kit", "").replace("_kit", "").lower()
        if clean_key_base.startswith("pd_"): 
            clean_key_base = clean_key_base[3:]
        if "wonder_woman" in clean_key_base: 
            clean_key_base = "ww_kit"
        if "poison_ivy" in clean_key_base: 
            clean_key_base = "pduck_ivy"

        possible_names = [
            self.key + ".thumb", 
            self.key + ".png", 
            f"{clean_key_base}_demo.png", 
            f"{clean_key_base}.thumb"
        ]

        manifest_thumb = self.data.get("thumb", "").strip()
        if manifest_thumb:
            possible_names.insert(0, os.path.basename(manifest_thumb))

        # 2. Check localized cache directories exactly in the profile user space
        cache_dir = os.path.normpath(os.path.join(env.path_userdata, "downloads", env.basename, "render"))
        os.makedirs(cache_dir, exist_ok=True)
        
        local_thumb_path = None
        for name in possible_names:
            p1 = os.path.normpath(os.path.join(cache_dir, name))
            if os.path.exists(p1) and os.path.getsize(p1) > 0: 
                local_thumb_path = p1
                break
            p2 = os.path.normpath(os.path.join(self.browser.local_install_destination, name))
            if os.path.exists(p2) and os.path.getsize(p2) > 0: 
                local_thumb_path = p2
                break

        # 3. Load image from disk instantly if it exists
        if local_thumb_path and os.path.exists(local_thumb_path):
            pix = QPixmap(local_thumb_path)
            if not pix.isNull():
                self.thumb_label.setPixmap(pix.scaled(125, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.thumb_label.setStyleSheet("border: 1px solid #555555; border-radius: 2px;")
                return

        # 4. absolute URL transformer for raw assets
        if manifest_thumb:

            raw_url = manifest_thumb.replace("https://github.com", "https://raw.githubusercontent.com")
            raw_url = raw_url.replace("http://github.com", "https://raw.githubusercontent.com")

            raw_url = raw_url.replace("/blob/main/", "/main/").replace("/tree/main/", "/main/")
            raw_url = raw_url.replace("/blob/master/", "/master/").replace("/tree/master/", "/master/")

            out_name = os.path.basename(raw_url)
            target_download_path = os.path.normpath(os.path.join(cache_dir, out_name))
            
            if not os.path.exists(target_download_path):
                try:
                    self.thumb_label.setText("🔄 Syncing...")
                    self.thumb_label.setStyleSheet("color: #D35400; font-size: 9px;")
                    self.browser.async_pull_thumbnail(raw_url, target_download_path, self)
                    return
                except Exception:
                    pass

        self.thumb_label.setText("📦 No Local Preview\n[Ready to Sync]")
        self.thumb_label.setStyleSheet("background-color: rgba(0, 0, 0, 40); color: #888888; font-size: 9px; border: 1px dashed #444444; border-radius: 2px;")

    def update_card_ui_states(self):
        if self.key in self.browser.favorites_db["assets"]:
            self.fav_btn.setText("★")
        else:
            self.fav_btn.setText("☆")
            
        if self.key in self.browser.download_cart:
            self.cart_btn.setText("In Cart ✓")
            self.cart_btn.setStyleSheet("font-weight: bold; color: #2ECC71;")
        else:
            self.cart_btn.setText("+ Cart")
            self.cart_btn.setStyleSheet("")

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

# =======================================================
# SECTION 3: THE MASTER DETACHED EXPLORER BACKEND PANEL
# =======================================================
class MH2AssetBrowserPanel(QWidget):
    def __init__(self, parent_extension, mh_glob):
        super().__init__()
        self.parent_ext = parent_extension
        self.mh_glob = mh_glob
        self.selected_card = None
        self.download_cart = []
        self.active_batch_processing_queue = []
        self.favorites_db = {"assets": []}
        self.current_view_mode = "ALL"
        self._thumb_threads = []
        self.repositories = {
            "Creative Commons BY (Attribution)": "Makehuman-2/MH2_Asset_Repository_CC-By",
            "Creative Commons 0 (Public Domain)": "Makehuman-2/MH2_Asset_Repository_CCO",
            "AGPL (Copyleft Software Archive)": "Makehuman-2/MH2_Asset_repository_AGPL",
            "Creator Portal(Current and Recent Uploads)": "https://raw.githubusercontent.com/Makehuman-2/MH2_Creator_Portal/main/manifest.json"
                                                 
        }
        env = self.mh_glob.env
        base_user_data = env.path_userdata.replace("\\", "/")
        self.local_install_destination = os.path.join(base_user_data, "downloads", "staging").replace("\\", "/")
        self.favorites_storage_file = os.path.normpath(os.path.join(base_user_data, "downloads", "mh2_archive_favorites.json"))
        self.manifest_data = {"packs": {}}
        self.load_local_favorites_database()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        layout.addWidget(QLabel("Active Repository Destination Tracker:"))
        repo_row = QHBoxLayout()
        self.repo_dropdown = QComboBox()
        self.repo_dropdown.addItems(list(self.repositories.keys()))
        self.repo_dropdown.currentIndexChanged.connect(self.fetch_remote_manifest)
        repo_row.addWidget(self.repo_dropdown, 1)
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.setToolTip("Force reload the current remote repository asset manifest catalog")
        self.btn_refresh.clicked.connect(self.fetch_remote_manifest)
        repo_row.addWidget(self.btn_refresh)
        layout.addLayout(repo_row)
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
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search registry by asset name or tags...")
        self.search_bar.textChanged.connect(lambda: self.filter_browser_grid())
        layout.addWidget(self.search_bar)
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setMinimumHeight(240)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(6)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.grid_scroll.setWidget(self.grid_container)
        layout.addWidget(self.grid_scroll)
        # ======================================
        # NEW DEEP INSPECTION TAB MATRIX LAYOUT
        # ======================================
        inspection_group = QGroupBox("Target Package Deep Inspector Matrix")
        inspection_layout = QVBoxLayout(inspection_group)
        inspection_layout.setContentsMargins(4, 4, 4, 4)
        inspection_layout.setSpacing(4)
        
        self.inspect_tabs = QTabWidget()
        
        # Tab A: Scroll-Backed High-Resolution Visual Workspace Canvas
        self.image_viewer_scroll = QScrollArea()
        self.image_viewer_scroll.setWidgetResizable(True)
        self.image_viewer_scroll.setAlignment(Qt.AlignCenter)
        self.image_viewer_scroll.setStyleSheet("background-color: rgba(0, 0, 0, 80); border: 1px solid #444444; border-radius: 4px;")
        
        self.preview_canvas = QLabel()
        self.preview_canvas.setAlignment(Qt.AlignCenter)
        self.preview_canvas.setText("Select an item card to inspect properties.")
        self.preview_canvas.setStyleSheet("color: #777777; background: transparent; border: none;")
        
        self.image_viewer_scroll.setWidget(self.preview_canvas)
        self.inspect_tabs.addTab(self.image_viewer_scroll, "🔍 Inspection Image")
        
        # Tab B: Monospace Metadata Registry Logs Stream
        self.meta_display = QTextEdit()
        self.meta_display.setReadOnly(True)
        self.meta_display.setMinimumHeight(140)
        self.meta_display.setStyleSheet("font-family: 'Courier New', monospace; font-size: 11px;")
        self.inspect_tabs.addTab(self.meta_display, "📄 Asset Profile Logs")
        
        inspection_layout.addWidget(self.inspect_tabs)
        layout.addWidget(inspection_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        ops_group = QGroupBox("Dedicated Batch Repository Actions")
        ops_layout = QVBoxLayout(ops_group)
        
        # Action Button 1: Download Core (Dynamic Text Hooked)
        self.btn_download = QPushButton("📥 Download Selected Data")
        self.btn_download.setEnabled(False)
        self.btn_download.setStyleSheet("font-weight: bold; padding: 4px;")
        self.btn_download.clicked.connect(self.execute_download_pipeline)
        ops_layout.addWidget(self.btn_download)
        
        # ACTION BUTTON  2: Download Everything Currently Visible in the Repo Grid View
        self.btn_download_repo = QPushButton("🌐 Download All Packs in Visible Repo")
        self.btn_download_repo.setStyleSheet("font-weight: bold; padding: 4px;")
        self.btn_download_repo.clicked.connect(self.execute_repo_bulk_download)
        ops_layout.addWidget(self.btn_download_repo)
        
        # Action Button 3: Unpack Core
        self.btn_extract = QPushButton("📦 Unpack And Sort Data Files")
        self.btn_extract.setStyleSheet("font-weight: bold; padding: 4px;")
        self.btn_extract.clicked.connect(self.execute_extraction_pipeline)
        ops_layout.addWidget(self.btn_extract)
        
        # Action Button 4: Cleanup Core
        self.btn_cleanup = QPushButton("🧹 Clear Temporary File Cache")
        self.btn_cleanup.setStyleSheet("padding: 3px;")
        self.btn_cleanup.clicked.connect(self.execute_cleanup_pipeline)
        ops_layout.addWidget(self.btn_cleanup)
        layout.addWidget(ops_group)

        self.fetch_remote_manifest()

    def async_pull_thumbnail(self, url, dest_path, card_widget):
        class QuickThumbWorker(QThread):
            done = Signal(bool)
            def run(self):
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "MH2_Archive_Downloader/3.2"})
                    with urllib.request.urlopen(req, timeout=15) as response:
                        with open(dest_path, "wb") as f:
                            f.write(response.read())
                    self.done.emit(True)
                except Exception:
                    self.done.emit(False)
        worker = QuickThumbWorker(self)
        worker.done.connect(lambda success: card_widget.refresh_thumbnail_preview() if success else None)
        self._thumb_threads.append(worker)
        worker.finished.connect(lambda: self._thumb_threads.remove(worker) if worker in self._thumb_threads else None)
        worker.start()

    def get_current_repo_path(self):
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
        self.btn_download.setEnabled(bool(self.download_cart or self.selected_card))

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
        
        if hasattr(self, 'preview_canvas') and self.preview_canvas:
            self.preview_canvas.clear()
            self.preview_canvas.setText("Select an item card to inspect properties.")
        if hasattr(self, 'meta_display') and self.meta_display:
            self.meta_display.clear()
            
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 1. Establish precise structural prefix mapping lists 
        if self.mh_glob.baseClass is None:
            allowprefix = ["common"]
            parentmesh = None
        else:
            parentmesh = self.mh_glob.baseClass.baseInfo.get("parentmesh")
            allowprefix = ["common", self.mh_glob.env.basename]

            if self.mh_glob.env.basename == "fantasy":
                allowprefix.append("hm08")
                
        if parentmesh:
            allowprefix.append(parentmesh)
                
        active_repo = self.repo_dropdown.currentText()
        repo_path = self.repositories.get(active_repo, "Makehuman-2/MH2_Asset_Repository_CC-By").strip()
        
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

                    if "-" not in pack_key:
                        card = MH2AssetCard(pack_key, pack_info, "PACK_MODE", self)
                        self.grid_layout.addWidget(card, row, col)
                        col += 1
                        if col >= columns_limit:
                            col = 0; row += 1
                        continue
 
                    parts = pack_key.split("-")
                    if parts[0] not in allowprefix:
                        continue
                        
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
        query = self.search_bar.text().lower().strip()
        for i in range(self.grid_layout.count()):
            card = self.grid_layout.itemAt(i).widget()
            if isinstance(card, MH2AssetCard):
                title = str(card.data.get("title", card.key)).lower()
                descr = str(card.data.get("descr", "")).lower()
                
                if self.current_view_mode == "FAVORITES" and card.key not in self.favorites_db["assets"]:
                    card.hide()
                    continue
                if self.current_view_mode == "CART" and card.key not in self.download_cart:
                    card.hide()
                    continue
                    
                if query and (query not in title and query not in descr):
                    card.hide()
                else:
                    card.show()

    def highlight_asset(self, asset_card):
        self.selected_card = asset_card
        
        if hasattr(self, 'inspect_tabs'):
            self.inspect_tabs.setCurrentIndex(0)
            
        env = self.mh_glob.env
        clean_key_base = asset_card.key.replace(".zip", "").replace("_unzip", "").replace("_Kit", "").replace("_kit", "").lower()
        if clean_key_base.startswith("pd_"): 
            clean_key_base = clean_key_base[3:]
        if "wonder_woman" in clean_key_base: 
            clean_key_base = "ww_kit"
        if "poison_ivy" in clean_key_base: 
            clean_key_base = "pduck_ivy"

        possible_names = [
            asset_card.key + ".thumb", 
            asset_card.key + ".png", 
            f"{clean_key_base}_demo.png", 
            f"{clean_key_base}.thumb"
        ]
        manifest_thumb = asset_card.data.get("thumb", "").strip()
        if manifest_thumb:
            possible_names.insert(0, os.path.basename(manifest_thumb))

        cache_dir = os.path.normpath(os.path.join(env.path_userdata, "downloads", env.basename, "render"))
        
        local_full_res_path = None
        for name in possible_names:
            p1 = os.path.normpath(os.path.join(cache_dir, name))
            if os.path.exists(p1) and os.path.getsize(p1) > 0:
                local_full_res_path = p1
                break
            p2 = os.path.normpath(os.path.join(self.local_install_destination, name))
            if os.path.exists(p2) and os.path.getsize(p2) > 0:
                local_full_res_path = p2
                break

        if local_full_res_path and os.path.exists(local_full_res_path):
            high_res_pixmap = QPixmap(local_full_res_path)
        else:
            high_res_pixmap = asset_card.thumb_label.pixmap()

        if high_res_pixmap and not high_res_pixmap.isNull():
            available_w = max(self.image_viewer_scroll.viewport().width() - 15, 480)
            available_h = max(self.image_viewer_scroll.viewport().height() - 15, 340)
            self.preview_canvas.setPixmap(high_res_pixmap.scaled(
                available_w, available_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        else:
            self.preview_canvas.clear()
            self.preview_canvas.setText("📦 Pack Staged\n[No Preview Cache discovered]")

        # CHECK ON-DISK AVAILABILITY FOR CLEARER LOGGING
        target_zip_file = os.path.normpath(os.path.join(self.local_install_destination, asset_card.key if asset_card.key.endswith(".zip") else f"{asset_card.key}.zip"))
        disk_status = "🟢 [STAGED & READY TO UNPACK]" if os.path.exists(target_zip_file) else "❌ [NOT DOWNLOADED YET]"
            
        if asset_card.mode == "PACK_MODE":
            pack_info = asset_card.data
            metadata_text = (
                f"== PACKAGE IDENTITY ARCHIVE ==\n"
                f"TARGET PACK: {asset_card.key}\n"
                f"STATUS:      {disk_status}\n"
                f"DESCRIPTION: {pack_info.get('descr', 'No description listed.')}\n"
                f"FILE SIZE:   {pack_info.get('size', 'Unknown')} MB\n"
                f"CACHE PATH:  {target_zip_file}"
            )
        else:
            metadata_text = (
                f"== INDIVIDUAL ASSET LOGS ==\n"
                f"ID INDEX:    {str(asset_card.data.get('id', asset_card.key))}\n"
                f"TITLE:       {asset_card.data.get('title', 'Generic Bundle')}\n"
                f"STATUS:      {disk_status}\n"
                f"FILE COUNT:  {len(asset_card.data.get('files', []))}\n"
                f"ROUTING:     Staging Stream active"
            )
        self.meta_display.setText(metadata_text)
        
        # DYNAMIC BUTTON TEXT INTERCHANGER
        if self.current_view_mode == "CART" or len(self.download_cart) > 1:
            self.btn_download.setText(f"📥 Download All in Cart ({len(self.download_cart)} Items)")
        else:
            self.btn_download.setText(f"📥 Download Highlighted Pack")
            
        self.btn_download.setEnabled(True)

    def execute_download_pipeline(self):

        self.active_batch_processing_queue = list(self.download_cart)
            
        if not self.active_batch_processing_queue:
            QMessageBox.information(self, "Cart Empty", "Your Cart is currently empty.\nPlease click '+ Cart' on the assets you want to download first.")
            return
            
        self.btn_download.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.process_next_queue_element()

    def process_next_queue_element(self):
        if not self.active_batch_processing_queue:
            self.progress_bar.setVisible(False)
            self.btn_download.setEnabled(True)
            self.meta_display.setText("All pipeline package download processes finished successfully!")
            QMessageBox.information(self, "Download Complete", "Staged operations built successfully! Ready to run Extract loops.")
            return

        # Safely extracts the clean text string filename from the front of the queue array list
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
        
        if repo_path.startswith("http"):
            if "://githubusercontent.com" in repo_path:
                parts = repo_path.split("://githubusercontent.com")[-1].split("/")
                if len(parts) >= 2:
                    repo_path = f"{parts[0]}/{parts[1]}"
                
        self.worker = AssetDownloadWorker(pack_info, self.local_install_destination, repo_path)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.log_signal.connect(self.meta_display.setText)
        self.worker.finished_signal.connect(self.pipeline_element_download_finished)
        self.worker.start()

    def pipeline_element_download_finished(self, success, message):
        if not self.active_batch_processing_queue:
            return

        # Always remove the completed or failed item from the front of the queue
        completed_key = self.active_batch_processing_queue.pop(0)
        if completed_key in self.download_cart:
            self.download_cart.remove(completed_key)
        self.sync_cart_label_counters()

        if success:
            try:
                staged_zip = os.path.normpath(os.path.join(self.local_install_destination, completed_key if completed_key.endswith(".zip") else f"{completed_key}.zip"))
                if os.path.exists(staged_zip):
                    with zipfile.ZipFile(staged_zip, 'r') as archive:
                        manifest_thumb_name = None
                        if "packs" in self.manifest_data and completed_key in self.manifest_data["packs"]:
                            manifest_thumb_url = self.manifest_data["packs"][completed_key].get("thumb", "")
                            if manifest_thumb_url:
                                manifest_thumb_name = os.path.basename(manifest_thumb_url).strip()
                        
                        internal_img = None
                        if manifest_thumb_name and manifest_thumb_name in archive.namelist():
                            internal_img = manifest_thumb_name
                        else:
                            internal_img = next((f for f in archive.namelist() if f.lower().endswith(('.thumb', '.png', '.jpg', '.jpeg'))), None)
                            
                        if internal_img:
                            render_cache_dir = os.path.normpath(os.path.join(self.mh_glob.env.path_userdata, "downloads", self.mh_glob.env.basename, "render"))
                            os.makedirs(render_cache_dir, exist_ok=True)
                            target_thumbnail_dest = os.path.join(render_cache_dir, completed_key + ".thumb")
                            
                            with archive.open(internal_img) as source_img, open(target_thumbnail_dest, 'wb') as dest_file:
                                dest_file.write(source_img.read())
            except Exception as img_err:
                print(f"[Image Extract Error] {str(img_err)}")
                
            for i in range(self.grid_layout.count()):
                w = self.grid_layout.itemAt(i).widget()
                if isinstance(w, MH2AssetCard) and w.key == completed_key:
                    w.refresh_thumbnail_preview()
                    w.update_card_ui_states()
                    if self.selected_card == w:
                        self.highlight_asset(w)
                    break
        else:

            print(f"[Queue Skip Alert] Target package '{completed_key}' failed: {message}")
            if hasattr(self, 'meta_display') and self.meta_display:
                self.meta_display.append(f"\n⚠️ [SKIPPED] {completed_key} failed to sync or stage.")

        # Always trigger the next queue item automatically
        self.process_next_queue_element()

    def execute_extraction_pipeline(self):
        """Scans the local staging cache and automatically unpacks all downloaded zip packages in a single batch operation."""
        if not os.path.exists(self.local_install_destination):
            QMessageBox.warning(self, "Queue Empty", "Staging cache folder not found.\nPlease download packages into your Cart first.")
            return

        staged_zips = [f for f in os.listdir(self.local_install_destination) if f.lower().endswith('.zip')]

        if not staged_zips:
            QMessageBox.information(self, "Nothing to Unpack", "No staging zip packages found.\nPlease run Download workflows first.")
            return

        try:
            from core.importfiles import AssetPack
            unzipper = AssetPack()
        except ImportError:
            QMessageBox.critical(self, "Engine Error", "Failed to interface with MakeHuman 2's core AssetPack module.")
            return

        mesh_folder = self.mh_glob.env.basename if self.mh_glob.env.basename else "hm08"
        user_data_path = os.path.normpath(self.mh_glob.env.path_userdata)
        
        processed_count = 0
        failed_count = 0

        for zip_file in staged_zips:
            staged_zip_path = os.path.normpath(os.path.join(self.local_install_destination, zip_file))
            pack_key = zip_file
            
            try:
                self.meta_display.setText(f"Batch Processing Extraction: {zip_file}...")
                temp_dir, error = unzipper.unZip(staged_zip_path)
                if error:
                    raise ValueError(error)

                temp_dir = temp_dir.replace("\\", "/")


                pack_type = ""
                for i in range(self.grid_layout.count()):
                    w = self.grid_layout.itemAt(i).widget()
                    if isinstance(w, MH2AssetCard) and w.key == zip_file:
                        pack_type = str(w.data.get("type", "")).lower().strip()
                        break

                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        source_file = os.path.join(root, file)
                        file_lower = file.lower()
                        root_lower = root.lower()

                        rel_zip_route = os.path.relpath(root, temp_dir).replace("\\", "/").lower()

                        if "hm08" in file_lower or "hm08" in rel_zip_route:
                            active_target_mesh = "hm08"
                        elif "fantasy" in file_lower or "fantasy" in rel_zip_route:
                            active_target_mesh = "fantasy"
                        else:
                            active_target_mesh = mesh_folder

                        # Clean item name extraction
                        split_tuple = os.path.splitext(file)
                        base_item_name = split_tuple[0]

                        # --- OFFICIAL PROTOCOL DEPLOYMENT ROUTING MATRIX ---
                        if file_lower.endswith(('.target', '.npz')) or "target" in rel_zip_route:
                            sub_route = os.path.join("target", active_target_mesh)
                            
                        elif file_lower.endswith(('.mhclo', '.obj', '.mhmat', '.mat', '.png', '.jpg', '.jpeg', '.thumb', '.json', '.mhp', '.bvh', '.mhs')):
                            
                            # --- 1. STRICT ISOLATED ACCESSORY CHANNELS FIRST (PREVENTS HIJACKING) ---
                            if "eyebrow" in rel_zip_route or "eyebrow" in file_lower:
                                sub_route = os.path.join("eyebrows", active_target_mesh, base_item_name)
                            elif "eyelash" in rel_zip_route or "eyelash" in file_lower:
                                sub_route = os.path.join("eyelashes", active_target_mesh, base_item_name)
                            elif "teeth" in rel_zip_route or "teeth" in file_lower:
                                sub_route = os.path.join("teeth", active_target_mesh, base_item_name)
                            elif "tongue" in rel_zip_route or "tongue" in file_lower:
                                sub_route = os.path.join("tongue", active_target_mesh, base_item_name)

                            # --- 2. COMPLEX HAIR FAMILY RECOLOR POOLING TRACKS ---
                            elif "hair" in rel_zip_route or "hair" in file_lower:
                                parent_dir_name = os.path.basename(root).strip().lower()
                                pack_folder_name = pack_key[:-4].replace("hm08-", "")
                                
                                explicit_hair_mesh = None
                                try:
                                    local_files = os.listdir(root)
                                    for f in local_files:
                                        if f.lower().endswith('.mhclo'):
                                            explicit_hair_mesh = os.path.splitext(f)[0]
                                            break
                                except Exception:
                                    pass

                                if explicit_hair_mesh:
                                    hair_family_folder = explicit_hair_mesh
                                elif parent_dir_name and parent_dir_name not in ["", "data", "resource", "temp", pack_folder_name.lower(), os.path.basename(temp_dir).lower(), "materials", "textures"]:
                                    hair_family_folder = os.path.basename(root)
                                else:
                                    clean_prefix = base_item_name.lower()
                                    if "_diffuse" in clean_prefix:
                                        clean_prefix = clean_prefix.split("_diffuse")[0]
                                    if "_material" in clean_prefix:
                                        clean_prefix = clean_prefix.split("_material")[0]
                                    for trait in ["_red", "_green", "_blue", "_blonde", "_black", "_brown", "_pink", "_purple", "_grey", "_white", "_recolor", "_pk", "_pack"]:
                                        if trait in clean_prefix:
                                            clean_prefix = clean_prefix.split(trait)[0]
                                            break
                                    hair_family_folder = clean_prefix

                                sub_route = os.path.join("hair", active_target_mesh, hair_family_folder)

                            # --- 3. HARD NAME UNIFIED KIT OVERRIDES (AVA & BIONICS etc) ---
                            else:
                                pack_folder_name = pack_key[:-4].replace("hm08-", "")
                                is_unified_kit = any(k in pack_folder_name.lower() or k in file_lower or k in rel_zip_route for k in ["ww_kit", "woman", "maid", "croft", "lara", "vader", "killer", "zombie", "bionic", "ava", "machina"])
                                
                                local_files = os.listdir(root) if os.path.exists(root) else []
                                has_clothing_sibling = any(f.lower().endswith('.mhclo') for f in local_files)

                                if is_unified_kit:
                                    if file_lower.endswith('.proxy'):
                                        sub_route = os.path.join("proxy", active_target_mesh, pack_folder_name)
                                    elif file_lower.endswith(('.png', '.jpg', '.jpeg', '.mhmat', '.mat')) and "proxy" in rel_zip_route:
                                        if file_lower.endswith(('.png', '.jpg', '.jpeg')) and not file_lower.endswith('.thumb'):
                                            sub_route = os.path.join("proxy", active_target_mesh, pack_folder_name, "materials")
                                        else:
                                            sub_route = os.path.join("proxy", active_target_mesh, pack_folder_name)
                                    else:
                                        sub_route = os.path.join("clothes", active_target_mesh, pack_folder_name)

                                # --- 4. EXTENSION ENFORCED CLOTHING MATRIX ---
                                elif file_lower.endswith('.mhclo') or (has_clothing_sibling and file_lower.endswith(('.obj', '.mhmat', '.mat', '.png', '.jpg', '.jpeg'))):
                                    parent_dir_name = os.path.basename(root).strip().lower()
                                    if parent_dir_name and parent_dir_name not in ["", "data", "resource", "temp", pack_folder_name.lower(), os.path.basename(temp_dir).lower()]:
                                        sub_route = os.path.join("clothes", active_target_mesh, os.path.basename(root))
                                    else:
                                        sub_route = os.path.join("clothes", active_target_mesh, base_item_name)

                                # --- 5. SHADER VIEWPORT SKYBOX & ENVIRONMENTS ---
                                elif "skybox" in pack_type or "skybox" in rel_zip_route or "skybox" in file_lower:
                                    parent_dir_name = os.path.basename(root).strip().lower()
                                    if not parent_dir_name or parent_dir_name in ["", "data", "resource", "materials", "temp", os.path.basename(temp_dir).lower()]:
                                        unique_skybox_folder = pack_key[:-4].replace("common-", "")
                                    else:
                                        unique_skybox_folder = os.path.basename(root)
                                    sub_route = os.path.join("shaders", "skybox", unique_skybox_folder)

                                elif "floor" in pack_type or "floor" in rel_zip_route or "floor" in file_lower:
                                    parent_dir_name = os.path.basename(root).strip().lower()
                                    if not parent_dir_name or parent_dir_name in ["", "data", "resource", "temp", os.path.basename(temp_dir).lower()]:
                                        unique_floor_folder = pack_key[:-4].replace("common-", "")
                                    else:
                                        unique_floor_folder = os.path.basename(root)
                                    sub_route = os.path.join("shaders", "floor", unique_floor_folder)

                                elif "themes" in rel_zip_route or (file_lower.endswith('.json') and "theme" in rel_zip_route):
                                    sub_route = "themes"

                                # --- 6. RIGS & ANIMATION MATRIX STACK ---
                                elif "mhskel" in rel_zip_route or "rig" in rel_zip_route or file_lower.endswith('.mhskel'):
                                    sub_route = "rigs"
                                elif "poses" in rel_zip_route or file_lower.endswith('.mhp'):
                                    sub_route = "poses"
                                elif "expressions" in rel_zip_route or file_lower.endswith('.mhs'):
                                    sub_route = "expressions"
                                elif "animations" in rel_zip_route or file_lower.endswith('.bvh'):
                                    sub_route = "animations"

                                # --- 7. PROPS & GENERAL PROXIES ---
                                elif "props" in rel_zip_route:
                                    sub_route = os.path.join("props", base_item_name)
                                elif "proxy" in rel_zip_route or "proxy" in pack_type:
                                    if file_lower.endswith(('.png', '.jpg', '.jpeg', '.mhmat', '.mat')):
                                        if file_lower.endswith(('.png', '.jpg', '.jpeg')) and not file_lower.endswith('.thumb'):
                                            sub_route = os.path.join("proxy", active_target_mesh, base_item_name, "materials")
                                        else:
                                            sub_route = os.path.join("proxy", active_target_mesh, base_item_name)
                                    else:
                                        sub_route = os.path.join("proxy", active_target_mesh, base_item_name)

                                # --- 8. PROTOCOL ACCURATE POOLED EYES MATRIX eyes still need work---
                                elif "eyes" in rel_zip_route or "eyes" in file_lower:
                                    if file_lower.endswith(('.png', '.jpg', '.jpeg')) and not file_lower.endswith('.thumb'):
                                    
                                        sub_route = os.path.join("eyes", active_target_mesh, "materials")
                                    else:
                                        sub_route = os.path.join("eyes", active_target_mesh)

                                # --- 9. PROTOCOL ACCURATE POOLED SKINS MATRIX ---
                                elif "skin" in rel_zip_route or "skin" in file_lower or ("material" in root_lower and not any(k in file_lower for k in ["hair", "eyebrow"])):
                                    if file_lower.endswith(('.png', '.jpg', '.jpeg')) and not file_lower.endswith('.thumb'):
                                        sub_route = os.path.join("skins", active_target_mesh, "materials")
                                    else:
                                        sub_route = os.path.join("skins", active_target_mesh)

                                # --- 10. GENERAL BULK CLOTHING OVERLAY FALLBACKS ---
                                else:
                                    parent_dir_name = os.path.basename(root).strip().lower()
                                    if parent_dir_name and parent_dir_name not in ["", "data", "resource", "temp", pack_folder_name.lower(), os.path.basename(temp_dir).lower()]:
                                        sub_route = os.path.join("clothes", active_target_mesh, os.path.basename(root))
                                    else:
                                        sub_route = os.path.join("clothes", active_target_mesh, base_item_name)
                        else:
                            sub_route = os.path.normpath(os.path.join(os.path.relpath(root, temp_dir))).replace("data/", "")

                        # Deploy and recycle compiled binary interferences to prevent corruption
                        final_destination = os.path.join(user_data_path, sub_route, file).replace("\\", "/")
                        os.makedirs(os.path.dirname(final_destination), exist_ok=True)

                        potential_mhbin = final_destination + "bin"
                        if os.path.exists(potential_mhbin):
                            try:
                                os.remove(potential_mhbin)
                            except Exception:
                                pass

                        shutil.copy2(source_file, final_destination)

                unzipper.cleanupUnzip()
                processed_count += 1
            except Exception as e:
                print(f"[Batch Extract Failed] Missing or broken elements in {zip_file}: {str(e)}")
                failed_count += 1
                continue

        self.mh_glob.MainWindow.syncRepositories()

        completion_msg = f"Batch extraction complete!\nSuccessfully Unpacked: {processed_count} packages."
        if failed_count > 0:
            completion_msg += f"\nSkipped Errors: {failed_count} packages."

        self.meta_display.setText(completion_msg)
        QMessageBox.information(self, "Batch Process Finished", completion_msg)

    def execute_repo_bulk_download(self):
        """Scans the active layout grid and builds a downloading task queue for every single visible pack."""
        visible_keys = []
        for i in range(self.grid_layout.count()):
            card = self.grid_layout.itemAt(i).widget()
            if isinstance(card, MH2AssetCard) and not card.isHidden():
                visible_keys.append(card.key)
                
        if not visible_keys:
            QMessageBox.information(self, "No Packs Found", "There are no visible asset packs to download in this repository view right now.")
            return
            
        confirm = QMessageBox.question(
            self, 
            "Confirm Bulk Download", 
            f"Are you sure you want to download ALL {len(visible_keys)} visible packs in this repository view back-to-back?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            # Force the processing queue to populate with every single visible card key in the repo panel
            self.active_batch_processing_queue = list(visible_keys)
            self.btn_download.setEnabled(False)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            self.process_next_queue_element()


    def execute_cleanup_pipeline(self):
        if not os.path.exists(self.local_install_destination):
            return
        try:
            shutil.rmtree(self.local_install_destination)
            os.makedirs(self.local_install_destination, exist_ok=True)
            self.meta_display.setText("Staging folders cache completely cleared.")
            QMessageBox.information(self, "Cleared", "Temporary staging folders cache cleared successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

# ============================================
# SECTION 4: THE MAIN EXTENSION ANCHOR HOOKS
# ============================================
class MH2ArchiveExtension:
    def __init__(self, mh_app, mh_glob, pluginname):
        self.mh_app = mh_app
        self.mh_glob = mh_glob
        self.mainwindow = mh_glob.MainWindow
        self.repo = mh_glob.pluginRepo
        self.pluginname = pluginname
        self.dock = None
        self.panel = None

    def initialize(self):
        """Assembles, binds, and positions the extension interface natively."""
        self.dock = QDockWidget("MH2 Asset Archive Portal (Standalone Edition)", self.mainwindow)
        self.panel = MH2AssetBrowserPanel(self, self.mh_glob)
        self.dock.setWidget(self.panel)
        self.mainwindow.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.show()
        
        # Register extension instance inside application environment repositories
        self.repo[self.pluginname] = self
        return True

    def shutdown(self):
        """Executes a clean interface destruction sequence on application exit."""
        if self.dock:
            self.mainwindow.removeDockWidget(self.dock)
            self.dock.close()
            self.dock.deleteLater()
            self.dock = None
        self.panel = None

def load_extension(app, glob):
    """Entry point hook triggered automatically by MakeHuman 2's loader module."""
    name = os.path.abspath(__file__)
    plugin = MH2ArchiveExtension(app, glob, name)
    return plugin.initialize()

def unload_extension(glob):
    """Clean unloader engine callback loop wrapper."""
    name = os.path.abspath(__file__)
    if name in glob.pluginRepo:
        glob.pluginRepo[name].shutdown()
        glob.pluginRepo.pop(name)
