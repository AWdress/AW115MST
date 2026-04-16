"""
配置初始化模块
自动检查和创建缺失的配置文件
"""

import shutil
from pathlib import Path
from typing import Dict, Any, List, Tuple

try:
    from ruamel.yaml import YAML
    HAS_RUAMEL = True
except ImportError:
    import yaml
    HAS_RUAMEL = False


def merge_config(user_config: Dict[str, Any], default_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    递归合并配置，用户配置优先，缺失的项从默认配置补充
    
    :param user_config: 用户配置
    :param default_config: 默认配置
    :return: 合并后的配置
    """
    merged = default_config.copy()
    
    for key, value in user_config.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            # 递归合并字典
            merged[key] = merge_config(value, merged[key])
        else:
            # 直接使用用户配置
            merged[key] = value
    
    return merged


def check_and_merge_config():
    """
    检查并合并配置文件
    如果用户配置缺少某些项，从示例配置补充（保留注释）
    """
    config_path = Path('./config/config.yaml')
    example_path = Path('./config/config.yaml.example')
    
    if not config_path.exists():
        return False, []  # 配置文件不存在
    
    if not example_path.exists():
        return True, []  # 示例文件不存在，跳过合并
    
    try:
        if HAS_RUAMEL:
            # 使用 ruamel.yaml 保留注释和格式
            yaml_handler = YAML()
            yaml_handler.preserve_quotes = True
            yaml_handler.default_flow_style = False
            
            # 读取用户配置
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = yaml_handler.load(f) or {}
            
            # 读取示例配置（带注释）
            with open(example_path, 'r', encoding='utf-8') as f:
                example_config = yaml_handler.load(f) or {}
            
            # 合并配置
            merged_config = merge_config(user_config, example_config)
            
            # 检查是否有新增项
            added_keys = []
            find_new_keys(user_config, merged_config, added_keys)
            
            # 如果有新增项，更新配置文件
            if added_keys:
                # 备份原配置
                backup_path = config_path.with_suffix('.yaml.backup')
                shutil.copy(config_path, backup_path)
                
                # 写入合并后的配置（保留注释）
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml_handler.dump(merged_config, f)
                
                print(f"✅ 已更新配置文件，新增 {len(added_keys)} 个配置项")
                print(f"📝 原配置已备份至: {backup_path}")
                
                return True, added_keys
            
            return True, []
        else:
            # 降级方案：使用标准 yaml（会丢失注释，但提示用户）
            import yaml
            
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f) or {}
            
            with open(example_path, 'r', encoding='utf-8') as f:
                example_config = yaml.safe_load(f) or {}
            
            merged_config = merge_config(user_config, example_config)
            
            added_keys = []
            find_new_keys(user_config, merged_config, added_keys)
            
            if added_keys:
                print("⚠️  检测到配置文件缺少新配置项")
                print("⚠️  建议手动对比 config.yaml.example 并更新配置")
                print(f"\n新增的配置项（共 {len(added_keys)} 个）：")
                for key in added_keys[:10]:
                    print(f"   • {key}")
                if len(added_keys) > 10:
                    print(f"   ... 还有 {len(added_keys) - 10} 个")
                print("\n💡 提示：安装 ruamel.yaml 可自动合并配置并保留注释")
                print("   运行: pip install ruamel.yaml\n")
                
                return True, added_keys
            
            return True, []
        
    except Exception as e:
        print(f"⚠️  配置合并失败: {e}")
        return True, []


def find_new_keys(user_dict: Dict, merged_dict: Dict, added_keys: List[str], prefix: str = ''):
    """递归查找新增的配置项"""
    for key, value in merged_dict.items():
        full_key = f"{prefix}.{key}" if prefix else key
        
        if key not in user_dict:
            added_keys.append(full_key)
        elif isinstance(value, dict) and isinstance(user_dict.get(key), dict):
            find_new_keys(user_dict[key], value, added_keys, full_key)


def init_config_files():
    """
    初始化配置文件
    如果配置文件不存在，从示例文件复制
    """
    config_dir = Path('./config')
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # 配置文件映射：目标文件 -> 示例文件
    config_files = {
        'config/config.yaml': 'config/config.yaml.example',
        'config/115-cookies.txt': 'config/115-cookies.txt.example'
    }
    
    created_files = []
    
    for target_file, example_file in config_files.items():
        target_path = Path(target_file)
        example_path = Path(example_file)
        
        # 如果目标文件不存在
        if not target_path.exists():
            # 检查示例文件是否存在
            if example_path.exists():
                # 复制示例文件
                shutil.copy(example_path, target_path)
                created_files.append(target_file)
                print(f"✅ 已创建配置文件: {target_file}")
            else:
                print(f"⚠️  警告: 示例文件不存在: {example_file}")
    
    # 如果配置文件已存在，检查并合并配置
    if not created_files and Path('./config/config.yaml').exists():
        config_exists, added_keys = check_and_merge_config()
        if added_keys:
            print("\n📋 新增的配置项：")
            for key in added_keys[:10]:  # 只显示前10个
                print(f"   • {key}")
            if len(added_keys) > 10:
                print(f"   ... 还有 {len(added_keys) - 10} 个")
            print()
    
    # 创建必要的目录（从配置文件中读取实际路径）
    config_yaml = Path('./config/config.yaml')
    dirs_to_create = ['logs', 'data']  # 始终需要的固定目录

    try:
        if config_yaml.exists():
            if HAS_RUAMEL:
                _yaml = YAML()
                with open(config_yaml, 'r', encoding='utf-8') as f:
                    _cfg = _yaml.load(f)
            else:
                import yaml as _pyyaml
                with open(config_yaml, 'r', encoding='utf-8') as f:
                    _cfg = _pyyaml.safe_load(f)

            if isinstance(_cfg, dict):
                fp = _cfg.get('file_processing', {})
                input_dir = fp.get('input_dir', './待检测').lstrip('.').lstrip('/')
                ms = fp.get('move_strategy', {})
                rapid_dir = ms.get('rapid_files_dir', './可秒传').lstrip('.').lstrip('/')
                non_rapid_dir = ms.get('non_rapid_files_dir', './待秒传').lstrip('.').lstrip('/')
                dirs_to_create += [input_dir, rapid_dir, non_rapid_dir]
    except Exception:
        dirs_to_create += ['待检测', '可秒传', '待秒传']

    for dir_name in dirs_to_create:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ 已创建目录: {dir_name}/")
    
    # 如果创建了新配置文件，提示用户
    if created_files:
        print("\n" + "=" * 60)
        print("⚠️  检测到首次运行，已自动创建配置文件")
        print("=" * 60)
        print("\n📝 请按以下步骤配置：\n")
        
        if 'config/115-cookies.txt' in created_files:
            print("1️⃣  配置 115 Cookies:")
            print("   • 编辑 config/115-cookies.txt")
            print("   • 替换为你的真实 Cookie 值")
            print("   • 获取方法见文件内注释\n")
        
        if 'config/config.yaml' in created_files:
            print("2️⃣  配置应用设置（可选）:")
            print("   • 编辑 config/config.yaml")
            print("   • 根据需要调整各项配置")
            print("   • Telegram 通知、定时间隔等\n")
        
        print("3️⃣  配置完成后重新运行程序")
        print("=" * 60 + "\n")
        
        return False  # 返回 False 表示需要用户配置
    
    return True  # 返回 True 表示配置已就绪


def check_cookies_configured():
    """
    检查 cookies 是否已配置
    """
    cookies_file = Path('./config/115-cookies.txt')
    
    if not cookies_file.exists():
        return False
    
    try:
        with open(cookies_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            
            # 检查是否还是示例内容
            if not content or 'YOUR_UID_HERE' in content or 'YOUR_CID_HERE' in content:
                return False
            
            # 检查是否包含必要的字段
            if 'UID=' not in content or 'CID=' not in content:
                return False
            
            return True
    except Exception:
        return False


def validate_config():
    """
    验证配置文件
    """
    errors = []
    warnings = []
    
    # 检查配置文件
    config_file = Path('./config/config.yaml')
    if not config_file.exists():
        errors.append("配置文件不存在: config/config.yaml")
    
    # 检查 cookies 文件
    if not check_cookies_configured():
        errors.append("115 Cookies 未配置或配置错误")
        warnings.append("请编辑 config/115-cookies.txt 并填入真实的 Cookie 值")
    
    # 检查必要目录（从 config.yaml 读取实际路径）
    dirs_to_check = ['logs', 'data']
    try:
        if config_file.exists():
            if HAS_RUAMEL:
                _yaml = YAML()
                with open(config_file, 'r', encoding='utf-8') as f:
                    _cfg = _yaml.load(f)
            else:
                import yaml as _pyyaml
                with open(config_file, 'r', encoding='utf-8') as f:
                    _cfg = _pyyaml.safe_load(f)
            if isinstance(_cfg, dict):
                fp = _cfg.get('file_processing', {})
                dirs_to_check.append(fp.get('input_dir', './待检测').lstrip('./'))
                ms = fp.get('move_strategy', {})
                dirs_to_check.append(ms.get('rapid_files_dir', './可秒传').lstrip('./'))
                dirs_to_check.append(ms.get('non_rapid_files_dir', './待秒传').lstrip('./'))
    except Exception:
        dirs_to_check += ['待检测', '可秒传', '待秒传']

    for dir_name in dirs_to_check:
        if not Path(dir_name).exists():
            warnings.append(f"目录不存在: {dir_name}/ (将自动创建)")
    
    return errors, warnings


def print_validation_result(errors, warnings):
    """
    打印验证结果
    """
    if errors:
        print("\n" + "=" * 60)
        print("❌ 配置验证失败")
        print("=" * 60)
        for error in errors:
            print(f"  ❌ {error}")
        print("\n请修复以上错误后重新运行")
        print("=" * 60 + "\n")
        return False
    
    if warnings:
        print("\n" + "=" * 60)
        print("⚠️  配置警告")
        print("=" * 60)
        for warning in warnings:
            print(f"  ⚠️  {warning}")
        print("=" * 60 + "\n")
    
    return True
