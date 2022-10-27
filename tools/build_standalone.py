import argparse
import os
import PyInstaller.__main__


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("arch", nargs="?")
    args = parser.parse_args()

    # build PyInstaller arguments
    tools_dir = os.path.dirname(__file__)
    name = "aqt" if args.arch is None else "aqt_" + args.arch
    args = [
        '--noconfirm',
        '--onefile',
        '--name', name,
        '--paths', ".",
        '--hidden-import', "aqt",
    ]

    # Add data files
    if os.name == 'nt':
        adddata_arg = "{src:s};aqt"
    else:
        adddata_arg = "{src:s}:aqt"
    for data in ["aqt/logging.ini", "aqt/settings.ini", "aqt/combinations.json"]:
        args.append('--add-data')
        args.append(adddata_arg.format(src=data))
    args.append(os.path.join(tools_dir, "launch_aqt.py"))

    # launch PyInstaller
    PyInstaller.__main__.run(args)
