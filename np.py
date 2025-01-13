from os import system
from requests import Session
from json import loads, JSONDecodeError
from uuid import uuid4
from time import sleep
import sys
from colorama import Fore, Style, init
from hashlib import md5
from requests.exceptions import ReadTimeout, ConnectionError, ProxyError, HTTPError
from random import choice
import sqlite3
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from itertools import cycle
import stem.process
from stem.util import term
import stem.control
import subprocess

init(autoreset=True)

# تنظیمات Tor
TOR_PORT = 9050
TOR_CONTROL_PORT = 9051

# تنظیمات Snowflake
SNOWFLAKE_CONFIG = {
    'UseBridges': '1',
    'ClientTransportPlugin': 'obfs4 exec /usr/bin/obfs4proxy',
    'Bridge': 'snowflake 192.0.2.3:1',
}

class TorManager:
    def __init__(self):
        self.tor_process = None
        self.session = None

    def start_tor(self):
        """شروع Tor با پیکربندی Snowflake"""
        try:
            print(f"{Fore.YELLOW}Starting Tor with Snowflake...{Style.RESET_ALL}")
            self.tor_process = stem.process.launch_tor_with_config(
                config={
                    'SocksPort': str(TOR_PORT),
                    'ControlPort': str(TOR_CONTROL_PORT),
                    **SNOWFLAKE_CONFIG
                },
                init_msg_handler=lambda line: print(f"{Fore.CYAN}{term.format(line, term.Color.BLUE)}{Style.RESET_ALL}") if "Bootstrapped" in line else None,
            )
            print(f"{Fore.GREEN}Tor started successfully!{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Failed to start Tor: {e}{Style.RESET_ALL}")
            sys.exit(1)

    def stop_tor(self):
        """متوقف کردن Tor"""
        if self.tor_process:
            print(f"{Fore.YELLOW}Stopping Tor...{Style.RESET_ALL}")
            self.tor_process.terminate()
            print(f"{Fore.GREEN}Tor stopped successfully!{Style.RESET_ALL}")

    def create_session(self):
        """ایجاد یک Session با استفاده از Tor"""
        self.session = Session()
        self.session.proxies = {
            'http': f'socks5h://127.0.0.1:{TOR_PORT}',
            'https': f'socks5h://127.0.0.1:{TOR_PORT}',
        }
        return self.session

class BotConfig:
    def __init__(self):
        self.doon_speed = 0.1
        self.search_speed = 2
        self.second_search_speed = 1
        self.max_doon = 5000
        self.attack_suspended = False
        self.fruit_pass = False
        self.custom_user_id = None
        self.retry_delay = 5
        self.max_retries = 5

class MultiDBManager:
    def __init__(self, league_id):
        self.dbs = {
            'normal': f'normal_league_{league_id}.db',
            'special': f'special_league_{league_id}.db',
            'users': f'users_league_{league_id}.db',
            'suspended': f'suspended_league_{league_id}.db'
        }
        self.init_all_dbs()

    def init_all_dbs(self):
        for db_path in self.dbs.values():
            self.init_db(db_path)

    def init_db(self, db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                id TEXT PRIMARY KEY,
                name TEXT,
                level INTEGER,
                power INTEGER,
                gold INTEGER,
                doon INTEGER,
                last_attack TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

user_agents = [
    'Dalvik/2.1.0 (Linux; U; Android 10; PO-X1100 Build/RP1A.200320.012)',
    'Dalvik/2.1.0 (Linux; U; Android 9; SM-A505F Build/PPR1.180610.011)',
    'Dalvik/2.1.0 (Linux; U; Android 11; SM-N9700 Build/RP1A.200720.012)',
]

def decode(data):
    return '&'.join([f"{key}={data[key]}" for key in data])

def change_url_base():
    global url_base
    url_base = 'https://iran.fruitcraft.ir/' if url_base == 'http://iran.fruitcraft.ir/' else 'http://iran.fruitcraft.ir/'

def make_request(session, method, url, data=None, timeout=10):
    retries = 0

    while retries < config.max_retries:
        try:
            if method.lower() == 'get':
                response = session.get(url, timeout=timeout)
            else:
                response = session.post(url, data=data, timeout=timeout)

            response.raise_for_status()

            if response.status_code == 429:
                print(f"{Fore.YELLOW}Rate limit hit. Waiting...{Style.RESET_ALL}")
                sleep(config.retry_delay)
                retries += 1
                continue

            return response

        except HTTPError as e:
            if e.response.status_code == 429:
                print(f"{Fore.YELLOW}Rate limit hit. Waiting...{Style.RESET_ALL}")
                sleep(config.retry_delay)
            else:
                print(f"{Fore.RED}HTTP Error: {e}. Retrying...{Style.RESET_ALL}")

        except (ReadTimeout, ConnectionError):
            print(f"{Fore.RED}Connection issue. Retrying...{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}Unexpected error: {e}. Retrying...{Style.RESET_ALL}")

        retries += 1
        sleep(config.retry_delay)

    return None

def load(restore_key):
    data = {
        'game_version': '1.7.10655',
        'device_name': 'unknown',
        'os_version': '10',
        'model': 'SM-A750F',
        'udid': config.custom_user_id or str(uuid4()),
        'store_type': 'iraqapps',
        'restore_key': restore_key,
        'os_type': 2
    }
    if config.fruit_pass:
        data['fruit_pass'] = '1'
    while True:
        try:
            response = make_request(session, 'post', f'{url_base}player/load', data)
            if response:
                return loads(response.text)
            raise ConnectionError("Failed to get response")
        except (ReadTimeout, ConnectionError):
            print(f"{Fore.RED}Connection issue encountered, waiting 5 seconds before retrying...{Style.RESET_ALL}")
            sleep(5)
            change_url_base()
        except JSONDecodeError as e:
            print(f"{Fore.RED}Error decoding JSON: {e}. Response text: {response.text}. Waiting 5 seconds before retrying...{Style.RESET_ALL}")
            sleep(5)
        except Exception as e:
            print(f"{Fore.RED}Unexpected error: {e}. Waiting 5 seconds before retrying...{Style.RESET_ALL}")
            sleep(5)

def save_high_gold_players_to_file(players, filename='gold.txt'):
    existing_players = set()
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            for line in f:
                if line.strip():
                    player_id = line.split(",")[1].split(":")[1].strip()
                    existing_players.add(player_id)
    with open(filename, 'a') as f:
        for player in players:
            if player['gold'] > 500000000000 and str(player['id']) not in existing_players:
                f.write(f"Name: {player['name']}, ID: {player['id']}, League: {player['league_id']}, Gold: {player['gold']}, Tribe: {player['tribe_name']}\n")

def fetch_players_from_server(session, min_level=8):
    try:
        response = make_request(session, 'get', f'{url_base}battle/getopponents')
        if not response:
            return []

        players = loads(response.text)['data']['players']
        save_high_gold_players_to_file(players)

        filtered_players = []
        for p in players:
            if p['level'] >= min_level:
                if not config.attack_suspended and p.get('is_suspended', False):
                    continue
                filtered_players.append({
                    'id': p['id'],
                    'def_power': p['def_power'],
                    'level': p['level'],
                    'league_id': p['league_id'],
                    'gold': p['gold'],
                    'name': p['name'],
                    'tribe': p['tribe_name']
                })
        return filtered_players
    except Exception as e:
        print(f"{Fore.RED}Error fetching players: {e}. Retrying...{Style.RESET_ALL}")
        sleep(5)
        change_url_base()
        return fetch_players_from_server(session, min_level)

def create_or_open_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS Accounts (
        id TEXT UNIQUE,
        power NUMERIC,
        level NUMERIC,
        league NUMERIC,
        PRIMARY KEY(id))''')
    conn.commit()
    return conn, cursor

def update_players_in_db(cursor, players, min_level_for_storage):
    for player in players:
        if player['level'] >= min_level_for_storage:
            cursor.execute('''INSERT INTO Accounts (id, power, level, league)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                power=excluded.power,
                level=excluded.level,
                league=excluded.league''',
                (player['id'], player['def_power'], player['level'], player['league_id']))

def get_enemies_from_db(db_path, max_power, min_level):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = '''SELECT id, power, level, league FROM Accounts WHERE level >= ?'''
    cursor.execute(query, (min_level,))
    enemies = cursor.fetchall()
    conn.close()
    return [{'id': e[0], 'power': e[1], 'level': e[2], 'league': e[3]} for e in enemies]

def battle(opponent_id, q, cards, attacks_in_today, hero_id=None):
    data = {
        'opponent_id': opponent_id,
        'check': md5(str(q).encode()).hexdigest(),
        'cards': str(cards).replace(' ', ''),
        'attacks_in_today': attacks_in_today
    }
    if hero_id:
        data['hero_id'] = hero_id
    if config.fruit_pass:
        data['fruit_pass'] = '1'
    
    print(f"{Fore.YELLOW}Sending request with data: {data}{Style.RESET_ALL}")
    response = make_request(session, 'get', f'{url_base}battle/battle?' + decode(data))
    if response:
        try:
            battle_result = loads(response.text)
            print(f"{Fore.CYAN}Server Response: {battle_result}{Style.RESET_ALL}")
            if 'data' in battle_result:
                doon = battle_result['data'].get('weekly_score', 0)
                xp = battle_result['data'].get('xp_added', 0)
                print(f"{Fore.GREEN}Updated Doon: {doon}, XP: {xp}{Style.RESET_ALL}")
                return battle_result
            else:
                print(f"{Fore.RED}Invalid battle result format: {battle_result}{Style.RESET_ALL}")
                return None
        except JSONDecodeError as e:
            print(f"{Fore.RED}Error decoding JSON: {e}. Response text: {response.text}{Style.RESET_ALL}")
            return None
    return None

def update_cards():
    global cards
    if cards:
        cards.append(cards[0])
        cards.pop(0)

def attack_offline():
    global db_file, conn, cursor
    q = load['data']['q']
    win = 0
    lost = 0
    xp = 0
    doon = 0
    attacked = {}
    while True:
        try:
            enemies = get_enemies_from_db(db_file, max_power, min_level)
            new_players = fetch_players_from_server(session, min_level=min_level)

            if new_players:
                update_players_in_db(cursor, new_players, min_level_for_storage)
                conn.commit()
            if not enemies:
                print(f"{Fore.YELLOW}No enemies found in database. Fetching new opponents...{Style.RESET_ALL}")
                enemies = fetch_players_from_server(session, min_level=8)
                if enemies:
                    update_players_in_db(cursor, enemies, min_level_for_storage)
                    conn.commit()
                    enemies = get_enemies_from_db(db_file, max_power, min_level)
            if not enemies:
                print(f"{Fore.YELLOW}No opponents available. Waiting {config.search_speed} seconds...{Style.RESET_ALL}")
                sleep(config.search_speed)
                continue

            def attack_enemy(enemy):
                nonlocal q, win, lost, xp, doon
                attacked[enemy['id']] = 0
                print(f"{Fore.MAGENTA}Attacking player ID: {Fore.BLUE}{enemy['id']}{Fore.MAGENTA}...Level: {Fore.GREEN}{enemy['level']}{Style.RESET_ALL}")

                for i in range(max_attempts_per_player):
                    battle_result = battle(enemy['id'], q, [cards[0]], attacked[enemy['id']])

                    if battle_result is None:
                        break

                    if battle_result['data'].get('xp_added', 0) > 0:
                        xp = battle_result["data"]["xp_added"]
                        win += 1
                    else:
                        lost += 1
                        break
                    doon = battle_result['data'].get('weekly_score', 0)
                    print(f"{Fore.GREEN}Updated Doon: {doon}, XP: {xp}{Style.RESET_ALL}")
                    if doon >= config.max_doon:
                        print(f"{Fore.YELLOW}Maximum doon reached ({config.max_doon}). Stopping attacks.{Style.RESET_ALL}")
                        return True

                    q = battle_result['data']['q']
                    attacked[enemy['id']] += 1
                    print(f"• player ID: {Fore.MAGENTA}{enemy['id']}{Fore.RESET} --- • Win: {Fore.GREEN}{win}{Fore.RESET} --- • Lose: {Fore.RED}{lost}{Fore.RESET} --- • Doon: {doon} --- • XP: {Fore.RED}{xp}{Fore.RESET}")
                    sleep(config.doon_speed)
                    update_cards()
                print(f"Finished attacking player ID: {enemy['id']}... Waiting {config.search_speed} seconds before next player.")
                sleep(config.search_speed)
                return False

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(attack_enemy, enemy) for enemy in enemies]
                for future in futures:
                    if future.result():
                        return
        except Exception as e:
            print(f"{Fore.RED}Error in attack_offline: {str(e)}. Retrying...{Style.RESET_ALL}")
            sleep(5)
            continue

def display_welcome_message():
    print(f"{Fore.LIGHTMAGENTA_EX}╔═══════════════════════════════════════╗")
    print(f"║ Welcome to the Battle Bot ║")
    print(f"║ Created by Nilo ║")
    print(f"╚═══════════════════════════════════════╝{Style.RESET_ALL}")
    print(f"{Fore.LIGHTYELLOW_EX}Let's start your adventure!{Style.RESET_ALL}")

def manage_multiple_accounts():
    accounts = []
    while True:
        choice = input(f"{Fore.LIGHTCYAN_EX}Do you want to add a new account? (yes/no): {Style.RESET_ALL}")
        if choice.lower() == 'yes':
            restore_key = input(f"{Fore.LIGHTCYAN_EX}Enter the restore key for the account: {Style.RESET_ALL}")
            accounts.append(restore_key)
        else:
            break
    for restore_key in accounts:
        load_account(restore_key)

def load_account(restore_key):
    global session, url_base, load, max_power, min_level, min_level_for_storage, max_attempts_per_player, cards, db_file, conn, cursor, config, multi_db
    session = tor_manager.create_session()
    selected_user_agent = choice(user_agents)
    session.headers.update({
        'User-Agent': selected_user_agent,
        'Accept-Encoding': 'gzip',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
    })
    url_base = 'http://iran.fruitcraft.ir/'
    config = BotConfig()

    print("\nAdditional Settings:")
    config.doon_speed = float(input("Doon Speed (Default 0.1): ") or config.doon_speed)
    config.search_speed = float(input("Search Speed (Default 2): ") or config.search_speed)
    config.second_search_speed = float(input("Second Search Speed (Default 1): ") or config.second_search_speed)
    config.max_doon = int(input("Max Doon (Default 5000): ") or config.max_doon)
    config.attack_suspended = input("Attack Suspended Players (y/n): ").lower() == 'y'
    config.fruit_pass = input("Activate Fruit Pass (y/n): ").lower() == 'y'
    custom_user_id = input("Custom User ID (Enter for random): ")
    if custom_user_id:
        config.custom_user_id = custom_user_id
    load = load(restore_key)
    if load['status']:
        print(f"{Fore.GREEN}Connection successful!{Style.RESET_ALL}")
        account_info = load['data']
        tribe_name = account_info['tribe']['name'] if account_info.get('tribe') else 'No Tribe'
        print(f"Account Name: {Fore.CYAN}{account_info['name']}{Style.RESET_ALL}, Level: {Fore.YELLOW}{account_info['level']}{Style.RESET_ALL}, Gold: {Fore.MAGENTA}{account_info['gold']}{Style.RESET_ALL}, Tribe: {Fore.BLUE}{tribe_name}{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}Connection failed! Please check your restore key.{Style.RESET_ALL}")
        return
    max_power = int(input(f"{Fore.LIGHTCYAN_EX}Enter your power: {Style.RESET_ALL}"))
    min_level = int(input(f"{Fore.LIGHTCYAN_EX}Enter the minimum level to attack: {Style.RESET_ALL}"))
    min_level_for_storage = int(input(f"{Fore.LIGHTCYAN_EX}Enter the minimum level for storage in the database: {Style.RESET_ALL}"))
    max_attempts_per_player = int(input(f"{Fore.LIGHTCYAN_EX}Enter the number of attacks per enemy: {Style.RESET_ALL}"))
    cards = []
    if input("Do you want to use Administrative Cards? (y/n): ").lower() == 'y':
        cards = [i['id'] for i in account_info['cards'] if i['power'] < 100]
    else:
        cards = [i['id'] for i in account_info['cards'] if i['power'] >= 100]
    if len(cards) < 20:
        print(f"{Fore.RED}You have less than 20 cards!!!{Style.RESET_ALL}")
        return
    players = fetch_players_from_server(session, min_level=min_level)
    if not players:
        print(f"{Fore.RED}No players fetched from the server.{Style.RESET_ALL}")
        return
    league_id = players[0]['league_id']
    multi_db = MultiDBManager(league_id)
    db_file = multi_db.dbs['normal']
    conn, cursor = create_or_open_db(db_file)
    update_players_in_db(cursor, players, min_level_for_storage)
    conn.commit()
    print(f"{Fore.GREEN}{len(players)} players stored in database.{Style.RESET_ALL}")
    while True:
        print("\n" * 4)
        attack_offline()

if __name__ == "__main__":
    try:
        tor_manager = TorManager()
        tor_manager.start_tor()
        display_welcome_message()
        manage_multiple_accounts()
        restore_key = input(f"{Fore.LIGHTCYAN_EX}Enter your restore key: {Style.RESET_ALL}")
        load_account(restore_key)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Bot stopped by user.{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}Fatal error: {str(e)}{Style.RESET_ALL}")
    finally:
        if 'conn' in globals():
            conn.close()
        tor_manager.stop_tor()
