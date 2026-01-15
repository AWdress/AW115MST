"""
调度器模块
管理实时监控和定时任务
"""

import time
import signal
import sys
import threading
from datetime import datetime, timedelta
from typing import Callable, Dict, Any
from pathlib import Path


class Scheduler:
    """任务调度器"""
    
    def __init__(self, config: Dict[str, Any], controller):
        """
        初始化调度器
        
        :param config: 调度配置
        :param controller: 控制器实例
        """
        self.config = config
        self.controller = controller
        self.running = False
        
        # 实时监控配置
        self.watch_enabled = config.get('watch', {}).get('enabled', True)
        self.debounce_seconds = config.get('watch', {}).get('debounce_seconds', 5)
        
        # 定时任务配置
        self.cron_enabled = config.get('cron', {}).get('enabled', True)
        self.cron_interval = self._parse_interval(config.get('cron', {}).get('interval', '6h'))
        
        # Telegram Bot 配置
        telegram_config = controller.config_manager.get('telegram', {})
        self.bot_enabled = telegram_config.get('enabled', False) and telegram_config.get('bot_token', '')
        self.bot = None
        
        # 线程
        self.watch_thread = None
        self.cron_thread = None
        self.bot_thread = None
        
        # 上次执行时间
        self.last_cron_time = None
    
    def _parse_interval(self, interval_str: str) -> int:
        """
        解析时间间隔字符串
        
        :param interval_str: 时间间隔字符串 (如: "5m", "30m", "1h", "6h")
        :return: 秒数
        """
        interval_str = interval_str.strip().lower()
        
        # 分钟格式: 5m, 30m, 60m
        if interval_str.endswith('m'):
            minutes = int(interval_str[:-1])
            return minutes * 60
        
        # 小时格式: 1h, 6h, 24h
        if interval_str.endswith('h'):
            hours = int(interval_str[:-1])
            return hours * 3600
        
        # 默认 30 分钟
        return 30 * 60
    
    def _should_run_cron(self) -> bool:
        """判断是否应该运行定时任务"""
        if not self.last_cron_time:
            return True
        
        elapsed = time.time() - self.last_cron_time
        return elapsed >= self.cron_interval
    
    def start(self):
        """启动调度器"""
        self.running = True
        
        # 注册信号处理器（用于 Docker 容器优雅停止）
        # 只在主线程中注册信号处理器
        try:
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
        except ValueError:
            # 不在主线程中，跳过信号注册
            pass
        
        print("\n" + "=" * 60)
        print("🚀 AW115MST 调度器启动")
        print("=" * 60)
        
        # 启动实时监控
        if self.watch_enabled:
            print(f"✅ 实时监控: 已启用 (防抖: {self.debounce_seconds}秒)")
            self.watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
            self.watch_thread.start()
        else:
            print("⏸️  实时监控: 已禁用")
        
        # 启动定时任务
        if self.cron_enabled:
            if self.cron_interval >= 3600:
                cron_hours = self.cron_interval / 3600
                print(f"✅ 定时任务: 每 {cron_hours:.1f} 小时（扫描 + 重检）")
            else:
                cron_minutes = self.cron_interval / 60
                print(f"✅ 定时任务: 每 {cron_minutes:.0f} 分钟（扫描 + 重检）")
            self.cron_thread = threading.Thread(target=self._cron_loop, daemon=True)
            self.cron_thread.start()
        else:
            print("⏸️  定时任务: 已禁用")
        
        # 启动 Telegram Bot
        if self.bot_enabled:
            print(f"✅ Telegram Bot: 已启用（交互控制）")
            self.bot_thread = threading.Thread(target=self._bot_loop, daemon=True)
            self.bot_thread.start()
        else:
            print("⏸️  Telegram Bot: 已禁用")
        
        print("=" * 60)
        print("💡 提示: 使用 docker stop 停止容器")
        print("=" * 60 + "\n")
        
        # 主线程保持运行
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️  收到停止信号...")
            self.stop()
    
    def _signal_handler(self, signum, frame):
        """信号处理器（用于 Docker 容器优雅停止）"""
        print(f"\n⏹️  收到信号 {signum}，正在停止...")
        self.stop()
        sys.exit(0)
    
    def _watch_loop(self):
        """实时监控循环"""
        from .file_watcher import FileWatcher
        
        input_path = Path('./input')
        
        def process_callback(file_path: Path):
            """文件处理回调（实时监控到新文件）"""
            try:
                print(f"🔍 正在检测: {file_path.name} ...")
                
                # 实时监控到的新文件，先检测但不移动
                result = self.controller.check_and_record(file_path)
                
                if result.get('success'):
                    if result.get('can_rapid'):
                        print(f"✅ {file_path.name}: 可秒传（将在定时任务中移动）")
                    else:
                        print(f"📝 {file_path.name}: 不可秒传（已记录，将定时重检）")
                else:
                    print(f"⚠️  {file_path.name}: 检测失败 - {result.get('error', '未知错误')}")
            except Exception as e:
                print(f"❌ {file_path.name}: 处理失败 - {e}")
                import traceback
                traceback.print_exc()
        
        watcher = FileWatcher(
            watch_path=input_path,
            callback=process_callback,
            debounce_seconds=self.debounce_seconds,
            recursive=True
        )
        
        watcher.start()
    
    def _cron_loop(self):
        """定时任务循环"""
        while self.running:
            try:
                # 检查是否需要运行定时任务
                if self._should_run_cron():
                    current_time = time.time()
                    print(f"\n⏰ [{datetime.now().strftime('%H:%M:%S')}] 定时任务开始...")
                    
                    # 1. 检测并移动 input 目录中的文件
                    try:
                        print("  📂 检测 input 目录...")
                        result = self.controller.process_input_with_delay()
                        if result.get('success'):
                            rapid = result.get('rapid_moved', 0)
                            non_rapid = result.get('non_rapid_moved', 0)
                            pending = result.get('pending', 0)
                            print(f"  ✅ 检测完成: {rapid} 个可秒传已移动, {non_rapid} 个不可秒传已移动, {pending} 个待重检")
                    except Exception as e:
                        print(f"  ❌ 检测失败: {e}")
                        self.controller.telegram.notify_error(f"定时检测失败: {e}")
                    
                    # 2. 重新检测 non_rapid 目录
                    try:
                        print("  🔄 重新检测 non_rapid 目录...")
                        result = self.controller.recheck_non_rapid_files()
                        if result.get('success'):
                            now_rapid = result.get('now_rapid', 0)
                            print(f"  ✅ 重检完成: {now_rapid} 个变为可秒传")
                    except Exception as e:
                        print(f"  ❌ 重检失败: {e}")
                        self.controller.telegram.notify_error(f"定时重检失败: {e}")
                    
                    self.last_cron_time = current_time
                    print(f"✅ 定时任务完成\n")
                
                # 每分钟检查一次
                time.sleep(60)
                
            except Exception as e:
                print(f"❌ 调度器错误: {e}")
                time.sleep(60)
    
    def _bot_loop(self):
        """Telegram Bot 循环"""
        try:
            from modules.telegram_bot import TelegramBot
            
            telegram_config = self.controller.config_manager.get('telegram', {})
            bot_token = telegram_config.get('bot_token', '')
            
            if not bot_token:
                print("⚠️  Telegram Bot Token 未配置，跳过启动")
                return
            
            print("🤖 正在启动 Telegram Bot...")
            self.bot = TelegramBot(bot_token, self.controller)
            
            # 在单独的线程中运行 Bot
            self.bot.run()
            
        except Exception as e:
            print(f"❌ Telegram Bot 启动失败: {e}")
            import traceback
            traceback.print_exc()
    
    def stop(self):
        """停止调度器"""
        print("\n⏹️  正在停止调度器...")
        self.running = False
        
        if self.watch_thread:
            self.watch_thread.join(timeout=2)
        
        if self.cron_thread:
            self.cron_thread.join(timeout=2)
        
        if self.bot and self.bot_thread:
            try:
                # 停止 Bot
                if hasattr(self.bot, 'application') and self.bot.application:
                    self.bot.application.stop()
            except Exception as e:
                print(f"⚠️  停止 Bot 时出错: {e}")
            self.bot_thread.join(timeout=2)
        
        print("✅ 调度器已停止")
