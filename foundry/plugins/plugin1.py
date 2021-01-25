from ..api._v1 import *

class Plugin1(FoundryPlugin):
    def __init__(self):
        print('Hello from init!')

    def load(self, main_window):
        print('Hello from load!')
        print('\tmain_window: {}'.format(main_window))

    def enable(self, main_window):
        print('Hello from enable!')
        print('\tmain_window: {}'.format(main_window))
