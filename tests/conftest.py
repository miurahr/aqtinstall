from pytest_socket import disable_socket


def pytest_runtest_setup():
    disable_socket()
