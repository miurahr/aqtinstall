py -m pip install -U pip
py -m venv build_venv
call build_venv\Scripts\activate.bat
pip install -U gravitybee setuptools setuptools_scm wheel
move pyproject.toml pyproject.toml.bak
pip install -e .
set GB_APP_NAME=aqtinstall
set GB_PKG_NAME=aqt
set GB_SCRIPT=build_venv\Scripts\aqt-script.py
set GB_NAME_FORMAT=aqt
gravitybee --with-latest
call build_venv\Scripts\deactivate.bat
