import re
import traceback, sys, os, shutil, zipfile, json
from datetime import datetime

class DOSProgress:
    """老式DOS风格进度条"""
    def __init__(self, total, bar_width=40):
        self.total = total
        self.bar_width = bar_width
        self.current = 0
        self.last_percent = -1
        
    def update(self, current=None, filename=""):
        """更新进度"""
        if current is not None:
            self.current = current
        else:
            self.current += 1
            
        percent = int((self.current / self.total) * 100)
        
        # 只在百分比变化时更新进度条（避免闪烁）
        if percent != self.last_percent:
            self.last_percent = percent
            
            # 计算进度条填充
            filled_length = int(self.bar_width * self.current // self.total)
            bar = '=' * filled_length + '>' + '.' * (self.bar_width - filled_length - 1)
            
            # 构建输出行
            output = f"\r  [{bar}] {percent:3d}% "
            if filename:
                # 限制文件名长度，保持输出整洁
                display_name = filename[:50] + "..." if len(filename) > 50 else filename
                output += f"- {display_name}"
            
            # 清除到行尾并输出
            sys.stdout.write(output)
            sys.stdout.flush()
    
    def finish(self):
        """完成进度条"""
        print()  # 换行

def zip_directory_dos_style(zip_name, dir_path, compress_type=zipfile.ZIP_DEFLATED):
    """DOS风格进度显示的目录压缩函数"""
    # 先收集所有要压缩的文件
    all_files = []
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, dir_path)
            all_files.append((file_path, arcname))
    
    if not all_files:
        print(f"  警告：{dir_path} 目录中没有文件")
        return
    
    print(f"  正在压缩: {os.path.basename(zip_name)}")
    
    # 创建进度条
    progress = DOSProgress(len(all_files))
    
    # 创建ZIP文件
    with zipfile.ZipFile(zip_name, 'w', compress_type) as zipf:
        for idx, (file_path, arcname) in enumerate(all_files, 1):
            # 显示当前正在压缩的文件
            progress.update(idx, arcname)
            zipf.write(file_path, arcname=arcname)
    
    progress.finish()
    print(f"  完成: {len(all_files)} 个文件已压缩\n")

def copy_files_dos_style(files, dest_dir):
    """DOS风格的文件复制"""
    if not files:
        return
    
    progress = DOSProgress(len(files))
    print(f"  复制 {len(files)} 个文件...")
    
    for idx, file in enumerate(files, 1):
        dest_path = os.path.join(dest_dir, file)
        progress.update(idx, file)
        shutil.copy(file, dest_path)
    
    progress.finish()
    print()

def zip_multiple_folders_dos_style(folders, output_dir="."):
    """批量压缩多个文件夹的DOS风格显示"""
    if not folders:
        return
    
    total_folders = len(folders)
    print(f"  共需压缩 {total_folders} 个文件夹\n")
    
    for idx, folder in enumerate(folders, 1):
        print(f"  [{idx}/{total_folders}] 压缩文件夹: {folder}")
        zip_directory_dos_style(folder+".zip", folder, zipfile.ZIP_DEFLATED)

def get_immediate_subdirectories(path):
    temp114514 = []
    for name in os.listdir(path):
        if os.path.isdir(os.path.join(path, name)):
            temp114514.append(name)
    return temp114514

def clean_temp_files():
    print("\n正在清理临时文件...")
    shutil.rmtree("dist\\pack")
    os.remove("dist\\metadata.json")
    for name in os.listdir("pack"):
        if os.path.isfile(os.path.join(os.getcwd(), "pack", name)):
            if len(name.split(".")) >= 2 and name.split(".")[1] == "zip":
                os.remove(os.path.join(os.getcwd(), "pack", name))
    print("临时文件清理完成")

def print_header(text, char="=", width=60):
    """打印标题头"""
    print("\n" + char * width)
    print(f"  {text}")
    print(char * width)

def change_value_in_json(path, key, value):
    if path is not None and key is not None and value is not None:
        if os.path.exists(path):
            with open(path, 'r', encoding='UTF-8') as file:
                content = file.read()
                
                # 检测是否包含Unicode编码（如 \u4e2d\u6587）
                has_unicode = bool(re.search(r'\\u[0-9a-fA-F]{4}', content))
                
                # 如果包含Unicode编码，先转换为中文文本
                if has_unicode:
                    # 方法1：只转换 \uXXXX 格式，不处理其他转义
                    def replace_unicode(match):
                        code = match.group(1)
                        try:
                            return chr(int(code, 16))
                        except:
                            return match.group(0)
                    
                    # 只替换 \uXXXX 格式
                    content = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode, content)
                
                # 加载JSON
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误: {e}")
                    print(f"错误位置: 行 {e.lineno}, 列 {e.colno}")
                    print(f"错误内容: {content[max(0, e.pos-50):e.pos+50]}")
                    return
            if key in data:
                before = data[key]
                data[key] = value
                with open(path, 'w', encoding='UTF-8') as file:
                    json.dump(data, file, indent=1, ensure_ascii=False)
                print("Changed " + key + " in " + path + " from " + before + " to " + value)
            else:
                print("There's no " + key + " in " + path)
        else:
            print("Can't find " + path)
    else:
        print("Path or key or value is null!")

def change_value_in_lang_json(path, key, value):
    if path is not None and key is not None and value is not None:
        if os.path.exists(path):
            with open(path, 'r', encoding='UTF-8') as file:
                content = file.read()
                
                # 检测是否包含Unicode编码（如 \u4e2d\u6587）
                has_unicode = bool(re.search(r'\\u[0-9a-fA-F]{4}', content))
                
                # 如果包含Unicode编码，先转换为中文文本
                if has_unicode:
                    # 方法1：只转换 \uXXXX 格式，不处理其他转义
                    def replace_unicode(match):
                        code = match.group(1)
                        try:
                            return chr(int(code, 16))
                        except:
                            return match.group(0)
                    
                    # 只替换 \uXXXX 格式
                    content = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode, content)
                
                # 加载JSON
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误: {e}")
                    print(f"错误位置: 行 {e.lineno}, 列 {e.colno}")
                    print(f"错误内容: {content[max(0, e.pos-50):e.pos+50]}")
                    return
            if "items" in data:
                found = False
                for stuff in data["items"]:
                    if stuff["key"] == key:
                        before = stuff["value"]
                        stuff["value"] = value
                        found = True
                        break
                if found:
                    with open(path, 'w', encoding='UTF-8') as file:
                        json_str = json.dumps(data, indent=2, ensure_ascii=False)
    
                        # 将每个对象压缩到一行
                        # 匹配 {"key": "value", ...} 格式，包括多行
                        def compact_obj(match):
                            # 获取对象内容
                            content = match.group(1)
                            # 移除所有换行和多余空格
                            content = re.sub(r'\n\s*', ' ', content)
                            # 压缩多个空格为一个
                            content = re.sub(r'\s+', ' ', content)
                            # 规范化空格：在 : 后面加空格，在 , 后面加空格
                            content = re.sub(r':\s+', ': ', content)
                            content = re.sub(r',\s+', ', ', content)
                            return '{' + content + '}'
                        
                        # 递归压缩所有对象（但保留数组结构）
                        # 先找到所有对象 {...}
                        json_str = re.sub(r'{\s*([^{}]*?)\s*}', compact_obj, json_str)
                        
                        # 修复数组格式 - 确保数组元素换行
                        # 将 "], {" 替换为 "],\n    {"
                        json_str = re.sub(r'],\s*{', '],\n    {', json_str)
                        json_str = re.sub(r'}\s*]', '}\n  ]', json_str)
                        
                        file.write(json_str)
                    print("Changed " + key + " in " + path + " from " + before + " to " + value)
                else:
                    print("There's no " + key + " in " + path)
            else:
                print("There's no items in " + path)
        else:
            print("Can't find " + path)
    else:
        print("Path or key or value is null!")

def update_version_after_text(file_path, search_text, new_version):
    """Replace version number after specific text on the same line."""
    with open(file_path, 'r', encoding='UTF-8') as file:
        lines = file.readlines()
    
    before = ""
    # Find and update the specific line
    for i, line in enumerate(lines):
        if search_text in line:
            # Replace version number (assuming format: text version=1.2.3)
            # or text: version 1.2.3
            before = lines[i]
            lines[i] = line.replace(line.split()[-1], new_version)
            break
    
    with open(file_path, 'w', encoding='UTF-8') as file:
        file.writelines(lines)
    print("Changed from " + before.replace('\n', '') + " to " + search_text + new_version + " in " + file_path)

if __name__ == '__main__':
    try:
        print_header("BB+ Mod 打包工具", "#", 50)
        
        files = ["header.png", "left.png", "items.json", "icon.ico", "LICENSE", "readme.txt"]
        mini_folders = ["BBDevAPI", "BBPC", "BepInEx64", "BepInEx86"]
        temp_folder_variables = get_immediate_subdirectories(os.path.join(os.getcwd(), "pack"))
        full_folders = []
        
        for folder in temp_folder_variables:
            if folder not in mini_folders:
                full_folders.append(folder)
        
        mini_zip_files = [ folder + ".zip" for folder in mini_folders ]
        full_zip_files = [ folder + ".zip" for folder in full_folders ]
        
        game_ver = input("\nEnter expected game version number: ").strip()
        if not game_ver:
            raise ValueError("Version number cannot be None or empty.")
        
        ver = input("Enter the pack version number: ").strip()
        if not ver:
            raise ValueError("Version number cannot be None or empty.")
        
        ModInfoKey = "BBPC_Menu_ModInfo"
        ModInfoEng = "BB+ Chinese Mod V" + ver
        ModInfoSChu = "汉化模组 V" + ver
        ModInfoTChi = "漢化模組 V" + ver

        change_value_in_json("metadata.json", "version", ver)
        change_value_in_lang_json("MOD\\Assets\\Language\\English\\BBPC_Subtitles.json", ModInfoKey, ModInfoEng)
        change_value_in_lang_json("MOD\\Assets\\Language\\SChinese\\BBPC_Subtitles.json", ModInfoKey, ModInfoSChu)
        change_value_in_lang_json("MOD\\Assets\\Language\\TChinese\\BBPC_Subtitles.json", ModInfoKey, ModInfoTChi)
        change_value_in_lang_json("pack\\BBPC\\BALDI_Data\\StreamingAssets\\Modded\\com.baymaxawa.bbpc\\Language\\English\\BBPC_Subtitles.json", ModInfoKey, ModInfoEng)
        change_value_in_lang_json("pack\\BBPC\\BALDI_Data\\StreamingAssets\\Modded\\com.baymaxawa.bbpc\\Language\\SChinese\\BBPC_Subtitles.json", ModInfoKey, ModInfoSChu)
        change_value_in_lang_json("pack\\BBPC\\BALDI_Data\\StreamingAssets\\Modded\\com.baymaxawa.bbpc\\Language\\TChinese\\BBPC_Subtitles.json", ModInfoKey, ModInfoTChi)
        update_version_after_text("pack\\readme.txt", "当前版本: ", ver)
        update_version_after_text("MOD\\readme.txt", "当前版本: ", ver)
        os.system("explorer pack\\readme.txt")
        os.system("explorer MOD\\readme.txt")
        input("Press any key after you changed update log")
        
        print_header("开始打包流程", "-", 50)
        
        # 准备temp目录
        os.makedirs("temp", exist_ok=True)
        if os.path.isfile("metadata.json"):
            shutil.copy("metadata.json", "temp\\metadata.json")
        
        os.chdir("pack")
        os.makedirs("..\\temp\\pack", exist_ok=True)
        
        # 复制基础文件
        print_header("复制基础文件", "-", 50)
        copy_files_dos_style("main.exe", "..\\temp\\pack")
        copy_files_dos_style("main.x86_64", "..\\temp\\pack")
        copy_files_dos_style("main.bin", "..\\temp\\pack")
        copy_files_dos_style(files, "..\\temp\\pack")
        
        # 压缩MINI版本文件夹
        print_header("创建 MINI 版本压缩包", "-", 50)
        zip_multiple_folders_dos_style(mini_folders)
        
        # 复制MINI版本ZIP文件
        print_header("复制 MINI 版本ZIP文件", "-", 50)
        copy_files_dos_style(mini_zip_files, "..\\temp\\pack")
        
        os.chdir("..")
        
        # 创建最终MINI包
        print_header("创建最终 MINI 包", "-", 50)
        zip_directory_dos_style("BB+ "+game_ver+" v"+ver+" [MINI].zip", "temp", zipfile.ZIP_DEFLATED)
        
        os.chdir("pack")
        
        # 压缩FULL版本文件夹
        if full_folders:
            print_header("创建 FULL 版本压缩包", "-", 50)
            zip_multiple_folders_dos_style(full_folders)
            
            # 复制FULL版本ZIP文件
            print_header("复制 FULL 版本ZIP文件", "-", 50)
            copy_files_dos_style(full_zip_files, "..\\temp\\pack")
        
        os.chdir("..")
        
        # 创建最终FULL包
        print_header("创建最终 FULL 包", "-", 50)
        zip_directory_dos_style("BB+ " + game_ver + " v" + ver + " [FULL].zip", "temp", zipfile.ZIP_DEFLATED)
        
        # 创建MOD包
        print_header("创建 MOD 包", "-", 50)
        zip_directory_dos_style("BB+ " + game_ver + " v" + ver + " [MOD].zip", "MOD", zipfile.ZIP_DEFLATED)
        
        clean_temp_files()
        
        print_header("打包完成！", "#", 50)
        print(f"  游戏版本: {game_ver}")
        print(f"  包版本: v{ver}")
        print(f"  输出文件:")
        print(f"    - BB+ {game_ver} v{ver} [MINI].zip")
        print(f"    - BB+ {game_ver} v{ver} [FULL].zip")
        print(f"    - BB+ {game_ver} v{ver} [MOD].zip")
        print("#" * 50)
        
    except Exception as e:
        print("\n" + "!" * 50)
        print("发生错误！请检查 errors.log 文件！")
        print("!" * 50)
        
        if os.path.exists("errors.log"): 
            os.remove("errors.log")
        
        with open("errors.log", "a") as f:
            f.write(f"[ERROR {datetime.now().isoformat()}] Error Type: {type(e).__name__}, Traceback:\n")
            exc_type, exc_value, exc_tb = sys.exc_info()
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
            f.write("".join(tb_lines))
        
        try:
            clean_temp_files()
        except:
            pass
        
        input("\n按回车键退出...")
        exit(1)