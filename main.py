import os
import sys
import shutil
import json
import tkinter as tk
import re
import xml.etree.ElementTree as ET
from PIL import Image
import zipfile
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
from datetime import datetime

# === 路径设置 ===
COLORS_JSON = "colors.json"

CLIP_PNG_PATH = os.path.join("assets", "clip.png")   # size=320
CLIP_ROUND_PNG_PATH = os.path.join("assets", "clip-round.png")   # size=350 圆形留边多一点好看；这样内部图标就不用重采样了
SUB_XML_PATH = os.path.join("assets", "manifest.xml")
CALENDAR_XML_PATH = os.path.join("assets", "com.android.calendar", "manifest.xml")
CALENDAR_DUO_XML_PATH = os.path.join("assets", "com.android.calendar", "manifest-duo.xml")
NAME_MAPPING = os.path.join("assets", "name_mapping_by_MrBocchi.json")

DRAWABLE_ZIP_PATH = os.path.join("lawnicons_assets", "drawable.zip")
APPFILTER_XML = os.path.join("lawnicons_assets", "appfilter_plain.xml")

TEMP_DIR = "temp"
DRAWABLE_DIR = os.path.join("temp", "drawable")
PREPROCESS_DIR = os.path.join("temp", "_Preprocess")
PREPROCESS_NIGHT_DIR = os.path.join("temp", "_Preprocess-night")
THEME_FALLBACK_XML = os.path.join("temp", "theme_fallback.xml")
GENERAL_XML_PATH = os.path.join("temp", "transform_config.xml")

OUTPUT_ICONS = "icons"
FANCY_ICONS_DIR = "fancy_icons"
RES_DIR = os.path.join("res", "drawable-xxhdpi")

PACK_MAGISK = os.path.join("assets", "pack-magisk")
PACK_MAGISK_TEMP = os.path.join("temp", "pack-magisk")
PACK_MAGISK_OUTPUT = "HyperOS Monet Launcher.zip"
PACK_MTZ = os.path.join("assets", "pack-mtz")
PACK_MTZ_TEMP = os.path.join("temp", "pack-mtz")
PACK_MTZ_OUTPUT = "HyperOS Monet Launcher.mtz"

def CLEAR_LAST_LINE(n=1):
    for _ in range(n):
        sys.stdout.write("\033[F\033[K")
    sys.stdout.flush()

# === 修复 colors.json 尾部多余逗号 ===
def fix_color():
    with open(COLORS_JSON, 'r', encoding='utf-8') as f:
        content = f.read()

    # 从结尾向前找 '}' 前是否有多余逗号（逗号后面紧跟换行和 }）
    fixed_content = re.sub(r',\s*(\n\s*})', r'\1', content, count=1)

    # 只在内容变动时写入
    if fixed_content != content:
        with open(COLORS_JSON, 'w', encoding='utf-8') as f:
            f.write(fixed_content)

# === 查询并验证颜色配置文件 ===
def check_colors():
    def is_color(val):
        return isinstance(val, str) and val.startswith("#") and len(val) in (7, 9)

    while True:
        try:
            with open(COLORS_JSON, 'r', encoding="utf-8") as f:
                colors = json.load(f)

            required_keys = ["accent1_100", "accent1_200", "accent1_700"]

            # 遍历检查
            for key in required_keys:
                if not is_color(colors.get(key)):
                    raise ValueError("格式错误")

        except Exception:
            print("⚠ 配置信息格式错误，读取失败！请阅读说明文档重新填写！")
            print("保存并关闭文件以继续...")
            os.system(f'notepad "{COLORS_JSON}"')
            CLEAR_LAST_LINE(2)
            fix_color()
            continue
        else:
            return True

# === 色值设置（ARGB格式）===
def prepare_color():
    with open(COLORS_JSON, 'r') as f:
        colors = json.load(f)

    accent1_100 = colors["accent1_100"]
    accent1_200 = colors["accent1_200"]
    accent1_700 = colors["accent1_700"]

    return accent1_100, accent1_200, accent1_700

# === 功能2 预览颜色配置 ===
def preview_color():
    # 读取 colors.json
    with open(COLORS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 过滤并按数字排序 accent1_xxx 项
    accent_colors = {
        k: v for k, v in data.items() if k.startswith("accent1_")
    }
    # 排序（按数字后缀排序）
    accent_colors = dict(sorted(accent_colors.items(), key=lambda item: int(item[0].split("_")[1])))

    # 矩形尺寸设置
    rect_width = 200
    rect_height = 50
    padding = 2

    # 计算窗口高度
    canvas_height = len(accent_colors) * (rect_height + padding)
    canvas_width = rect_width

    # 创建窗口和画布
    root = tk.Tk()
    root.title("预览")
    root.resizable(False, False)

    # 使窗口首次显示时置顶
    root.lift()
    root.attributes("-topmost", True)
    root.after(0, lambda: root.attributes("-topmost", False))

    canvas = tk.Canvas(root, width=canvas_width, height=canvas_height, bg="white")
    canvas.pack()

    # 绘制颜色块
    y = 0
    for name, hex_color in accent_colors.items():
        canvas.create_rectangle(
            0, y, rect_width, y + rect_height,
            fill=hex_color, outline=""
        )
        canvas.create_text(
            rect_width // 2, y + rect_height // 2,
            text="system_" + name,
            fill="white" if int(hex_color.lstrip("#")[0:2], 16) < 128 else "black"
        )
        y += rect_height + padding

    # 启动窗口循环
    root.mainloop()

# === 功能3 预处理图片 以下三个函数 ===
def generate_icon(foreground_color, background_color, base_img: Image.Image, clip_alpha: Image.Image) -> Image.Image:
    # 创建背景层
    bg = Image.new("RGBA", clip_alpha.size, background_color)

    # 创建前景图（215x215）并填充颜色 + alpha
    fg_raw = Image.new("RGBA", base_img.size, foreground_color)
    fg_raw.putalpha(base_img.getchannel("A"))

    # 创建前景层画布（320x320）并将小图居中粘贴进去
    fg = Image.new("RGBA", clip_alpha.size, (0, 0, 0, 0))
    offset = (
        (clip_alpha.width - base_img.width) // 2,
        (clip_alpha.height - base_img.height) // 2
    )
    fg.paste(fg_raw, offset)

    # 合成图层
    composed = Image.alpha_composite(bg, fg)

    # 应用clip.png的alpha通道
    composed.putalpha(clip_alpha.getchannel("A"))

    return composed

def process_file(file_name, input_dir, accent1_100, accent1_200, accent1_700, clip_png):
    input_path = os.path.join(input_dir, file_name)
    os.makedirs(PREPROCESS_DIR, exist_ok=True)
    os.makedirs(PREPROCESS_NIGHT_DIR, exist_ok=True)

    # 读取图片
    base = Image.open(input_path).convert("RGBA")

    # 加载clip.png的alpha通道
    clip = Image.open(clip_png).convert("RGBA")

    # 生成浅色图标
    icon0 = generate_icon(accent1_700, accent1_100, base, clip)
    icon0.save(os.path.join(PREPROCESS_DIR, file_name))

    # 生成深色图标
    icon1 = generate_icon(accent1_200, accent1_700, base, clip)
    icon1.save(os.path.join(PREPROCESS_NIGHT_DIR, file_name))

def create_theme_fallback_xml():
    print(f"正在生成 {THEME_FALLBACK_XML}...")

    # 读取映射 JSON
    with open(NAME_MAPPING, 'r', encoding='utf-8') as f:
        mapping_data = json.load(f)
    filtered_mapping = {k: v for k, v in mapping_data.items() if not k.startswith("_comment-")}

    tree = ET.parse(APPFILTER_XML)
    root = tree.getroot()

    output_lines = [
        "<?xml version='1.0' encoding='utf-8' standalone='yes'?>",
        "<MIUI_Theme_Values>"
    ]

    # 处理 appfilter 中的包名
    written_packages = set()
    for item in root.findall("item"):
        component = item.attrib.get("component", "")
        drawable = item.attrib.get("drawable", "")
        if not component or not drawable:
            continue
        if not (component.startswith("ComponentInfo{") and component.endswith("}")):
            continue
        comp_str = component[len("ComponentInfo{"):-1]
        if "/" not in comp_str:
            continue
        pkg_name, cls_name = comp_str.split("/", 1)
        if "*" in cls_name:
            continue
        if pkg_name in written_packages:
            continue
        drawable_png = f"{drawable}.png"
        output_lines.append(f'<drawable name="{pkg_name}.png">{drawable_png}</drawable>')
        written_packages.add(pkg_name)

    # 处理 NAME_MAPPING 里的包名
    for key, drawable in filtered_mapping.items():
        if '/' in key:
            pkg_name = key.split('/', 1)[0]
        else:
            pkg_name = key
        drawable_png = f"{drawable}.png"
        output_lines.append(f'<drawable name="{pkg_name}.png">{drawable_png}</drawable>')

    output_lines.append("</MIUI_Theme_Values>")

    with open(THEME_FALLBACK_XML, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

# === 进度条 ===
def print_progress_bar(current, total, bar_length=40):
    percent = current / total
    filled_length = int(bar_length * percent)
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    sys.stdout.write(f"\r进度: |{bar}| {current}/{total} ({percent*100:.1f}%)")
    sys.stdout.flush()

# === 功能4 打包导出 ===
def icon_package(switch_function, light_mode):
    if switch_function == "y":

        tree = ET.parse(APPFILTER_XML)
        root = tree.getroot()

        # 收集 appfilter 里的包名
        package_names = set()
        valid_items = []
        for item in root.findall('item'):
            component = item.get('component')
            drawable = item.get('drawable')
            if not component or not drawable:
                continue
            match = re.match(r'ComponentInfo\{(.+)\}', component)
            if not match:
                continue
            full_path = match.group(1)
            if '*' in full_path:
                continue
            parts = full_path.split('/')
            if len(parts) < 2:
                continue
            package_name = parts[0]
            package_names.add(package_name)
            valid_items.append((full_path, drawable))

        # 读取映射 JSON（直接用 NAME_MAPPING 常量路径）
        with open(NAME_MAPPING, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)

        # 去掉 _comment-* 键
        filtered_mapping = {
            k: v for k, v in mapping_data.items() if not k.startswith("_comment-")
        }

        # 计算 total：唯一包名数量 + 映射内的键数量 - 日历
        total = len(package_names) + len(filtered_mapping) - 1
        current = 0

        with zipfile.ZipFile(OUTPUT_ICONS, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 初始化时直接跳过日历包
            written_packages = {"com.android.calendar"}

            # 先处理 appfilter 里的
            for full_path, drawable in valid_items:
                parts = full_path.split('/')
                package_name = parts[0]

                if package_name in written_packages:
                    continue

                folder = os.path.join(FANCY_ICONS_DIR, package_name)

                src_light = os.path.join(PREPROCESS_DIR, f"{drawable}.png")
                src_dark = os.path.join(PREPROCESS_NIGHT_DIR, f"{drawable}.png")
                if not (os.path.exists(src_light) and os.path.exists(src_dark) and os.path.exists(SUB_XML_PATH)):
                    continue

                zipf.write(src_light, os.path.join(folder, "iconBg_0.png"))
                zipf.write(src_dark, os.path.join(folder, "iconBg_1.png"))
                zipf.write(SUB_XML_PATH, os.path.join(folder, "manifest.xml"))

                written_packages.add(package_name)
                current += 1
                print_progress_bar(current, total)

            # 再处理映射 JSON 里的
            for key, drawable in filtered_mapping.items():
                if '/' in key:  # 活动名（全路径）
                    folder = os.path.join(FANCY_ICONS_DIR, key)
                else:  # 包名
                    folder = os.path.join(FANCY_ICONS_DIR, key)

                src_light = os.path.join(PREPROCESS_DIR, f"{drawable}.png")
                src_dark = os.path.join(PREPROCESS_NIGHT_DIR, f"{drawable}.png")
                if not (os.path.exists(src_light) and os.path.exists(src_dark) and os.path.exists(SUB_XML_PATH)):
                    continue

                zipf.write(src_light, os.path.join(folder, "iconBg_0.png"))
                zipf.write(src_dark, os.path.join(folder, "iconBg_1.png"))
                zipf.write(SUB_XML_PATH, os.path.join(folder, "manifest.xml"))

                current += 1
                print_progress_bar(current, total)

            sys.stdout.flush()
            sys.stdout.write("\n")

            # 1. 白天模式日历图标
            for i in range(1, 32):
                src = os.path.join(PREPROCESS_DIR, f"themed_icon_calendar_{i}.png")
                dst = f"fancy_icons/com.android.calendar/calendar_0/themed_icon_calendar_{i}.png"
                zipf.write(src, dst)

            # 2. 夜间模式日历图标
            for i in range(1, 32):
                src = os.path.join(PREPROCESS_NIGHT_DIR, f"themed_icon_calendar_{i}.png")
                dst = f"fancy_icons/com.android.calendar/calendar_1/themed_icon_calendar_{i}.png"
                zipf.write(src, dst)

            # 3. manifest-duo.xml
            zipf.write(CALENDAR_DUO_XML_PATH, "fancy_icons/com.android.calendar/manifest.xml")

            # 加入 transform_config.xml
            zipf.write(GENERAL_XML_PATH, "transform_config.xml")

    else:  # switch_function == "n"

        input_dir = PREPROCESS_DIR if light_mode == "y" else PREPROCESS_NIGHT_DIR

        # 计算总量 = input_dir 内所有 png 数量
        total = len([f for f in os.listdir(input_dir) if f.lower().endswith(".png")])
        current = 0

        with zipfile.ZipFile(OUTPUT_ICONS, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 直接复制所有 png
            for filename in os.listdir(input_dir):
                if not filename.lower().endswith(".png"):
                    continue
                src_file = os.path.join(input_dir, filename)
                if not os.path.isfile(src_file):
                    continue
                zipf.write(src_file, os.path.join(RES_DIR, filename))
                current += 1
                print_progress_bar(current, total)

            sys.stdout.flush()
            sys.stdout.write("\n")

            # 1. 普通日历图标
            for i in range(1, 32):
                src = os.path.join(DRAWABLE_DIR, f"themed_icon_calendar_{i}.png")
                dst = f"fancy_icons/com.android.calendar/calendar/themed_icon_calendar_{i}.png"
                zipf.write(src, dst)

            # 2. manifest.xml
            zipf.write(CALENDAR_XML_PATH, "fancy_icons/com.android.calendar/manifest.xml")

            # 加入 theme_fallback.xml 和 transform_config.xml
            zipf.write(THEME_FALLBACK_XML, "theme_fallback.xml")
            zipf.write(GENERAL_XML_PATH, "transform_config.xml")

# === 清屏 ===
def clear():
    os.system("cls" if os.name == "nt" else "clear")

# === 主程序 ===

def main():
    for filepath in [CLIP_PNG_PATH, SUB_XML_PATH, DRAWABLE_ZIP_PATH]:
        if not os.path.isfile(filepath):
            clear()
            print("错误：文件检测不完整，请重新完整解压。")
            sys.exit(1)

    if not os.path.exists(DRAWABLE_DIR) or not any(os.scandir(DRAWABLE_DIR)):
        clear()
        os.makedirs(DRAWABLE_DIR, exist_ok=True)
        with zipfile.ZipFile(DRAWABLE_ZIP_PATH, 'r') as zipf:
            file_list = zipf.infolist()
            total_files = len(file_list)

            for idx, member in enumerate(file_list, start=1):
                zipf.extract(member, path=TEMP_DIR)
                percent = (idx / total_files) * 100
                print(f"\r首次运行，资源文件解压中 ({percent:.1f}%)...", end="", flush=True)

    while True:
        clear()
        print("╔═══════════════════════════════════╗")
        print("║     HyperOS桌面莫奈图标生成器     ║")
        print("║         by 酷安@Mr_Bocchi         ║")
        print("╟───────────────────────────────────╢")
        print("║ 【1】编辑颜色配置                 ║")
        print("║ 【2】预览颜色配置                 ║")
        print("║ 【3】预处理图片                   ║")
        print("║ 【4】打包导出icons                ║")
        print("║ 【5】生成面具模块 / 【6】生成mtz  ║")
        print("║ 【0】退出                         ║")
        print("╚═══════════════════════════════════╝")
        user_input = input("请选择：").strip()

        if user_input == "1":

            print("在手机端使用 Material You Color Previewer 获取当前颜色配置，粘贴入打开的 json 文件内。")
            print("保存并关闭文件以继续...")
            os.system(f'notepad "{COLORS_JSON}"')
            CLEAR_LAST_LINE()

            fix_color()

            check_colors()
            print("配置读取成功！可使用【功能2】预览颜色！")
            input("回车键以继续...")

            continue

        elif user_input == "2":

            print("在新的窗口中预览。")
            print("关闭预览窗口以继续...")
            fix_color()


            preview_color()
            continue

        elif user_input == "3":

            fix_color()
            check_colors()
            print(" ")
            print("请选择使用的图标风格：")
            while True:
                icon_style = input("(1：圆角矩形 / 2：圆形): ").strip()

                if icon_style == "1":
                    clip_png = CLIP_PNG_PATH
                    shutil.copyfile(os.path.join("assets", "transform_config.xml"), GENERAL_XML_PATH)
                    break
                elif icon_style == "2":
                    clip_png = CLIP_ROUND_PNG_PATH
                    shutil.copyfile(os.path.join("assets", "transform_config-round.xml"), GENERAL_XML_PATH)
                    break
                else:
                    CLEAR_LAST_LINE()

            print("该步骤较慢，请耐心等待...")
            accent1_100, accent1_200, accent1_700 = prepare_color()
            png_files = [file for file in os.listdir(DRAWABLE_DIR) if file.lower().endswith(".png")]
            total_files = len(png_files)

            for idx, file in enumerate(png_files, 1):
                print_progress_bar(idx, total_files)
                process_file(file, DRAWABLE_DIR, accent1_100, accent1_200, accent1_700, clip_png)

            # 解决刷新问题
            sys.stdout.flush()
            sys.stdout.write("\n")

            create_theme_fallback_xml()
            print(" ")
            print("处理完成！接下来可以打包导出！")
            input("回车键以继续...")
            continue

        elif user_input == "4":

            if not os.path.exists(PREPROCESS_DIR) or not any(os.scandir(PREPROCESS_DIR)) or not os.path.exists(THEME_FALLBACK_XML) or not os.path.exists(GENERAL_XML_PATH):
                print("缓存区为空！请先执行【功能1、3】预处理图片！")
                input("回车键以继续...")
                continue

            print(" ")
            print("提示：如果您已修改颜色配置，请务必先执行【功能3】，否则打包的图标颜色不会生效！")
            user_confirm = input("回车键以继续；键入任意内容【返回功能选择】... ")

            if user_confirm:
                continue

            print(" ")
            print("是否启用“自动切换深色模式”功能？启用将显著增加文件体积。")
            while True:
                switch_function = input("(y：启用 / n：禁用): ").strip()

                if switch_function in ("y", "n"):
                    break
                else:
                    CLEAR_LAST_LINE()

            light_mode = "y"  # 不提前赋值的话，switch_function 启用时，代码会炸

            if switch_function == "n":
                print(" ")
                print("请选择要打包的“单色图标”风格：")
                while True:
                    light_mode = input("(y：浅色图标包 / n：深色图标包): ").strip()

                    if light_mode in ("y", "n"):
                        break
                    else:
                        CLEAR_LAST_LINE()

            # 执行
            print(" ")
            print("开始打包...")
            icon_package(switch_function, light_mode)
            print(" ")
            print("处理完成！icons 文件已生成于项目根目录。")
            print("接下来您可以：")
            print("方案1(推荐)：将icons直接复制至手机/data/system/theme/，然后重启桌面。具体细节见说明文档。")
            print("方案2：使用功能5生成面具模块，然后刷入并重启手机。")
            print("方案3：使用功能6生成mtz主题包，然后使用主题破解模块安装。")
            print(" ")
            input("回车键以继续...")
            continue

        elif user_input == "5":

            if not os.path.exists(OUTPUT_ICONS):
                print("找不到 icons 文件，请先执行【功能1、3、4】生成图标包！")
                continue

            print("打包中...")

            # 1. 复制 PACK_MAGISK 到 PACK_MAGISK_TEMP
            if os.path.exists(PACK_MAGISK_TEMP):
                shutil.rmtree(PACK_MAGISK_TEMP)
            shutil.copytree(PACK_MAGISK, PACK_MAGISK_TEMP)

            # 2. 修改 module.prop，加入构建时间
            module_prop_path = os.path.join(PACK_MAGISK_TEMP, "module.prop")
            if os.path.exists(module_prop_path):
                with open(module_prop_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if lines:
                    lines[-1] = lines[-1].strip() + now_str + "\n"
                
                with open(module_prop_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)

            # 3. 打包到 PACK_MAGISK_OUTPUT
            with zipfile.ZipFile(PACK_MAGISK_OUTPUT, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(PACK_MAGISK_TEMP):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, PACK_MAGISK_TEMP)
                        zipf.write(file_path, arcname)
                
                zipf.write(
                    OUTPUT_ICONS,
                    os.path.join("product", "media", "theme", "default", "icons")
                )

            print(f"打包完成: {PACK_MAGISK_OUTPUT}")
            input("回车键以继续...")
            continue

        elif user_input == "6":

            if not os.path.exists(OUTPUT_ICONS):
                print("找不到 icons 文件，请先执行【功能1、3、4】生成图标包！")
                continue

            print("打包中...")

            # 1. 复制 PACK_MTZ 到 PACK_MTZ_TEMP
            if os.path.exists(PACK_MTZ_TEMP):
                shutil.rmtree(PACK_MTZ_TEMP)
            shutil.copytree(PACK_MTZ, PACK_MTZ_TEMP)

            # 2. 修改 description.xml，加入构建时间
            description_xml_path = os.path.join(PACK_MTZ_TEMP, "description.xml")
            with open(description_xml_path, "r", encoding="utf-8") as f:
                content = f.read()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            pos = content.find("构建时间：")
            if pos != -1:
                pos += len("构建时间：")
                content = content[:pos] + now_str + content[pos:]
            with open(description_xml_path, "w", encoding="utf-8") as f:
                f.write(content)

            # 3. 打包到 PACK_MTZ_OUTPUT
            with zipfile.ZipFile(PACK_MTZ_OUTPUT, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(PACK_MTZ_TEMP):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, PACK_MTZ_TEMP)
                        zipf.write(file_path, arcname)
                
                zipf.write(OUTPUT_ICONS)

            print(f"打包完成: {PACK_MTZ_OUTPUT}")
            print("请使用主题破解模块安装！")
            input("回车键以继续...")
            continue

        elif user_input == "0":

            sys.exit(1)

        elif user_input == "999":

            print("999.开发者打包图标模式")
            print("打包中...")

            with zipfile.ZipFile(DRAWABLE_ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(DRAWABLE_DIR):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, os.path.dirname(DRAWABLE_DIR))  # 保留 drawable 目录层级
                        zipf.write(file_path, arcname)

            # 删除目录及内容
            shutil.rmtree(DRAWABLE_DIR)

            print("打包成功！已解压的图标文件已删除。")
            sys.exit(1)

        else:
            continue  # 输入非法，自动清空并重来
        
        input("应该执行不到这一步。执行到了牛牛剪掉( *・ω・)✄╰ひ╯")

if __name__ == "__main__":
    main()
