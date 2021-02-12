import importlib.util
import inspect
import os
from os.path import isfile, join, basename
from zipfile import ZipFile, BadZipFile
from pathlib import Path
from foundry.api._v1 import FoundryPlugin as FoundryPlugin_v1

class LoadedPluginException(Exception):
    pass

class PluginNoPythonError(LoadedPluginException):
    pass
class PluginBadZipError(LoadedPluginException):
    pass
class PluginBadPathError(LoadedPluginException):
    pass

class LoadedPlugin(object):
    '''Represents the plugin as we've discovered and extracted it.
    All the files and paths associated with the FPL, whether or not
    it has been loaded or enabled, etc. is stored in this object.

    Useful properties for consumers:
        self.dirpath: string with the full path to where the FPL was extracted
    Exceptions:
        raises PluginBadZipError if the FPL file is not a properly constructed zip file
        raises PluginNoPythonError if the FPL file does not contain a python/ directory
        raises PluginBadPathError if failed to create a directory for the extracted plugin
    '''
    SUPPORTED_PLUGIN_TYPES = [
        FoundryPlugin_v1,
    ]

    def __init__(self, fplpath):
        '''Given a path to a `.fpl` file, extract it and build up
        the object representing it in memory.
        '''
        # We need a translation dictionary for our fpl dirpath
        # The dirpath must conform to Python module and package
        # naming conventions
        chars_to_become_underscores = [' ', '-']
        td = {ord(c):'_' for c in chars_to_become_underscores}

        self.fplpath = Path(fplpath)            # e.g. '/home/user/.smb3foundry/plugins/expand-base-rom.fpl'
        self.name = self.fplpath.name[:-4]      # e.g. 'expand-base-rom'
        dirpath = self.name.translate(td)       # e.g. '/home/user/.smb3foundry/plugins/_expand_base_rom
        self._dirpath = self.fplpath.parent / ('_' + dirpath)
        self.pypath = self._dirpath / 'python'  # e.g. '/home/user/.smb3foundry/plugins/_expand_base_rom/python'
        self.loaded = False
        self.enabled = False
        self.zf = None
        self.modules = []
        self.instances = []

        try:
            self._ensure_valid_plugin()
            self._extract_plugin()
        except Exception as e:
            raise e
        finally:
            if self.zf:
                self.zf.close()

    @property
    def dirpath(self):
        return str(self._dirpath)

    def load_python(self):
        '''Find all .py files under python/ within this plugin and use
        importlib to import the module.

        IMPORTANT SECURITY NOTE: This is the first time the plugin is given
        execution, although plugins that follow our standard will not
        have any code to execute on import.
        '''
        pyfiles = [join(self.pypath, f) for f in os.listdir(self.pypath) if isfile(join(self.pypath, f))]
        pyfiles = [f for f in pyfiles if f.endswith('.py')]
        for f in pyfiles:
            spec = importlib.util.spec_from_file_location(
                '.'.join([self.dirpath, 'python', basename(f)]), f)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.modules.append(module)

    def import_python(self):
        '''For each class in the loaded modules that derives from one of our
        supported plugin types, instantiate an instance of that class.

        IMPORTANT SECURITY NOTE: This will also give any plugin module that has
        a class that derives from one of our supported plugin types execution
        in that class's `__init__` method.
        '''
        for mod in self.modules:
            for name, cls_ in inspect.getmembers(mod):
                if inspect.isclass(cls_):
                    for b in cls_.__bases__:
                        if any(issubclass(b, c) for c in LoadedPlugin.SUPPORTED_PLUGIN_TYPES):
                            # If one of this class's base classes is any of our supported
                            # types, then this is a plugin we need to create an instance of.
                            self.instances.append(cls_())
                            break

    def _ensure_zip(self):
        '''Ensure this FPL file can be opened with ZipFile
        
        Exceptions:
            raises PluginBadZipError if ZipFile creation failed.
        '''
        try:
            self.zf = ZipFile(self.fplpath, 'r')
        except BadZipFile as e:
            raise PluginBadZipError(
                'The given plugin "{}" is not a zip file. '
                'Contact the plugin creator. Error content:\n'
                '{}'.format(self.fplpath, e)
            )

    def _ensure_python(self):
        '''Ensure this FPL file has a python/ directory in its top level
        
        Exceptions:
            raises PluginNoPythonError if ZipFile creation failed.
        '''
        if not any(name.startswith('python/') for name in self.zf.namelist()):
            raise PluginNoPythonError(
                'The given plugin "{}" does not contain a '
                'python directory. Contact the plugin creator.'.format(self.fplpath)
            )

    def _ensure_valid_plugin(self):
        '''Do all sanity checks on plugin format.

        Exceptions:
            raises PluginBadZipError if the FPL file is not a properly constructed zip file
            raises PluginNoPythonError if the FPL file does not contain a python/ directory
        '''
        self._ensure_zip()
        self._ensure_python()

    def _extract_plugin(self):
        '''Extracts the plugin.
        
        Exceptions:
            raises PluginBadPathError if the path for the extracted plugin
                could not be created.
            raises PluginBadZipError if extraction fails.
        '''
        try:
            self._dirpath.mkdir(exist_ok=True)
        except Exception as e:
            raise PluginBadPathError(
                'Error creating a directory for the extracted plugin "{}"\n'
                'Contact the plugin creator. Error content:\n'
                '{}'.format(self.fplpath, e)
            )
        try:
            self.zf.extractall(self.dirpath)
        except BadZipFile as e:
            raise PluginBadZipError(
                'Error extracting the plugin "{}"\n'
                'Contact the plugin creator. Error content:\n'
                '{}'.format(self.fplpath, e)
            )

