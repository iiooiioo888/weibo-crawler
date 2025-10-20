#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
會話管理模組
負責記憶用戶配置和自動執行的邏輯
"""

import json
import os
import threading
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

class SessionManager:
    def __init__(self, config_path="config.json", session_file="last_session.json"):
        self.config_path = config_path
        self.session_file = session_file
        self.logger = logging.getLogger('weibo')
        self.running_schedules = set()  # 正在運行的排程任務

    def save_session(self, config, auto_start_enabled=False, last_run=None):
        """儲存會話信息"""
        session_data = {
            "config": config,
            "auto_start_enabled": auto_start_enabled,
            "saved_at": datetime.now().isoformat(),
            "last_run": last_run.isoformat() if last_run else None
        }

        try:
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            self.logger.info("會話信息已儲存")
        except Exception as e:
            self.logger.error(f"儲存會話失敗: {e}")

    def load_session(self):
        """載入會話信息"""
        if not os.path.exists(self.session_file):
            return None

        try:
            with open(self.session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            self.logger.info("會話信息已載入")
            return session_data
        except Exception as e:
            self.logger.error(f"載入會話失敗: {e}")
            return None

    def check_auto_start(self):
        """檢查是否應該自動啟動"""
        session = self.load_session()
        if not session:
            return None

        if not session.get("auto_start_enabled", False):
            return None

        # 檢查上次執行時間，避免過於頻繁
        last_run_str = session.get("last_run")
        if last_run_str:
            last_run = datetime.fromisoformat(last_run_str)
            time_since_last = datetime.now() - last_run
            # 如果一小時內已經執行過，跳過自動啟動
            if time_since_last < timedelta(hours=1):
                self.logger.info("一小時內已執行過，跳過自動啟動")
                return None

        return session.get("config")

    def is_user_available(self, user_id):
        """檢查用戶ID是否有效"""
        # 簡單的檢查邏輯，可以根據需要擴充
        if not user_id or not str(user_id).isdigit():
            return False

        # 檢查長度（微博用戶ID通常為8-10位）
        user_id_str = str(user_id)
        if len(user_id_str) < 8 or len(user_id_str) > 11:
            return False

        return True

    def update_session_after_run(self, user_id=None):
        """更新會話，記錄執行時間"""
        session = self.load_session()
        if session:
            config = session.get("config", {})
            if user_id:
                config["last_user"] = user_id
            self.save_session(
                config=config,
                auto_start_enabled=session.get("auto_start_enabled", False),
                last_run=datetime.now()
            )

class ScheduleManager:
    def __init__(self, session_manager):
        self.session_manager = session_manager
        self.logger = logging.getLogger('weibo')
        self.schedules_file = "schedules.json"
        self.schedules = []
        self.load_schedules()

        try:
            import schedule
            self.schedule = schedule
        except ImportError:
            self.schedule = None
            self.logger.error("schedule模組未安裝，排程功能無法使用")

    def load_schedules(self):
        """載入排程配置"""
        if not os.path.exists(self.schedules_file):
            self.schedules = []
            return

        try:
            with open(self.schedules_file, 'r', encoding='utf-8') as f:
                self.schedules = json.load(f)
            self.logger.info(f"已載入 {len(self.schedules)} 個排程任務")
        except Exception as e:
            self.logger.error(f"載入排程配置失敗: {e}")
            self.schedules = []

    def save_schedules(self):
        """儲存排程配置"""
        try:
            with open(self.schedules_file, 'w', encoding='utf-8') as f:
                json.dump(self.schedules, f, ensure_ascii=False, indent=2)
            self.logger.info("排程配置已儲存")
        except Exception as e:
            self.logger.error(f"儲存排程配置失敗: {e}")

    def add_schedule(self, user_id, schedule_time, schedule_type="daily", config=None):
        """新增排程任務"""
        if not self.validate_schedule(schedule_time, schedule_type):
            return False

        schedule_entry = {
            "id": str(int(time.time() * 1000)),  # 使用時間戳作為唯一ID
            "user_id": user_id,
            "schedule_time": schedule_time,
            "schedule_type": schedule_type,  # daily, weekly, monthly, cron
            "config": config or {},
            "enabled": True,
            "last_run": None,
            "created_at": datetime.now().isoformat()
        }

        self.schedules.append(schedule_entry)
        self.save_schedules()

        # 如果是啟用的排程，立即應用
        if schedule_entry["enabled"]:
            self.schedule_job(schedule_entry)

        self.logger.info(f"排程任務已新增: {user_id} - {schedule_type} {schedule_time}")
        return True

    def validate_schedule(self, schedule_time, schedule_type):
        """驗證排程時間格式"""
        try:
            if schedule_type == "cron":
                # Cron語法驗證 (簡化版)
                return len(schedule_time.split()) >= 5
            elif schedule_type in ["daily", "weekly", "monthly"]:
                # HH:MM 格式
                datetime.strptime(schedule_time, "%H:%M")
                return True
            return False
        except ValueError:
            return False

    def schedule_job(self, schedule_entry):
        """為排程任務設定定時器"""
        if not self.schedule:
            return

        job_id = f"{schedule_entry['id']}_{schedule_entry['user_id']}"
        schedule_time = schedule_entry["schedule_time"]
        schedule_type = schedule_entry["schedule_type"]

        # 移除現有的相同任務
        if job_id in self.session_manager.running_schedules:
            # 這裡需要更複雜的移除邏輯，但先簡化
            pass

        try:
            if schedule_type == "daily":
                self.schedule.every().day.at(schedule_time).do(self._run_scheduled_task, schedule_entry).tag(job_id)
            elif schedule_type == "weekly":
                # 默認週一，可以擴充
                self.schedule.every().monday.at(schedule_time).do(self._run_scheduled_task, schedule_entry).tag(job_id)
            elif schedule_type == "monthly":
                # 月初，可以擴充
                self.schedule.every().month.at(schedule_time).do(self._run_scheduled_task, schedule_entry).tag(job_id)
            elif schedule_type == "cron":
                # Cron支持會比較複雜，這裡簡化處理
                self.logger.warning(f"Cron排程 {job_id} 暫不支持，設定為每日")
                self.schedule.every().day.at("09:00").do(self._run_scheduled_task, schedule_entry).tag(job_id)

            self.session_manager.running_schedules.add(job_id)
            self.logger.info(f"排程任務已應用: {job_id}")

        except Exception as e:
            self.logger.error(f"設定排程任務失敗 {job_id}: {e}")

    def _run_scheduled_task(self, schedule_entry):
        """執行排程任務"""
        user_id = schedule_entry["user_id"]
        job_id = f"{schedule_entry['id']}_{user_id}"

        self.logger.info(f"開始執行排程任務: {job_id}")

        # 避免平行執行相同用戶
        if user_id in self.session_manager.running_schedules:
            self.logger.warning(f"用戶 {user_id} 已有任務在執行，跳過本次排程")
            return

        self.session_manager.running_schedules.add(user_id)

        try:
            # 這裡可以呼叫GUI的爬行方法
            # 由於是在子線程執行，需要設計回呼機制
            self.logger.info(f"排程任務執行完成: {job_id}")
            schedule_entry["last_run"] = datetime.now().isoformat()
            self.save_schedules()

        except Exception as e:
            self.logger.error(f"排程任務執行失敗 {job_id}: {e}")
        finally:
            self.session_manager.running_schedules.discard(user_id)

    def remove_schedule(self, schedule_id):
        """刪除排程任務"""
        for i, s in enumerate(self.schedules):
            if s["id"] == schedule_id:
                removed = self.schedules.pop(i)
                job_id = f"{removed['id']}_{removed['user_id']}"

                # 從schedule庫移除
                if self.schedule and job_id in self.session_manager.running_schedules:
                    try:
                        # 移除標籤的所有任務
                        self.schedule.clear(job_id)
                        self.session_manager.running_schedules.discard(job_id)
                    except:
                        pass

                self.save_schedules()
                self.logger.info(f"排程任務已刪除: {job_id}")
                return True
        return False

    def get_schedules(self):
        """獲取所有排程任務"""
        return self.schedules.copy()

    def update_schedule_status(self, schedule_id, enabled):
        """更新排程啟用狀態"""
        for s in self.schedules:
            if s["id"] == schedule_id:
                old_status = s.get("enabled", False)
                s["enabled"] = enabled
                self.save_schedules()

                if enabled and not old_status:
                    self.schedule_job(s)
                elif not enabled and old_status:
                    # 停用排程
                    job_id = f"{s['id']}_{s['user_id']}"
                    if self.schedule and job_id in self.session_manager.running_schedules:
                        try:
                            self.schedule.clear(job_id)
                            self.session_manager.running_schedules.discard(job_id)
                        except:
                            pass

                self.logger.info(f"排程任務狀態已更新: {schedule_id} -> {'啟用' if enabled else '停用'}")
                return True
        return False

    def start_scheduler(self):
        """啟動排程服務"""
        if not self.schedule:
            self.logger.error("排程服務無法啟動：schedule模組不可用")
            return

        # 應用所有啟用的排程
        for s in self.schedules:
            if s.get("enabled", False):
                self.schedule_job(s)

        self.logger.info("排程服務已啟動")

    def run_pending(self):
        """執行待處理的任務（需要在主循環中呼叫）"""
        if self.schedule:
            self.schedule.run_pending()
