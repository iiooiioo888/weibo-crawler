#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統計資料管理模組
負責爬取統計數據收集、可視化和分析
"""

import sqlite3
import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
import logging

class StatisticsManager:
    def __init__(self, db_path="weibo_stats.db"):
        self.db_path = db_path
        self.logger = logging.getLogger('weibo')
        self.stats_cache = {}  # 緩存統計數據
        self.lock = threading.Lock()
        self.setup_database()

    def setup_database(self):
        """初始化統計資料庫"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 爬取記錄表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crawl_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    status TEXT DEFAULT 'running',  -- running, completed, failed
                    total_weibos INTEGER DEFAULT 0,
                    image_count INTEGER DEFAULT 0,
                    video_count INTEGER DEFAULT 0,
                    comment_count INTEGER DEFAULT 0,
                    repost_count INTEGER DEFAULT 0,
                    duration REAL DEFAULT 0,  -- 秒數
                    efficiency REAL DEFAULT 0,  -- weibos/分鐘
                    config_snapshot TEXT  -- JSON格式的配置快照
                )
            ''')

            # 每日統計表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT PRIMARY KEY,
                    total_sessions INTEGER DEFAULT 0,
                    successful_sessions INTEGER DEFAULT 0,
                    total_weibos INTEGER DEFAULT 0,
                    total_images INTEGER DEFAULT 0,
                    total_videos INTEGER DEFAULT 0,
                    total_duration REAL DEFAULT 0,
                    avg_efficiency REAL DEFAULT 0
                )
            ''')

            # 用戶統計表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id TEXT PRIMARY KEY,
                    crawled_times INTEGER DEFAULT 0,
                    last_crawl TEXT,
                    total_weibos INTEGER DEFAULT 0,
                    avg_efficiency REAL DEFAULT 0,
                    success_rate REAL DEFAULT 0,
                    favorite_config TEXT  -- 最常用配置
                )
            ''')

            # 效能指標表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    timestamp TEXT PRIMARY KEY,
                    memory_usage REAL,
                    network_speed REAL,
                    cpu_usage REAL,
                    error_count INTEGER DEFAULT 0,
                    retry_count INTEGER DEFAULT 0
                )
            ''')

            conn.commit()

        self.logger.info("統計資料庫初始化完成")

    def start_crawl_session(self, user_id, config):
        """開始新的爬取會話"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                start_time = datetime.now().isoformat()

                cursor.execute('''
                    INSERT INTO crawl_sessions
                    (user_id, start_time, status, config_snapshot)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, start_time, 'running', json.dumps(config)))

                session_id = cursor.lastrowid
                conn.commit()
                return session_id

    def update_crawl_progress(self, session_id, weibo_count=None, image_count=None,
                            video_count=None, comment_count=None, repost_count=None):
        """更新爬取進度"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                updates = {}
                params = []

                if weibo_count is not None:
                    updates['total_weibos'] = weibo_count
                if image_count is not None:
                    updates['image_count'] = image_count
                if video_count is not None:
                    updates['video_count'] = video_count
                if comment_count is not None:
                    updates['comment_count'] = comment_count
                if repost_count is not None:
                    updates['repost_count'] = repost_count

                if updates:
                    set_clause = ', '.join(f'{k}=?' for k in updates.keys())
                    params.extend(updates.values())
                    params.append(session_id)

                    cursor.execute(f'''
                        UPDATE crawl_sessions
                        SET {set_clause}
                        WHERE id=?
                    ''', params)

                    conn.commit()

    def end_crawl_session(self, session_id, status='completed'):
        """結束爬取會話"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                end_time = datetime.now()

                # 獲取開始時間並計算統計
                cursor.execute('SELECT start_time, total_weibos FROM crawl_sessions WHERE id=?',
                              (session_id,))
                result = cursor.fetchone()

                if result:
                    start_time_str, total_weibos = result
                    start_time = datetime.fromisoformat(start_time_str)
                    duration = (end_time - start_time).total_seconds()
                    efficiency = (total_weibos / max(duration, 1)) * 60  # weibos/分鐘

                    cursor.execute('''
                        UPDATE crawl_sessions
                        SET end_time=?, status=?, duration=?, efficiency=?
                        WHERE id=?
                    ''', (end_time.isoformat(), status, duration, efficiency, session_id))

                    # 更新每日統計和用戶統計
                    self.update_daily_stats(end_time.date().isoformat())
                    cursor.execute('SELECT user_id FROM crawl_sessions WHERE id=?', (session_id,))
                    user_result = cursor.fetchone()
                    if user_result:
                        self.update_user_stats(user_result[0])

                conn.commit()

    def update_daily_stats(self, date):
        """更新每日統計"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 計算當日統計
            cursor.execute('''
                SELECT COUNT(*), SUM(total_weibos), SUM(image_count), SUM(video_count), AVG(duration)
                FROM crawl_sessions
                WHERE DATE(start_time)=? AND status='completed'
            ''', (date,))

            result = cursor.fetchone()
            if result:
                total_sessions, total_weibos, total_images, total_videos, avg_duration = result
                successful_sessions = total_sessions or 0

                cursor.execute('''
                    INSERT OR REPLACE INTO daily_stats
                    (date, successful_sessions, total_weibos, total_images, total_videos, total_duration, avg_efficiency)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (date, successful_sessions, total_weibos or 0, total_images or 0,
                      total_videos or 0, avg_duration or 0,
                      (total_weibos or 0) / max(avg_duration or 1, 1) * 60))

                conn.commit()

    def update_user_stats(self, user_id):
        """更新用戶統計"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 計算用戶統計
            cursor.execute('''
                SELECT COUNT(*), MAX(end_time), SUM(total_weibos), AVG(efficiency),
                       COUNT(CASE WHEN status='completed' THEN 1 END) * 1.0 / COUNT(*) as success_rate
                FROM crawl_sessions
                WHERE user_id=?
            ''', (user_id,))

            result = cursor.fetchone()
            if result:
                crawled_times, last_crawl, total_weibos, avg_efficiency, success_rate = result

                cursor.execute('''
                    INSERT OR REPLACE INTO user_stats
                    (user_id, crawled_times, last_crawl, total_weibos, avg_efficiency, success_rate)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, crawled_times or 0, last_crawl, total_weibos or 0,
                      avg_efficiency or 0, success_rate or 0))

                conn.commit()

    def get_recent_sessions(self, limit=50):
        """獲取最近的爬取會話"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM crawl_sessions
                ORDER BY start_time DESC LIMIT ?
            ''', (limit,))

            columns = ['id', 'user_id', 'start_time', 'end_time', 'status',
                      'total_weibos', 'image_count', 'video_count', 'comment_count',
                      'repost_count', 'duration', 'efficiency', 'config_snapshot']

            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_daily_chart_data(self, days=30):
        """獲取每日統計圖表數據"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 獲取最近days天的數據
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)

            cursor.execute('''
                SELECT date, successful_sessions, total_weibos, total_images,
                       total_videos, avg_efficiency
                FROM daily_stats
                WHERE date BETWEEN ? AND ?
                ORDER BY date ASC
            ''', (start_date.isoformat(), end_date.isoformat()))

            return cursor.fetchall()

    def get_user_chart_data(self, limit=20):
        """獲取用戶統計圖表數據"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT user_id, total_weibos, crawled_times, success_rate, avg_efficiency
                FROM user_stats
                ORDER BY total_weibos DESC LIMIT ?
            ''', (limit,))

            return cursor.fetchall()

    def get_performance_metrics(self, hours=24):
        """獲取效能指標圖表數據"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            start_time = datetime.now() - timedelta(hours=hours)
            cursor.execute('''
                SELECT timestamp, memory_usage, network_speed, cpu_usage
                FROM performance_metrics
                WHERE timestamp > ?
                ORDER BY timestamp ASC
            ''', (start_time.isoformat(),))

            return cursor.fetchall()

    def add_performance_metric(self, memory_usage=None, network_speed=None,
                              cpu_usage=None, error_count=0, retry_count=0):
        """添加效能指標"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                timestamp = datetime.now().isoformat()

                cursor.execute('''
                    INSERT OR REPLACE INTO performance_metrics
                    (timestamp, memory_usage, network_speed, cpu_usage, error_count, retry_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (timestamp, memory_usage, network_speed, cpu_usage, error_count, retry_count))

                conn.commit()

    def get_summary_stats(self):
        """獲取總結統計數據"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 總計統計
            cursor.execute('''
                SELECT COUNT(*), SUM(total_weibos), SUM(image_count), SUM(video_count),
                       AVG(efficiency), COUNT(DISTINCT user_id)
                FROM crawl_sessions
                WHERE status='completed'
            ''')

            result = cursor.fetchone()
            if not result:
                return None

            total_sessions, total_weibos, total_images, total_videos, avg_efficiency, unique_users = result

            # 今日統計
            today = datetime.now().date().isoformat()
            cursor.execute('''
                SELECT successful_sessions, total_weibos, total_images, total_videos
                FROM daily_stats
                WHERE date=?
            ''', (today,))

            today_stats = cursor.fetchone()
            today_sessions, today_weibos, today_images, today_videos = today_stats or (0, 0, 0, 0)

            return {
                'total_sessions': total_sessions or 0,
                'total_weibos': total_weibos or 0,
                'total_images': total_images or 0,
                'total_videos': total_videos or 0,
                'avg_efficiency': avg_efficiency or 0,
                'unique_users': unique_users or 0,
                'today_sessions': today_sessions,
                'today_weibos': today_weibos,
                'today_images': today_images,
                'today_videos': today_videos
            }

    def cleanup_old_data(self, days=365):
        """清理舊數據（保留最近days天的數據）"""
        cutoff_date = datetime.now() - timedelta(days=days)

        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 清理舊的會話記錄
                cursor.execute('DELETE FROM crawl_sessions WHERE start_time < ?',
                              (cutoff_date.isoformat(),))

                # 清理舊的效能指標（只保留最近7天）
                perf_cutoff = datetime.now() - timedelta(days=7)
                cursor.execute('DELETE FROM performance_metrics WHERE timestamp < ?',
                              (perf_cutoff.isoformat(),))

                conn.commit()

                deleted_sessions = cursor.rowcount
                cursor.execute('DELETE FROM performance_metrics WHERE timestamp < ?',
                              (perf_cutoff.isoformat(),))
                deleted_metrics = cursor.rowcount

                self.logger.info(f"清理了 {deleted_sessions} 條舊會話記錄和 {deleted_metrics} 條效能指標記錄")
                return deleted_sessions + deleted_metrics
