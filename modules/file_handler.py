"""
文件处理模块
负责文件扫描、哈希计算、文件移动等操作
"""

import os
import shutil
from pathlib import Path
from hashlib import sha1
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime


class FileHandler:
    """文件处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化文件处理器
        
        :param config: 文件处理配置
        """
        self.config = config
        self.filters = config.get('filters', {})
        self.move_strategy = config.get('move_strategy', {})
        self.hash_chunk_size = config.get('hash_chunk_size', 8192)
    
    def scan_files(self, path: str | Path, recursive: bool = True) -> List[Path]:
        """
        扫描文件或文件夹
        
        :param path: 文件或文件夹路径
        :param recursive: 是否递归扫描子目录
        :return: 文件路径列表
        """
        path = Path(path)
        files = []
        
        if path.is_file():
            if self._should_process_file(path):
                files.append(path)
        elif path.is_dir():
            if recursive:
                for file_path in path.rglob('*'):
                    if file_path.is_file() and self._should_process_file(file_path):
                        files.append(file_path)
            else:
                for file_path in path.iterdir():
                    if file_path.is_file() and self._should_process_file(file_path):
                        files.append(file_path)
        
        return files
    
    def _should_process_file(self, file_path: Path) -> bool:
        """
        判断文件是否应该被处理
        
        :param file_path: 文件路径
        :return: 是否处理
        """
        # 检查文件大小
        try:
            file_size = file_path.stat().st_size
        except OSError:
            return False
        
        min_size = self.filters.get('min_size', 0)
        max_size = self.filters.get('max_size', float('inf'))
        
        if file_size < min_size or file_size > max_size:
            return False
        
        # 检查文件扩展名
        ext = file_path.suffix.lower()
        
        # 排除列表
        exclude_exts = self.filters.get('exclude_extensions', [])
        if ext in exclude_exts:
            return False
        
        # 包含列表（如果指定了包含列表，则只处理列表中的扩展名）
        include_exts = self.filters.get('include_extensions', [])
        if include_exts and ext not in include_exts:
            return False
        
        return True
    
    def calculate_sha1(self, file_path: Path, progress_callback: Optional[Callable] = None) -> str:
        """
        计算文件的SHA-1哈希值
        
        :param file_path: 文件路径
        :param progress_callback: 进度回调函数
        :return: SHA-1哈希值（大写）
        """
        sha1_hash = sha1()
        file_size = file_path.stat().st_size
        bytes_read = 0
        
        with open(file_path, 'rb') as f:
            while chunk := f.read(self.hash_chunk_size):
                sha1_hash.update(chunk)
                bytes_read += len(chunk)
                
                if progress_callback:
                    progress_callback(bytes_read, file_size)
        
        return sha1_hash.hexdigest().upper()
    
    def get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """
        获取文件信息
        
        :param file_path: 文件路径
        :return: 文件信息字典
        """
        stat = file_path.stat()
        
        return {
            'path': str(file_path.absolute()),
            'name': file_path.name,
            'size': stat.st_size,
            'size_human': self._format_size(stat.st_size),
            'mtime': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'extension': file_path.suffix.lower(),
        }
    
    @staticmethod
    def _format_size(size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    def move_file(self, source: Path, target_dir: Path, keep_structure: bool = False, 
                  base_path: Optional[Path] = None) -> Path:
        """
        移动文件到目标目录（保持文件夹结构）
        
        :param source: 源文件路径
        :param target_dir: 目标目录
        :param keep_structure: 是否保持目录结构
        :param base_path: 基础路径（用于计算相对路径）
        :return: 目标文件路径
        """
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        
        if keep_structure and base_path:
            # 保持目录结构
            relative_path = source.relative_to(base_path)
            target_path = target_dir / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            # 直接移动到目标目录
            target_path = target_dir / source.name
        
        # 处理文件名冲突
        if target_path.exists():
            base_name = target_path.stem
            extension = target_path.suffix
            counter = 1
            while target_path.exists():
                target_path = target_path.parent / f"{base_name}_{counter}{extension}"
                counter += 1
        
        # 移动文件
        shutil.move(str(source), str(target_path))
        
        # 清理空文件夹
        self._cleanup_empty_dirs(source.parent, base_path)
        
        return target_path
    
    def _cleanup_empty_dirs(self, dir_path: Path, stop_at: Optional[Path] = None):
        """
        清理空文件夹（递归向上）
        
        :param dir_path: 要检查的目录
        :param stop_at: 停止清理的目录（不删除此目录及其父目录）
        """
        try:
            # 如果到达停止目录，不再继续
            if stop_at and dir_path.resolve() == stop_at.resolve():
                return
            
            # 检查目录是否为空
            if dir_path.exists() and dir_path.is_dir():
                # 获取目录内容（排除隐藏文件）
                contents = list(dir_path.iterdir())
                
                if not contents:
                    # 目录为空，删除它
                    dir_path.rmdir()
                    # 递归检查父目录
                    if dir_path.parent != dir_path:
                        self._cleanup_empty_dirs(dir_path.parent, stop_at)
        except (OSError, PermissionError):
            # 忽略权限错误或其他系统错误
            pass
    
    def copy_file(self, source: Path, target_dir: Path, keep_structure: bool = False,
                  base_path: Optional[Path] = None) -> Path:
        """
        复制文件到目标目录
        
        :param source: 源文件路径
        :param target_dir: 目标目录
        :param keep_structure: 是否保持目录结构
        :param base_path: 基础路径
        :return: 目标文件路径
        """
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        
        if keep_structure and base_path:
            relative_path = source.relative_to(base_path)
            target_path = target_dir / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            target_path = target_dir / source.name
        
        # 处理文件名冲突
        if target_path.exists():
            base_name = target_path.stem
            extension = target_path.suffix
            counter = 1
            while target_path.exists():
                target_path = target_path.parent / f"{base_name}_{counter}{extension}"
                counter += 1
        
        # 复制文件
        shutil.copy2(str(source), str(target_path))
        
        return target_path
