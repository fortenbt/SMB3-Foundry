#!/usr/bin/env python3
import logging
import os
from os.path import join, basename
import pkgutil
import sys
import traceback

import foundry.plugins
from foundry.plugins import LoadedPlugin, LoadedPluginException

from pathlib import Path

from PySide2.QtWidgets import QApplication, QMessageBox

from foundry import auto_save_rom_path, github_issue_link, default_plugins_path
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

def _discover_plugins():
    '''Discover .fpl files in the default plugins path.
    Creates LoadedPlugin objects for each found .fpl file. The LoadedPlugin
    class ensures the format of each .fpl is correct.
    '''
    print('[+] Discovering plugins in "{}"'.format(default_plugins_path))
    fpls = []
    for dirpath, dirnames, filenames in os.walk(default_plugins_path):
        fpls += [join(dirpath, f) for f in filenames if f.endswith('.fpl')]
    print('    [+] Found {} possible plugins'.format(len(fpls)))

    # fpls is now a list of string paths, e.g
    # [
    #      '/home/user/.smb3foundry/plugins/expand-base-rom.fpl',
    #      '/home/user/.smb3foundry/plugins/on-off-blocks.fpl',
    # ]
    plugins = {}
    for fpl in fpls:
        print('{:8}- Extracting {}...'.format(' ', os.path.basename(fpl)))
        try:
            lp = LoadedPlugin(fpl)
        except LoadedPluginException as e:
            print('{:12}{}'.format(' ', e))
            continue
        plugins[fpl] = lp

    return plugins

def _import_plugin(lp):
    '''Import the python files in the LoadedPlugin's python/ directory'''
    lp.load_python()
    for mod in lp.modules:
        print('{:8}- Import {}'.format(' ', mod.__file__))
    lp.import_python()

def _load_plugin(lp, mw):
    '''Call the LoadedPlugin instance's `load` method'''
    for inst in lp.instances:
        inst.load(mw)

def load_plugins(mw):
    plugins = _discover_plugins()
    if not plugins:
        return
    for fpl, lp in plugins.items():
        print('    [+] Loading {}...'.format(lp.name))
        _import_plugin(lp)
        _load_plugin(lp, mw)
    return plugins

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
    plugins = load_plugins(mw)
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
