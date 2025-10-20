#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微博爬蟲圖形化介面
使用Tkinter建立美化優化的用戶界面
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, font
import json
import os
import sys
from pathlib import Path
import logging
import threading
import queue
import time
from datetime import datetime

from weibo import Weibo, setup_logging, get_config
from session_manager import SessionManager, ScheduleManager
from statistics_manager import StatisticsManager

# 圖表支持
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logging.warning("matplotlib未安裝，圖表功能將被禁用")

class WeiboCrawlerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("微博爬蟲 - Weibo Crawler")
        self.root.geometry("800x700")
        self.root.resizable(True, True)

        # 創建配置變數
        self.config_vars = {
            "user_id_list": tk.StringVar(),
            "since_date": tk.StringVar(value="1"),
            "only_crawl_original": tk.BooleanVar(value=True),
            "original_pic_download": tk.BooleanVar(value=True),
            "original_video_download": tk.BooleanVar(value=True),
            "write_csv": tk.BooleanVar(value=True),
            "write_json": tk.BooleanVar(value=False),
            "write_sqlite": tk.BooleanVar(value=True),
            "download_comment": tk.BooleanVar(value=False),
            "download_repost": tk.BooleanVar(value=False),
        }

        # 自動模式設定
        self.auto_start_var = tk.BooleanVar(value=False)
        self.countdown_var = tk.StringVar(value="")

        # 日誌隊列和狀態
        self.log_queue = queue.Queue()
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar(value="就緒")
        self.stats_var = tk.StringVar(value="等待開始...")
        self.is_running = False

        # 初始化管理器
        self.session_manager = SessionManager()
        self.schedule_manager = ScheduleManager(self.session_manager)
        self.stats_manager = StatisticsManager()

        # 設定字體和樣式
        self.setup_styles()
        self.root.configure(bg='#F8F9FA')

        # 創建界面
        self.create_widgets()

        # 設置日誌处理器
        self.setup_logging()

        # 載入現有配置
        self.load_config()

        # 檢查自動啟動
        self.check_auto_start()

        # 啟動排程服務
        self.schedule_manager.start_scheduler()
        self.start_scheduler_thread()

    def setup_styles(self):
        """設置字體和樣式"""
        style = ttk.Style()

        # 設定整體主題
        try:
            style.theme_use('clam')
        except:
            pass

        # 自定義樣式
        style.configure("Title.TLabel",
                       font=("Microsoft YaHei", 14, "bold"),
                       foreground="#2E86C1",
                       padding=(10, 10))

        style.configure("Status.TLabel",
                       font=("Microsoft YaHei", 10),
                       foreground="#28A745",
                       background="#F8F9FA")

        style.configure("Large.TButton",
                       font=("Microsoft YaHei", 10, "bold"),
                       padding=(15, 10))

        style.configure("Normal.TButton",
                       font=("Microsoft YaHei", 9),
                       padding=(8, 4))

        # 進度條樣式
        style.configure("TProgressbar",
                       troughcolor='#E9ECEF',
                       borderwidth=2,
                       lightcolor='#4A90E2',
                       darkcolor='#4A90E2')

    def create_widgets(self):
        """創建所有UI組件"""
        # 歡迎標題
        title_label = ttk.Label(self.root,
                               text="微博爬蟲工具",
                               style="Title.TLabel")
        title_label.pack(pady=(10, 0))

        # 狀態欄
        status_frame = ttk.Frame(self.root, relief="sunken", borderwidth=1)
        status_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(status_frame, text="狀態:", style="Status.TLabel").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Label(status_frame, textvariable=self.status_var).grid(row=0, column=1, sticky="w", padx=10)
        ttk.Label(status_frame, textvariable=self.stats_var).grid(row=0, column=2, sticky="e", padx=10)

        # 進度條
        self.progress_bar = ttk.Progressbar(self.root,
                                           orient="horizontal",
                                           length=400,
                                           mode="determinate",
                                           variable=self.progress_var)
        self.progress_bar.pack(fill=tk.X, padx=10, pady=(0, 10))

        # 創建notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 配置頁面
        self.create_config_tab()

        # 排程管理頁面
        self.create_schedule_tab()

        # 統計儀表板
        self.create_statistics_tab()

        # 日誌頁面
        self.create_log_tab()

        # 底部按鈕
        self.create_bottom_buttons()

    def create_config_tab(self):
        """創建配置設定頁面"""
        config_frame = ttk.Frame(self.notebook)
        self.notebook.add(config_frame, text="配置設定")

        # 主要設定區塊
        main_settings = ttk.LabelFrame(config_frame, text="主要設定", padding=10)
        main_settings.pack(fill=tk.X, padx=5, pady=5)

        # 用戶ID列表
        ttk.Label(main_settings, text="用戶ID列表文件:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        user_id_frame = ttk.Frame(main_settings)
        user_id_frame.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        self.user_id_entry = ttk.Entry(user_id_frame, textvariable=self.config_vars["user_id_list"])
        self.user_id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(user_id_frame, text="選擇文件", command=self.select_user_file).pack(side=tk.RIGHT)

        # 日期範圍
        ttk.Label(main_settings, text="爬取天數:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(main_settings, textvariable=self.config_vars["since_date"]).grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        # 內容類型
        type_frame = ttk.LabelFrame(config_frame, text="內容類型", padding=10)
        type_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Checkbutton(type_frame, text="只爬取原創微博",
                        variable=self.config_vars["only_crawl_original"]).grid(row=0, column=0, sticky="w", padx=5, pady=2)

        # 下載選項
        download_frame = ttk.LabelFrame(config_frame, text="下載選項", padding=10)
        download_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Checkbutton(download_frame, text="下載原創圖片",
                        variable=self.config_vars["original_pic_download"]).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Checkbutton(download_frame, text="下載原創視頻",
                        variable=self.config_vars["original_video_download"]).grid(row=0, column=1, sticky="w", padx=5, pady=2)

        # 輸出格式
        output_frame = ttk.LabelFrame(config_frame, text="輸出格式", padding=10)
        output_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Checkbutton(output_frame, text="CSV格式",
                       variable=self.config_vars["write_csv"]).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Checkbutton(output_frame, text="JSON格式",
                       variable=self.config_vars["write_json"]).grid(row=0, column=1, sticky="w", padx=5, pady=2)
        ttk.Checkbutton(output_frame, text="SQLite資料庫",
                       variable=self.config_vars["write_sqlite"]).grid(row=0, column=2, sticky="w", padx=5, pady=2)

        # 進階選項
        advanced_frame = ttk.LabelFrame(config_frame, text="進階選項", padding=10)
        advanced_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Checkbutton(advanced_frame, text="下載評論",
                       variable=self.config_vars["download_comment"]).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Checkbutton(advanced_frame, text="下載轉發",
                       variable=self.config_vars["download_repost"]).grid(row=0, column=1, sticky="w", padx=5, pady=2)

        # 配置操作按鈕
        btn_frame = ttk.Frame(config_frame)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="載入配置", command=self.load_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="儲存配置", command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="測試連線", command=self.test_connection).pack(side=tk.LEFT, padx=5)

        # 配置欄位
        main_settings.columnconfigure(1, weight=1)
        type_frame.columnconfigure(1, weight=1)
        download_frame.columnconfigure(2, weight=1)
        output_frame.columnconfigure(3, weight=1)

    def create_log_tab(self):
        """創建日誌顯示頁面"""
        log_frame = ttk.Frame(self.notebook)
        self.notebook.add(log_frame, text="運行日誌")

        # 創建滾動文字區域
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=25)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 日誌操作按鈕
        log_btn_frame = ttk.Frame(log_frame)
        log_btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(log_btn_frame, text="清空日誌", command=self.clear_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(log_btn_frame, text="儲存日誌", command=self.save_log).pack(side=tk.RIGHT, padx=5)

    def create_bottom_buttons(self):
        """創建底部操作按鈕"""
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame, text="開始爬取", command=self.start_crawling).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="停止爬取", command=self.stop_crawling, state=tk.DISABLED).pack(side=tk.RIGHT, padx=5)

    def select_user_file(self):
        """選擇用戶ID列表文件"""
        filename = filedialog.askopenfilename(
            title="選擇用戶ID列表文件",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            self.config_vars["user_id_list"].set(filename)

    def load_config(self):
        """載入現有配置"""
        try:
            config = get_config()
            for key, var in self.config_vars.items():
                if key == "user_id_list":
                    if isinstance(config.get(key), list):
                        var.set("列表模式")
                    else:
                        var.set(config.get(key, ""))
                elif key.startswith("write_"):
                    formats = config.get("write_mode", [])
                    format_name = key.replace("write_", "")
                    var.set(format_name in formats)
                elif key in config:
                    var.set(config[key])

            messagebox.showinfo("成功", "配置載入完成")
        except Exception as e:
            self.log_message(f"載入配置失敗: {e}")

    def save_config(self):
        """儲存配置到文件"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            config = get_config()

            # 更新配置
            for key, var in self.config_vars.items():
                if key == "user_id_list":
                    value = var.get()
                    if value != "列表模式":
                        config[key] = value
                elif key.startswith("write_"):
                    format_name = key.replace("write_", "")
                    if var.get():
                        if format_name not in config.get("write_mode", []):
                            config.setdefault("write_mode", []).append(format_name)
                    else:
                        if format_name in config.get("write_mode", []):
                            config["write_mode"].remove(format_name)
                else:
                    config[key] = var.get()

            # 寫入文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)

            # 保存會話（但不啟用自動啟動）
            if any(self.config_vars[key].get() for key in self.config_vars.keys()):
                session_config = self.build_config_from_ui()
                self.session_manager.save_session(
                    config=session_config,
                    auto_start_enabled=self.auto_start_var.get()
                )

            messagebox.showinfo("成功", "配置儲存完成")
        except Exception as e:
            self.log_message(f"儲存配置失敗: {e}")

    def test_connection(self):
        """測試連線"""
        self.log_message("Testing connection...")

        # 確保配置正確
        user_list_file = self.config_vars["user_id_list"].get()
        if not user_list_file or user_list_file == "列表模式":
            self.log_message("Error: No user ID list file specified")
            messagebox.showwarning("Warning", "Please specify a user ID list file first")
            return

        try:
            config = get_config()

            # 使用當前UI配置而不是檔案中的配置
            ui_config = self.build_config_from_ui()
            config.update(ui_config)

            wb = Weibo(config)
            wb._Weibo__validate_config(config)  # 測試配置驗證

            # 嘗試獲取第一個用戶資訊
            wb.user_config_list = wb.get_user_config_list(user_list_file)
            if wb.user_config_list:
                wb.user_config = wb.user_config_list[0]
                wb.initialize_info(wb.user_config)
                if wb.get_user_info() == 0:
                    self.log_message("Connection test successful!")
                    wb.print_user_info()
                    messagebox.showinfo("Success", "Connection test passed!")
                else:
                    self.log_message("Connection test failed: Unable to get user info")
                    messagebox.showwarning("Warning", "Connection test failed: Unable to get user info")
            else:
                self.log_message("Connection test failed: User list is empty")
                messagebox.showwarning("Warning", "Connection test failed: User list is empty")

        except Exception as e:
            self.log_message(f"Connection test failed: {e}")
            messagebox.showerror("Error", f"Connection test failed: {e}")

    def start_crawling(self):
        """開始爬取"""
        if messagebox.askyesno("確認", "確定要開始爬取微博嗎？\n這可能需要較長時間。"):
            self.log_message("開始爬取微博...")
            self.is_running = True
            # 在新線程中運行
            self.crawler_thread = threading.Thread(target=self._run_crawler)
            self.crawler_thread.daemon = True
            self.crawler_thread.start()

    def _run_crawler(self):
        """在新線程中運行爬蟲"""
        try:
            config = get_config()
            wb = Weibo(config)
            wb.start()
            self.log_message("爬取完成！")
        except Exception as e:
            self.log_message(f"爬取過程中發生錯誤: {e}")
        finally:
            self.is_running = False

    def stop_crawling(self):
        """停止爬取"""
        self.is_running = False
        self.log_message("正在停止爬取...")

    def setup_logging(self):
        """設置日誌處理器"""
        class GUILogHandler(logging.Handler):
            def __init__(self, gui):
                super().__init__()
                self.gui = gui

            def emit(self, record):
                msg = self.format(record)
                self.gui.log_queue.put(msg)

        # 創建GUI日誌處理器
        gui_handler = GUILogHandler(self)
        gui_handler.setLevel(logging.INFO)
        gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        # 獲取應用程序日誌器並添加處理器
        logger = logging.getLogger('weibo')
        logger.addHandler(gui_handler)

        # 開始日誌監視線程
        self.log_monitor_thread = threading.Thread(target=self._monitor_log_queue, daemon=True)
        self.log_monitor_thread.start()

    def _monitor_log_queue(self):
        """監視日誌隊列並更新UI"""
        while True:
            try:
                while not self.log_queue.empty():
                    msg = self.log_queue.get_nowait()
                    self.log_text.insert(tk.END, msg + '\n')
                    self.log_text.see(tk.END)
            except Exception:
                pass
            # 小延遲避免CPU過載
            import time
            time.sleep(0.1)

    def log_message(self, msg):
        """記錄訊息到日誌"""
        logger = logging.getLogger('weibo')
        logger.info(msg)

    def clear_log(self):
        """清空日誌"""
        self.log_text.delete(1.0, tk.END)

    def save_log(self):
        """儲存日誌到文件"""
        filename = filedialog.asksaveasfilename(
            title="儲存日誌",
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.log_text.get(1.0, tk.END))

    def check_auto_start(self):
        """檢查自動啟動"""
        auto_config = self.session_manager.check_auto_start()
        if auto_config:
            self.log_message("發現自動啟動配置，3秒後自動開始...")
            self.status_var.set("準備自動啟動")

            # 顯示倒計時
            self.countdown_var.set("3秒後自動開始...")
            self.root.after(1000, lambda: self.countdown_var.set("2秒後自動開始..."))
            self.root.after(2000, lambda: self.countdown_var.set("1秒後自動開始..."))
            self.root.after(3000, self.perform_auto_start)
        else:
            self.log_message("就緒，等待手動操作")

    def perform_auto_start(self):
        """執行自動啟動"""
        self.log_message("執行自動啟動...")
        self.start_crawling()

    def start_scheduler_thread(self):
        """啟動排程監視線程"""
        def run_scheduler():
            while not self.is_running:
                self.schedule_manager.run_pending()
                time.sleep(1)

        self.scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()
        self.log_message("排程服務已啟動")

    def create_schedule_tab(self):
        """創建排程管理頁面"""
        schedule_frame = ttk.Frame(self.notebook)
        self.notebook.add(schedule_frame, text="排程管理")

        # 自動模式設定
        auto_frame = ttk.LabelFrame(schedule_frame, text="自動模式設定", padding=10)
        auto_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Checkbutton(auto_frame, text="啟動時自動執行最後的配置",
                       variable=self.auto_start_var, command=self.toggle_auto_start).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(auto_frame, textvariable=self.countdown_var).grid(row=0, column=1, sticky="w", padx=5, pady=2)

        # 排程列表
        list_frame = ttk.LabelFrame(schedule_frame, text="排程任務列表", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 創建表格
        columns = ("ID", "用戶", "時間", "類型", "狀態", "最後執行")
        self.schedule_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)

        # 設定欄位標題
        for col in columns:
            self.schedule_tree.heading(col, text=col)
            self.schedule_tree.column(col, width=80, anchor="center")

        # 添加滾動條
        v_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.schedule_tree.yview)
        self.schedule_tree.configure(yscrollcommand=v_scrollbar.set)

        self.schedule_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 排程操作按鈕
        btn_frame = ttk.Frame(schedule_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="新增排程", command=self.add_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="編輯排程", command=self.edit_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刪除排程", command=self.delete_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="重新載入", command=self.refresh_schedules).pack(side=tk.RIGHT, padx=5)

        # 載入排程列表
        self.refresh_schedules()

    def toggle_auto_start(self):
        """切換自動啟動"""
        enabled = self.auto_start_var.get()
        if enabled:
            # 保存會話
            config = self.build_config_from_ui()
            self.session_manager.save_session(
                config=config,
                auto_start_enabled=True
            )
            self.log_message("自動啟動已啟用")
        else:
            # 停用自動啟動
            self.session_manager.save_session(
                config={},
                auto_start_enabled=False
            )
            self.log_message("自動啟動已停用")

    def add_schedule(self):
        """新增排程"""
        # 選擇用戶
        user_id, user_name = self.select_user_from_list()
        if not user_id:
            return

        # 選擇時間類型
        schedule_type = self.select_schedule_type()
        if not schedule_type:
            return

        # 輸入時間
        time_str = self.select_schedule_time(schedule_type)
        if not time_str:
            return

        # 添加排程
        config = self.build_config_from_ui()
        if self.schedule_manager.add_schedule(user_id, time_str, schedule_type, config):
            self.log_message(f"Schedule added: {user_name}({user_id}) - {schedule_type} {time_str}")
            self.refresh_schedules()
        else:
            messagebox.showerror("Error", "Failed to add schedule, please check parameters")

    def select_time_type(self):
        """選擇時間類型"""
        from tkinter import simpledialog
        types = ["daily", "weekly", "monthly"]
        type_str = simpledialog.askstring("選擇類型",
                                         "請選擇排程類型:\n1. daily - 每日\n2. weekly - 每週\n3. monthly - 每月",
                                         initialvalue="daily")
        return type_str if type_str in types else None

    def edit_schedule(self):
        """編輯排程"""
        selected = self.schedule_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "請先選擇要編輯的排程")
            return

        item = selected[0]
        schedule_id = self.schedule_tree.item(item, "values")[0]

        # 這裡可以實現編輯功能，簡化處理就重新載入列表
        self.log_message(f"編輯功能暫未實作 (排程ID: {schedule_id})")

    def delete_schedule(self):
        """刪除排程"""
        selected = self.schedule_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "請先選擇要刪除的排程")
            return

        item = selected[0]
        values = self.schedule_tree.item(item, "values")
        schedule_id = values[0]

        if self.schedule_manager.remove_schedule(schedule_id):
            self.log_message(f"排程已刪除: ID {schedule_id}")
            self.refresh_schedules()
        else:
            messagebox.showerror("錯誤", "刪除排程失敗")

    def refresh_schedules(self):
        """重新載入排程列表"""
        # 清空樹狀圖
        for item in self.schedule_tree.get_children():
            self.schedule_tree.delete(item)

        # 載入排程
        schedules = self.schedule_manager.get_schedules()
        for s in schedules:
            status = "啟用" if s.get("enabled", True) else "停用"
            last_run = s.get("last_run", "從未")
            if last_run != "從未":
                last_run = last_run[:19]  # 簡化時間顯示

            self.schedule_tree.insert("", tk.END, values=(
                s["id"],
                s["user_id"],
                s["schedule_time"],
                s["schedule_type"],
                status,
                last_run
            ))

        self.log_message(f"已載入 {len(schedules)} 個排程任務")

    def create_statistics_tab(self):
        """創建統計儀表板頁面"""
        stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(stats_frame, text="Statistics Dashboard")

        # 統計總覽區域
        summary_frame = ttk.LabelFrame(stats_frame, text="Statistics Overview", padding=10)
        summary_frame.pack(fill=tk.X, padx=5, pady=5)

        # 總結統計顯示
        self.summary_labels = {}
        summary_stats = [
            ("Total Sessions", "total_sessions"),
            ("Total Weibo Posts", "total_weibos"),
            ("Total Images", "total_images"),
            ("Total Videos", "total_videos"),
            ("Avg Efficiency", "avg_efficiency"),
            ("Unique Users", "unique_users")
        ]

        for i, (label_text, key) in enumerate(summary_stats):
            row = i // 3
            col = (i % 3) * 2
            ttk.Label(summary_frame, text=f"{label_text}:").grid(row=row, column=col, sticky="e", padx=5, pady=2)
            self.summary_labels[key] = ttk.Label(summary_frame, text="0", font=("Microsoft YaHei", 10, "bold"))
            self.summary_labels[key].grid(row=row, column=col+1, sticky="w", padx=5, pady=2)

        # 圖表區域
        chart_frame = ttk.LabelFrame(stats_frame, text="Data Charts", padding=10)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 圖表控制按鈕
        chart_controls = ttk.Frame(chart_frame)
        chart_controls.pack(fill=tk.X, pady=(0, 10))

        self.chart_type_var = tk.StringVar(value="daily_trend")
        chart_types = [
            ("Daily Trend", "daily_trend"),
            ("User Stats", "user_stats"),
            ("Performance", "performance")
        ]

        for text, value in chart_types:
            ttk.Radiobutton(chart_controls, text=text, variable=self.chart_type_var,
                          value=value, command=self.update_chart).pack(side=tk.LEFT, padx=10)

        # 圖表顯示區域
        if MATPLOTLIB_AVAILABLE:
            self.figure = Figure(figsize=(8, 5), dpi=100, facecolor='#F8F9FA')
            self.canvas_frame = ttk.Frame(chart_frame)
            self.canvas_frame.pack(fill=tk.BOTH, expand=True)
            self.canvas = FigureCanvasTkAgg(self.figure, master=self.canvas_frame)
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            # 創建初始圖表
            self.update_chart()
        else:
            ttk.Label(chart_frame, text="圖表功能未啟用：matplotlib 未安裝",
                     foreground="red").pack(expand=True)

        # 最新會話顯示
        sessions_frame = ttk.LabelFrame(stats_frame, text="Recent Sessions", padding=10)
        sessions_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 創建會話表格
        columns = ("Start Time", "User", "Status", "Weibos", "Images", "Efficiency")
        self.sessions_tree = ttk.Treeview(sessions_frame, columns=columns, show="headings", height=6)

        # 設定欄位標題
        column_widths = [140, 100, 80, 80, 80, 80]
        for col, width in zip(columns, column_widths):
            self.sessions_tree.heading(col, text=col)
            self.sessions_tree.column(col, width=width, anchor="center")

        # 添加滾動條
        v_scrollbar = ttk.Scrollbar(sessions_frame, orient="vertical", command=self.sessions_tree.yview)
        self.sessions_tree.configure(yscrollcommand=v_scrollbar.set)

        self.sessions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 統計操作按鈕
        stats_btn_frame = ttk.Frame(stats_frame)
        stats_btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(stats_btn_frame, text="Refresh Stats", command=self.refresh_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(stats_btn_frame, text="Clean Old Data", command=self.cleanup_old_data).pack(side=tk.RIGHT, padx=5)

        # 載入初始統計數據
        self.refresh_statistics()

    def update_chart(self):
        """更新圖表顯示"""
        if not MATPLOTLIB_AVAILABLE:
            return

        chart_type = self.chart_type_var.get()
        self.figure.clear()

        try:
            if chart_type == "daily_trend":
                self._create_daily_trend_chart()
            elif chart_type == "user_stats":
                self._create_user_stats_chart()
            elif chart_type == "performance":
                self._create_performance_chart()

            self.canvas.draw()
        except Exception as e:
            self.log_message(f"圖表更新失敗: {e}")

    def _create_daily_trend_chart(self):
        """創建每日趨勢圖表"""
        data = self.stats_manager.get_daily_chart_data()

        if not data:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "無數據可顯示", transform=ax.transAxes, ha="center", va="center",
                   fontsize=14, color="gray")
            ax.set_title("每日爬取趨勢", fontsize=12, fontweight='bold')
            return

        ax1 = self.figure.add_subplot(111)

        # 提取數據
        dates = [row[0] for row in data]
        weibo_counts = [row[2] for row in data]
        efficiency = [row[5] for row in data]

        # 繪製雙軸圖
        bars = ax1.bar(dates, weibo_counts, alpha=0.7, color='#4A90E2', label='微博數')
        ax1.set_ylabel('微博數', color='#4A90E2')
        ax1.tick_params(axis='y', labelcolor='#4A90E2')

        ax2 = ax1.twinx()
        line = ax2.plot(dates, efficiency, 'r-', linewidth=2, marker='o', label='效率')
        ax2.set_ylabel('效率 (微博/分鐘)', color='red')
        ax2.tick_params(axis='y', labelcolor='red')

        # 設置標題和格式
        ax1.set_title("每日爬取統計", fontsize=12, fontweight='bold')
        ax1.set_xlabel("日期")

        # 旋轉x軸標籤
        plt.setp(ax1.get_xticklabels(), rotation=45, ha='right')

        # 添加圖例
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    def _create_user_stats_chart(self):
        """創建用戶統計圖表"""
        data = self.stats_manager.get_user_chart_data()

        if not data:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "無數據可顯示", transform=ax.transAxes, ha="center", va="center",
                   fontsize=14, color="gray")
            ax.set_title("用戶統計", fontsize=12, fontweight='bold')
            return

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 4))

        # 提取前10個用戶的數據
        users = [row[0][:8] + "..." if len(row[0]) > 8 else row[0] for row in data[:10]]
        weibo_counts = [row[1] for row in data[:10]]
        success_rates = [row[3] * 100 for row in data[:10]]

        # 微博數量柱狀圖
        bars = ax1.bar(range(len(users)), weibo_counts, color='#28A745', alpha=0.7)
        ax1.set_title("用戶微博數量")
        ax1.set_xticks(range(len(users)))
        ax1.set_xticklabels(users, rotation=45, ha='right')
        ax1.set_ylabel("微博數")

        # 添加數值標籤
        for bar, count in zip(bars, weibo_counts):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{count}', ha='center', va='bottom', fontsize=8)

        # 成功率圓餅圖
        success_data = sum(success_rates) / len(success_rates)
        fail_data = 100 - success_data

        ax2.pie([success_data, fail_data], labels=['成功', '失敗'],
               autopct='%1.1f%%', colors=['#28A745', '#DC3545'], startangle=90)
        ax2.set_title("平均成功率")

        plt.tight_layout()
        plt.figure(self.figure.number)  # 確保我們在正確的figure上工作
        self.figure.clear()
        self.figure = fig

    def _create_performance_chart(self):
        """創建效能指標圖表"""
        data = self.stats_manager.get_performance_metrics()

        if not data:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "無數據可顯示", transform=ax.transAxes, ha="center", va="center",
                   fontsize=14, color="gray")
            ax.set_title("效能指標", fontsize=12, fontweight='bold')
            return

        ax1 = self.figure.add_subplot(111)

        # 提取數據
        timestamps = [row[0][:19] for row in data]  # 簡化時間顯示
        memory_usage = [row[1] or 0 for row in data]
        network_speed = [row[2] or 0 for row in data]
        cpu_usage = [row[3] or 0 for row in data]

        # 繪製多線圖
        ax1.plot(timestamps, memory_usage, 'b-', linewidth=1.5, marker='o', markersize=3, label='記憶體使用量 (MB)')
        ax1.plot(timestamps, network_speed, 'g-', linewidth=1.5, marker='s', markersize=3, label='網路速度 (KB/s)')
        ax1.plot(timestamps, cpu_usage, 'r-', linewidth=1.5, marker='^', markersize=3, label='CPU使用率 (%)')

        ax1.set_title("效能指標趨勢", fontsize=12, fontweight='bold')
        ax1.set_xlabel("時間")
        ax1.set_ylabel("數值")
        ax1.legend(loc='upper right')

        # 旋轉x軸標籤
        plt.setp(ax1.get_xticklabels(), rotation=45, ha='right')

        # 設置網格
        ax1.grid(True, alpha=0.3)

    def refresh_statistics(self):
        """刷新統計數據顯示"""
        try:
            # 獲取總結統計
            summary_stats = self.stats_manager.get_summary_stats()

            if summary_stats:
                self.summary_labels['total_sessions'].config(text=str(summary_stats['total_sessions']))
                self.summary_labels['total_weibos'].config(text=str(summary_stats['total_weibos']))
                self.summary_labels['total_images'].config(text=str(summary_stats['total_images']))
                self.summary_labels['total_videos'].config(text=str(summary_stats['total_videos']))

                avg_eff = summary_stats['avg_efficiency']
                self.summary_labels['avg_efficiency'].config(
                    text=".1f" if avg_eff else "0")

                self.summary_labels['unique_users'].config(text=str(summary_stats['unique_users']))

            # 刷新會話列表
            self._refresh_sessions_tree()

            # 刷新圖表
            self.update_chart()

        except Exception as e:
            self.log_message(f"刷新統計失敗: {e}")

    def _refresh_sessions_tree(self):
        """刷新會話樹狀圖"""
        # 清空樹狀圖
        for item in self.sessions_tree.get_children():
            self.sessions_tree.delete(item)

        # 載入最近會話
        sessions = self.stats_manager.get_recent_sessions(limit=20)

        for session in sessions:
            # 格式化顯示
            start_time = session['start_time'][:19] if session['start_time'] else "未知"
            user_id = session['user_id'][:10] if session['user_id'] else "未知"
            status = session['status'] or "未知"
            weibo_count = str(session['total_weibos'])
            image_count = str(session['image_count'])
            efficiency = ".1f" if session['efficiency'] else "0"

            self.sessions_tree.insert("", tk.END, values=(
                start_time, user_id, status, weibo_count, image_count, efficiency
            ))

    def cleanup_old_data(self):
        """清理舊數據"""
        if messagebox.askyesno("確認", "確定要清理一年以前的舊數據嗎？\n此操作無法撤銷。"):
            try:
                deleted_count = self.stats_manager.cleanup_old_data()
                messagebox.showinfo("完成", f"已清理 {deleted_count} 條舊數據記錄")
                self.refresh_statistics()
            except Exception as e:
                messagebox.showerror("錯誤", f"清理失敗: {e}")

    def select_user_from_list(self):
        """從用戶ID列表文件中選擇用戶"""
        user_list_file = self.config_vars["user_id_list"].get()

        if not user_list_file or not os.path.exists(user_list_file):
            user_list_file = os.path.join(os.path.dirname(__file__), "user_id_list.txt")
            if not os.path.exists(user_list_file):
                messagebox.showwarning("Warning", "No user ID list file found. Please specify one in config settings.")
                return None, None

        # 讀取用戶列表
        users = []
        try:
            with open(user_list_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        parts = line.split()
                        if len(parts) >= 2 and parts[0].isdigit():
                            user_id = parts[0]
                            user_name = ' '.join(parts[1:])
                            users.append((user_id, user_name))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read user list: {e}")
            return None, None

        if not users:
            messagebox.showwarning("Warning", "User list is empty.")
            return None, None

        # 創建用戶選擇對話框
        dialog = tk.Toplevel(self.root)
        dialog.title("Select User")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        # 用戶列表
        listbox = tk.Listbox(dialog, height=10)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        for user_id, user_name in users:
            listbox.insert(tk.END, "2")

        # 按鈕
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        selected_user = [None, None]

        def on_select():
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                selected_user[0], selected_user[1] = users[index]
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        ttk.Button(btn_frame, text="Select", command=on_select).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side=tk.RIGHT, padx=5)

        # 等待對話框關閉
        self.root.wait_window(dialog)

        return selected_user[0], selected_user[1]

    def select_schedule_type(self):
        """選擇排程類型"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Schedule Type")
        dialog.geometry("300x200")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Choose schedule type:", font=("Arial", 10, "bold")).pack(pady=10)

        selected_type = [None]

        def select_daily():
            selected_type[0] = "daily"
            dialog.destroy()

        def select_weekly():
            selected_type[0] = "weekly"
            dialog.destroy()

        def select_monthly():
            selected_type[0] = "monthly"
            dialog.destroy()

        ttk.Button(dialog, text="Daily\n(Every day)", command=select_daily, width=15).pack(pady=5)
        ttk.Button(dialog, text="Weekly\n(Every Monday)", command=select_weekly, width=15).pack(pady=5)
        ttk.Button(dialog, text="Monthly\n(First day)", command=select_monthly, width=15).pack(pady=5)

        self.root.wait_window(dialog)
        return selected_type[0]

    def select_schedule_time(self, schedule_type):
        """選擇排程時間"""
        if schedule_type == "daily":
            prompt = "Enter daily execution time (HH:MM):"
            initial = "09:00"
        elif schedule_type == "weekly":
            prompt = "Enter weekly execution time (HH:MM):"
            initial = "09:00"
        elif schedule_type == "monthly":
            prompt = "Enter monthly execution time (HH:MM):"
            initial = "09:00"

        from tkinter import simpledialog
        time_str = simpledialog.askstring("Schedule Time", prompt, initialvalue=initial)
        return time_str

    def build_config_from_ui(self):
        """從UI建立配置字典"""
        config = {}
        for key, var in self.config_vars.items():
            if key == "user_id_list":
                value = var.get()
                config[key] = value
            elif key.startswith("write_"):
                # 不處理，稍後重新建立
                pass
            else:
                config[key] = var.get()

        # 重新建立write_mode
        write_modes = []
        if self.config_vars["write_csv"].get():
            write_modes.append("csv")
        if self.config_vars["write_json"].get():
            write_modes.append("json")
        if self.config_vars["write_sqlite"].get():
            write_modes.append("sqlite")
        config["write_mode"] = write_modes

        return config

    def update_session_after_run(self):
        """執行後更新會話"""
        config = self.build_config_from_ui()
        user_id = None

        # 嘗試從配置中獲取用戶ID
        user_list_file = config.get("user_id_list")
        if user_list_file and os.path.exists(user_list_file):
            try:
                with open(user_list_file, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    if first_line.isdigit():
                        user_id = first_line
            except:
                pass

        self.session_manager.update_session_after_run(user_id)

def main():
    # 確保能正常運行GUI
    import sys
    import os

    # 設定環境
    if hasattr(sys, '_MEIPASS'):
        # 如果是打包後執行
        os.chdir(sys._MEIPASS)

    root = tk.Tk()
    app = WeiboCrawlerGUI(root)

    # 設置關閉事件
    root.protocol("WM_DELETE_WINDOW", lambda: (setattr(app, 'is_running', False), root.destroy()))

    root.mainloop()

if __name__ == "__main__":
    main()
