#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from user_manager import UserManager


async def main():
    print("📱 Phone Number Converter")

    user_manager = UserManager()
    converted = await user_manager.convert_phones_to_usernames()

    if converted > 0:
        print(f"✅ Successfully converted {converted} numbers")
        move = input("Move converted users to target? (y/n): ").lower()
        if move == 'y':
            moved = await user_manager.move_new_to_target()
            print(f"✅ Moved {moved} users to target")
    else:
        print("❌ No numbers converted")


if __name__ == "__main__":
    asyncio.run(main())