#!/usr/bin/env python3
"""Windows desktop interface for the student drawing analyzer."""

from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageChops, ImageOps, ImageTk

import analyze_drawings as analyzer


APP_TITLE = "学生绘图作业分析器"
BG = "#eef1f4"
SURFACE = "#ffffff"
INK = "#18232c"
MUTED = "#6c7680"
LINE = "#d5dbe1"
BLUE = "#0d3b70"
BLUE_HOVER = "#082d58"
GREEN = "#187653"
GOLD = "#d5a32a"
RED = "#c73935"
PREVIEW_BG = "#e5e9ed"


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


class ImagePane(tk.Frame):
    def __init__(self, master: tk.Misc, title: str, fit_whole: bool) -> None:
        super().__init__(master, bg=SURFACE, highlightbackground=LINE, highlightthickness=1)
        self.fit_whole = fit_whole
        self.photo: ImageTk.PhotoImage | None = None
        self.image_item: int | None = None

        heading = tk.Frame(self, bg=SURFACE, height=44)
        heading.pack(fill="x")
        heading.pack_propagate(False)
        tk.Label(heading, text=title, bg=SURFACE, fg=INK, font=("Microsoft YaHei UI", 11, "bold")).pack(
            side="left", padx=16
        )

        viewport = tk.Frame(self, bg=PREVIEW_BG)
        viewport.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(viewport, bg=PREVIEW_BG, highlightthickness=0, width=460, height=500)
        vertical = ttk.Scrollbar(viewport, orient="vertical", command=self.canvas.yview)
        horizontal = ttk.Scrollbar(viewport, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        viewport.grid_rowconfigure(0, weight=1)
        viewport.grid_columnconfigure(0, weight=1)
        self.placeholder = self.canvas.create_text(
            230,
            250,
            text="尚未选择图纸",
            fill=MUTED,
            font=("Microsoft YaHei UI", 12),
        )

    def clear(self, message: str = "尚未生成检查结果") -> None:
        self.canvas.delete("all")
        self.photo = None
        self.image_item = None
        self.canvas.configure(scrollregion=(0, 0, 460, 500))
        self.placeholder = self.canvas.create_text(
            230,
            250,
            text=message,
            fill=MUTED,
            font=("Microsoft YaHei UI", 12),
        )

    def show(self, path: Path) -> None:
        try:
            with Image.open(path) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
        except Exception as exc:
            self.clear(f"无法预览图像\n{exc}")
            return

        self.update_idletasks()
        viewport_width = max(320, self.canvas.winfo_width() - 24)
        viewport_height = max(320, self.canvas.winfo_height() - 24)
        if self.fit_whole:
            scale = min(viewport_width / image.width, viewport_height / image.height, 1.0)
        else:
            scale = min(viewport_width / image.width, 1.0)
        rendered_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        if rendered_size != image.size:
            image = image.resize(rendered_size, Image.Resampling.LANCZOS)

        self.photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        canvas_width = max(viewport_width, rendered_size[0])
        canvas_height = max(viewport_height, rendered_size[1])
        x = max(0, (canvas_width - rendered_size[0]) // 2)
        y = max(0, (viewport_height - rendered_size[1]) // 2) if self.fit_whole else 0
        self.image_item = self.canvas.create_image(x, y, anchor="nw", image=self.photo)
        self.canvas.configure(scrollregion=(0, 0, canvas_width, canvas_height))
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)


class AnalyzerWindow:
    def __init__(self, root: tk.Tk, initial_path: Path | None = None) -> None:
        self.root = root
        self.selected_path: Path | None = None
        self.result: analyzer.RunResult | None = None
        self.messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self.running = False
        self.network_status = analyzer.NetworkStatus(False, "检测中")
        self.brand_images: list[ImageTk.PhotoImage] = []

        root.title(f"{APP_TITLE} {analyzer.VERSION}")
        root.geometry("1180x820")
        root.minsize(980, 680)
        root.configure(bg=BG)
        self._configure_styles()
        self._build_ui()
        root.after(100, self._poll_messages)
        root.after(300, self._start_network_check)
        if initial_path:
            root.after(250, lambda: self.select_file(initial_path, auto_start=True))

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("App.Horizontal.TProgressbar", troughcolor="#dfe3e7", background=BLUE, borderwidth=0)

    def _load_brand_logo(self, filename: str, size: tuple[int, int]) -> ImageTk.PhotoImage:
        with Image.open(resource_path(f"assets/{filename}")) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
        white = Image.new("RGB", image.size, "white")
        difference = ImageChops.difference(image, white).convert("L")
        bounds = difference.point(lambda value: 255 if value > 12 else 0).getbbox()
        if bounds:
            image = image.crop(bounds)
        image.thumbnail(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", size, "white")
        canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
        photo = ImageTk.PhotoImage(canvas)
        self.brand_images.append(photo)
        return photo

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg=SURFACE, height=104, highlightbackground=LINE, highlightthickness=0)
        header.pack(fill="x")
        header.pack_propagate(False)
        brand = tk.Frame(header, bg=SURFACE)
        brand.pack(side="left", padx=28, pady=14)
        tju_logo = self._load_brand_logo("tju_arch_logo.png", (68, 68))
        zhihui_logo = self._load_brand_logo("zhihui_logo.png", (68, 68))
        self.root.iconphoto(True, tju_logo)
        tk.Label(brand, image=tju_logo, bg=SURFACE).pack(side="left")
        tk.Frame(brand, bg=LINE, width=1, height=56).pack(side="left", padx=16)
        tk.Label(brand, image=zhihui_logo, bg=SURFACE).pack(side="left")
        title_group = tk.Frame(brand, bg=SURFACE)
        title_group.pack(side="left", padx=(18, 0))
        tk.Label(
            title_group,
            text=APP_TITLE,
            bg=SURFACE,
            fg=BLUE,
            font=("Microsoft YaHei UI", 18, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_group,
            text="天津大学建筑学院 × 智绘小屋｜建筑制图智能检查",
            bg=SURFACE,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w")
        header_actions = tk.Frame(header, bg=SURFACE)
        header_actions.pack(side="right", padx=28)
        network_chip = tk.Frame(header_actions, bg="#f0f3f5", padx=12, pady=8)
        network_chip.pack(side="left", padx=(0, 10))
        self.network_dot = tk.Label(network_chip, text="●", bg="#f0f3f5", fg=GOLD, font=("Segoe UI", 9))
        self.network_dot.pack(side="left")
        self.network_label = tk.Label(
            network_chip,
            text="网络检测中",
            bg="#f0f3f5",
            fg=INK,
            font=("Microsoft YaHei UI", 9),
        )
        self.network_label.pack(side="left", padx=(6, 0))
        self.network_button = self._button(header_actions, "重新检测", self._manual_network_check, kind="secondary")
        self.network_button.pack(side="left", padx=(0, 10))
        self.settings_button = self._button(header_actions, "设置", self._open_settings, kind="primary")
        self.settings_button.pack(side="left")
        tk.Frame(self.root, bg=BLUE, height=4).pack(fill="x")

        command_bar = tk.Frame(self.root, bg=BG)
        command_bar.pack(fill="x", padx=28, pady=(20, 14))
        self.choose_button = self._button(command_bar, "选择图纸并开始检查", self._choose_file, kind="primary")
        self.choose_button.pack(side="left")
        self.open_image_button = self._button(command_bar, "打开检查图", self._open_result, kind="secondary")
        self.open_image_button.pack(side="left", padx=(10, 0))
        self.open_image_button.configure(state="disabled")
        self.open_folder_button = self._button(command_bar, "打开结果目录", self._open_folder, kind="secondary")
        self.open_folder_button.pack(side="left", padx=(10, 0))
        self.open_folder_button.configure(state="disabled")
        self.file_label = tk.Label(
            command_bar,
            text="未选择文件",
            bg=BG,
            fg=MUTED,
            anchor="e",
            font=("Microsoft YaHei UI", 9),
        )
        self.file_label.pack(side="right", fill="x", expand=True, padx=(18, 0))

        preview_area = tk.Frame(self.root, bg=BG)
        preview_area.pack(fill="both", expand=True, padx=28)
        preview_area.grid_columnconfigure(0, weight=1, uniform="preview")
        preview_area.grid_columnconfigure(1, weight=1, uniform="preview")
        preview_area.grid_rowconfigure(0, weight=1)
        self.source_pane = ImagePane(preview_area, "01  原始图纸", fit_whole=True)
        self.source_pane.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.result_pane = ImagePane(preview_area, "02  智能批注结果", fit_whole=False)
        self.result_pane.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self.result_pane.clear()

        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", padx=28, pady=(12, 18))
        self.status_dot = tk.Label(footer, text="●", bg=BG, fg=MUTED, font=("Segoe UI", 10))
        self.status_dot.pack(side="left")
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg=BG,
            fg=INK,
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left", padx=(7, 16))
        self.progress = ttk.Progressbar(footer, mode="indeterminate", style="App.Horizontal.TProgressbar", length=250)

    def _button(self, master: tk.Misc, text: str, command: object, kind: str) -> tk.Button:
        palette = {
            "primary": (BLUE, "white", BLUE_HOVER),
            "secondary": ("#e8edf1", INK, "#dce3e8"),
            "dark": (INK, "white", "#303d47"),
        }
        bg, fg, active = palette[kind]
        return tk.Button(
            master,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active,
            activeforeground=fg,
            disabledforeground="#9aa0a6",
            relief="flat",
            bd=0,
            padx=18,
            pady=9,
            cursor="hand2",
            font=("Microsoft YaHei UI", 9, "bold"),
        )

    def _start_network_check(self, show_dialog: bool = False) -> None:
        if self.running:
            return
        self.network_label.configure(text="网络检测中")
        self.network_dot.configure(fg=GOLD)
        self.network_button.configure(state="disabled")

        def worker() -> None:
            status = analyzer.probe_api_connectivity(timeout=6)
            self.messages.put(("network", (status, show_dialog)))

        threading.Thread(target=worker, daemon=True).start()

    def _manual_network_check(self) -> None:
        self._start_network_check(show_dialog=True)

    def _network_checked(self, payload: object) -> None:
        status, show_dialog = payload  # type: ignore[misc]
        self.network_status = status
        if not self.running:
            self.network_button.configure(state="normal")
        if status.reachable:
            self.network_label.configure(text=f"网络已就绪 · {status.transport}")
            self.network_dot.configure(fg=GREEN)
            if show_dialog:
                messagebox.showinfo(APP_TITLE, "OpenAI API 网络连接正常，可以开始检查图纸。")
        else:
            self.network_label.configure(text="VPN 未连接")
            self.network_dot.configure(fg=RED)
            if show_dialog:
                messagebox.showwarning(
                    APP_TITLE,
                    "当前无法连接 OpenAI API。请先连接 VPN，并开启全局、TUN 或系统代理模式，然后再次检测。",
                )

    def _choose_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="选择学生图纸",
            filetypes=[
                ("图像文件", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"),
                ("所有文件", "*.*"),
            ],
        )
        if selected:
            self.select_file(Path(selected), auto_start=True)

    def select_file(self, path: Path, auto_start: bool) -> None:
        path = path.resolve()
        if not path.is_file() or path.suffix.lower() not in analyzer.IMAGE_EXTENSIONS:
            messagebox.showerror(APP_TITLE, "请选择 PNG、JPG、WebP、BMP 或 TIFF 图像。")
            return
        self.selected_path = path
        self.result = None
        self.file_label.configure(text=path.name)
        self.source_pane.show(path)
        self.result_pane.clear()
        self.open_image_button.configure(state="disabled")
        self.open_folder_button.configure(state="disabled")
        self.status_var.set("图纸已载入")
        self.status_dot.configure(fg=BLUE)
        if auto_start:
            self._start_analysis()

    def _start_analysis(self) -> None:
        if self.running or not self.selected_path:
            return
        if not os.getenv("OPENAI_API_KEY", "").strip() and not analyzer.load_saved_api_key():
            self.status_var.set("尚未设置 API 密钥")
            self.status_dot.configure(fg="#c5221f")
            messagebox.showinfo(APP_TITLE, "尚未设置 API 密钥。请点击右上角“密钥设置”完成一次性配置。")
            return

        self.running = True
        self.choose_button.configure(state="disabled")
        self.settings_button.configure(state="disabled")
        self.network_button.configure(state="disabled")
        self.status_dot.configure(fg=BLUE)
        self.status_var.set("正在准备分析...")
        self.progress.pack(side="right")
        self.progress.start(12)
        selected = self.selected_path

        def worker() -> None:
            try:
                network = analyzer.probe_api_connectivity(timeout=6, preferred_proxy=self.network_status.proxy_url)
                self.messages.put(("network", (network, False)))
                if not network.reachable:
                    raise analyzer.AnalyzerError(
                        "当前无法连接 OpenAI API。请先连接 VPN，并开启全局、TUN 或系统代理模式，然后点击“重新检测”。"
                    )
                args = analyzer.build_parser().parse_args([str(selected), "--no-open"])
                args.proxy = network.proxy_url
                result = analyzer.run(args, progress=lambda value: self.messages.put(("progress", value)))
                self.messages.put(("complete", result))
            except Exception as exc:
                self.messages.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_messages(self) -> None:
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == "progress":
                    self.status_var.set(str(payload))
                elif kind == "complete":
                    self._analysis_complete(payload)
                elif kind == "error":
                    self._analysis_failed(payload)
                elif kind == "network":
                    self._network_checked(payload)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_messages)

    def _analysis_complete(self, payload: object) -> None:
        self.running = False
        self.progress.stop()
        self.progress.pack_forget()
        self.choose_button.configure(state="normal")
        self.settings_button.configure(state="normal")
        self.network_button.configure(state="normal")
        self.result = payload if isinstance(payload, analyzer.RunResult) else None
        if not self.result or not self.result.direct_marked_image:
            self._analysis_failed(analyzer.AnalyzerError("没有生成可预览的检查图片。"))
            return
        self.result_pane.show(self.result.direct_marked_image)
        self.open_image_button.configure(state="normal")
        self.open_folder_button.configure(state="normal")
        self.status_dot.configure(fg=GREEN)
        self.status_var.set(f"检查完成：{self.result.direct_marked_image.name}")

    def _analysis_failed(self, payload: object) -> None:
        self.running = False
        self.progress.stop()
        self.progress.pack_forget()
        self.choose_button.configure(state="normal")
        self.settings_button.configure(state="normal")
        self.network_button.configure(state="normal")
        self.status_dot.configure(fg="#c5221f")
        self.status_var.set("检查失败")
        messagebox.showerror(APP_TITLE, str(payload))

    def _open_result(self) -> None:
        if self.result and self.result.direct_marked_image and self.result.direct_marked_image.exists():
            os.startfile(self.result.direct_marked_image)  # type: ignore[attr-defined]

    def _open_folder(self) -> None:
        if self.result and self.result.output_root.exists():
            os.startfile(self.result.output_root)  # type: ignore[attr-defined]

    def _open_settings(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("密钥设置")
        dialog.geometry("520x230")
        dialog.resizable(False, False)
        dialog.configure(bg=SURFACE)
        dialog.transient(self.root)
        dialog.grab_set()
        tk.Label(
            dialog,
            text="OpenAI API 密钥",
            bg=SURFACE,
            fg=INK,
            font=("Microsoft YaHei UI", 13, "bold"),
        ).pack(anchor="w", padx=28, pady=(24, 6))
        current = "本机已有加密密钥" if analyzer.load_saved_api_key() else "本机尚未保存密钥"
        state_label = tk.Label(dialog, text=current, bg=SURFACE, fg=GREEN if analyzer.load_saved_api_key() else MUTED)
        state_label.pack(anchor="w", padx=28)
        entry = tk.Entry(dialog, show="*", relief="solid", bd=1, font=("Segoe UI", 10))
        entry.pack(fill="x", padx=28, pady=(16, 14), ipady=7)
        actions = tk.Frame(dialog, bg=SURFACE)
        actions.pack(fill="x", padx=28)

        def save() -> None:
            try:
                analyzer.save_api_key(entry.get().strip())
            except analyzer.AnalyzerError as exc:
                messagebox.showerror(APP_TITLE, str(exc), parent=dialog)
                return
            dialog.destroy()
            self.status_var.set("API 密钥已加密保存")
            self.status_dot.configure(fg=GREEN)

        def clear() -> None:
            if messagebox.askyesno(APP_TITLE, "确定清除本机保存的 API 密钥吗？", parent=dialog):
                analyzer.forget_saved_api_key()
                dialog.destroy()
                self.status_var.set("本机密钥已清除")
                self.status_dot.configure(fg=MUTED)

        self._button(actions, "保存", save, kind="primary").pack(side="left")
        self._button(actions, "清除已保存密钥", clear, kind="secondary").pack(side="left", padx=(10, 0))
        self._button(actions, "取消", dialog.destroy, kind="secondary").pack(side="right")


def main() -> int:
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    initial_path = None
    if len(sys.argv) > 1:
        candidate = Path(sys.argv[1].strip('"'))
        if candidate.is_file():
            initial_path = candidate
    AnalyzerWindow(root, initial_path)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
