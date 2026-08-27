from __future__ import annotations

import argparse

from .pipeline import analyze_directory, analyze_file


def main() -> None:
    parser = argparse.ArgumentParser(description="分析家庭 Excel 账单：去重、分类、统计并生成待入账结果")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("file", nargs="?", help="账单文件路径（.xlsx/.xls/.xlsm/.csv）")
    input_group.add_argument("--dir", dest="directory", help="账单文件夹路径，将处理其中所有 Excel/CSV 文件")
    parser.add_argument("--recursive", action="store_true", help="递归处理 --dir 下的子文件夹")
    parser.add_argument("--output", help="导出已去重并分类的 CSV 文件路径")
    args = parser.parse_args()
    result = analyze_directory(args.directory, recursive=args.recursive) if args.directory else analyze_file(args.file)
    print(f"交易总数: {result['total_count']}")
    if "file_count" in result:
        print(f"处理文件数: {result['file_count']}")
    print(f"重复交易: {result['duplicate_count']}")
    print(f"待入账交易: {result['posted_count']}")
    print(f"收入: ¥{result['totals']['income']:.2f}")
    print(f"支出: ¥{result['totals']['expense']:.2f}")
    print(f"结余: ¥{result['totals']['balance']:.2f}")
    print("\n支出分类:")
    print(result["category_summary"].to_string(index=False))
    if args.output:
        result["posted"].to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"\n已导出: {args.output}")


if __name__ == "__main__":
    main()
