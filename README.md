# Qt CLI installer

This is a simple script replacing the graphical Qt installer. It can download
prebuilt Qt binaries for any target (you're not bound to Linux binaries on
Linux; you could also download iOS binaries). Currently it's limited to Linux/
OS X users, because it's just calling wget/7z via. os.system() (I could have
realized this as shell script, yes).

Also one thing is currently the Qt version: The script is hard-coded to one Qt
version, because it (currently) doesn't parse the repository xml files.
Unfortunately this means the build date needs to be changed for every target in
the script when updating Qt.

**Dependencies**: python3, wget, 7z

General usage looks like this:
```
./qli-installer.py <host> <target> [<arch>]
```
Host is one of: `linux`, `mac`, `windows`  
Target is one of: `desktop`, `android`, `ios` (iOS only works with mac host)  
For android and windows you also need to specify an arch: `win64_msvc2017_64`,
`win64_msvc2015_64`, `win32_msvc2015`, `win32_mingw53`, `android_x86`,
`android_armv7`

Example: Installing Linux Qt:
```bash
./qli-installer.py linux desktop
```

Example: Installing Android (armv7) Qt for Linux systems:
```bash
./qli-installer.py linux android android_armv7
```

## To Do

- [ ] Parse [XML files](https://download.qt.io/online/qtsdkrepository/linux_x64/android/qt5_5112/Updates.xml)

