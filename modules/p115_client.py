"""
115接口交互模块
封装115网盘秒传查询接口
"""

import time
import threading
from functools import wraps
from pathlib import Path
from typing import Dict, Any, Optional
from p115client import P115Client, check_response


class SessionExpiredError(Exception):
    """115 会话失效（errNo 990001 登录超时）。

    此类错误意味着 cookie 已被服务端判为超时/失效，重试或刷新 user_key 都无效，
    必须更新 cookie。抛出后由上层停止本轮处理并告警，避免无效重试和刷屏。
    """
    pass


# 115 会话失效相关错误码（登录超时/请重新登录）
_SESSION_EXPIRED_ERRNOS = {990001, 990002}


def _serialized_client_call(func):
    """串行化对同一个 p115client 实例的完整操作。"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        with self._client_lock:
            return func(self, *args, **kwargs)
    return wrapper


def is_session_expired(obj: Any) -> bool:
    """判断一个响应 dict 或异常是否表示 115 会话失效。"""
    if isinstance(obj, dict):
        errno = obj.get('errNo', obj.get('errno', obj.get('errcode')))
        if errno in _SESSION_EXPIRED_ERRNOS:
            return True
        text = f"{obj.get('error', '')}{obj.get('message', '')}{obj.get('msg', '')}"
    else:
        text = str(obj)
    return '990001' in text or '登录超时' in text or '请重新登录' in text


class P115ClientWrapper:
    """115客户端封装类"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化115客户端
        
        :param config: 115配置
        """
        self.config = config
        cookies_file = Path(config.get('cookies_file', '~/115-cookies.txt')).expanduser()
        self.cookies_file = cookies_file  # 保存路径，供 reload_cookies 热加载使用
        # 默认关闭自动重登：它对油猴/网页签发的 cookie 换不出可用会话，反而会刷屏空转，
        # 且可能把刷新的坏 cookie 写回文件。会话失效改由上层识别 990001 后停止并告警。
        check_for_relogin = config.get('check_for_relogin', False)
        self._check_for_relogin = check_for_relogin

        # 以「字符串」而非文件路径传入 cookie：
        # 传路径会让 p115client 把自动刷新的 cookie 写回该文件，可能覆盖掉用户手贴的好 cookie。
        # 传字符串则库不持有 cookies_path，绝不会改动用户的 cookie 文件。
        cookies_str = ""
        if cookies_file.exists():
            try:
                cookies_str = cookies_file.read_text(encoding='utf-8').strip()
            except Exception:
                cookies_str = ""

        # 创建客户端
        # 注意：不同 p115client 版本 __init__ 签名不同（新版已移除 check_for_relogin 参数），
        # 统一「构造后用属性赋值」以兼容各版本。
        # p115client 的上传初始化流程会缓存 user_key/加密器状态，这些状态不是线程安全的。
        # 调度器的实时监控、定时任务和 Bot 会从不同线程共用本实例，因此必须串行访问。
        self._client_lock = threading.RLock()
        self._cookies_str = cookies_str
        self.client = self._new_client(cookies_str)
        
        # 性能配置
        self.request_timeout = config.get('request_timeout', 10)
        self.retry_times = config.get('retry_times', 3)
        self.retry_delay = config.get('retry_delay', 2)
        
        # 本次运行的远程目录 ID 缓存，避免重复 API 调用
        # key: (parent_pid, dir_name)  value: cid
        self._remote_dir_cache: dict = {}

    def _new_client(self, cookies_str: str) -> P115Client:
        """创建一个干净的客户端，并应用跨版本兼容配置。"""
        client = P115Client(cookies_str)
        try:
            client.check_for_relogin = self._check_for_relogin
        except Exception:
            pass
        return client

    def _reset_client(self) -> None:
        """丢弃可能已污染的上传凭证/加密状态，效果等同于进程重启。"""
        self.client = self._new_client(self._cookies_str)
        self._remote_dir_cache.clear()

    def reload_cookies(self) -> str:
        """重新从 cookies_file 读取 cookie 并热加载到客户端（无需重启进程）。

        用于 Bot 扫码登录写入新 cookie 后立即生效。
        :return: 新 cookie 的 UID（读取失败或为空时返回空串）
        """
        cookies_str = ""
        if self.cookies_file.exists():
            try:
                cookies_str = self.cookies_file.read_text(encoding='utf-8').strip()
            except Exception:
                cookies_str = ""
        # 与正在进行的秒传请求互斥，避免替换到一半的客户端被其他线程使用。
        with self._client_lock:
            self._cookies_str = cookies_str
            self._reset_client()
        import re as _re
        m = _re.search(r'UID=([^;]+)', cookies_str)
        return m.group(1) if m else ""

    @_serialized_client_call
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
        # upload_init 的两次调用必须使用同一个、未被其他线程改动的客户端状态。
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
                    pickcode = resp.get("pickcode") or resp.get("pick_code")
                    if not pickcode:
                        raise RuntimeError(
                            f"upload_init 返回 status=2 但无 pickcode，文件可能未入库（响应: {resp}）"
                        )
                    return {
                        'success': True,
                        'can_rapid': True,
                        'status': status,
                        'pickcode': pickcode,
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
                        pickcode2 = resp2.get("pickcode") or resp2.get("pick_code")
                        if not pickcode2:
                            raise RuntimeError(
                                f"upload_init 二次验证返回 status=2 但无 pickcode（响应: {resp2}）"
                            )
                        return {
                            'success': True,
                            'can_rapid': True,
                            'status': status2,
                            'pickcode': pickcode2,
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
                
            except SessionExpiredError:
                # cookie 失效，重试/刷新 user_key 都无意义，直接上抛让上层停止并告警
                raise
            except Exception as e:
                # 会话失效（990001 登录超时）：重试和 upload_key() 都救不了，立即上抛
                if is_session_expired(e):
                    raise SessionExpiredError(str(e))
                if attempt < self.retry_times - 1:
                    # upload_key() 只刷新 key，却不会清掉 p115client 已损坏的加密器缓存。
                    # 日志中的 "index out of bounds on dimension 1" 会因此一直持续到重启。
                    # 直接重建客户端，既能刷新 user_key，也能彻底清理内部状态。
                    self._reset_client()
                    time.sleep(self.retry_delay)
                    continue
                return {
                    'success': False,
                    'can_rapid': False,
                    'status': None,
                    'response': None,
                    'message': f'检查失败: {str(e)}',
                    'error': str(e),
                }
    
    @_serialized_client_call
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

    @_serialized_client_call
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
            except SessionExpiredError:
                raise
            except Exception as e:
                if is_session_expired(e):
                    raise SessionExpiredError(str(e))
                if attempt < self.retry_times - 1:
                    try:
                        self.client.upload_key()
                    except Exception:
                        pass
                    time.sleep(self.retry_delay)
                    continue
                return {
                    'success': False,
                    'error': str(e),
                }

    @_serialized_client_call
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
            if is_session_expired(resp):
                raise SessionExpiredError(f"建立目录时会话失效: {resp}")
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
            if is_session_expired(resp):
                raise SessionExpiredError(f"查询目录时会话失效: {resp}")
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
