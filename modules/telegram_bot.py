"""
Telegram Bot 模块
提供交互式菜单控制
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes


class TelegramBot:
    """Telegram Bot 控制器"""
    
    def __init__(self, bot_token: str, controller):
        """
        初始化 Telegram Bot
        
        :param bot_token: Bot Token
        :param controller: RapidUploadController 实例
        """
        self.bot_token = bot_token
        self.controller = controller
        self.app = None
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /start 命令"""
        keyboard = [
            [
                InlineKeyboardButton("📊 查看状态", callback_data="status"),
                InlineKeyboardButton("🔍 立即检测", callback_data="scan_now")
            ],
            [
                InlineKeyboardButton("🔄 重新检测", callback_data="recheck_now"),
                InlineKeyboardButton("📈 查看统计", callback_data="statistics")
            ],
            [
                InlineKeyboardButton("🧹 清理记录", callback_data="clean_processed"),
                InlineKeyboardButton("📁 文件列表", callback_data="file_list")
            ],
            [
                InlineKeyboardButton("⚙️ 系统信息", callback_data="system_info"),
                InlineKeyboardButton("🔔 通知设置", callback_data="notification_settings")
            ],
            [
                InlineKeyboardButton("❓ 帮助", callback_data="help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = """
🤖 <b>AW115MST 控制面板</b>

欢迎使用 115 网盘秒传检测工具！

📌 <b>功能说明：</b>
• 自动监控 input 目录
• 智能延迟移动策略
• 定时重新检测
• 实时状态查询

👇 请选择功能：
"""
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理按钮回调"""
        query = update.callback_query
        await query.answer()
        
        action = query.data
        
        if action == "status":
            await self.show_status(query)
        elif action == "scan_now":
            await self.scan_now(query)
        elif action == "recheck_now":
            await self.recheck_now(query)
        elif action == "clean_processed":
            await self.clean_processed(query)
        elif action == "statistics":
            await self.show_statistics(query)
        elif action == "file_list":
            await self.show_file_list(query)
        elif action == "system_info":
            await self.show_system_info(query)
        elif action == "notification_settings":
            await self.show_notification_settings(query)
        elif action == "help":
            await self.show_help(query)
        elif action.startswith("toggle_notify_"):
            await self.toggle_notification(query, action)
        elif action == "back_to_menu":
            await self.back_to_menu(query)
    
    async def show_status(self, query):
        """显示当前状态"""
        try:
            # 读取重检记录
            recheck_file = Path(self.controller.recheck_file)
            recheck_data = {}
            if recheck_file.exists():
                with open(recheck_file, 'r', encoding='utf-8') as f:
                    recheck_data = json.load(f)
            
            # 统计各目录文件数
            input_path = Path('./input')
            rapid_path = Path('./rapid')
            non_rapid_path = Path('./non_rapid')
            
            input_files = len(list(input_path.rglob('*'))) if input_path.exists() else 0
            rapid_files = len(list(rapid_path.rglob('*'))) if rapid_path.exists() else 0
            non_rapid_files = len(list(non_rapid_path.rglob('*'))) if non_rapid_path.exists() else 0
            
            # 统计待检测文件
            pending_files = sum(1 for k, v in recheck_data.items() 
                              if v.get('location') == 'input')
            
            status_text = f"""
📊 <b>系统状态</b>

📁 <b>文件分布：</b>
• Input 目录: {input_files} 个文件
• Rapid 目录: {rapid_files} 个文件
• Non-Rapid 目录: {non_rapid_files} 个文件

⏳ <b>待处理：</b>
• 待检测文件: {pending_files} 个
• 记录总数: {len(recheck_data)} 条

⚙️ <b>调度器状态：</b>
• 实时监控: {'✅ 运行中' if self.controller.config_manager.get('scheduler.watch.enabled', True) else '⏸️ 已停止'}
• 定时任务: {'✅ 运行中' if self.controller.config_manager.get('scheduler.cron.enabled', True) else '⏸️ 已停止'}

🕐 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            keyboard = [[InlineKeyboardButton("🔙 返回菜单", callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                status_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            await query.edit_message_text(f"❌ 获取状态失败: {str(e)}")
    
    async def scan_now(self, query):
        """立即执行扫描"""
        await query.edit_message_text("🔍 开始扫描 input 目录...\n请稍候...")
        
        try:
            result = self.controller.process_input_with_delay()
            
            if result.get('success'):
                rapid = result.get('rapid_moved', 0)
                non_rapid = result.get('non_rapid_moved', 0)
                pending = result.get('pending', 0)
                
                result_text = f"""
✅ <b>扫描完成</b>

📊 <b>处理结果：</b>
• ✅ 可秒传已移动: {rapid} 个
• ⚠️ 不可秒传已移动: {non_rapid} 个
• ⏳ 待重检: {pending} 个

🕐 完成时间: {datetime.now().strftime('%H:%M:%S')}
"""
            else:
                result_text = f"❌ 扫描失败: {result.get('error', '未知错误')}"
            
            keyboard = [[InlineKeyboardButton("🔙 返回菜单", callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                result_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            await query.edit_message_text(f"❌ 扫描失败: {str(e)}")
    
    async def recheck_now(self, query):
        """立即执行重新检测"""
        await query.edit_message_text("🔄 开始重新检测 non_rapid 目录...\n请稍候...")
        
        try:
            result = self.controller.recheck_non_rapid_files()
            
            if result.get('success'):
                total = result.get('total', 0)
                now_rapid = result.get('now_rapid', 0)
                still_non_rapid = result.get('still_non_rapid', 0)
                skipped = result.get('skipped', 0)
                
                result_text = f"""
✅ <b>重新检测完成</b>

📊 <b>检测结果：</b>
• 检测文件数: {total}
• ✅ 变为可秒传: {now_rapid} 个
• ⚠️ 仍不可秒传: {still_non_rapid} 个
• ⏭ 跳过: {skipped} 个

🕐 完成时间: {datetime.now().strftime('%H:%M:%S')}
"""
            else:
                result_text = f"❌ 重新检测失败: {result.get('error', '未知错误')}"
            
            keyboard = [[InlineKeyboardButton("🔙 返回菜单", callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                result_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            await query.edit_message_text(f"❌ 重新检测失败: {str(e)}")
    
    async def clean_processed(self, query):
        """清理已处理文件记录"""
        await query.edit_message_text("🧹 开始清理已处理文件记录...\n请稍候...")
        
        try:
            result = self.controller.clean_processed_records()
            
            if result.get('success'):
                cleaned = result.get('cleaned', 0)
                total_before = result.get('total_before', 0)
                total_after = result.get('total_after', 0)
                
                result_text = f"""
✅ <b>清理完成</b>

📊 <b>清理结果：</b>
• 清理前记录数: {total_before}
• 清理后记录数: {total_after}
• 已清理: {cleaned} 条

💡 <b>说明：</b>
清理已处理文件的标记，这些文件将在下次扫描时重新检测。

🕐 完成时间: {datetime.now().strftime('%H:%M:%S')}
"""
            else:
                result_text = f"❌ 清理失败: {result.get('error', '未知错误')}"
            
            keyboard = [[InlineKeyboardButton("🔙 返回菜单", callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                result_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            await query.edit_message_text(f"❌ 清理失败: {str(e)}")
    
    async def show_statistics(self, query):
        """显示统计信息"""
        try:
            # 读取日志统计
            log_dir = Path('./logs')
            total_rapid = 0
            total_non_rapid = 0
            
            if log_dir.exists():
                # 这里可以解析日志文件获取统计
                # 简化版本：只显示当前目录统计
                pass
            
            rapid_path = Path('./rapid')
            non_rapid_path = Path('./non_rapid')
            
            rapid_count = len([f for f in rapid_path.rglob('*') if f.is_file()]) if rapid_path.exists() else 0
            non_rapid_count = len([f for f in non_rapid_path.rglob('*') if f.is_file()]) if non_rapid_path.exists() else 0
            
            # 计算总大小
            rapid_size = sum(f.stat().st_size for f in rapid_path.rglob('*') if f.is_file()) if rapid_path.exists() else 0
            non_rapid_size = sum(f.stat().st_size for f in non_rapid_path.rglob('*') if f.is_file()) if non_rapid_path.exists() else 0
            
            def format_size(size):
                for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                    if size < 1024.0:
                        return f"{size:.2f} {unit}"
                    size /= 1024.0
                return f"{size:.2f} PB"
            
            stats_text = f"""
📈 <b>统计信息</b>

📁 <b>可秒传文件：</b>
• 文件数: {rapid_count}
• 总大小: {format_size(rapid_size)}

📁 <b>不可秒传文件：</b>
• 文件数: {non_rapid_count}
• 总大小: {format_size(non_rapid_size)}

📊 <b>总计：</b>
• 文件总数: {rapid_count + non_rapid_count}
• 总大小: {format_size(rapid_size + non_rapid_size)}
• 秒传率: {(rapid_count / (rapid_count + non_rapid_count) * 100) if (rapid_count + non_rapid_count) > 0 else 0:.1f}%

🕐 统计时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            keyboard = [[InlineKeyboardButton("🔙 返回菜单", callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                stats_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            await query.edit_message_text(f"❌ 获取统计失败: {str(e)}")
    
    async def show_file_list(self, query):
        """显示最近文件列表"""
        try:
            recheck_file = Path(self.controller.recheck_file)
            recheck_data = {}
            if recheck_file.exists():
                with open(recheck_file, 'r', encoding='utf-8') as f:
                    recheck_data = json.load(f)
            
            # 按最后检测时间排序
            sorted_files = sorted(
                recheck_data.items(),
                key=lambda x: x[1].get('last_check_time', 0),
                reverse=True
            )[:10]  # 只显示最近 10 个
            
            if not sorted_files:
                file_list_text = "📁 <b>最近文件</b>\n\n暂无记录"
            else:
                file_list_text = "📁 <b>最近检测的文件（前10个）</b>\n\n"
                for file_path, info in sorted_files:
                    filename = Path(file_path).name
                    status = "✅ 可秒传" if info.get('last_status') == 'rapid' else "⚠️ 不可秒传"
                    check_count = info.get('check_count', 0)
                    location = info.get('location', 'unknown')
                    
                    file_list_text += f"• <code>{filename[:30]}...</code>\n"
                    file_list_text += f"  状态: {status} | 检测: {check_count}次 | 位置: {location}\n\n"
            
            keyboard = [[InlineKeyboardButton("🔙 返回菜单", callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                file_list_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            await query.edit_message_text(f"❌ 获取文件列表失败: {str(e)}")
    
    async def show_system_info(self, query):
        """显示系统信息"""
        try:
            import psutil
            
            # CPU 使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存使用
            memory = psutil.virtual_memory()
            memory_used = memory.used / (1024**3)
            memory_total = memory.total / (1024**3)
            memory_percent = memory.percent
            
            # 磁盘使用
            disk = psutil.disk_usage('/')
            disk_used = disk.used / (1024**3)
            disk_total = disk.total / (1024**3)
            disk_percent = disk.percent
            
            system_text = f"""
⚙️ <b>系统信息</b>

💻 <b>CPU：</b>
• 使用率: {cpu_percent}%

🧠 <b>内存：</b>
• 已使用: {memory_used:.2f} GB / {memory_total:.2f} GB
• 使用率: {memory_percent}%

💾 <b>磁盘：</b>
• 已使用: {disk_used:.2f} GB / {disk_total:.2f} GB
• 使用率: {disk_percent}%

🐍 <b>Python：</b>
• 版本: {os.sys.version.split()[0]}

🕐 系统时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            keyboard = [[InlineKeyboardButton("🔙 返回菜单", callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                system_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except ImportError:
            await query.edit_message_text(
                "❌ 需要安装 psutil 模块\n运行: pip install psutil"
            )
        except Exception as e:
            await query.edit_message_text(f"❌ 获取系统信息失败: {str(e)}")
    
    async def show_notification_settings(self, query):
        """显示通知设置"""
        telegram_config = self.controller.config_manager.get('telegram', {})
        
        notify_complete = telegram_config.get('notify_on_complete', True)
        notify_error = telegram_config.get('notify_on_error', True)
        notify_rapid = telegram_config.get('notify_on_rapid', False)
        
        settings_text = f"""
🔔 <b>通知设置</b>

当前配置：
• 完成通知: {'✅ 开启' if notify_complete else '❌ 关闭'}
• 错误通知: {'✅ 开启' if notify_error else '❌ 关闭'}
• 单文件通知: {'✅ 开启' if notify_rapid else '❌ 关闭'}

💡 提示：点击按钮切换设置
"""
        
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{'✅' if notify_complete else '❌'} 完成通知",
                    callback_data="toggle_notify_complete"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{'✅' if notify_error else '❌'} 错误通知",
                    callback_data="toggle_notify_error"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{'✅' if notify_rapid else '❌'} 单文件通知",
                    callback_data="toggle_notify_rapid"
                )
            ],
            [
                InlineKeyboardButton("🔙 返回菜单", callback_data="back_to_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            settings_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def toggle_notification(self, query, action):
        """切换通知设置"""
        # 注意：这里只是演示，实际需要修改配置文件
        setting_name = action.replace('toggle_notify_', '')
        
        await query.answer(f"⚠️ 通知设置需要修改配置文件后重启生效")
        await self.show_notification_settings(query)
    
    async def show_help(self, query):
        """显示帮助信息"""
        help_text = """
❓ <b>帮助信息</b>

<b>命令列表：</b>
• /start - 显示主菜单
• /status - 查看系统状态
• /scan - 立即扫描
• /recheck - 立即重检

<b>功能说明：</b>

📊 <b>查看状态</b>
查看当前文件分布和系统运行状态

🔍 <b>立即检测</b>
手动触发 input 目录扫描

🔄 <b>重新检测</b>
手动触发 non_rapid 目录重检

🧹 <b>清理记录</b>
清理已处理文件的标记（复制模式）

📈 <b>查看统计</b>
查看文件统计和秒传率

📁 <b>文件列表</b>
查看最近检测的文件

⚙️ <b>系统信息</b>
查看 CPU、内存、磁盘使用情况

🔔 <b>通知设置</b>
配置通知选项（需重启生效）

<b>项目地址：</b>
https://github.com/AWdress/AW115MST
"""
        
        keyboard = [[InlineKeyboardButton("🔙 返回菜单", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def back_to_menu(self, query):
        """返回主菜单"""
        keyboard = [
            [
                InlineKeyboardButton("📊 查看状态", callback_data="status"),
                InlineKeyboardButton("🔍 立即检测", callback_data="scan_now")
            ],
            [
                InlineKeyboardButton("🔄 重新检测", callback_data="recheck_now"),
                InlineKeyboardButton("📈 查看统计", callback_data="statistics")
            ],
            [
                InlineKeyboardButton("🧹 清理记录", callback_data="clean_processed"),
                InlineKeyboardButton("📁 文件列表", callback_data="file_list")
            ],
            [
                InlineKeyboardButton("⚙️ 系统信息", callback_data="system_info"),
                InlineKeyboardButton("🔔 通知设置", callback_data="notification_settings")
            ],
            [
                InlineKeyboardButton("❓ 帮助", callback_data="help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🤖 <b>AW115MST 控制面板</b>\n\n👇 请选择功能：",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /status 命令"""
        # 创建一个临时 query 对象
        class TempQuery:
            def __init__(self, message):
                self.message = message
            
            async def edit_message_text(self, text, **kwargs):
                await self.message.reply_text(text, **kwargs)
        
        await self.show_status(TempQuery(update.message))
    
    async def scan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /scan 命令"""
        class TempQuery:
            def __init__(self, message):
                self.message = message
            
            async def edit_message_text(self, text, **kwargs):
                await self.message.reply_text(text, **kwargs)
        
        await self.scan_now(TempQuery(update.message))
    
    async def recheck_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /recheck 命令"""
        class TempQuery:
            def __init__(self, message):
                self.message = message
            
            async def edit_message_text(self, text, **kwargs):
                await self.message.reply_text(text, **kwargs)
        
        await self.recheck_now(TempQuery(update.message))
    
    def run(self):
        """运行 Bot"""
        self.app = Application.builder().token(self.bot_token).build()
        
        # 注册命令处理器
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("scan", self.scan_command))
        self.app.add_handler(CommandHandler("recheck", self.recheck_command))
        
        # 注册回调处理器
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        
        print("🤖 Telegram Bot 启动成功")
        print(f"📱 Bot Token: {self.bot_token[:10]}...")
        
        # 运行 Bot
        self.app.run_polling()
