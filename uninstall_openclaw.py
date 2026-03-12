import os
import shutil
import sys
from typing import List, Dict


SEARCH_KEYWORDS = [
    "openclaw",
    "qclaw",
    "claw",
    "小龙虾",
]


EXCLUDED_DIRNAMES = {
    "Windows",
    "$Recycle.Bin",
    "System Volume Information",
    "Recovery",
    "PerfLogs",
}


def is_windows() -> bool:
    return os.name == "nt"


def list_drives() -> List[str]:
    """列出当前机器上的所有盘符，例如 C:\\, D:\\."""
    from string import ascii_uppercase

    drives = []
    for letter in ascii_uppercase:
        path = f"{letter}:\\"
        if os.path.exists(path):
            drives.append(path)
    return drives


def path_matches_keywords(path: str) -> bool:
    lower = path.lower()
    for kw in SEARCH_KEYWORDS:
        if kw.lower() in lower:
            return True
    return False


def scan_drive(drive_root: str, lang: str) -> Dict[str, str]:
    """
    扫描单个盘符，返回疑似 openclaw / qclaw / 小龙虾 安装目录的字典：
    {display_name: absolute_path}
    """
    candidates: Dict[str, str] = {}
    if lang == "zh":
        print(f"\n开始扫描磁盘 {drive_root}，这可能需要一些时间，请耐心等待...")
    else:
        print(f"\nScanning drive {drive_root}. This may take some time, please wait...")

    for root, dirs, files in os.walk(drive_root, topdown=True):
        # 排除一些常见的系统目录，加快扫描速度
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRNAMES]

        # 判断当前目录名
        if path_matches_keywords(os.path.basename(root)):
            if lang == "zh":
                display = f"[目录匹配] {root}"
            else:
                display = f"[Directory match] {root}"
            candidates[display] = root
            # 既然整个目录都匹配，就没必要再深挖它的子目录（通常就是安装根目录）
            dirs[:] = []
            continue

        # 判断当前目录下的可执行文件名
        for filename in files:
            if filename.lower().endswith(".exe") and path_matches_keywords(filename):
                install_dir = root
                if lang == "zh":
                    display = f"[可执行文件匹配] {os.path.join(root, filename)}"
                else:
                    display = f"[Executable match] {os.path.join(root, filename)}"
                # 用安装目录作为真正要删除的路径
                candidates[display] = install_dir

    return candidates


def scan_all_drives(lang: str) -> Dict[str, str]:
    """扫描所有盘符，汇总所有候选安装目录。"""
    all_candidates: Dict[str, str] = {}
    for drive in list_drives():
        drive_candidates = scan_drive(drive, lang=lang)
        all_candidates.update(drive_candidates)
    return all_candidates


def confirm(prompt_zh: str, prompt_en: str, lang: str) -> bool:
    prompt = prompt_zh if lang == "zh" else prompt_en
    ans = input(f"{prompt} (y/N): ").strip().lower()
    return ans == "y" or ans == "yes"


def delete_path(path: str, lang: str) -> bool:
    """递归删除目录或文件。删除成功返回 True，失败返回 False。"""
    if not os.path.exists(path):
        if lang == "zh":
            print(f"路径不存在：{path}")
        else:
            print(f"Path does not exist: {path}")
        return False

    try:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=False)
        else:
            os.remove(path)
        if lang == "zh":
            print(f"已删除：{path}")
        else:
            print(f"Deleted: {path}")
        return True
    except PermissionError:
        if lang == "zh":
            print(f"删除失败（权限不足），请尝试以管理员身份运行本程序：{path}")
        else:
            print(f"Failed to delete (insufficient permission). Try running as Administrator: {path}")
        return False
    except Exception as e:
        if lang == "zh":
            print(f"删除失败：{path}\n原因：{e}")
        else:
            print(f"Failed to delete: {path}\nReason: {e}")
        return False


def choose_language() -> str:
    """
    简单的语言选择：
    zh = 中文
    en = English
    默认 zh
    """
    print("Select language / 选择语言:")
    print("1. 中文 (zh)")
    print("2. English (en)")
    choice = input("Enter 1 or 2 (default 1): ").strip()
    if choice == "2":
        return "en"
    return "zh"


def main() -> None:
    lang = choose_language()

    if not is_windows():
        if lang == "zh":
            print("本工具仅支持在 Windows 系统上运行。")
        else:
            print("This tool only supports Windows.")
        return

    if lang == "zh":
        print("=== OpenClaw / QClaw / 小龙虾 类应用卸载工具 ===")
        print("说明：")
        print("1. 本工具会扫描所有磁盘，查找名称中包含以下关键字的目录或可执行文件：")
        print("   " + ", ".join(SEARCH_KEYWORDS))
        print("2. 扫描完成后会列出所有疑似安装目录，由你选择要删除的项目。")
        print("3. 删除操作是物理删除目录/文件，不会自动清理注册表。")
        print("4. 建议先关闭相关程序，并以【管理员身份】运行本工具。")
    else:
        print("=== OpenClaw / QClaw / Lobster-like App Uninstaller ===")
        print("Notes:")
        print("1. This tool will scan all drives and look for directories or executables")
        print("   whose names contain any of the following keywords:")
        print("   " + ", ".join(SEARCH_KEYWORDS))
        print("2. After scanning, it will list all suspected install locations,")
        print("   and you can choose which ones to delete.")
        print("3. Deletion is a physical delete of directories/files and will not")
        print("   automatically clean Windows registry entries.")
        print("4. It is recommended to close related apps and run this tool as Administrator.")

    if not confirm(
        "是否开始全盘扫描？",
        "Start scanning all drives?",
        lang=lang,
    ):
        if lang == "zh":
            print("已取消。")
        else:
            print("Cancelled.")
        return

    all_candidates = scan_all_drives(lang=lang)
    if not all_candidates:
        if lang == "zh":
            print("\n没有找到任何疑似 OpenClaw / QClaw / 小龙虾 相关的目录或程序。")
        else:
            print("\nNo suspected OpenClaw / QClaw / related directories or executables were found.")
        return

    if lang == "zh":
        print("\n扫描完成，找到以下疑似安装目录/程序：\n")
    else:
        print("\nScan finished. Found the following suspected install directories/programs:\n")

    items = list(all_candidates.items())  # [(display, path), ...]
    for idx, (display, path) in enumerate(items, start=1):
        print(f"{idx}. {display}")
        if lang == "zh":
            print(f"    路径：{path}")
        else:
            print(f"    Path: {path}")

    if lang == "zh":
        print("\n你可以：")
        print(" - 输入具体序号，例如：1 或 1,3,5")
        print(" - 输入 all 表示删除列表中的全部项目")
        raw = input("请选择要删除的项目：").strip().lower()
    else:
        print("\nYou can:")
        print(" - Enter specific indices, e.g.: 1 or 1,3,5")
        print(" - Enter all to delete all listed items")
        raw = input("Please choose which items to delete: ").strip().lower()

    if not raw:
        if lang == "zh":
            print("未选择任何项目，已退出。")
        else:
            print("No selection made. Exiting.")
        return

    to_delete_indices: List[int] = []
    if raw == "all":
        to_delete_indices = list(range(1, len(items) + 1))
    else:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        for p in parts:
            if not p.isdigit():
                if lang == "zh":
                    print(f"非法输入：{p}（已忽略）")
                else:
                    print(f"Invalid input: {p} (ignored)")
                continue
            idx = int(p)
            if 1 <= idx <= len(items):
                to_delete_indices.append(idx)
            else:
                if lang == "zh":
                    print(f"序号超出范围：{p}（已忽略）")
                else:
                    print(f"Index out of range: {p} (ignored)")

    if not to_delete_indices:
        if lang == "zh":
            print("没有有效的选择，已退出。")
        else:
            print("No valid selections. Exiting.")
        return

    if lang == "zh":
        print("\n即将删除以下项目（此操作不可恢复，请谨慎）：\n")
    else:
        print("\nAbout to delete the following items (this operation cannot be undone, proceed with caution):\n")

    final_targets: List[str] = []
    for idx in sorted(set(to_delete_indices)):
        display, path = items[idx - 1]
        print(f"{idx}. {display}")
        if lang == "zh":
            print(f"    路径：{path}")
        else:
            print(f"    Path: {path}")
        final_targets.append(path)

    if not confirm(
        "确认删除上述所有目录/文件吗？",
        "Are you sure you want to delete all the directories/files listed above?",
        lang=lang,
    ):
        if lang == "zh":
            print("已取消删除。")
        else:
            print("Deletion cancelled.")
        return

    if lang == "zh":
        print("\n开始删除...\n")
    else:
        print("\nStarting deletion...\n")

    for path in final_targets:
        delete_path(path, lang=lang)

    if lang == "zh":
        print("\n操作完成。建议重启计算机以确保所有变更生效。")
    else:
        print("\nDone. It is recommended to restart your computer to ensure all changes take effect.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # 不区分中英文，这里统一给出简单提示
        print("\nInterrupted by user, exiting.")
