"""
日志模块
负责记录操作日志、生成报告
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from colorama import Fore, Style, init

# 初始化colorama
init(autoreset=True)


class Logger:
    """日志管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化日志管理器
        
        :param config: 日志配置
        """
        self.config = config
        self.log_dir = Path(config.get('log_dir', './logs'))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建日志记录器
        self.logger = logging.getLogger('RapidUploadTool')
        self.logger.setLevel(getattr(logging, config.get('level', 'INFO')))
        
        # 清除已有的处理器
        self.logger.handlers.clear()
        
        # 控制台处理器
        if config.get('console_output', True):
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
        
        # 文件处理器
        if config.get('file_output', True):
            log_file = self.log_dir / f"rapid_upload_{datetime.now().strftime('%Y%m%d')}.log"
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        
        # 文件记录列表
        self.rapid_files: List[Dict[str, Any]] = []
        self.non_rapid_files: List[Dict[str, Any]] = []
        self.failed_files: List[Dict[str, Any]] = []
    
    def info(self, message: str, color: str = None):
        """记录INFO级别日志"""
        if color:
            print(f"{color}{message}{Style.RESET_ALL}")
        self.logger.info(message)
    
    def debug(self, message: str):
        """记录DEBUG级别日志"""
        self.logger.debug(message)
    
    def warning(self, message: str):
        """记录WARNING级别日志"""
        print(f"{Fore.YELLOW}{message}{Style.RESET_ALL}")
        self.logger.warning(message)
    
    def error(self, message: str):
        """记录ERROR级别日志"""
        print(f"{Fore.RED}{message}{Style.RESET_ALL}")
        self.logger.error(message)
    
    def success(self, message: str):
        """记录成功信息"""
        self.info(message, Fore.GREEN)
    
    def add_rapid_file(self, file_info: Dict[str, Any]):
        """添加可秒传文件记录"""
        self.rapid_files.append(file_info)
    
    def add_non_rapid_file(self, file_info: Dict[str, Any]):
        """添加不可秒传文件记录"""
        self.non_rapid_files.append(file_info)
    
    def add_failed_file(self, file_info: Dict[str, Any]):
        """添加失败文件记录"""
        self.failed_files.append(file_info)
    
    def print_summary(self, start_time: datetime, end_time: datetime):
        """
        打印处理摘要
        
        :param start_time: 开始时间
        :param end_time: 结束时间
        """
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "=" * 60)
        print(f"{Fore.CYAN}处理完成！{Style.RESET_ALL}")
        print("=" * 60)
        print(f"总耗时: {duration:.2f} 秒")
        print(f"{Fore.GREEN}✓ 可秒传文件: {len(self.rapid_files)} 个{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}○ 不可秒传文件: {len(self.non_rapid_files)} 个{Style.RESET_ALL}")
        print(f"{Fore.RED}✗ 失败文件: {len(self.failed_files)} 个{Style.RESET_ALL}")
        print(f"总处理文件: {len(self.rapid_files) + len(self.non_rapid_files) + len(self.failed_files)} 个")
        print("=" * 60)
