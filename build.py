import traceback, sys, os, shutil, zipfile
from datetime import datetime

def activate_venv(venv_path):
    if sys.platform == "win32":
        activate_script = os.path.join(venv_path, "Scripts", "activate_this.py")
    else:
        activate_script = os.path.join(venv_path, "bin", "activate_this.py")

    exec(open(activate_script).read(), {'__file__': activate_script})


def zip_directory(zip_name, dir_path, compress_type=zipfile.ZIP_DEFLATED):
    with zipfile.ZipFile(zip_name, 'w', compress_type) as zipf:
        # 遍历目录
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                # 计算在ZIP中的相对路径
                arcname = os.path.relpath(file_path, dir_path)
                zipf.write(file_path, arcname=arcname)

def detect_venv():
    # 方法1：比较路径
    base_prefix = getattr(sys, "base_prefix", sys.prefix)
    in_venv = sys.prefix != base_prefix

    # 方法2：检查环境变量
    venv_var = os.environ.get("VIRTUAL_ENV")

    # 方法3：检查site-packages路径
    site_packages = [p for p in sys.path if "site-packages" in p]
    venv_site_packages = [p for p in site_packages if "venv" in p or "virtualenv" in p]

    return in_venv or venv_var or len(venv_site_packages) > 0

def get_immediate_subdirectories(path):
    temp114514 = []
    for name in os.listdir(path):
        if os.path.isdir(os.path.join(path, name)):
            temp114514.append(name)
    return temp114514

def clean_temp_files():
    shutil.rmtree("dist\\pack")
    os.remove("dist\\metadata.json")
    for name in os.listdir("pack"):
        if os.path.isfile(os.path.join(os.getcwd(), "pack", name)):
            if len(name.split(".")) >= 2 and name.split(".")[1] == "zip":
                os.remove(os.path.join(os.getcwd(), "pack", name))

if __name__ == '__main__':
    try:
        files = ["header.png", "left.png", "items.json", "icon.ico", "LICENSE", "readme.txt"]
        mini_folders = ["BBDevAPI", "BBPC", "BepInEx64", "BepInEx86"]
        temp_folder_variables = get_immediate_subdirectories(os.path.join(os.getcwd(), "pack"))
        full_folders = []
        for folder in temp_folder_variables:
            if folder not in mini_folders:
                full_folders.append(folder)
        mini_zip_files = [ folder + ".zip" for folder in mini_folders ]
        full_zip_files = [ folder + ".zip" for folder in full_folders ]
        game_ver = input("Enter expected game version number: ")
        if game_ver is None or game_ver == "" or game_ver == " ":
            raise ValueError("Version number cannot be None or empty.")
        ver = input("Enter the pack version number: ")
        if ver is None or ver == "" or ver == " ":
            raise ValueError("Version number cannot be None or empty.")
        activate_venv(".venv")
        params = [
            'main.py',
            '--onefile',
            '--windowed',
            '--icon=pack/icon.ico'
        ]
        from PyInstaller.__main__ import run as pyinstaller_run
        pyinstaller_run(params)
        if os.path.isfile("metadata.json"):
            shutil.copy("metadata.json", "dist\\metadata.json")
        os.chdir("pack")
        shutil.copy("com.baymaxawa.bbpc.cfg", "BBPC\\BepInEx\\config\\com.baymaxawa.bbpc.cfg")
        os.makedirs("..\\dist\\pack", exist_ok=True)
        for file in files:
            shutil.copy(file, "..\\dist\\pack\\"+file)
        for folder in mini_folders:
            zip_directory(folder+".zip", folder, zipfile.ZIP_DEFLATED)
        for zip_file in mini_zip_files:
            shutil.copy(zip_file, "..\\dist\\pack\\"+zip_file)
        os.chdir("..")
        zip_directory("BB+ "+game_ver+" v"+ver+" [MINI].zip", "dist", zipfile.ZIP_DEFLATED)
        os.chdir("pack")
        for folder in full_folders:
            zip_directory(folder+".zip", folder, zipfile.ZIP_DEFLATED)
        for zip_file in full_zip_files:
            shutil.copy(zip_file, "..\\dist\\pack\\"+zip_file)
        os.chdir("..")
        zip_directory("BB+ " + game_ver + " v" + ver + " [FULL].zip", "dist", zipfile.ZIP_DEFLATED)
        clean_temp_files()
    except Exception as e:
        print("An error occurred! Please check errors.log!")
        if os.path.exists("errors.log"): os.remove("errors.log")
        with open("errors.log", "a") as f:
            f.write(f"[ERROR {datetime.now().isoformat()}] Error Type: {type(e).__name__}, Traceback:\n")
            exc_type, exc_value, exc_tb = sys.exc_info()
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
            f.write("".join(tb_lines))
        clean_temp_files()
        exit(1)