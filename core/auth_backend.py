from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password
from core.models import User


class CustomUserBackend(BaseBackend):
    """
    Кастомный backend для аутентификации через password_hash вместо password
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        print(f"[AUTH] Попытка входа: username={username}, password={'*' * len(password) if password else None}")

        try:
            user = User.objects.get(username=username)
            print(f"[AUTH] Пользователь найден: {user.username}, hash={user.password_hash[:50]}...")

            # Проверяем пароль через password_hash
            result = check_password(password, user.password_hash)
            print(f"[AUTH] Проверка пароля: {result}")

            if result:
                return user
        except User.DoesNotExist:
            print(f"[AUTH] Пользователь {username} не найден")
            return None
        except Exception as e:
            print(f"[AUTH] Ошибка: {e}")
            return None

        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None