import asyncio
import time
import random
import csv
import aiohttp
from collections import Counter
from urllib.parse import urlparse

# Настройки нагрузки
CONCURRENT_REQUESTS = 15  # Количество параллельных запросов
TOTAL_REQUESTS = 150       # Всего запросов в рамках одного теста
TIMEOUT_SECONDS = 5        # Таймаут ожидания ответа от сервера

# Список реальных User-Agent для имитации разных устройств
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
]

# Глобальные контейнеры метрик
stats = {
    "latencies": [],
    "status_codes": Counter(),
    "errors": Counter(),
    "rate_limited_count": 0,
    "raw_logs": []  # Сюда пишем данные для выгрузки в CSV
}

async def send_request(session, target_url, request_id, semaphore):
    """Отправляет запрос, замеряет скорость ответа и адаптируется под лимиты."""
    async with semaphore:
        user_agent = random.choice(USER_AGENTS)
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
            "Connection": "keep-alive"
        }
        
        start_time = time.time()
        try:
            timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
            async with session.get(target_url, headers=headers, timeout=timeout) as response:
                latency = time.time() - start_time
                
                # Фиксация базовой статистики
                stats["latencies"].append(latency)
                stats["status_codes"][response.status] += 1
                
                # Логируем каждую попытку для CSV отчёта
                stats["raw_logs"].append({
                    "Request_ID": request_id,
                    "Status": response.status,
                    "Latency_Sec": round(latency, 4),
                    "User_Agent": user_agent,
                    "Error": "None"
                })
                
                # Умное адаптивное сканирование
                if response.status == 429:
                    stats["rate_limited_count"] += 1
                    # Сервер перегружен или включил защиту — делаем паузу перед следующей попыткой в пуле
                    backoff_time = random.uniform(1.5, 3.0)
                    print(f"[!] Запрос {request_id}: Статус 429 (Rate Limit). Адаптивная пауза {backoff_time:.2f} сек...")
                    await asyncio.sleep(backoff_time)
                elif response.status == 403:
                    print(f"[!] Запрос {request_id}: Статус 403 (Forbidden) -> Возможно, сработал WAF.")
                else:
                    print(f"[+] Запрос {request_id}: Статус {response.status} | Время: {latency:.3f} сек")
                
        except asyncio.TimeoutError:
            stats["errors"]["Timeout"] += 1
            stats["raw_logs"].append({"Request_ID": request_id, "Status": "TIMEOUT", "Latency_Sec": TIMEOUT_SECONDS, "User_Agent": user_agent, "Error": "TimeoutError"})
            print(f"[-] Запрос {request_id}: Превышено время ожидания сервера")
        except aiohttp.ClientError as e:
            err_name = e.__class__.__name__
            stats["errors"][err_name] += 1
            stats["raw_logs"].append({"Request_ID": request_id, "Status": "ERROR", "Latency_Sec": 0, "User_Agent": user_agent, "Error": err_name})
            print(f"[-] Запрос {request_id}: Сетевая ошибка ({err_name})")

def prepare_url(user_input):
    """Безопасно форматирует и проверяет ввод пользователя."""
    user_input = user_input.strip()
    if not user_input.startswith(("http://", "https://")):
        user_input = "https://" + user_input
    
    parsed = urlparse(user_input)
    if not parsed.netloc:
        print("[-] Некорректный формат домена. Попробуйте еще раз.")
        return None
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

def save_to_csv(filename="audit_report.csv"):
    """Экспортирует собранные логи запросов в таблицу CSV."""
    if not stats["raw_logs"]:
        return
    
    keys = stats["raw_logs"][0].keys()
    with open(filename, 'w', newline='', encoding='utf-8') as output_file:
        dict_writer = csv.DictWriter(output_file, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(stats["raw_logs"])
    print(f"\n[Экспорт] Все сырые данные успешно сохранены в файл: {filename}")

async def main():
    print("=" * 60)
    print(" АСИНХРОННЫЙ АУДИТОР СЕТЕВОЙ БЕЗОПАСНОСТИ И ПРОИЗВОДИТЕЛЬНОСТИ")
    print("=" * 60)
    
    target_url = None
    while not target_url:
        user_input = input("Введите целевой домен (например, ddostest.me): ")
        target_url = prepare_url(user_input)
        
    print(f"\n[Запуск] Инициирован аудит для: {target_url}")
    print(f"[Конфигурация] Потоков: {CONCURRENT_REQUESTS} | Всего запросов: {TOTAL_REQUESTS}\n")
    
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    start_test_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = [
            asyncio.create_task(send_request(session, target_url, i, semaphore))
            for i in range(1, TOTAL_REQUESTS + 1)
        ]
        await asyncio.gather(*tasks)
        
    end_test_time = time.time()
    total_duration = end_test_time - start_test_time
    
    # Генерация итогового отчета
    print("\n" + "=" * 60)
    print("АНАЛИТИЧЕСКИЙ ОТЧЕТ СИСТЕМЫ ПО ЗАВЕРШЕНИИ ТЕСТА")
    print("=" * 60)
    print(f"Общее время выполнения теста: {total_duration:.2f} сек")
    
    if stats["latencies"]:
        avg_latency = sum(stats["latencies"]) / len(stats["latencies"])
        print(f"Среднее время ответа (Latency): {avg_latency:.4f} сек")
        print(f"Минимальное время ответа: {min(stats['latencies']):.4f} сек")
        print(f"Максимальное время ответа: {max(stats['latencies']):.4f} сек")
    
    print("\n[Статистика HTTP-ответов сервера]:")
    for code, count in stats["status_codes"].items():
        print(f"  HTTP {code}: {count} раз(а)")
        
    if stats["errors"]:
        print("\n[Статистика сбоев соединения]:")
        for err_type, count in stats["errors"].items():
            print(f"  {err_type}: {count} раз(а)")
            
    print("\n[Заключение по механизмам защиты]:")
    if stats["rate_limited_count"] > 0:
        print(f"  -> На сервере активна политика Rate Limiting. Зафиксировано {stats['rate_limited_count']} ограничений.")
        print("  -> Функция адаптивного сканирования успешно применила задержки для предотвращения перманентного бана.")
    elif stats["status_codes"][403] > (TOTAL_REQUESTS * 0.2):
        print("  -> Высокий процент ошибок 403 Forbidden. Сессия или пул заголовков частично заблокированы Web Application Firewall (WAF).")
    else:
        print("  -> Целевой узел стабильно обрабатывал входящую асинхронную нагрузку.")
    print("=" * 60)
    
    # Сохранение результатов в файл
    save_to_csv()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[-] Тестирование аварийно остановлено пользователем. Экспорт текущих данных...")
        save_to_csv()
