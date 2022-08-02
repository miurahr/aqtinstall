from pytest_socket import disable_socket


def pytest_runtest_setup():
    disable_socket()


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "load_default_settings(use_defaults): mark test not to load from the default settings.ini file"
    )
