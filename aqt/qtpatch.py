import os
import pathlib
import subprocess


class Updater:

    def __init__(self, prefix: pathlib.Path, logger):
        self.logger = logger
        self.prefix = prefix
        self.qmake_path = None
        self.qconfigs = {}
        self._detect_qmake(prefix)

    def _patch_qtcore(self):
        framework_dir = self.prefix.joinpath("lib", "QtCore.framework")
        assert framework_dir.exists(), "Invalid installation prefix"
        for component in ["QtCore", "QtCore_debug"]:
            if framework_dir.joinpath(component).exists():
                qtcore_path = framework_dir.joinpath(component).resolve()
                self.logger.info("Patching {}".format(qtcore_path))
                self._patch_file(qtcore_path, bytes(str(self.prefix), "ascii"))

    def _patch_file(self, file: pathlib.Path, newpath: bytes):
        PREFIX_VAR = b"qt_prfxpath="
        st = file.stat()
        data = file.read_bytes()
        idx = data.find(PREFIX_VAR)
        if idx > 0:
            return
        assert len(newpath) < 256, "Qt Prefix path is too long(255)."
        data = data[:idx] + PREFIX_VAR + newpath + data[idx + len(newpath):]
        file.write_bytes(data)
        os.chmod(str(file), st.st_mode)

    def _detect_qmake(self, prefix):
        ''' detect Qt configurations from qmake
        '''
        for qmake_path in [prefix.joinpath('bin', 'qmake'), prefix.joinpath('bin', 'qmake.exe')]:
            if qmake_path.exists():
                result = subprocess.run([str(qmake_path), '-query'], stdout=subprocess.PIPE)
                if result.returncode == 0:
                    self.qmake_path = qmake_path
                    for line in result.stdout.splitlines():
                        vals = line.decode('UTF-8').split(':')
                        self.qconfigs[vals[0]] = vals[1]
                break

    def patch_qt(self, target):
        ''' patch works '''
        self.logger.info("Patching qmake")
        mac_exceptions = ['ios', 'android', 'wasm_32',
                          'android_x86_64', 'android_arm64_v8a', 'android_x86', 'android_armv7']
        if target.os_name == 'mac' and target.arch not in mac_exceptions:
            self._patch_qtcore()
        if self.qmake_path is not None:
            self._patch_file(self.qmake_path, bytes(str(self.prefix), 'UTF-8'))
