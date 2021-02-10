from zipfile import ZipFile, BadZipFile
from pathlib import Path

class PluginNoPythonError(Exception):
    pass
class PluginBadZipError(Exception):
    pass
class PluginBadPathError(Exception):
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
    def __init__(self, fplpath):
        '''Given a path to a `.fpl` file, extract it and build up
        the object representing it in memory.
        '''
        self.fplpath = Path(fplpath)
        # e.g. expand-base-rom.fpl -> _expand-base-rom/
        self._dirpath = self.fplpath.parent / ('_' + self.fplpath.name[:-4])
        self.loaded = False
        self.enabled = False
        self.zf = None  # zipfile object set in _ensure_zip

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

