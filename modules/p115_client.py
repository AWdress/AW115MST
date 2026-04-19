"""
115接口交互模块
封装115网盘秒传查询接口
"""

import time
from pathlib import Path
from typing import Dict, Any, Optional
from p115client import P115Client, check_response


class P115ClientWrapper:
    """115客户端封装类"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化115客户端
        
        :param config: 115配置
        """
        self.config = config
        cookies_file = Path(config.get('cookies_file', '~/115-cookies.txt')).expanduser()
        check_for_relogin = config.get('check_for_relogin', True)
        
        # 创建客户端
        self.client = P115Client(cookies_file, check_for_relogin=check_for_relogin)
        
        # 性能配置
        self.request_timeout = config.get('request_timeout', 10)
        self.retry_times = config.get('retry_times', 3)
        self.retry_delay = config.get('retry_delay', 2)
        
        # 本次运行的远程目录 ID 缓存，避免重复 API 调用
        # key: (parent_pid, dir_name)  value: cid
        self._remote_dir_cache: dict = {}
    
    def check_rapid_upload(self, filename: str, filesize: int, filesha1: str,
                          read_range_bytes_or_hash: Optional[callable] = None,
                          pid: int = 0) -> Dict[str, Any]:
        """
        检查文件是否可以秒传
        
        :param filename: 文件名
        :param filesize: 文件大小
        :param filesha1: 文件SHA-1哈希值（大写）
        :param read_range_bytes_or_hash: 读取范围数据的函数（文件>=1MB时需要）
        :param pid: 目标目录ID
        :return: 检查结果
        """
        for attempt in range(self.retry_times):
            try:
                # 使用 upload_init 接口
                target = f"U_1_{pid}"
                
                # 第一次调用
                resp = self.client.upload_init({
                    "filename": filename,
                    "filesize": filesize,
                    "fileid": filesha1,
                    "target": target,
                })
                
                # 先判断 status，避免 check_response 对秒传响应误抛异常
                status = resp.get("status")
                state = resp.get("state")
                
                # status=2 表示可以秒传（无论 state 值如何）
                if status == 2:
                    return {
                        'success': True,
                        'can_rapid': True,
                        'status': status,
                        'response': resp,
                        'message': '可以秒传',
                    }
                
                # 对非秒传响应才检查 API 错误
                if state == 0 or state is False:
                    err_msg = resp.get('message', resp.get('msg', f'API返回state={state}'))
                    raise RuntimeError(f"upload_init API 错误: {err_msg}（完整响应: {resp}）")
                
                # status=7 需要二次验证
                if status == 7:
                    if read_range_bytes_or_hash is None:
                        raise ValueError(f"文件需要二次验证但未提供 read_range_bytes_or_hash（filesize={filesize}）")
                    
                    # 获取验证范围
                    sign_check = resp.get("sign_check", "")
                    if not sign_check:
                        raise ValueError(f"upload_init 未返回 sign_check，响应: {resp}")
                    
                    # 读取指定范围的数据
                    range_data = read_range_bytes_or_hash(sign_check)
                    
                    # 计算范围数据的SHA-1
                    from hashlib import sha1 as _sha1
                    sign_val = _sha1(range_data).hexdigest().upper()
                    
                    # 第二次调用，提交验证
                    resp2 = self.client.upload_init({
                        "filename": filename,
                        "filesize": filesize,
                        "fileid": filesha1,
                        "target": target,
                        "sign_key": resp.get("sign_key", ""),
                        "sign_check": sign_check,
                        "sign_val": sign_val,
                    })
                    
                    status2 = resp2.get("status")
                    state2 = resp2.get("state")
                    
                    # status=2 表示二次验证通过，可秒传
                    if status2 == 2:
                        return {
                            'success': True,
                            'can_rapid': True,
                            'status': status2,
                            'response': resp2,
                            'message': '可以秒传',
                        }
                    
                    # 二次验证后仍不可秒传
                    if state2 == 0 or state2 is False:
                        err_msg = resp2.get('message', resp2.get('msg', f'API返回state={state2}'))
                        raise RuntimeError(f"upload_init 二次验证 API 错误: {err_msg}（响应: {resp2}）")
                    
                    return {
                        'success': True,
                        'can_rapid': False,
                        'status': status2,
                        'response': resp2,
                        'message': f'需要上传（二次验证后 status={status2}）',
                    }
                
                # status=1 或其他，需要上传
                return {
                    'success': True,
                    'can_rapid': False,
                    'status': status,
                    'response': resp,
                    'message': f'需要上传（status={status}）',
                }
                
            except Exception as e:
                if attempt < self.retry_times - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    return {
                        'success': False,
                        'can_rapid': False,
                        'status': None,
                        'response': None,
                        'message': f'检查失败: {str(e)}',
                        'error': str(e),
                    }
    
    def get_user_info(self) -> Dict[str, Any]:
        """获取用户信息"""
        try:
            resp = self.client.user_info()
            check_response(resp)
            return {
                'success': True,
                'data': resp.get('data', {}),
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }

    def upload_file(self, file_path: Path, pid: int = 0,
                    progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        真实上传文件到 115（分块断点续传）

        :param file_path: 本地文件路径
        :param pid: 目标目录 ID
        :param progress_callback: 进度回调 (uploaded_bytes, total_bytes) -> None
        :return: 上传结果
        """
        for attempt in range(self.retry_times):
            try:
                resp = self.client.upload_file(
                    file=file_path,
                    pid=pid,
                    partsize=-1,  # 自动选择分块大小
                )
                return {
                    'success': True,
                    'response': resp,
                }
            except Exception as e:
                if attempt < self.retry_times - 1:
                    time.sleep(self.retry_delay)
                    continue
                return {
                    'success': False,
                    'error': str(e),
                }

    def ensure_remote_path(self, parts: tuple, base_pid: int) -> int:
        """
        确保 115 上存在指定多级路径，不存在则逐级创建。返回最终目录的 cid。
        
        :param parts: 目录名称元组，如 ('电影', '2026')
        :param base_pid: 起始父目录 ID（通常为 target_pid）
        :return: 最终目录 cid
        """
        current_pid = base_pid
        for name in parts:
            cache_key = (current_pid, name)
            if cache_key in self._remote_dir_cache:
                current_pid = self._remote_dir_cache[cache_key]
                continue
            
            # 尝试新建目录
            resp = self.client.fs_mkdir({"cname": name, "pid": current_pid})
            cid = None
            if resp.get("state"):
                try:
                    cid = int(resp["data"]["cid"])
                except (KeyError, TypeError, ValueError):
                    # 响应格式异常，尝试从列表中找（目录已成功创建）
                    cid = self._find_dir_cid(current_pid, name)
            else:
                # 目录可能已存在，在列表中搜索
                cid = self._find_dir_cid(current_pid, name)
            if cid is None:
                raise RuntimeError(
                    f"无法在115创建或找到目录: {name}（上级 pid={current_pid}，响应: {resp}）"
                )
            
            self._remote_dir_cache[cache_key] = cid
            current_pid = cid
        
        return current_pid
    
    def _find_dir_cid(self, parent_pid: int, name: str) -> Optional[int]:
        """
        在 115 指定目录下按名称查找子目录，返回其 cid（不存在返回 None）。
        """
        offset = 0
        while True:
            resp = self.client.fs_files({
                "cid": parent_pid,
                "show_dir": 1,
                "nf": "1",   # 不显示文件，只看目录
                "limit": 1150,
                "offset": offset,
            })
            items = resp.get("data", [])
            if not items:
                break
            for item in items:
                # 目录没有 fid 字段，文件有
                if item.get("n") == name and "fid" not in item:
                    return int(item["cid"])
            if len(items) < 1150:
                break
            offset += 1150
        return None
    
    def check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            user_info = self.get_user_info()
            return user_info.get('success', False)
        except Exception:
            return False
