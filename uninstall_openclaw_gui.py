import os
import shutil
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import List, Dict, Tuple


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


class UninstallApp:
    def __init__(self, root: tk.Tk, lang: str = "zh") -> None:
        self.root = root
        self.lang = lang  # "zh" or "en"
        self.root.title(
            "OpenClaw / QClaw 卸载工具 (GUI)" if lang == "zh" else "OpenClaw / QClaw Uninstaller (GUI)"
        )
        self.root.geometry("900x600")

        self.scanning = False
        self.scan_thread: threading.Thread | None = None

        # (tree item id -> absolute path)
        self.item_to_path: Dict[str, str] = {}

        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self) -> None:
        top_frame = ttk.Frame(self.root)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=4)

        if self.lang == "zh":
            btn_scan_text = "开始扫描"
            btn_delete_text = "删除所选"
            btn_exit_text = "退出"
        else:
            btn_scan_text = "Start Scan"
            btn_delete_text = "Delete Selected"
            btn_exit_text = "Exit"

        self.btn_scan = ttk.Button(top_frame, text=btn_scan_text, command=self.on_start_scan)
        self.btn_scan.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_delete = ttk.Button(top_frame, text=btn_delete_text, command=self.on_delete_selected)
        self.btn_delete.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_exit = ttk.Button(top_frame, text=btn_exit_text, command=self.root.destroy)
        self.btn_exit.pack(side=tk.LEFT, padx=(0, 4))

        # progress + status
        progress_frame = ttk.Frame(self.root)
        progress_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 4))

        self.progress = ttk.Progressbar(progress_frame, mode="indeterminate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.status_var = tk.StringVar()
        status_default = "就绪" if self.lang == "zh" else "Ready"
        self.status_var.set(status_default)
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var, width=40, anchor="w")
        self.status_label.pack(side=tk.LEFT, padx=(4, 0))

        # split: upper tree, lower log
        paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # Tree for candidates
        tree_frame = ttk.Frame(paned)
        paned.add(tree_frame, weight=3)

        columns = ("type", "path")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="extended",  # multi-select
        )
        if self.lang == "zh":
            self.tree.heading("type", text="类型")
            self.tree.heading("path", text="路径")
        else:
            self.tree.heading("type", text="Type")
            self.tree.heading("path", text="Path")

        self.tree.column("type", width=120, anchor="w")
        self.tree.column("path", width=650, anchor="w")

        vsb_tree = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb_tree.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb_tree.grid(row=0, column=1, sticky="ns")

        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        # Log text
        log_frame = ttk.Frame(paned)
        paned.add(log_frame, weight=2)

        self.log_text = tk.Text(log_frame, height=8, wrap="none", state="disabled")
        vsb_log = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=vsb_log.set)

        self.log_text.grid(row=0, column=0, sticky="nsew")
        vsb_log.grid(row=0, column=1, sticky="ns")

        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

    # ---------- helpers ----------
    def log(self, message: str) -> None:
        def _append() -> None:
            self.log_text.configure(state="normal")
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state="disabled")

        self.root.after(0, _append)

    def set_status(self, text: str) -> None:
        self.root.after(0, lambda: self.status_var.set(text))

    def set_scanning_state(self, scanning: bool) -> None:
        def _update() -> None:
            self.scanning = scanning
            if scanning:
                self.progress.start(10)
                self.btn_scan.configure(state="disabled")
            else:
                self.progress.stop()
                self.btn_scan.configure(state="normal")

        self.root.after(0, _update)

    def add_candidate(self, kind: str, path: str) -> None:
        """
        在 UI 线程中往 TreeView 里加一项。
        kind: "dir" | "exe"
        """
        def _add() -> None:
            if self.lang == "zh":
                type_text = "目录" if kind == "dir" else "可执行文件"
            else:
                type_text = "Directory" if kind == "dir" else "Executable"
            item_id = self.tree.insert("", tk.END, values=(type_text, path))
            self.item_to_path[item_id] = path

        self.root.after(0, _add)

    # ---------- scanning logic ----------
    def do_scan(self) -> None:
        self.set_scanning_state(True)

        if self.lang == "zh":
            self.log("开始全盘扫描...")
        else:
            self.log("Starting full drive scan...")

        drives = list_drives()
        if not drives:
            if self.lang == "zh":
                self.log("未找到任何盘符。")
                self.set_status("未找到盘符")
            else:
                self.log("No drives found.")
                self.set_status("No drives found")
            self.set_scanning_state(False)
            return

        for drive in drives:
            if self.lang == "zh":
                msg = f"正在扫描磁盘 {drive}..."
            else:
                msg = f"Scanning drive {drive}..."
            self.log(msg)
            self.set_status(msg)

            for root, dirs, files in os.walk(drive, topdown=True):
                # 排除系统目录
                dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRNAMES]

                # 当前目录名匹配
                dirname = os.path.basename(root)
                if path_matches_keywords(dirname):
                    self.add_candidate("dir", root)
                    if self.lang == "zh":
                        self.log(f"[目录匹配] {root}")
                    else:
                        self.log(f"[Directory match] {root}")
                    # 不再深入子目录
                    dirs[:] = []
                    continue

                # 当前目录下的 exe 匹配
                for filename in files:
                    if not filename.lower().endswith(".exe"):
                        continue
                    if path_matches_keywords(filename):
                        fullpath = os.path.join(root, filename)
                        self.add_candidate("exe", fullpath)
                        if self.lang == "zh":
                            self.log(f"[可执行文件匹配] {fullpath}")
                        else:
                            self.log(f"[Executable match] {fullpath}")

        if self.lang == "zh":
            done_msg = "扫描完成。"
        else:
            done_msg = "Scan finished."
        self.log(done_msg)
        self.set_status(done_msg)
        self.set_scanning_state(False)

    # ---------- events ----------
    def on_start_scan(self) -> None:
        if self.scanning:
            return

        # 清理旧数据
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.item_to_path.clear()

        if self.lang == "zh":
            self.log("==== 新的扫描会话 ====")
        else:
            self.log("==== New scan session ====")

        self.scan_thread = threading.Thread(target=self.do_scan, daemon=True)
        self.scan_thread.start()

    def on_delete_selected(self) -> None:
        selected_items = self.tree.selection()
        if not selected_items:
            if self.lang == "zh":
                messagebox.showinfo("提示", "请先在列表中选择要删除的项目。")
            else:
                messagebox.showinfo("Info", "Please select items to delete in the list first.")
            return

        paths: List[Tuple[str, str]] = []
        for item_id in selected_items:
            path = self.item_to_path.get(item_id)
            if path:
                values = self.tree.item(item_id, "values")
                kind_text = values[0] if values else ""
                paths.append((item_id, path))

        if not paths:
            return

        if self.lang == "zh":
            msg = "确认删除所选目录/文件吗？该操作不可恢复！"
            title = "确认删除"
        else:
            msg = "Are you sure you want to delete the selected directories/files? This cannot be undone!"
            title = "Confirm deletion"

        if not messagebox.askyesno(title, msg):
            return

        for item_id, path in paths:
            self._delete_path_and_update_ui(item_id, path)

    def _delete_path_and_update_ui(self, item_id: str, path: str) -> None:
        if not os.path.exists(path):
            if self.lang == "zh":
                self.log(f"[跳过] 路径不存在：{path}")
            else:
                self.log(f"[Skip] Path does not exist: {path}")
            # 无论如何从列表中移除
            self.tree.delete(item_id)
            self.item_to_path.pop(item_id, None)
            return

        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=False)
            else:
                os.remove(path)
            if self.lang == "zh":
                self.log(f"[已删除] {path}")
            else:
                self.log(f"[Deleted] {path}")
            self.tree.delete(item_id)
            self.item_to_path.pop(item_id, None)
        except PermissionError:
            if self.lang == "zh":
                self.log(f"[失败] 权限不足，无法删除：{path}")
                messagebox.showerror(
                    "删除失败",
                    f"权限不足，无法删除：\n{path}\n\n请尝试以管理员身份运行此程序。",
                )
            else:
                self.log(f"[Failed] Insufficient permission to delete: {path}")
                messagebox.showerror(
                    "Delete failed",
                    f"Insufficient permission to delete:\n{path}\n\nPlease try running this program as Administrator.",
                )
        except Exception as e:
            if self.lang == "zh":
                self.log(f"[失败] 删除 {path} 失败：{e}")
                messagebox.showerror("删除失败", f"删除失败：\n{path}\n\n原因：{e}")
            else:
                self.log(f"[Failed] Failed to delete {path}: {e}")
                messagebox.showerror("Delete failed", f"Failed to delete:\n{path}\n\nReason: {e}")


def choose_language_dialog(root: tk.Tk) -> str:
    """
    简单语言选择：
    弹出一个 Yes/No 对话框：
    Yes -> English
    No  -> 中文
    """
    root.withdraw()
    res = messagebox.askyesno(
        "Language / 选择语言",
        "Use English interface?\n\nYes = English\nNo  = 中文界面",
    )
    root.deiconify()
    return "en" if res else "zh"


def main() -> None:
    if not is_windows():
        print("This GUI tool only supports Windows.")
        return

    root = tk.Tk()
    lang = choose_language_dialog(root)
    app = UninstallApp(root, lang=lang)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # If launched from console for debugging, allow Ctrl+C
        print("\nInterrupted by user.")
