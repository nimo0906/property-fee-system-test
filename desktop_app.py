#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desktop launcher for the property management system."""

import argparse
import http.server
import os
import sys
from pathlib import Path
import threading
import webbrowser


from desktop_runtime import (
    APP_DIR_NAME, APP_TITLE, build_window_model, choose_desktop_port, find_free_port,
    format_runtime_status, get_app_data_dir, get_resource_dir, get_runtime_status,
    open_path, prepare_runtime, write_runtime_status_log, write_startup_error,
)


def create_server(port):
    os.environ["PM_PORT"] = str(port)
    from server import Handler, db_init
    from server.backups import ensure_startup_backups

    db_init()
    ensure_startup_backups()
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)


def run_server(port):
    prepare_runtime()
    server = create_server(port)
    url = f"http://127.0.0.1:{port}"
    print(f"{APP_TITLE} 已启动: {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在关闭...")
    finally:
        server.server_close()


def run_gui():
    import tkinter as tk
    from tkinter import messagebox

    data_dir, db_path, backup_dir = prepare_runtime()
    server = None
    thread = None
    port = choose_desktop_port()
    server = create_server(port)
    url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    model = build_window_model(url, data_dir, db_path, backup_dir)

    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("560x340")
    root.resizable(False, False)

    status = tk.StringVar(value=f"系统已启动: {url}")
    tk.Label(root, text=APP_TITLE, font=("Microsoft YaHei", 18, "bold")).pack(pady=(20, 6))
    tk.Label(root, textvariable=status, font=("Microsoft YaHei", 10)).pack(pady=3)
    tk.Label(root, text=model["service_status"], font=("Microsoft YaHei", 10), fg="#1f6b4a").pack(pady=3)
    tk.Label(root, text=model["hint"], wraplength=500, justify="center", fg="#555").pack(pady=3)
    tk.Label(root, text=f"数据目录: {data_dir}", wraplength=520, justify="left").pack(pady=3)
    tk.Label(root, text=f"数据库: {db_path.name}    备份: {backup_dir.name}", fg="#555").pack(pady=3)

    def show_diagnostics():
        current = get_runtime_status(data_dir=data_dir)
        runtime_log = write_runtime_status_log(current)
        messagebox.showinfo(APP_TITLE, format_runtime_status(current) + f"\n\n诊断已保存: {runtime_log}")

    def open_startup_log():
        log_path = Path(model["startup_log"])
        if not log_path.exists():
            log_path.write_text("No startup error has been recorded.\n", encoding="utf-8")
        open_file(log_path)

    def restart_service():
        nonlocal server, thread, port, url, model
        try:
            if server:
                server.shutdown()
                server.server_close()
            port = choose_desktop_port()
            server = create_server(port)
            url = f"http://127.0.0.1:{port}"
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            model = build_window_model(url, data_dir, db_path, backup_dir)
            status.set(f"系统已重新启动: {url}")
        except Exception as exc:
            log_path = write_startup_error(exc, data_dir)
            status.set(f"服务重启失败，错误日志: {log_path}")

    buttons = tk.Frame(root)
    buttons.pack(pady=14)
    tk.Button(buttons, text="打开系统", width=14, command=lambda: webbrowser.open(url)).grid(row=0, column=0, padx=6, pady=4)
    tk.Button(buttons, text="重新启动服务", width=14, command=restart_service).grid(row=0, column=1, padx=6, pady=4)
    tk.Button(buttons, text="打开数据目录", width=14, command=lambda: open_folder(data_dir)).grid(row=1, column=0, padx=6, pady=4)
    tk.Button(buttons, text="查看诊断信息", width=14, command=show_diagnostics).grid(row=1, column=1, padx=6, pady=4)
    tk.Button(buttons, text="打开错误日志", width=14, command=open_startup_log).grid(row=2, column=0, padx=6, pady=4)
    tk.Button(buttons, text="检查更新", width=14, command=lambda: webbrowser.open(url + "/system_update")).grid(row=2, column=1, padx=6, pady=4)

    def close_app():
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
        root.destroy()

    tk.Button(root, text="退出", width=12, command=close_app).pack(pady=(2, 8))
    root.protocol("WM_DELETE_WINDOW", close_app)
    webbrowser.open(url)
    root.mainloop()


def show_startup_error(log_path, exc):
    message = f"系统启动失败：{exc}\n\n错误日志：{log_path}"
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(APP_TITLE, message)
        root.destroy()
    except Exception:
        print(message, file=sys.stderr)


def open_file(path):
    open_path(path)


def open_folder(path):
    open_path(path)


def main():
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--serve-only", action="store_true", help="Run HTTP server without the desktop window")
    parser.add_argument("--port", type=int, default=None, help="Local HTTP port")
    parser.add_argument("--diagnose", action="store_true", help="Print runtime diagnostics and exit")
    args = parser.parse_args()
    try:
        if args.diagnose:
            print(format_runtime_status(get_runtime_status()))
            return
        if args.serve_only:
            run_server(args.port or choose_desktop_port())
        else:
            run_gui()
    except Exception as exc:
        log_path = write_startup_error(exc)
        show_startup_error(log_path, exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
