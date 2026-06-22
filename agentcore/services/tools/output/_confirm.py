"""操作确认弹窗 — output 工具共用。"""


def confirm(title: str, detail: str) -> bool:
    """弹窗确认，返回 True 表示用户同意。"""
    print()
    print("=" * 50)
    print(f"  ⚠ {title}")
    print("=" * 50)
    print(f"  {detail}")
    print("-" * 50)
    answer = input("  确认执行？(y/N): ").strip().lower()
    print()
    return answer in ("y", "yes")
