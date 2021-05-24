import os

from aqt import helper

# Early load custom configuration for test because it is Borg/Singleton
helper.Settings(os.path.join(os.path.dirname(__file__), "data", "settings.ini"))
