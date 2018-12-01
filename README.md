# Qt CLI installer

This is a simple script replacing the official graphical Qt installer. It can
automatically download prebuilt Qt binaries for any target (you're not bound to
Linux binaries on Linux; you could also download iOS binaries). Currently it's
limited to Linux/OS X users, because it's just calling wget/7z via. os.system().

**Dependencies**: python3, wget, 7z

General usage looks like this:
```
./qli-installer.py <qt-version> <host> <target> [<arch>]
```
The Qt version is formatted like this: `5.11.3`  
Host is one of: `linux`, `mac`, `windows`  
Target is one of: `desktop`, `android`, `ios` (iOS only works with mac host)  
For android and windows you also need to specify an arch: `win64_msvc2017_64`,
`win64_msvc2015_64`, `win32_msvc2015`, `win32_mingw53`, `android_x86`,
`android_armv7`

Example: Installing Qt 5.12.0 for Linux:
```bash
./qli-installer.py 5.12.0 linux desktop
```

Example: Installing Android (armv7) Qt 5.10.2:
```bash
./qli-installer.py 5.10.2 linux android android_armv7
```

## To Do

- [ ] Get rid of `os.system`; Use lzma and requests module.
