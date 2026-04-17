"""
文件监控模块
使用 watchdog 监控文件系统变化
"""

import time
import threading
from pathlib import Path
from typing import Callable, Dict, Set
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


class FileWatcher:
    """文件监控器"""
    
    def __init__(self, watch_path: Path, callback: Callable,
                 debounce_seconds: int = 5, recursive: bool = True,
                 exclude_extensions: list = None):
        """
        初始化文件监控器
        
        :param watch_path: 监控路径
        :param callback: 文件稳定后的回调函数
        :param debounce_seconds: 防抖时间（秒），文件稳定后才触发
        :param recursive: 是否递归监控子目录
        :param exclude_extensions: 忽略的扩展名列表（如 [".part", ".tmp"]）
        """
        self.watch_path = Path(watch_path)
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.recursive = recursive
        # 下载中/临时文件扩展名，匹配到则直接忽略
        self.exclude_extensions = set(e.lower() for e in (exclude_extensions or []))
        
        # 文件变化追踪
        self.pending_files: Dict[str, float] = {}  # {文件路径: 最后修改时间}
        self.processing_files: Set[str] = set()    # 正在处理的文件
        self.lock = threading.Lock()
        
        # 创建观察者
        self.observer = Observer()
        self.event_handler = FileChangeHandler(self)
        
        # 防抖检查线程
        self.debounce_thread = None
        self.running = False
    
    def start(self):
        """启动监控"""
        if not self.watch_path.exists():
            raise FileNotFoundError(f"监控路径不存在: {self.watch_path}")
        
        print(f"🔍 开始监控目录: {self.watch_path}")
        print(f"⏱️  防抖时间: {self.debounce_seconds} 秒")
        print(f"📁 递归监控: {'是' if self.recursive else '否'}\n")
        
        # 启动观察者
        self.observer.schedule(
            self.event_handler, 
            str(self.watch_path), 
            recursive=self.recursive
        )
        self.observer.start()
        
        # 启动防抖检查线程
        self.running = True
        self.debounce_thread = threading.Thread(target=self._debounce_checker, daemon=True)
        self.debounce_thread.start()
    
    def stop(self):
        """停止监控"""
        print("\n⏹️  停止监控...")
        self.running = False
        self.observer.stop()
        self.observer.join()
        if self.debounce_thread:
            self.debounce_thread.join(timeout=2)
        print("✓ 监控已停止")
    
    def on_file_event(self, event: FileSystemEvent):
        """
        文件事件处理
        
        :param event: 文件系统事件
        """
        # 忽略目录事件
        if event.is_directory:
            return
        
        # 对于移动/重命名事件，使用目标路径（src_path 是临时文件名，dest_path 才是真实文件名）
        if hasattr(event, 'dest_path') and event.dest_path:
            file_path = Path(event.dest_path)
        else:
            file_path = Path(event.src_path)

        # 忽略临时文件和隐藏文件
        if file_path.name.startswith('.') or file_path.name.startswith('~'):
            return
        
        # 忽略下载中的临时扩展名（避免对未完成文件打印误导性日志）
        if self.exclude_extensions and file_path.suffix.lower() in self.exclude_extensions:
            return
        
        # 忽略正在处理的文件
        file_path_str = str(file_path.absolute())
        if file_path_str in self.processing_files:
            return
        
        # 记录文件变化时间（只在首次检测到时打印）
        with self.lock:
            is_new = file_path_str not in self.pending_files
            self.pending_files[file_path_str] = time.time()
            
            # 只在首次检测到文件时显示信息
            if is_new:
                print(f"📥 检测到新文件: {file_path.name}")
    
    def _debounce_checker(self):
        """防抖检查线程（定期检查稳定的文件）"""
        while self.running:
            time.sleep(1)  # 每秒检查一次
            
            current_time = time.time()
            stable_files = []
            
            with self.lock:
                # 找出稳定的文件（超过防抖时间且未被修改）
                for file_path, last_modified in list(self.pending_files.items()):
                    if current_time - last_modified >= self.debounce_seconds:
                        # 检查文件是否还存在
                        if Path(file_path).exists():
                            stable_files.append(file_path)
                            self.processing_files.add(file_path)
                        # 从待处理列表移除
                        del self.pending_files[file_path]
            
            # 处理稳定的文件
            for file_path in stable_files:
                try:
                    print(f"✅ 文件稳定，开始处理: {Path(file_path).name}")
                    self.callback(Path(file_path))
                except Exception as e:
                    print(f"❌ 处理文件失败: {Path(file_path).name} - {str(e)}")
                finally:
                    with self.lock:
                        self.processing_files.discard(file_path)


class FileChangeHandler(FileSystemEventHandler):
    """文件变化处理器"""
    
    def __init__(self, watcher: FileWatcher):
        """
        初始化处理器
        
        :param watcher: 文件监控器实例
        """
        super().__init__()
        self.watcher = watcher
    
    def on_created(self, event: FileSystemEvent):
        """文件创建事件"""
        self.watcher.on_file_event(event)
    
    def on_modified(self, event: FileSystemEvent):
        """文件修改事件"""
        self.watcher.on_file_event(event)
    
    def on_moved(self, event: FileSystemEvent):
        """文件移动事件（视为新文件）"""
        self.watcher.on_file_event(event)
