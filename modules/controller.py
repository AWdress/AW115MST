"""
主控制模块
协调各模块完成文件检查与移动流程
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from tqdm import tqdm

from .file_handler import FileHandler
from .p115_client import P115ClientWrapper
from .logger import Logger
from .config_manager import ConfigManager
from .telegram_notifier import TelegramNotifier


class RapidUploadController:
    """秒传检查与移动控制器"""
    
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
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        初始化控制器
        
        :param config_path: 配置文件路径
        """
        # 加载配置
        self.config_manager = ConfigManager(config_path)
        
        # 初始化各模块
        self.file_handler = FileHandler(
            self.config_manager.get_file_processing_config()
        )
        
        p115_config = self.config_manager.get_p115_config()
        performance_config = self.config_manager.get_performance_config()
        p115_config.update(performance_config)
        self.p115_client = P115ClientWrapper(p115_config)
        self.target_pid = int(p115_config.get('target_pid', 0))
        
        self.logger = Logger(self.config_manager.get_logging_config())
        
        # Telegram 通知
        telegram_config = self.config_manager.get('telegram', {})
        self.telegram = TelegramNotifier(telegram_config)
        
        # 断点续传配置
        self.checkpoint_config = self.config_manager.get_checkpoint_config()
        self.checkpoint_file = Path(self.checkpoint_config.get('checkpoint_file', './checkpoint.json'))
        self.processed_files: set = set()
        
        # 重新检测配置
        self.recheck_config = self.config_manager.get('recheck', {})
        self.recheck_file = Path(self.recheck_config.get('recheck_file', './data/recheck.json'))
        self.delay_move_times = self.recheck_config.get('delay_move_times', 3)

        # SQLite 数据库（替代 recheck.json / checkpoint.json）
        from .db_manager import DBManager
        db_path = self.recheck_file.parent / 'aw115mst.db'
        self.db = DBManager(str(db_path))
        self.db.migrate_from_json(self.recheck_file, self.checkpoint_file)
        
        # 统计信息
        self.stats = {
            'total': 0,
            'rapid': 0,
            'non_rapid': 0,
            'failed': 0,
            'moved': 0,
        }
        
        # 登录状态缓存（避免每次定时任务都重复校验）
        self._login_cache_time: Optional[datetime] = None
        self._login_cache_ttl: int = 3600  # 1小时内不重复校验
    
    def _remove_empty_parents(self, path: Path, stop_at: Path):
        """删除文件删除后留下的空目录，向上清理直到 stop_at 为止"""
        current = path.parent
        while current != stop_at and current != current.parent:
            try:
                if current.is_dir() and not any(current.iterdir()):
                    current.rmdir()
                else:
                    break
            except Exception:
                break
            current = current.parent

    def check_login(self) -> bool:
        """检查115登录状态（结果缓存1小时，避免每次定时任务重复校验）"""
        now = datetime.now()
        if self._login_cache_time is not None:
            elapsed = (now - self._login_cache_time).total_seconds()
            if elapsed < self._login_cache_ttl:
                return True  # 缓存仍有效，直接跳过
        
        self.logger.info("检查115登录状态...")
        if self.p115_client.check_login_status():
            user_info = self.p115_client.get_user_info()
            if user_info.get('success'):
                username = user_info.get('data', {}).get('user_name', '未知')
                self.logger.success(f"✓ 登录成功，用户: {username}")
                self._login_cache_time = datetime.now()  # 更新缓存
                return True
        
        self._login_cache_time = None  # 清除缓存，下次强制重新检查
        self.logger.error("✗ 115登录失败，请检查cookies配置")
        return False
    
    def load_checkpoint(self) -> set:
        """加载断点信息（从 SQLite 数据库）"""
        if not self.checkpoint_config.get('enabled', True):
            return set()
        self.processed_files = self.db.get_all_processed()
        self.logger.info(f"加载断点信息: 已处理 {len(self.processed_files)} 个文件")
        return self.processed_files
    
    def save_checkpoint(self):
        """保存断点信息（SQLite 实时写入，此方法保留向后兼容）"""
        pass
    
    def process_file(self, file_path: Path, target_dir: Optional[Path] = None,
                    base_path: Optional[Path] = None, move_files: bool = True) -> Dict[str, Any]:
        """
        处理单个文件
        
        :param file_path: 文件路径
        :param target_dir: 目标目录
        :param base_path: 基础路径（用于保持目录结构）
        :param move_files: 是否移动文件
        :return: 处理结果
        """
        file_path_str = str(file_path.absolute())
        
        # 检查是否已处理
        if file_path_str in self.processed_files:
            return {'skipped': True, 'reason': '已处理'}
        
        try:
            # 获取文件信息
            file_info = self.file_handler.get_file_info(file_path)
            self.logger.debug(f"处理文件: {file_info['name']} ({file_info['size_human']})")
            
            # 计算SHA-1（添加进度提示）
            file_size_mb = file_info['size'] / (1024 * 1024)
            if file_size_mb > 100:  # 大于 100MB 显示进度，每 10% 刷新一次
                print(f"  ⏳ 计算哈希: {file_info['name']} ({file_info['size_human']})...")
                _last_pct = [0]
                def _hash_progress(bytes_read, total, _name=file_info['name']):
                    pct = int(bytes_read * 100 / total)
                    if pct >= _last_pct[0] + 10:
                        _last_pct[0] = pct - (pct % 10)
                        print(f"         {_name}: {_last_pct[0]}%")
                filesha1 = self.file_handler.calculate_sha1(file_path, progress_callback=_hash_progress)
            else:
                filesha1 = self.file_handler.calculate_sha1(file_path)
            self.logger.debug(f"计算SHA-1: {file_info['name']}")
            file_info['sha1'] = filesha1
            
            # 定义二次验证函数
            def read_range_bytes(sign_check: str) -> bytes:
                start, end = map(int, sign_check.split('-'))
                with open(file_path, 'rb') as f:
                    f.seek(start)
                    return f.read(end - start + 1)
            
            # 计算实际目标 pid（保持子目录结构）
            actual_pid = self.target_pid
            if base_path:
                try:
                    rel_parts = file_path.parent.relative_to(base_path).parts
                    if rel_parts:
                        actual_pid = self.p115_client.ensure_remote_path(rel_parts, self.target_pid)
                except Exception as e:
                    self.logger.warning(f"⚠ 建立115子目录失败，回退到根目录: {e}")
            
            # 检查秒传状态
            self.logger.debug(f"检查秒传状态: {file_info['name']}")
            result = self.p115_client.check_rapid_upload(
                filename=file_info['name'],
                filesize=file_info['size'],
                filesha1=filesha1,
                read_range_bytes_or_hash=read_range_bytes,
                pid=actual_pid,
            )
            
            if not result['success']:
                # 检查失败
                self.stats['failed'] += 1
                file_info['status'] = '检查失败'
                file_info['note'] = result.get('message', '')
                file_info['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.logger.add_failed_file(file_info)
                self.logger.error(f"✗ {file_info['name']}: {result.get('message', '')}")
                return {'success': False, 'error': result.get('message', '')}
            
            # 记录处理状态
            file_info['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if result['can_rapid']:
                # 可以秒传
                self.stats['rapid'] += 1
                file_info['status'] = '可秒传'
                file_info['note'] = f"状态码: {result['status']}"
                
                # 移动文件
                if move_files and target_dir:
                    try:
                        delete_after_rapid = self.config_manager.get('file_processing.move_strategy.delete_after_rapid', False)
                        delete_source = self.config_manager.get('file_processing.move_strategy.delete_source_after_rapid', False)
                        use_copy = self.config_manager.get('file_processing.move_strategy.use_copy', False)
                        keep_structure = self.config_manager.get('file_processing.move_strategy.create_subdirs', True)
                        new_path = self.file_handler.move_or_copy_file(
                            file_path, target_dir,
                            keep_structure=keep_structure,
                            base_path=base_path,
                            use_copy=use_copy
                        )
                        file_info['target_path'] = str(new_path)
                        self.stats['moved'] += 1
                        suffix_parts = []
                        if delete_after_rapid:
                            new_path.unlink(missing_ok=True)
                            self._remove_empty_parents(new_path, target_dir)
                            suffix_parts.append("暂存副本已删除")
                        else:
                            action = "已复制" if use_copy else "已移动"
                            suffix_parts.append(f"{action}到 {target_dir.name}/")
                        if delete_source and use_copy:
                            file_path.unlink()
                            self._remove_empty_parents(file_path, base_path or file_path.parent)
                            suffix_parts.append("原文件已删除")
                        self.logger.success(f"✓ [秒传成功] {file_info['name']}: 115已入库，{'，'.join(suffix_parts)}")
                    except Exception as e:
                        file_info['note'] += f" | 操作失败: {str(e)}"
                        self.logger.error(f"✗ {file_info['name']}: 操作失败 - {str(e)}")
                else:
                    self.logger.success(f"✓ [秒传成功] {file_info['name']}: 115已入库")
                
                self.logger.add_rapid_file(file_info)
                
            else:
                # 不可秒传
                self.stats['non_rapid'] += 1
                file_info['status'] = '不可秒传'
                file_info['note'] = f"状态码: {result['status']}"
                
                # 根据配置决定是否移动
                keep_in_place = self.config_manager.get('file_processing.move_strategy.keep_non_rapid_in_place', True)
                if not keep_in_place and move_files:
                    non_rapid_dir = Path(self.config_manager.get('file_processing.move_strategy.non_rapid_files_dir', './待秒传'))
                    try:
                        keep_structure = self.config_manager.get('file_processing.move_strategy.create_subdirs', True)
                        use_copy = self.config_manager.get('file_processing.move_strategy.use_copy', False)
                        new_path = self.file_handler.move_or_copy_file(
                            file_path, non_rapid_dir,
                            keep_structure=keep_structure,
                            base_path=base_path,
                            use_copy=use_copy
                        )
                        file_info['target_path'] = str(new_path)
                        action = "已复制" if use_copy else "已移动"
                        self.logger.info(f"○ {file_info['name']}: 不可秒传，{action}到暂存目录")
                    except Exception as e:
                        file_info['note'] += f" | 移动失败: {str(e)}"
                        self.logger.error(f"✗ {file_info['name']}: 移动失败 - {str(e)}")
                else:
                    self.logger.info(f"○ {file_info['name']}: 不可秒传")
                
                self.logger.add_non_rapid_file(file_info)
            
            # 标记为已处理
            self.processed_files.add(file_path_str)
            self.db.mark_processed(file_path_str)
            
            return {'success': True, 'can_rapid': result['can_rapid']}
            
        except Exception as e:
            self.stats['failed'] += 1
            self.logger.error(f"✗ {file_path.name}: 处理异常 - {str(e)}")
            self.logger.add_failed_file({
                'path': file_path_str,
                'status': '处理异常',
                'note': str(e),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            })
            return {'success': False, 'error': str(e)}
    
    def process_directory(self, input_path: str | Path, target_path: Optional[str | Path] = None,
                         recursive: bool = True, move_files: bool = True) -> Dict[str, Any]:
        """
        处理目录
        
        :param input_path: 输入路径（文件或目录）
        :param target_path: 目标路径（可秒传文件的目标目录）
        :param recursive: 是否递归处理子目录
        :param move_files: 是否移动文件
        :return: 处理结果
        """
        input_path = Path(input_path)
        
        # 检查登录状态
        if not self.check_login():
            return {'success': False, 'error': '115登录失败'}
        
        # 加载断点
        self.load_checkpoint()
        
        # 确定目标目录
        if target_path:
            target_dir = Path(target_path)
        else:
            target_dir = Path(self.config_manager.get('file_processing.move_strategy.rapid_files_dir', './可秒传'))
        
        # 扫描文件
        self.logger.info(f"扫描文件: {input_path}")
        files = self.file_handler.scan_files(input_path, recursive=recursive)
        
        # 过滤已处理的文件
        files = [f for f in files if str(f.absolute()) not in self.processed_files]
        
        if not files:
            self.logger.warning("没有找到需要处理的文件")
            return {'success': True, 'total': 0}
        
        self.logger.info(f"找到 {len(files)} 个文件待处理")
        self.stats['total'] = len(files)
        
        # 确定基础路径（用于保持目录结构）
        base_path = input_path if input_path.is_dir() else input_path.parent
        
        # 处理文件
        start_time = datetime.now()
        auto_save_interval = self.checkpoint_config.get('auto_save_interval', 10)
        
        with tqdm(total=len(files), desc="处理进度", unit="文件") as pbar:
            for idx, file_path in enumerate(files, 1):
                self.process_file(file_path, target_dir, base_path, move_files)
                pbar.update(1)
                
                # 定期保存断点
                if idx % auto_save_interval == 0:
                    self.save_checkpoint()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 保存最终断点
        self.save_checkpoint()
        
        # 打印摘要
        self.logger.print_summary(start_time, end_time)
        
        # 发送 Telegram 通知
        self.telegram.notify_complete(self.stats, duration)
        
        return {
            'success': True,
            'total': self.stats['total'],
            'rapid_count': self.stats['rapid'],
            'non_rapid_count': self.stats['non_rapid'],
            'failed_count': self.stats['failed'],
            'moved_count': self.stats['moved'],
        }
    
    def check_only(self, input_path: str | Path, recursive: bool = True) -> Dict[str, Any]:
        """
        仅检查秒传状态，不移动文件
        
        :param input_path: 输入路径
        :param recursive: 是否递归
        :return: 检查结果
        """
        return self.process_directory(input_path, target_path=None, recursive=recursive, move_files=False)

    def recheck_non_rapid_files(self) -> Dict[str, Any]:
        """
        重新检测 non_rapid 目录中的文件
        检查是否有文件变成可秒传
        
        :return: 处理结果
        """
        try:
            # 获取配置
            recheck_config = self.config_manager.get('recheck', {})
            if not recheck_config.get('enabled', True):
                return {
                    'success': False,
                    'error': '重新检测功能未启用，请在 config.yaml 中启用'
                }
            
            max_recheck_times = recheck_config.get('max_recheck_times', 10)
            
            # 获取 待秒传 目录
            move_strategy = self.config_manager.get('file_processing.move_strategy', {})
            non_rapid_dir = Path(move_strategy.get('non_rapid_files_dir', './待秒传'))
            
            if not non_rapid_dir.exists():
                return {
                    'success': False,
                    'error': f'待秒传 目录不存在: {non_rapid_dir}'
                }
            
            # 扫描文件
            self.logger.info(f"扫描 待秒传 目录: {non_rapid_dir}")
            files = self.file_handler.scan_files(non_rapid_dir, recursive=True)
            
            if not files:
                self.logger.warning("待秒传 目录中没有文件")
                return {
                    'success': True,
                    'total': 0,
                    'now_rapid': 0,
                    'still_non_rapid': 0,
                    'skipped': 0
                }
            
            self.logger.info(f"找到 {len(files)} 个文件待重新检测")
            
            # 统计
            stats = {
                'total': len(files),
                'now_rapid': 0,
                'still_non_rapid': 0,
                'skipped': 0
            }
            
            # 处理文件
            rapid_dir = Path(move_strategy.get('rapid_files_dir', './可秒传'))
            rapid_dir.mkdir(parents=True, exist_ok=True)
            
            with tqdm(total=len(files), desc="重新检测进度", unit="文件") as pbar:
                for file_path in files:
                    file_key = str(file_path.absolute())
                    record = self.db.get_record(file_key) or {}
                    check_count = record.get('check_count', 0)

                    # 已真实上传过，跳过秒传检测
                    if record.get('uploaded'):
                        self.logger.debug(f"⊛ {file_path.name}: 已真实上传，跳过")
                        stats['skipped'] += 1
                        pbar.update(1)
                        continue

                    # 上传已失败过的文件，不再重复尝试（避免无限重试和重复通知）
                    if record.get('upload_failed'):
                        self.logger.debug(f"⊛ {file_path.name}: 上传曾失败，跳过")
                        pbar.update(1)
                        continue

                    # 检查是否超过最大检测次数（max_recheck_times 为 0 表示不限次数）
                    if max_recheck_times > 0 and check_count >= max_recheck_times:
                        upload_config = self.config_manager.get('upload', {})
                        if upload_config.get('enabled', False):
                            try:
                                upload_pid = self.target_pid
                                try:
                                    rel_parts = file_path.parent.relative_to(non_rapid_dir).parts
                                    if rel_parts:
                                        upload_pid = self.p115_client.ensure_remote_path(rel_parts, self.target_pid)
                                except Exception as e:
                                    self.logger.warning(f"⚠ 建立115子目录失败，回退到根目录: {e}")
                                self.logger.info(f"⬆ {file_path.name}: 重检达到上限({max_recheck_times}次)，开始上传...")
                                up_result = self.p115_client.upload_file(file_path, pid=upload_pid)
                                if up_result['success']:
                                    self.logger.success(f"✓ [上传成功] {file_path.name}: 已上传到115")
                                    stats['now_rapid'] += 1
                                    delete_after_upload = upload_config.get('delete_after_upload', True)
                                    source_input_key = record.get('source_input_key')
                                    if delete_after_upload:
                                        file_path.unlink(missing_ok=True)
                                        self._remove_empty_parents(file_path, non_rapid_dir)
                                        self.db.delete_record(file_key)
                                    else:
                                        self.db.upsert_record(file_key, uploaded=True)
                                    if source_input_key:
                                        src_rec = self.db.get_record(source_input_key)
                                        if src_rec:
                                            self.db.upsert_record(source_input_key,
                                                uploaded=True,
                                                non_rapid_dispatched=False,
                                                non_rapid_path=None,
                                            )
                                    if self.telegram.config.get('notify_on_rapid', False):
                                        self.telegram.notify_rapid_file(file_path.name, action='上传')
                                else:
                                    self.logger.error(f"✗ {file_path.name}: 上传失败 - {up_result.get('error', '')}")
                                    self.db.upsert_record(file_key, upload_failed=1)
                                    stats['skipped'] += 1
                            except Exception as e:
                                self.logger.error(f"✗ {file_path.name}: 上传异常 - {e}")
                                self.db.upsert_record(file_key, upload_failed=1)
                                stats['skipped'] += 1
                        else:
                            self.logger.info(f"⊛ {file_path.name}: 已达到最大检测次数({max_recheck_times})，跳过")
                            stats['skipped'] += 1
                        pbar.update(1)
                        continue

                    # 重新检测
                    result = self.check_and_record(file_path, base_path=non_rapid_dir)

                    if not result.get('success'):
                        stats['skipped'] += 1
                        pbar.update(1)
                        continue

                    # 确保 location 标记为 non_rapid
                    self.db.upsert_record(file_key, location='non_rapid')

                    if result['can_rapid']:
                        # 变成可秒传，移动到 rapid 目录
                        try:
                            delete_after_rapid = self.config_manager.get('file_processing.move_strategy.delete_after_rapid', False)
                            use_copy = self.config_manager.get('file_processing.move_strategy.use_copy', False)
                            keep_structure = self.config_manager.get('file_processing.move_strategy.create_subdirs', True)
                            new_path = self.file_handler.move_or_copy_file(
                                file_path, rapid_dir,
                                keep_structure=keep_structure,
                                base_path=non_rapid_dir,
                                use_copy=use_copy
                            )
                            suffix_parts = []
                            if delete_after_rapid:
                                new_path.unlink(missing_ok=True)
                                self._remove_empty_parents(new_path, rapid_dir)
                                suffix_parts.append("暂存副本已删除")
                            else:
                                action = "已复制" if use_copy else "已移动"
                                suffix_parts.append(f"{action}到 {rapid_dir.name}/")
                            if use_copy and file_path.exists():
                                file_path.unlink()
                                self._remove_empty_parents(file_path, non_rapid_dir)
                                suffix_parts.append("待秒传原件已清理")
                            self.logger.success(f"✓ [秒传成功] {file_path.name}: 现在可秒传！115已入库，{'，'.join(suffix_parts)}")
                            stats['now_rapid'] += 1
                            self.db.delete_record(file_key)
                            if self.telegram.config.get('notify_on_rapid', False):
                                self.telegram.notify_rapid_file(file_path.name)
                        except Exception as e:
                            self.logger.error(f"✗ {file_path.name}: 操作失败: {e}")
                    else:
                        self.logger.info(f"○ {file_path.name}: 仍不可秒传")
                        stats['still_non_rapid'] += 1

                    pbar.update(1)
            
            # 输出统计
            print("\n" + "=" * 60)
            print("重新检测完成！")
            print("=" * 60)
            print(f"总文件数: {stats['total']}")
            print(f"✓ 现在可秒传: {stats['now_rapid']} 个")
            print(f"○ 仍不可秒传: {stats['still_non_rapid']} 个")
            print(f"⊗ 跳过检测: {stats['skipped']} 个")
            print("=" * 60)
            
            # 发送 Telegram 通知
            self.telegram.notify_recheck_complete(stats)
            
            return {
                'success': True,
                **stats
            }
            
        except Exception as e:
            self.logger.error(f"重新检测失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }

    def check_and_record(self, file_path: Path, base_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        检查文件秒传状态并记录（不移动文件）
        用于实时监控和延迟移动策略
        
        :param file_path: 文件路径
        :return: 检查结果
        """
        try:
            # 获取文件信息
            file_info = self.file_handler.get_file_info(file_path)
            
            # 计算SHA-1（添加进度提示）
            file_size_mb = file_info['size'] / (1024 * 1024)
            if file_size_mb > 100:  # 大于 100MB 显示进度，每 10% 刷新一次
                print(f"  ⏳ 计算哈希: {file_info['name']} ({file_info['size_human']})...")
                _last_pct2 = [0]
                def _hash_progress2(bytes_read, total, _name=file_info['name']):
                    pct = int(bytes_read * 100 / total)
                    if pct >= _last_pct2[0] + 10:
                        _last_pct2[0] = pct - (pct % 10)
                        print(f"         {_name}: {_last_pct2[0]}%")
                filesha1 = self.file_handler.calculate_sha1(file_path, progress_callback=_hash_progress2)
            else:
                filesha1 = self.file_handler.calculate_sha1(file_path)
            
            # 定义二次验证函数
            def read_range_bytes(sign_check: str) -> bytes:
                start, end = map(int, sign_check.split('-'))
                with open(file_path, 'rb') as f:
                    f.seek(start)
                    return f.read(end - start + 1)
            
            # 计算实际目标 pid（保持子目录结构）
            actual_pid = self.target_pid
            if base_path:
                try:
                    rel_parts = file_path.parent.relative_to(base_path).parts
                    if rel_parts:
                        actual_pid = self.p115_client.ensure_remote_path(rel_parts, self.target_pid)
                except Exception as e:
                    self.logger.warning(f"⚠ 建立115子目录失败，回退到根目录: {e}")
            
            # 检查秒传状态（始终传入 read_range_bytes，支持任意大小文件的二次验证）
            result = self.p115_client.check_rapid_upload(
                filename=file_info['name'],
                filesize=file_info['size'],
                filesha1=filesha1,
                read_range_bytes_or_hash=read_range_bytes,
                pid=actual_pid,
            )
            
            if not result['success']:
                return {'success': False, 'error': result.get('message', '')}
            
            # 记录检测结果（使用 SQLite 替代 JSON 文件）
            file_key = str(file_path.absolute())
            current_time = datetime.now().timestamp()

            existing = self.db.get_record(file_key) or {}
            self.db.upsert_record(
                file_key,
                sha1=filesha1,
                size=file_info['size'],
                last_status='rapid' if result['can_rapid'] else 'non_rapid',
                check_count=existing.get('check_count', 0) + 1,
                first_check_time=existing.get('first_check_time', current_time),
                last_check_time=current_time,
                location=existing.get('location', 'input'),
            )

            return {
                'success': True,
                'can_rapid': result['can_rapid'],
                'check_count': existing.get('check_count', 0) + 1,
            }
            
        except Exception as e:
            self.logger.error(f"检查文件失败: {file_path.name} - {e}")
            return {'success': False, 'error': str(e)}
    
    def process_input_with_delay(self) -> Dict[str, Any]:
        """
        处理 input 目录中的文件（延迟移动策略）
        - 可秒传的文件：立即移动到 rapid/
        - 不可秒传的文件：检测 N 次后才移动到 non_rapid/
        
        :return: 处理结果
        """
        try:
            input_path = Path(self.config_manager.get('file_processing.input_dir', './待检测'))
            if not input_path.exists():
                return {'success': False, 'error': f'输入目录不存在: {input_path}'}
            
            # 检查登录状态
            if not self.check_login():
                return {'success': False, 'error': '115登录失败'}
            
            # 扫描 input 目录中的所有文件
            files = self.file_handler.scan_files(input_path, recursive=True)
            
            if not files:
                return {
                    'success': True,
                    'rapid_moved': 0,
                    'non_rapid_moved': 0,
                    'pending': 0
                }
            
            # 统计
            stats = {
                'rapid_moved': 0,
                'non_rapid_moved': 0,
                'pending': 0
            }
            
            # 目标目录
            move_strategy = self.config_manager.get('file_processing.move_strategy', {})
            rapid_dir = Path(move_strategy.get('rapid_files_dir', './可秒传'))
            non_rapid_dir = Path(move_strategy.get('non_rapid_files_dir', './待秒传'))
            rapid_dir.mkdir(parents=True, exist_ok=True)
            non_rapid_dir.mkdir(parents=True, exist_ok=True)
            use_copy = self.config_manager.get('file_processing.move_strategy.use_copy', False)
            
            for file_path in files:
                file_key = str(file_path.absolute())
                record = self.db.get_record(file_key) or {}
                
                # 跳过已处理文件（复制模式可秒传/已上传/副本存在）
                if record.get('processed') and record.get('last_status') == 'rapid':
                    continue
                if record.get('uploaded'):
                    continue
                if record.get('non_rapid_dispatched'):
                    non_rapid_path = record.get('non_rapid_path', '')
                    if non_rapid_path and Path(non_rapid_path).exists():
                        continue  # 副本存在，由 recheck_non_rapid_files 处理
                    if record.get('uploaded'):
                        continue
                
                # 若 DB 中已有缓存结果且文件大小未变，直接使用，避免重复计算哈希和调用 115 API
                cached_status = record.get('last_status')
                cached_size = record.get('size')
                if (cached_status in ('rapid', 'non_rapid')
                        and cached_size is not None
                        and file_path.exists()
                        and cached_size == file_path.stat().st_size):
                    result = {
                        'success': True,
                        'can_rapid': cached_status == 'rapid',
                        'check_count': record.get('check_count', 0),
                    }
                else:
                    # 无缓存或文件已变化，重新检查（check_and_record 内部会更新并写入磁盘）
                    result = self.check_and_record(file_path, base_path=input_path)
                
                if not result.get('success'):
                    continue
                
                check_count = result.get('check_count', 0)
                can_rapid = result.get('can_rapid', False)
                
                if can_rapid:
                    # 可秒传：移动/复制到 可秒传/，按开关决定是否删除副本和源文件
                    try:
                        delete_after_rapid = self.config_manager.get('file_processing.move_strategy.delete_after_rapid', False)
                        delete_source = self.config_manager.get('file_processing.move_strategy.delete_source_after_rapid', False)
                        keep_structure = self.config_manager.get('file_processing.move_strategy.create_subdirs', True)
                        new_path = self.file_handler.move_or_copy_file(
                            file_path, rapid_dir,
                            keep_structure=keep_structure,
                            base_path=input_path,
                            use_copy=use_copy
                        )
                        suffix_parts = []
                        if delete_after_rapid:
                            new_path.unlink(missing_ok=True)
                            self._remove_empty_parents(new_path, rapid_dir)
                            suffix_parts.append("暂存副本已删除")
                        else:
                            action = "已复制" if use_copy else "已移动"
                            suffix_parts.append(f"{action}到 {rapid_dir.name}/")
                        if delete_source and use_copy:
                            file_path.unlink()
                            self._remove_empty_parents(file_path, input_path)
                            suffix_parts.append("原文件已删除")
                        self.logger.success(f"✓ [秒传成功] {file_path.name}: 115已入库，{'，'.join(suffix_parts)}")
                        stats['rapid_moved'] += 1

                        # 直接写 DB（无需批量保存）
                        if use_copy and not delete_source:
                            self.db.upsert_record(file_key,
                                processed=True,
                                last_status='rapid',
                                processed_time=datetime.now().timestamp(),
                                target_path=str(new_path),
                            )
                        else:
                            self.db.delete_record(file_key)
                        
                        # 发送 Telegram 通知
                        if self.telegram.config.get('notify_on_rapid', False):
                            self.telegram.notify_rapid_file(file_path.name)
                            
                    except Exception as e:
                        self.logger.error(f"✗ {file_path.name}: 操作失败 - {e}")
                        
                else:
                    # 不可秒传：立即移动/复制到 待秒传/
                    try:
                        keep_structure = self.config_manager.get('file_processing.move_strategy.create_subdirs', True)
                        new_path = self.file_handler.move_or_copy_file(
                            file_path, non_rapid_dir,
                            keep_structure=keep_structure,
                            base_path=input_path,
                            use_copy=use_copy
                        )
                        action = "已复制" if use_copy else "已移动"
                        self.logger.info(f"○ {file_path.name}: 不可秒传，{action}到 {non_rapid_dir.name}/")
                        stats['non_rapid_moved'] += 1
                        non_rapid_key = str(new_path.absolute())
                        if use_copy:
                            # 为 待秒传/ 副本建立独立记录，源文件标记已分发
                            src = self.db.get_record(file_key) or {}
                            new_fields = {k: v for k, v in src.items() if k != 'file_key'}
                            new_fields.update({
                                'location': 'non_rapid',
                                'check_count': 0,
                                'source_input_key': file_key,
                                'non_rapid_dispatched': False,
                                'non_rapid_path': None,
                            })
                            self.db.upsert_record(non_rapid_key, **new_fields)
                            self.db.upsert_record(file_key,
                                non_rapid_dispatched=True,
                                non_rapid_path=non_rapid_key,
                            )
                        else:
                            self.db.rename_record(file_key, non_rapid_key,
                                location='non_rapid',
                                check_count=0,
                            )
                    except Exception as e:
                        self.logger.error(f"✗ {file_path.name}: 移动失败 - {e}")
            
            return {
                'success': True,
                **stats
            }
            
        except Exception as e:
            self.logger.error(f"处理 input 目录失败: {e}")
            return {'success': False, 'error': str(e)}

    def clean_processed_records(self) -> Dict[str, Any]:
        """
        清理已处理文件的记录
        用于复制模式下清理已复制文件的标记
        
        :return: 清理结果
        """
        try:
            all_records = self.db.get_all_records()
            total_before = len(all_records)
            cleaned_count = 0
            
            # 清理已处理的记录
            for file_key, record in all_records.items():
                if record.get('processed'):
                    self.db.delete_record(file_key)
                    cleaned_count += 1
            
            total_after = total_before - cleaned_count
            print(f"清理前记录数: {total_before}")
            print(f"清理后记录数: {total_after}")
            print(f"已清理: {cleaned_count} 条")
            
            return {
                'success': True,
                'cleaned': cleaned_count,
                'total_before': total_before,
                'total_after': total_after
            }
            
        except Exception as e:
            self.logger.error(f"清理记录失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
