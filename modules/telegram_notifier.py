"""
Telegram 通知模块
发送处理结果通知到 Telegram
"""

import requests
from typing import Dict, Any, Optional
from datetime import datetime


class TelegramNotifier:
    """Telegram 通知器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 Telegram 通知器
        
        :param config: 通知配置
        """
        self.enabled = config.get('enabled', False)
        self.bot_token = config.get('bot_token', '')
        self.chat_id = config.get('chat_id', '')
        self.notify_on_complete = config.get('notify_on_complete', True)
        self.notify_on_error = config.get('notify_on_error', True)
        self.notify_on_rapid = config.get('notify_on_rapid', False)
        self.config = config  # 保存完整配置
        
        if self.enabled and (not self.bot_token or not self.chat_id):
            print("⚠️  警告: Telegram 通知已启用但未配置 bot_token 或 chat_id")
            self.enabled = False
    
    def send_message(self, message: str, parse_mode: str = 'HTML') -> bool:
        """
        发送消息到 Telegram
        
        :param message: 消息内容
        :param parse_mode: 解析模式 (HTML/Markdown)
        :return: 是否发送成功
        """
        if not self.enabled:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Telegram 通知发送失败: {e}")
            return False

    @staticmethod
    def _bar(count: int, total: int, width: int = 10) -> str:
        """生成简单的文字进度条，如 ████░░░░░░ 40%"""
        if total == 0:
            return '░' * width + ' 0%'
        filled = round(count / total * width)
        pct = round(count / total * 100)
        return '█' * filled + '░' * (width - filled) + f' {pct}%'

    def notify_complete(self, stats: Dict[str, int], duration: float):
        """
        发送完成通知
        """
        if not self.enabled or not self.notify_on_complete:
            return

        total = stats.get('total', 0)
        rapid = stats.get('rapid', 0)
        non_rapid = stats.get('non_rapid', 0)
        failed = stats.get('failed', 0)

        bar = self._bar(rapid, total)

        if duration >= 3600:
            dur_str = f"{int(duration // 3600)}h {int(duration % 3600 // 60)}m"
        elif duration >= 60:
            dur_str = f"{int(duration // 60)}m {int(duration % 60)}s"
        else:
            dur_str = f"{duration:.1f}s"

        message = (
            f"🎉 <b>AW115MST 处理完成</b>\n"
            f"──────────────────\n"
            f"📊 <b>统计</b>\n"
            f"  📦 总计  <b>{total}</b> 个\n"
            f"  ✅ 秒传  <b>{rapid}</b> 个  {bar}\n"
            f"  🔁 待传  <b>{non_rapid}</b> 个\n"
            + (f"  ❌ 失败  <b>{failed}</b> 个\n" if failed else "")
            + f"──────────────────\n"
            f"⏱ 耗时：{dur_str}　🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send_message(message)

    def notify_rapid_file(self, filename: str, action: str = '秒传'):
        """
        发送单个文件成功通知

        :param filename: 文件名
        :param action: 操作类型，如 '秒传' 或 '上传'
        """
        if not self.enabled or not self.notify_on_rapid:
            return

        icon = '✅' if action == '秒传' else '📤'
        message = (
            f"{icon} <b>{action}成功</b>\n"
            f"──────────────────\n"
            f"📄 <code>{filename}</code>\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send_message(message)

    def notify_error(self, error_msg: str):
        """
        发送错误通知
        """
        if not self.enabled or not self.notify_on_error:
            return

        message = (
            f"❌ <b>AW115MST 错误</b>\n"
            f"──────────────────\n"
            f"⚠️ {error_msg}\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.send_message(message)

    def notify_recheck_complete(self, stats: Dict[str, int]):
        """
        发送重新检测完成通知
        """
        if not self.enabled or not self.notify_on_complete:
            return

        total = stats.get('total', 0)
        now_rapid = stats.get('now_rapid', 0)
        still_non_rapid = stats.get('still_non_rapid', 0)
        skipped = stats.get('skipped', 0)

        # 只有有实际结果时才发送
        if total == 0:
            return

        bar = self._bar(now_rapid, total - skipped) if (total - skipped) > 0 else '──────────'

        message = (
            f"🔄 <b>重检完成</b>\n"
            f"──────────────────\n"
            f"  📦 共检  <b>{total}</b> 个\n"
            f"  ✅ 秒传  <b>{now_rapid}</b> 个  {bar}\n"
            f"  🔁 仍待  <b>{still_non_rapid}</b> 个\n"
            + (f"  ⏭ 跳过  <b>{skipped}</b> 个\n" if skipped else "")
            + f"──────────────────\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send_message(message)

    def test_connection(self) -> bool:
        """
        测试 Telegram 连接

        :return: 是否连接成功
        """
        if not self.enabled:
            return False

        message = "🤖 <b>AW115MST</b> 已连接\n✅ Telegram 通知正常"
        return self.send_message(message)

