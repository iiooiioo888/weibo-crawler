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

from weibo import Weibo, setup_logging, get_config
from session_manager import SessionManager, ScheduleManager

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

        # 初始化會話和排程管理器
        self.session_manager = SessionManager()
        self.schedule_manager = ScheduleManager(self.session_manager)

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
        self.log_message("開始測試連線...")

        # 確保配置正確
        if not self.config_vars["user_id_list"].get() or self.config_vars["user_id_list"].get() == "列表模式":
            self.log_message("錯誤: 未指定用戶ID列表文件")
            return

        try:
            config = get_config()
            wb = Weibo(config)
            wb._Weibo__validate_config(config)  # 測試配置驗證

            # 嘗試獲取第一個用戶資訊
            wb.user_config_list = wb.get_user_config_list(self.config_vars["user_id_list"].get())
            if wb.user_config_list:
                wb.user_config = wb.user_config_list[0]
                wb.initialize_info(wb.user_config)
                if wb.get_user_info() == 0:
                    self.log_message("連線測試成功！")
                    wb.print_user_info()
                else:
                    self.log_message("連線測試失敗: 無法獲取用戶資訊")
            else:
                self.log_message("連線測試失敗: 用戶列表為空")

        except Exception as e:
            self.log_message(f"連線測試失敗: {e}")

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
        from tkinter import simpledialog

        user_id = simpledialog.askstring("新增排程", "請輸入用戶ID:")
        if not user_id:
            return

        # 選擇時間類型
        time_types = ["daily", "weekly", "monthly"]
        schedule_type = self.select_time_type()
        if not schedule_type:
            return

        # 輸入時間
        if schedule_type == "daily":
            time_str = simpledialog.askstring("時間設定", "請輸入每日執行時間 (HH:MM):", initialvalue="09:00")
        elif schedule_type == "weekly":
            time_str = simpledialog.askstring("時間設定", "請輸入每週執行時間 (HH:MM):", initialvalue="09:00")
        elif schedule_type == "monthly":
            time_str = simpledialog.askstring("時間設定", "請輸入每月執行時間 (HH:MM):", initialvalue="09:00")

        if not time_str:
            return

        # 添加排程
        config = self.build_config_from_ui()
        if self.schedule_manager.add_schedule(user_id, time_str, schedule_type, config):
            self.log_message(f"排程已新增: {user_id} - {schedule_type} {time_str}")
            self.refresh_schedules()
        else:
            messagebox.showerror("錯誤", "新增排程失敗，請檢查參數")

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
