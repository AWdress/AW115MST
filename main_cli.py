#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AW115MST - 115网盘秒传检测工具 (CLI)
"""

import argparse
import sys
from pathlib import Path
from modules.config_init import init_config_files, validate_config, print_validation_result
from modules.controller import RapidUploadController
from modules.file_watcher import FileWatcher
from modules.scheduler import Scheduler


def main():
    """主函数"""
    # 初始化配置文件
    print("🔧 检查配置文件...")
    config_ready = init_config_files()
    
    if not config_ready:
        # 首次运行，需要用户配置
        sys.exit(1)
    
    # 验证配置
    errors, warnings = validate_config()
    if not print_validation_result(errors, warnings):
        sys.exit(1)
    
    parser = argparse.ArgumentParser(
        description='AW115MST - 115网盘秒传检测工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  # 默认模式（启动调度器：实时监控 + 定时任务）
  python main_cli.py
  
  # 启动 Telegram Bot 交互模式
  python main_cli.py --telegram-bot
  
  # 手动模式（单次运行）
  python main_cli.py --manual
  
  # 检查指定目录
  python main_cli.py --manual --input /path/to/folder
  
  # 自定义可秒传文件目标目录
  python main_cli.py --manual --target /path/to/rapid-files
  
  # 仅检查不移动
  python main_cli.py --manual --check-only
  
  # 重新检测 non_rapid 目录中的文件
  python main_cli.py --recheck

  # 扫码登录取 cookie（写入配置的 cookies_file），换 cookie/失效时用
  python main_cli.py --login              # 默认登录到 115android(F3) 槽位
  python main_cli.py --login web          # 网页端(A1)
  python main_cli.py --login android      # 115生活_安卓端(F1)
  python main_cli.py --login 115android   # 115_安卓端(F3)
  python main_cli.py --login qandroid     # 115管理_安卓端(M1)
  python main_cli.py --login ios          # 115生活_苹果端(D1)
  python main_cli.py --login 115ios       # 115_苹果端(D3)
  python main_cli.py --login ipad         # 115生活_苹果平板端(H1)
  python main_cli.py --login tv           # 115生活_安卓电视端(I1)
  python main_cli.py --login qios         # 115管理_苹果端(N1)
  python main_cli.py --login harmony      # 115_鸿蒙端(S1)
  python main_cli.py --login wechatmini   # 115生活_微信小程序端(R1)
  python main_cli.py --login alipaymini   # 115生活_支付宝小程序端(R2)
  # 提示：给工具用一个你平时不碰的槽位，避免和手机/网页互相踢下线

  # 使用自定义配置文件
  python main_cli.py --config my_config.yaml
  
  # 测试 Telegram 通知
  python main_cli.py --test-telegram
        '''
    )
    
    parser.add_argument(
        '-i', '--input',
        default='./待检测',
        help='输入路径（待检测文件目录，默认: ./待检测）'
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
        '--clean-processed',
        action='store_true',
        help='清理已处理文件的记录（复制模式下使用）'
    )
    
    parser.add_argument(
        '--telegram-bot',
        action='store_true',
        help='启动 Telegram Bot 交互模式'
    )
    
    parser.add_argument(
        '--test-telegram',
        action='store_true',
        help='测试 Telegram 通知连接'
    )
    
    parser.add_argument(
        '--manual',
        action='store_true',
        help='手动模式：单次运行（不启动调度器）'
    )
    
    parser.add_argument(
        '-w', '--watch',
        action='store_true',
        help='（已废弃）监控模式现在默认启用，请使用配置文件控制'
    )
    
    parser.add_argument(
        '--debounce',
        type=int,
        default=5,
        help='监控模式下的防抖时间（秒，默认: 5）'
    )
    
    parser.add_argument(
        '--login',
        nargs='?',
        const='115android',
        metavar='APP',
        help='扫码登录到指定 app 槽位并写入 cookie 文件（默认 115android）。'
             '示例: --login 115android / --login qandroid / --login tv'
    )

    parser.add_argument(
        '-v', '--version',
        action='version',
        version='AW115MST v1.2.13'
    )
    
    args = parser.parse_args()

    # 扫码登录取 cookie：登录到指定 app 槽位并写入配置的 cookies_file，然后退出
    # （不启动监控/上传等流程；即使当前 cookie 已失效也能用它重新取一份）
    if args.login:
        from modules.config_manager import ConfigManager
        from p115client import P115Client
        import re

        app = args.login
        cfg = ConfigManager(args.config)
        p115_cfg = cfg.get_p115_config()
        cookies_file = Path(p115_cfg.get('cookies_file', './config/115-cookies.txt')).expanduser()

        print(f"\n=== 扫码登录到 app 槽位: {app} ===")
        print("请用手机 115 App 扫描下方二维码并确认登录...\n")
        try:
            client = P115Client(app=app, console_qrcode=True)
            cookies_str = client.cookies_str
            uid = re.search(r'UID=([^;]+)', cookies_str)
            print(f"\n✅ 扫码登录成功，UID: {uid.group(1) if uid else '(未知)'}")
            try:
                cookies_file.parent.mkdir(parents=True, exist_ok=True)
                cookies_file.write_text(cookies_str, encoding='utf-8')
                print(f"   cookie 已写入: {cookies_file}")
                print("   现在可以正常启动工具了。")
            except OSError as we:
                # Docker 里 config 常被挂成只读，写不进；退而打印出来让用户手动粘贴
                print(f"\n⚠ 无法写入 {cookies_file}：{we}")
                print("   （若在 Docker 中，config 目录可能是只读挂载 :ro，改成 :rw 后重建容器即可自动写入）")
                print("   请手动把下面这一整行 cookie 复制到该文件：")
                print("   " + "-" * 64)
                print(cookies_str)
                print("   " + "-" * 64)
            sys.exit(0)
        except KeyboardInterrupt:
            print("\n已取消登录")
            sys.exit(130)
        except Exception as e:
            print(f"\n❌ 扫码登录失败: {e}")
            sys.exit(1)

    # 处理 no-recursive 参数
    if args.no_recursive:
        args.recursive = False
    
    # 检查输入路径
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误: 输入路径不存在: {input_path}")
        if args.input == './待检测':
            print(f"提示: 默认扫描 ./待检测 目录，请将待检测文件放入该目录")
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
        
        # 测试 Telegram 连接
        if args.test_telegram:
            print("\n=== 测试 Telegram 通知 ===\n")
            if controller.telegram.test_connection():
                print("✅ Telegram 通知测试成功！")
                sys.exit(0)
            else:
                print("❌ Telegram 通知测试失败！")
                print("请检查配置文件中的 bot_token 和 chat_id")
                sys.exit(1)
        
        # 清理已处理文件记录
        if args.clean_processed:
            print("\n=== 清理已处理文件记录 ===\n")
            result = controller.clean_processed_records()
            if result.get('success'):
                print(f"✅ 清理完成！")
                print(f"清理记录数: {result.get('cleaned', 0)}")
                sys.exit(0)
            else:
                print(f"❌ 清理失败: {result.get('error', '未知错误')}")
                sys.exit(1)
        
        # 启动 Telegram Bot
        if args.telegram_bot:
            telegram_config = controller.config_manager.get('telegram', {})
            bot_token = telegram_config.get('bot_token', '')
            
            if not bot_token:
                print("❌ 错误: 未配置 Telegram bot_token")
                print("请在 config.yaml 中配置 telegram.bot_token")
                sys.exit(1)
            
            print("\n=== 启动 Telegram Bot ===\n")
            from modules.telegram_bot import TelegramBot
            
            bot = TelegramBot(bot_token, controller)
            bot.run()
            sys.exit(0)
        
        # 手动模式（单次运行）
        if args.manual or args.recheck or args.check_only or args.no_move:
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
        
        # 默认模式：启动调度器（实时监控 + 定时任务）
        scheduler_config = controller.config_manager.get('scheduler', {})
        scheduler = Scheduler(scheduler_config, controller)
        scheduler.start()
            
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
