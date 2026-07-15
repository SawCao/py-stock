#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票列表管理工具
用于手动更新、查看股票列表缓存
"""

import sys
import logging
import argparse
import stock_list_cache

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('update_stock_list')

def show_cache_status():
    """显示缓存状态"""
    print("\n" + "="*80)
    print("股票列表缓存状态")
    print("="*80)
    
    is_fresh, last_update = stock_list_cache.check_cache_freshness()
    
    if last_update:
        print(f"最后更新时间: {last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"缓存状态: {'✓ 新鲜' if is_fresh else '⚠ 过期（需要更新）'}")
    else:
        print("缓存状态: ✗ 空（需要首次更新）")
    
    # 获取缓存数据
    stock_list = stock_list_cache.get_stock_list_from_cache()
    if stock_list is not None and not stock_list.empty:
        print(f"缓存记录数: {len(stock_list)} 只股票")
        print("\n前5条记录:")
        print(stock_list.head().to_string())
    else:
        print("缓存记录数: 0")
    
    print("="*80 + "\n")

def update_cache(force: bool = False):
    """更新缓存"""
    print("\n" + "="*80)
    print("更新股票列表缓存")
    print("="*80)
    
    stock_list = stock_list_cache.get_stock_list(force_update=force)
    
    if stock_list is not None and not stock_list.empty:
        print(f"\n✓ 更新成功！共 {len(stock_list)} 只股票")
        print("\n前5条记录:")
        print(stock_list.head().to_string())
        print("\n后5条记录:")
        print(stock_list.tail().to_string())
    else:
        print("\n✗ 更新失败")
    
    print("="*80 + "\n")

def search_stock(keyword: str):
    """搜索股票"""
    print("\n" + "="*80)
    print(f"搜索股票: {keyword}")
    print("="*80)
    
    stock_list = stock_list_cache.get_stock_list_from_cache()
    
    if stock_list is None or stock_list.empty:
        print("✗ 缓存为空，请先更新缓存")
        return
    
    # 搜索代码或名称
    mask = (
        stock_list['code'].str.contains(keyword, case=False, na=False) |
        stock_list['raw_code'].str.contains(keyword, case=False, na=False) |
        stock_list['name'].str.contains(keyword, case=False, na=False)
    )
    
    results = stock_list[mask]
    
    if results.empty:
        print(f"✗ 未找到匹配 '{keyword}' 的股票")
    else:
        print(f"✓ 找到 {len(results)} 只匹配的股票:\n")
        print(results.to_string())
    
    print("="*80 + "\n")

def init_database():
    """初始化数据库表"""
    print("\n" + "="*80)
    print("初始化股票列表缓存表")
    print("="*80)
    
    if stock_list_cache.init_stock_list_table():
        print("✓ 初始化成功")
    else:
        print("✗ 初始化失败")
    
    print("="*80 + "\n")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='股票列表缓存管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 查看缓存状态
  python update_stock_list.py --status
  
  # 更新缓存（如果缓存未过期则不更新）
  python update_stock_list.py --update
  
  # 强制更新缓存
  python update_stock_list.py --update --force
  
  # 搜索股票
  python update_stock_list.py --search 平安
  python update_stock_list.py --search 600000
  
  # 初始化数据库表
  python update_stock_list.py --init
        """
    )
    
    parser.add_argument('--status', '-s', action='store_true',
                       help='查看缓存状态')
    parser.add_argument('--update', '-u', action='store_true',
                       help='更新缓存')
    parser.add_argument('--force', '-f', action='store_true',
                       help='强制更新（忽略缓存时间）')
    parser.add_argument('--search', '-q', type=str, metavar='KEYWORD',
                       help='搜索股票（按代码或名称）')
    parser.add_argument('--init', '-i', action='store_true',
                       help='初始化数据库表')
    
    args = parser.parse_args()
    
    # 如果没有参数，显示帮助
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    # 执行操作
    if args.init:
        init_database()
    
    if args.status:
        show_cache_status()
    
    if args.update:
        update_cache(force=args.force)
    
    if args.search:
        search_stock(args.search)

if __name__ == "__main__":
    main()

