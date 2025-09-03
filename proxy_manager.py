import os


class ProxyManager:
    def __init__(self, proxy_folder="proxies"):
        self.proxy_folder = proxy_folder
        os.makedirs(proxy_folder, exist_ok=True)

    def load_proxies(self, filename=None):
        """
        Загрузка прокси из указанного файла или всех файлов в папке.
        Возвращает список прокси-кортежей (proxy_type, host, port, user, pwd)
        """
        proxies = []
        if filename:
            files = [os.path.join(self.proxy_folder, filename)]
        else:
            files = [os.path.join(self.proxy_folder, f) for f in os.listdir(self.proxy_folder) if os.path.isfile(os.path.join(self.proxy_folder, f))]

        for path in files:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        proxy = self.parse_proxy_line(line.strip())
                        if proxy:
                            proxies.append(proxy)
            except Exception:
                pass
        return proxies

    def load_india_proxies(self):
        """Загрузка прокси для Индии"""
        return self.load_proxies("proxys_india_1000.txt")

    @staticmethod
    def parse_proxy_line(line):
        """
        Парсинг строки прокси.
        Поддерживаются форматы:
        - type://user:pass@host:port
        - host:port
        - host:port:user:pass
        """
        if not line or line.startswith("#"):
            return None

        try:
            if "://" in line:
                proxy_type, rest = line.split("://", 1)
                if "@" in rest:
                    auth, host_port = rest.split("@")
                    user, pwd = (auth.split(":") + [""])[:2]
                else:
                    host_port = rest
                    user = pwd = None
                host, port = host_port.split(":")
                return (proxy_type.lower(), host, int(port), user, pwd)
            else:
                parts = line.split(":")
                if len(parts) >= 2:
                    host = parts[0]
                    port = int(parts[1])
                    user = parts[2] if len(parts) > 2 else None
                    pwd = parts[3] if len(parts) > 3 else None
                    return ("socks5", host, port, user, pwd)
        except Exception:
            return None

    @staticmethod
    def create_proxy_tuple(proxy_info):
        """
        Создание кортежа для Telethon:
        (proxy_type, host, port, rdns, user, password)
        """
        if not proxy_info:
            return None

        proxy_type, host, port, user, pwd = proxy_info
        telethon_type = {
            "socks5": "socks5",
            "socks4": "socks4",
            "http": "http",
            "https": "http",
            "mtproto": "mtproto"
        }.get(proxy_type.lower(), "socks5")

        if user and pwd:
            return (telethon_type, host, port, True, user, pwd)
        else:
            return (telethon_type, host, port, True)

    @staticmethod
    def assign_proxies_to_sessions(session_files, proxies, accounts_per_proxy=1):
        """
        Распределение прокси по сессиям.
        Возвращает список длиной len(session_files)
        """
        if not proxies:
            return [None] * len(session_files)

        assigned = []
        proxy_count = len(proxies)
        for idx, session in enumerate(session_files):
            proxy_idx = (idx // accounts_per_proxy) % proxy_count
            assigned.append(proxies[proxy_idx])
        return assigned
