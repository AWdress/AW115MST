#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AW115MST - 115网盘秒传检测工具 (CLI)
"""

import argparse
import sys
from pathlib import Path
from modules.controller import RapidUploadController
from modules.file_watcher import FileWatcher


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='AW115MST - 115网盘秒传检测工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  # 检查 input 目录并自动分类（默认）
  python main_cli.py
  
  # 检查指定目录
  python main_cli.py --input /path/to/folder
  
  # 自定义可秒传文件目标目录
  python main_cli.py --target /path/to/rapid-files
  
  # 仅检查不移动
  python main_cli.py --check-only
  
  # 重新检测 non_rapid 目录中的文件
  python main_cli.py --recheck
  
  # 使用自定义配置文件
  python main_cli.py --config my_config.yaml
        '''
    )
    
    parser.add_argument(
        '-i', '--input',
        default='./input',
        help='输入路径（待检测文件目录，默认: ./input）'
    )
    
    parser.add_argument(
        '-t', '--target',
        help='可秒传文件目标目录（不指定则使用配置文件中的默认值: ./rapid）'
    )
    
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        default=True,
        help='递归处理子目录（默认启用）'
    )
    
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='不递归处理子目录'
    )
    
    parser.add_argument(
        '-c', '--config',
        default='config/config.yaml',
        help='配置文件路径（默认: config/config.yaml）'
    )
    
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='仅检查秒传状态，不移动文件'
    )
    
    parser.add_argument(
        '--no-move',
        action='store_true',
        help='不移动文件（同--check-only）'
    )
    
    parser.add_argument(
        '--recheck',
        action='store_true',
        help='重新检测 non_rapid 目录中的文件（检查是否变成可秒传）'
    )
    
    parser.add_argument(
        '-w', '--watch',
        action='store_true',
        help='监控模式：持续监控 input 目录，自动处理新文件'
    )
    
    parser.add_argument(
        '--debounce',
        type=int,
        default=5,
        help='监控模式下的防抖时间（秒，默认: 5）'
    )
    
    parser.add_argument(
        '-v', '--version',
        action='version',
        version='AW115MST v1.0.0'
    )
    
    args = parser.parse_args()
    
    # 处理 no-recursive 参数
    if args.no_recursive:
        args.recursive = False
    
    # 检查输入路径
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误: 输入路径不存在: {input_path}")
        if args.input == './input':
            print(f"提示: 默认扫描 ./input 目录，请将待检测文件放入该目录")
        sys.exit(1)
    
    # 检查配置文件
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"错误: 配置文件不存在: {config_path}")
        print("请先创建配置文件，可以参考 config/config.yaml 模板")
        sys.exit(1)
    
    try:
        # 创建控制器
        controller = RapidUploadController(config_path=str(config_path))
        
        # 监控模式
        if args.watch:
            print("\n=== 监控模式（实时监控文件变化） ===\n")
            
            def process_single_file(file_path: Path):
                """处理单个文件的回调函数"""
                try:
                    # 确定是否移动文件
                    move_files = not (args.check_only or args.no_move)
                    
                    # 处理文件
                    result = controller.process_file(
                        file_path=file_path,
                        target_dir=Path(args.target) if args.target else None,
                        base_path=input_path,
                        move_files=move_files
                    )
                    
                    if result.get('success'):
                        if result.get('can_rapid'):
                            print(f"✓ {file_path.name}: 可秒传" + (" (已移动)" if move_files else ""))
                        else:
                            print(f"○ {file_path.name}: 不可秒传" + (" (已移动)" if move_files else ""))
                    else:
                        print(f"✗ {file_path.name}: 处理失败 - {result.get('error', '未知错误')}")
                        
                except Exception as e:
                    print(f"✗ {file_path.name}: 处理异常 - {str(e)}")
            
            # 创建文件监控器
            watcher = FileWatcher(
                watch_path=input_path,
                callback=process_single_file,
                debounce_seconds=args.debounce,
                recursive=args.recursive
            )
            
            try:
                watcher.start()
                # 保持运行
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                watcher.stop()
                print("\n用户中断监控")
                sys.exit(0)
        
        # 重新检测模式
        if args.recheck:
            print("\n=== 重新检测模式（检查 non_rapid 目录） ===\n")
            result = controller.recheck_non_rapid_files()
            
            if result.get('success'):
                print(f"\n重新检测完成！")
                print(f"检测文件数: {result.get('total', 0)}")
                print(f"变为可秒传: {result.get('now_rapid', 0)} 个")
                print(f"仍不可秒传: {result.get('still_non_rapid', 0)} 个")
                sys.exit(0)
            else:
                print(f"\n错误: {result.get('error', '未知错误')}")
                sys.exit(1)
        
        # 确定是否移动文件
        move_files = not (args.check_only or args.no_move)
        
        # 处理文件
        if args.check_only or args.no_move:
            print("\n=== 仅检查模式（不移动文件） ===\n")
            result = controller.check_only(
                input_path=input_path,
                recursive=args.recursive
            )
        else:
            print("\n=== 检查并移动模式 ===\n")
            result = controller.process_directory(
                input_path=input_path,
                target_path=args.target,
                recursive=args.recursive,
                move_files=move_files
            )
        
        # 返回结果
        if result.get('success'):
            sys.exit(0)
        else:
            print(f"\n错误: {result.get('error', '未知错误')}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n用户中断操作")
        sys.exit(130)
    except Exception as e:
        print(f"\n错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
