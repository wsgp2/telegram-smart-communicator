import os


class ProxyManager:
    def __init__(self, proxy_folder="proxies"):
        self.proxy_folder = proxy_folder

    def load_proxies(self):
        if not os.path.exists(self.proxy_folder):
            os.makedirs(self.proxy_folder)
            return []

        proxies = []
        for fname in os.listdir(self.proxy_folder):
            path = os.path.join(self.proxy_folder, fname)
            if not os.path.isfile(path):
                continue
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    proxy = self.parse_proxy_line(line.strip())
                    if proxy:
                        proxies.append(proxy)
        return proxies

    def load_india_proxies(self):
        proxy_file = os.path.join(self.proxy_folder, "proxys_india_1000.txt")
        if not os.path.exists(proxy_file):
            return []

        proxies = []
        with open(proxy_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                proxy = self.parse_proxy_line(line.strip())
                if proxy:
                    proxies.append(proxy)
        return proxies

    def parse_proxy_line(self, line):
        if not line:
            return None

        try:
            if "://" in line:
                proxy_parts = line.split("://")
                proxy_type = proxy_parts[0].lower()
                auth_host = proxy_parts[1]

                if "@" in auth_host:
                    auth, host_port = auth_host.split("@")
                    user, pwd = auth.split(":") if ":" in auth else (auth, "")
                else:
                    host_port = auth_host
                    user, pwd = None, None

                host, port = host_port.split(":")
                return (proxy_type, host, int(port), user, pwd)
            else:
                parts = line.split(":")
                if len(parts) >= 2:
                    host = parts[0]
                    port = int(parts[1])
                    user = parts[2] if len(parts) > 2 else None
                    pwd = parts[3] if len(parts) > 3 else None
                    return ("socks5", host, port, user, pwd)
        except Exception:
            pass
        return None

    def create_proxy_tuple(self, proxy_info):
        if not proxy_info:
            return None

        proxy_type, host, port, user, pwd = proxy_info
        telethon_proxy_type = {
            "socks5": "socks5", "socks4": "socks4",
            "http": "http", "https": "http", "mtproto": "mtproto"
        }.get(proxy_type.lower(), "socks5")

        if user and pwd:
            return (telethon_proxy_type, host, port, True, user, pwd)
        else:
            return (telethon_proxy_type, host, port, True)

    def assign_proxies_to_sessions(self, session_files, proxies, accounts_per_proxy):
        if not proxies:
            return [None] * len(session_files)

        if len(proxies) == 1:
            return [proxies[0]] * len(session_files)

        assigned = []
        for i, proxy in enumerate(proxies):
            start_idx = i * accounts_per_proxy
            end_idx = min((i + 1) * accounts_per_proxy, len(session_files))
            for j in range(start_idx, end_idx):
                if j < len(session_files):
                    assigned.append(proxy)

        remaining = len(session_files) - len(assigned)
        if remaining > 0:
            for i in range(remaining):
                proxy_idx = i % len(proxies)
                assigned.append(proxies[proxy_idx])

        return assigned