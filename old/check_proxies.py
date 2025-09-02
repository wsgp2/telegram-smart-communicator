#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔍 Проверка прокси серверов
Простой скрипт для тестирования работоспособности HTTP прокси
"""

import subprocess
import time
import concurrent.futures
from typing import List, Dict, Tuple

def load_proxies(file_path: str = "proxies/proxy.txt") -> List[Dict[str, str]]:
    """Загружает прокси из файла"""
    proxies = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split(':')
                    if len(parts) == 4:
                        proxies.append({
                            'host': parts[0],
                            'port': int(parts[1]),
                            'username': parts[2],
                            'password': parts[3],
                            'line': line_num,
                            'raw': line
                        })
                    else:
                        print(f"❌ Неверный формат строки {line_num}: {line}")
        
        print(f"📁 Загружено {len(proxies)} прокси из {file_path}")
        return proxies
        
    except FileNotFoundError:
        print(f"❌ Файл {file_path} не найден!")
        return []
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return []

def test_proxy(proxy: Dict[str, str], timeout: int = 7) -> Tuple[bool, str, float]:
    """Тестирует один прокси через curl (SOCKS5 прокси)"""
    start_time = time.time()
    
    try:
        # Используем curl для тестирования SOCKS5 прокси
        cmd = [
            'curl', 
            '--socks5-hostname', f"{proxy['host']}:{proxy['port']}",
            '--proxy-user', f"{proxy['username']}:{proxy['password']}",
            '--connect-timeout', str(timeout),
            '--max-time', str(timeout),
            '--silent',
            '--show-error',
            'http://httpbin.org/ip'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+5)
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            # Парсим JSON ответ для получения IP
            try:
                import json
                data = json.loads(result.stdout)
                ip = data.get('origin', 'Unknown IP')
                return True, ip, elapsed
            except:
                return True, "Response OK", elapsed
        else:
            error_msg = result.stderr.strip() if result.stderr else f"Exit code {result.returncode}"
            if len(error_msg) > 50:
                error_msg = error_msg[:47] + "..."
            return False, error_msg, elapsed
            
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        return False, "Timeout", elapsed
    except Exception as e:
        elapsed = time.time() - start_time
        error_msg = str(e)
        if len(error_msg) > 50:
            error_msg = error_msg[:47] + "..."
        return False, error_msg, elapsed

def check_all_proxies():
    """Проверяет все прокси"""
    print("🚀 НАЧИНАЕМ ПРОВЕРКУ ПРОКСИ")
    print("=" * 60)
    
    proxies = load_proxies()
    if not proxies:
        print("❌ Нет прокси для проверки!")
        return
    
    working_proxies = []
    failed_proxies = []
    
    print(f"🧪 Тестируем {len(proxies)} прокси (таймаут: 7 сек каждый)...")
    print("")
    
    # Тестируем прокси по очереди (последовательно для лучшего вывода)
    for i, proxy in enumerate(proxies, 1):
        print(f"[{i:2}/{len(proxies)}] Тестируем {proxy['host']}:{proxy['port']}...", end=" ")
        
        success, result, elapsed = test_proxy(proxy)
        
        if success:
            print(f"✅ OK ({elapsed:.1f}s) - IP: {result}")
            working_proxies.append({**proxy, 'response_time': elapsed, 'ip': result})
        else:
            print(f"❌ FAIL ({elapsed:.1f}s) - {result}")
            failed_proxies.append({**proxy, 'error': result, 'response_time': elapsed})
    
    # Итоговая статистика
    print("")
    print("=" * 60)
    print("📊 ИТОГИ ПРОВЕРКИ:")
    print(f"✅ Рабочих прокси: {len(working_proxies)}")
    print(f"❌ Нерабочих прокси: {len(failed_proxies)}")
    print(f"📈 Процент успеха: {len(working_proxies)/len(proxies)*100:.1f}%")
    
    # Топ рабочих прокси (по скорости)
    if working_proxies:
        print("")
        print("🏆 ТОП-5 БЫСТРЫХ ПРОКСИ:")
        sorted_proxies = sorted(working_proxies, key=lambda x: x['response_time'])
        for i, proxy in enumerate(sorted_proxies[:5], 1):
            print(f"  {i}. {proxy['host']}:{proxy['port']} - {proxy['response_time']:.1f}s - {proxy['ip']}")
    
    # Сохраняем рабочие прокси
    if working_proxies:
        with open('proxies/working_proxies.txt', 'w', encoding='utf-8') as f:
            for proxy in working_proxies:
                f.write(proxy['raw'] + '\n')
        print(f"\n💾 Рабочие прокси сохранены в: proxies/working_proxies.txt")
    
    # Сохраняем нерабочие прокси
    if failed_proxies:
        with open('proxies/failed_proxies.txt', 'w', encoding='utf-8') as f:
            for proxy in failed_proxies:
                f.write(f"{proxy['raw']} # ERROR: {proxy['error']}\n")
        print(f"🗑️ Нерабочие прокси сохранены в: proxies/failed_proxies.txt")

if __name__ == "__main__":
    print("🔍 ПРОВЕРКА ПРОКСИ СЕРВЕРОВ")
    print("Автор: Telegram Smart Communicator")
    print("")
    
    try:
        check_all_proxies()
    except KeyboardInterrupt:
        print("\n⏹️ Проверка прервана пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
    
    print("\n🏁 Проверка завершена!")
