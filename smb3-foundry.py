#!/usr/bin/env python3
import importlib
import inspect
import logging
import os
import pkgutil
import sys
import traceback

import foundry.plugins

from PySide2.QtWidgets import QApplication, QMessageBox

from foundry import auto_save_rom_path, github_issue_link
from foundry.gui.AutoSaveDialog import AutoSaveDialog
from foundry.gui.settings import load_settings, save_settings

from foundry.api._v1 import FoundryPlugin

logger = logging.getLogger(__name__)

# change into the tmp directory pyinstaller uses for the data
if hasattr(sys, "_MEIPASS"):
    logger.info(f"Changing current dir to {getattr(sys, '_MEIPASS')}")
    os.chdir(getattr(sys, "_MEIPASS"))

from foundry.gui.MainWindow import MainWindow

def iter_namespace(ns_pkg):
    # Specifying the second argument (prefix) to iter_modules makes the
    # returned name an absolute name instead of a relative one. This allows
    # import_module to work without having to do additional modification to
    # the name.
    #
    # Source: https://packaging.python.org/guides/creating-and-discovering-plugins/
    print('Inside iter_namespace')
    return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")

def load_plugins(mw):
    print('Inside load_plugins')
    discovered_plugin_modules = {
        name: importlib.import_module(name)
        for _, name, _ in iter_namespace(foundry.plugins)
    }
    discovered_plugin_instances = []
    for modname,mod in discovered_plugin_modules.items():
        for name, cls_ in inspect.getmembers(mod):
            if inspect.isclass(cls_):
                for b in cls_.__bases__:
                    if issubclass(b, FoundryPlugin):
                        # If one of this class's base classes is FoundryPlugin,
                        # then this is a plugin we need to create an instance of.
                        discovered_plugin_instances.append(cls_())
                        break
    for instance in discovered_plugin_instances:
        instance.load(mw)

def main(path_to_rom):
    load_settings()

    app = QApplication()

    if auto_save_rom_path.exists():
        result = AutoSaveDialog().exec_()

        if result == QMessageBox.AcceptRole:
            path_to_rom = auto_save_rom_path

            QMessageBox.information(
                None, "Auto Save recovered", "Don't forget to save the loaded ROM under a new name!"
            )

    mw = MainWindow(path_to_rom)
    load_plugins(mw)
    app.exec_()

    save_settings()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = ""

    try:
        main(path)
    except Exception as e:
        box = QMessageBox()
        box.setWindowTitle("Crash report")
        box.setText(
            f"An unexpected error occurred! Please contact the developers at {github_issue_link} "
            f"with the error below:\n\n{str(e)}\n\n{traceback.format_exc()}"
        )
        box.exec_()
        raise
