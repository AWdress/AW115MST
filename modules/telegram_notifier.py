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
    
    def notify_complete(self, stats: Dict[str, int], duration: float):
        """
        发送完成通知
        
        :param stats: 统计信息
        :param duration: 处理耗时（秒）
        """
        if not self.enabled or not self.notify_on_complete:
            return
        
        total = stats.get('total', 0)
        rapid = stats.get('rapid', 0)
        non_rapid = stats.get('non_rapid', 0)
        failed = stats.get('failed', 0)
        
        message = f"""
🎉 <b>AW115MST 处理完成</b>

📊 <b>统计信息：</b>
• 总文件数: {total}
• ✅ 可秒传: {rapid}
• ⚠️ 不可秒传: {non_rapid}
• ❌ 失败: {failed}

⏱ 耗时: {duration:.2f} 秒
🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        self.send_message(message.strip())
    
    def notify_rapid_file(self, filename: str):
        """
        发送单个可秒传文件通知
        
        :param filename: 文件名
        """
        if not self.enabled or not self.notify_on_rapid:
            return
        
        message = f"""
✅ <b>发现可秒传文件</b>

📁 文件: <code>{filename}</code>
🕐 时间: {datetime.now().strftime('%H:%M:%S')}
"""
        
        self.send_message(message.strip())
    
    def notify_error(self, error_msg: str):
        """
        发送错误通知
        
        :param error_msg: 错误信息
        """
        if not self.enabled or not self.notify_on_error:
            return
        
        message = f"""
❌ <b>AW115MST 错误</b>

⚠️ {error_msg}

🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        self.send_message(message.strip())
    
    def notify_recheck_complete(self, stats: Dict[str, int]):
        """
        发送重新检测完成通知
        
        :param stats: 统计信息
        """
        if not self.enabled or not self.notify_on_complete:
            return
        
        total = stats.get('total', 0)
        now_rapid = stats.get('now_rapid', 0)
        still_non_rapid = stats.get('still_non_rapid', 0)
        skipped = stats.get('skipped', 0)
        
        message = f"""
🔄 <b>重新检测完成</b>

📊 <b>统计信息：</b>
• 检测文件数: {total}
• ✅ 变为可秒传: {now_rapid}
• ⚠️ 仍不可秒传: {still_non_rapid}
• ⏭ 跳过: {skipped}

🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        self.send_message(message.strip())
    
    def test_connection(self) -> bool:
        """
        测试 Telegram 连接
        
        :return: 是否连接成功
        """
        if not self.enabled:
            return False
        
        message = "🤖 AW115MST Telegram 通知测试\n\n✅ 连接成功！"
        return self.send_message(message)
