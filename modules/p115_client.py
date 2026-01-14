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
                
                # 检查响应
                check_response(resp)
                
                status = resp.get("status")
                
                # status=2 表示可以秒传
                if status == 2:
                    return {
                        'success': True,
                        'can_rapid': True,
                        'status': status,
                        'response': resp,
                        'message': '可以秒传',
                    }
                
                # status=7 需要二次验证（文件>=1MB）
                elif status == 7:
                    if read_range_bytes_or_hash is None:
                        raise ValueError("文件大小>=1MB，需要提供read_range_bytes_or_hash参数")
                    
                    # 获取验证范围
                    sign_check = resp.get("sign_check", "")
                    if not sign_check:
                        raise ValueError("未获取到sign_check参数")
                    
                    # 读取指定范围的数据
                    range_data = read_range_bytes_or_hash(sign_check)
                    
                    # 计算范围数据的SHA-1
                    from hashlib import sha1
                    sign_val = sha1(range_data).hexdigest().upper()
                    
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
                    
                    check_response(resp2)
                    status2 = resp2.get("status")
                    
                    return {
                        'success': True,
                        'can_rapid': status2 == 2,
                        'status': status2,
                        'response': resp2,
                        'message': '可以秒传' if status2 == 2 else '需要上传',
                    }
                
                # status=1 或其他，需要上传
                else:
                    return {
                        'success': True,
                        'can_rapid': False,
                        'status': status,
                        'response': resp,
                        'message': '需要上传',
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
    
    def check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            user_info = self.get_user_info()
            return user_info.get('success', False)
        except Exception:
            return False
