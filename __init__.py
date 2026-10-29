from .mh2_archive import MH2ArchiveUI

def load_as_mh2_plugin(parent_notebook):
    # Initializes the clean UI layout variable matching your main file class name
    plugin_tab = MH2ArchiveUI()
    parent_notebook.addTab(plugin_tab, "MH2 Archive Sync")
    return plugin_tab
