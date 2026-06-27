#!/usr/bin/env python3
"""
自動バージョンバンプスクリプト
version.txt を自動更新して Git にコミット・プッシュ
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, check=True):
    """コマンド実行"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"❌ Error: {result.stderr}")
        return None
    return result.stdout.strip()

def get_git_hash():
    """現在のコミットハッシュを取得"""
    hash_short = run_command("git rev-parse --short HEAD")
    return hash_short or "unknown"

def read_version():
    """version.txt からバージョンを読む"""
    if not Path("version.txt").exists():
        print("❌ version.txt not found")
        return None
    
    with open("version.txt", "r", encoding="utf-8") as f:
        content = f.read().strip()
    
    # +HASH の部分を削除
    version = content.split("+")[0] if "+" in content else content
    return version

def parse_version(version_str):
    """バージョンをパース (1.2.3 -> (1, 2, 3))"""
    try:
        parts = version_str.split(".")
        return int(parts[0]), int(parts[1]), int(parts[2])
    except (ValueError, IndexError):
        print(f"❌ Invalid version format: {version_str}")
        return None

def increment_version(major, minor, patch, bump_type):
    """バージョンをインクリメント"""
    if bump_type == "patch":
        patch += 1
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        print(f"❌ Invalid bump type: {bump_type}")
        return None
    
    return f"{major}.{minor}.{patch}"

def write_version(version):
    """version.txt に書き込み"""
    hash_short = get_git_hash()
    full_version = f"{version}+{hash_short}"
    
    with open("version.txt", "w", encoding="utf-8") as f:
        f.write(full_version)
    
    return full_version

def main():
    print()
    print("=" * 50)
    print("  自動バージョンバンプ")
    print("=" * 50)
    print()
    
    # 現在のバージョンを読む
    current_version = read_version()
    if not current_version:
        sys.exit(1)
    
    print(f"📍 現在のバージョン: {current_version}")
    print()
    
    # インクリメント種類を選択
    print("=====================")
    print("バージョンのインクリメント:")
    print("  1. Patch (1.0.0 -> 1.0.1)")
    print("  2. Minor (1.0.0 -> 1.1.0)")
    print("  3. Major (1.0.0 -> 2.0.0)")
    print("=====================")
    print()
    
    bump_choice = input("Select (1, 2 or 3): ").strip()
    
    bump_map = {"1": "patch", "2": "minor", "3": "major"}
    bump_type = bump_map.get(bump_choice)
    
    if not bump_type:
        print("❌ Invalid selection")
        sys.exit(1)
    
    # バージョンをパース
    major, minor, patch = parse_version(current_version)
    if major is None:
        sys.exit(1)
    
    # 新バージョンを計算
    new_version = increment_version(major, minor, patch, bump_type)
    if not new_version:
        sys.exit(1)
    
    print()
    print(f"✨ 新しいバージョン: {new_version} ({bump_type.upper()} bump)")
    print()
    
    # version.txt を更新
    full_version = write_version(new_version)
    print(f"✅ Updated version.txt: {full_version}")
    print()
    
    # コミットメッセージを入力
    msg = input("Commit message: ").strip()
    if not msg:
        msg = f"release {new_version}"
    
    # Git にコミット
    print()
    print("📤 Git に追加中...")
    run_command("git add version.txt")
    run_command(f'git commit -m "{msg}"')
    
    # リモートにプッシュ
    print("📤 リモートにプッシュ中...")
    run_command("git push origin main")
    
    # タグを作成
    tag = f"v{new_version}"
    print(f"🏷️  タグ作成: {tag}")
    run_command(f"git tag {tag}")
    
    # タグをプッシュ
    print("🚀 タグをプッシュ中...")
    run_command(f"git push origin {tag}")
    
    print()
    print("=" * 50)
    print("✅ SUCCESS")
    print("=" * 50)
    print(f"Tag: {tag}")
    print("GitHub Actions triggered")
    print("Build will start automatically...")
    print()

if __name__ == "__main__":
    main()
