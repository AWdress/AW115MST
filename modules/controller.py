"""
主控制模块
协调各模块完成文件检查与移动流程
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from tqdm import tqdm

from .file_handler import FileHandler
from .p115_client import P115ClientWrapper
from .logger import Logger
from .config_manager import ConfigManager


class RapidUploadController:
    """秒传检查与移动控制器"""
    
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
        
        self.logger = Logger(self.config_manager.get_logging_config())
        
        # 断点续传配置
        self.checkpoint_config = self.config_manager.get_checkpoint_config()
        self.checkpoint_file = Path(self.checkpoint_config.get('checkpoint_file', './checkpoint.json'))
        self.processed_files: set = set()
        
        # 统计信息
        self.stats = {
            'total': 0,
            'rapid': 0,
            'non_rapid': 0,
            'failed': 0,
            'moved': 0,
        }
    
    def check_login(self) -> bool:
        """检查115登录状态"""
        self.logger.info("检查115登录状态...")
        if self.p115_client.check_login_status():
            user_info = self.p115_client.get_user_info()
            if user_info.get('success'):
                username = user_info.get('data', {}).get('user_name', '未知')
                self.logger.success(f"✓ 登录成功，用户: {username}")
                return True
        
        self.logger.error("✗ 115登录失败，请检查cookies配置")
        return False
    
    def load_checkpoint(self) -> set:
        """加载断点信息"""
        if not self.checkpoint_config.get('enabled', True):
            return set()
        
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.processed_files = set(data.get('processed_files', []))
                    self.logger.info(f"加载断点信息: 已处理 {len(self.processed_files)} 个文件")
                    return self.processed_files
            except Exception as e:
                self.logger.warning(f"加载断点信息失败: {e}")
        
        return set()
    
    def save_checkpoint(self):
        """保存断点信息"""
        if not self.checkpoint_config.get('enabled', True):
            return
        
        try:
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'processed_files': list(self.processed_files),
                    'timestamp': datetime.now().isoformat(),
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.warning(f"保存断点信息失败: {e}")
    
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
            
            # 计算SHA-1
            self.logger.debug(f"计算SHA-1: {file_info['name']}")
            filesha1 = self.file_handler.calculate_sha1(file_path)
            file_info['sha1'] = filesha1
            
            # 定义二次验证函数
            def read_range_bytes(sign_check: str) -> bytes:
                start, end = map(int, sign_check.split('-'))
                with open(file_path, 'rb') as f:
                    f.seek(start)
                    return f.read(end - start + 1)
            
            # 检查秒传状态
            self.logger.debug(f"检查秒传状态: {file_info['name']}")
            result = self.p115_client.check_rapid_upload(
                filename=file_info['name'],
                filesize=file_info['size'],
                filesha1=filesha1,
                read_range_bytes_or_hash=read_range_bytes if file_info['size'] >= 1048576 else None,
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
                        keep_structure = self.config_manager.get('file_processing.move_strategy.create_subdirs', True)
                        new_path = self.file_handler.move_file(
                            file_path, target_dir,
                            keep_structure=keep_structure,
                            base_path=base_path
                        )
                        file_info['target_path'] = str(new_path)
                        self.stats['moved'] += 1
                        self.logger.success(f"✓ {file_info['name']}: 可秒传，已移动")
                    except Exception as e:
                        file_info['note'] += f" | 移动失败: {str(e)}"
                        self.logger.error(f"✗ {file_info['name']}: 移动失败 - {str(e)}")
                else:
                    self.logger.success(f"✓ {file_info['name']}: 可秒传")
                
                self.logger.add_rapid_file(file_info)
                
            else:
                # 不可秒传
                self.stats['non_rapid'] += 1
                file_info['status'] = '不可秒传'
                file_info['note'] = f"状态码: {result['status']}"
                
                # 根据配置决定是否移动
                keep_in_place = self.config_manager.get('file_processing.move_strategy.keep_non_rapid_in_place', True)
                if not keep_in_place and move_files:
                    non_rapid_dir = Path(self.config_manager.get('file_processing.move_strategy.non_rapid_files_dir', './non_rapid'))
                    try:
                        keep_structure = self.config_manager.get('file_processing.move_strategy.create_subdirs', True)
                        new_path = self.file_handler.move_file(
                            file_path, non_rapid_dir,
                            keep_structure=keep_structure,
                            base_path=base_path
                        )
                        file_info['target_path'] = str(new_path)
                        self.logger.info(f"○ {file_info['name']}: 不可秒传，已移动到暂存目录")
                    except Exception as e:
                        file_info['note'] += f" | 移动失败: {str(e)}"
                        self.logger.error(f"✗ {file_info['name']}: 移动失败 - {str(e)}")
                else:
                    self.logger.info(f"○ {file_info['name']}: 不可秒传")
                
                self.logger.add_non_rapid_file(file_info)
            
            # 标记为已处理
            self.processed_files.add(file_path_str)
            
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
            target_dir = Path(self.config_manager.get('file_processing.move_strategy.rapid_files_dir', './rapid_files'))
        
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
        
        # 保存最终断点
        self.save_checkpoint()
        
        # 打印摘要
        self.logger.print_summary(start_time, end_time)
        
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
            
            recheck_file = Path(recheck_config.get('recheck_file', './recheck.json'))
            recheck_interval = recheck_config.get('recheck_interval', 86400)  # 默认24小时
            max_recheck_times = recheck_config.get('max_recheck_times', 10)
            
            # 加载重新检测记录
            recheck_data = {}
            if recheck_file.exists():
                with open(recheck_file, 'r', encoding='utf-8') as f:
                    recheck_data = json.load(f)
            
            # 获取 non_rapid 目录
            move_strategy = self.config_manager.get('file_processing.move_strategy', {})
            non_rapid_dir = Path(move_strategy.get('non_rapid_files_dir', './non_rapid'))
            
            if not non_rapid_dir.exists():
                return {
                    'success': False,
                    'error': f'non_rapid 目录不存在: {non_rapid_dir}'
                }
            
            # 扫描文件
            self.logger.info(f"扫描 non_rapid 目录: {non_rapid_dir}")
            files = self.file_handler.scan_files(non_rapid_dir, recursive=True)
            
            if not files:
                self.logger.warning("non_rapid 目录中没有文件")
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
            rapid_dir = Path(move_strategy.get('rapid_files_dir', './rapid'))
            rapid_dir.mkdir(parents=True, exist_ok=True)
            
            current_time = datetime.now().timestamp()
            
            with tqdm(total=len(files), desc="重新检测进度", unit="文件") as pbar:
                for file_path in files:
                    file_key = str(file_path)
                    
                    # 检查重新检测记录
                    if file_key in recheck_data:
                        record = recheck_data[file_key]
                        last_check_time = record.get('last_check_time', 0)
                        check_count = record.get('check_count', 0)
                        
                        # 检查是否超过最大检测次数
                        if check_count >= max_recheck_times:
                            self.logger.info(f"⊗ {file_path.name}: 已达到最大检测次数({max_recheck_times})，跳过")
                            stats['skipped'] += 1
                            pbar.update(1)
                            continue
                        
                        # 检查是否到达检测间隔
                        if current_time - last_check_time < recheck_interval:
                            remaining = int((recheck_interval - (current_time - last_check_time)) / 3600)
                            self.logger.info(f"⊗ {file_path.name}: 距离上次检测不足间隔时间，还需 {remaining} 小时")
                            stats['skipped'] += 1
                            pbar.update(1)
                            continue
                    
                    # 重新检测
                    result = self.process_file(
                        file_path, 
                        target_dir=rapid_dir,
                        base_path=non_rapid_dir,
                        move_files=False  # 先不移动，检测后再决定
                    )
                    
                    # 更新记录
                    if file_key not in recheck_data:
                        recheck_data[file_key] = {
                            'first_check_time': current_time,
                            'check_count': 0
                        }
                    
                    recheck_data[file_key]['last_check_time'] = current_time
                    recheck_data[file_key]['check_count'] = recheck_data[file_key].get('check_count', 0) + 1
                    recheck_data[file_key]['last_status'] = 'rapid' if result['can_rapid'] else 'non_rapid'
                    
                    if result['can_rapid']:
                        # 变成可秒传，移动到 rapid 目录
                        try:
                            relative_path = file_path.relative_to(non_rapid_dir)
                            target_path = rapid_dir / relative_path
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            self.file_handler.move_file(file_path, target_path)
                            self.logger.success(f"✓ {file_path.name}: 现在可秒传！已移动到 rapid/")
                            stats['now_rapid'] += 1
                            
                            # 从记录中删除（已经可秒传了）
                            del recheck_data[file_key]
                        except Exception as e:
                            self.logger.error(f"✗ {file_path.name}: 移动失败: {e}")
                    else:
                        self.logger.info(f"○ {file_path.name}: 仍不可秒传")
                        stats['still_non_rapid'] += 1
                    
                    pbar.update(1)
            
            # 保存重新检测记录
            with open(recheck_file, 'w', encoding='utf-8') as f:
                json.dump(recheck_data, f, ensure_ascii=False, indent=2)
            
            # 输出统计
            print("\n" + "=" * 60)
            print("重新检测完成！")
            print("=" * 60)
            print(f"总文件数: {stats['total']}")
            print(f"✓ 现在可秒传: {stats['now_rapid']} 个")
            print(f"○ 仍不可秒传: {stats['still_non_rapid']} 个")
            print(f"⊗ 跳过检测: {stats['skipped']} 个")
            print("=" * 60)
            
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
