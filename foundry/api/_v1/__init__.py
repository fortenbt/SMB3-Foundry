from abc import ABC, abstractmethod

class FoundryPlugin(ABC):
    '''The abstract base class to be derived from when writing a
    new Foundry plugin.
    '''
    @abstractmethod
    def __init__(self):
        '''Generally needs to do nothing, unless there is special
        setup the plugin would like to do in its constructor.
        '''
        raise NotImplementedError

    @abstractmethod
    def load(self, main_window):
        '''Initialize the plugin.

        This method is called by Foundry once the plugin is discovered
        and extracted. This is called prior to the user enabling the
        plugin, so it should generally not do anything visible to the
        editor.

        Args:
        main_window -- Foundry's global MainWindow object containing
                       all of its state and attributes.
        '''
        raise NotImplementedError

    @abstractmethod
    def enable(self, main_window):
        '''Enable the plugin.

        This method is called by Foundry when the user enables the
        plugin. At this point, the user has decided to take the risk
        of breaking their ROM or editor by enabling your plugin. You
        may add menus, change metadata, or change all global editor
        state.

        Args:
        main_window -- Foundry's global MainWindow object containing
                       all of its state and attributes.
        '''
        raise NotImplementedError