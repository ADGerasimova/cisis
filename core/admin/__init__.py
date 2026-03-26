"""
All admin classes are registered via @admin.register() decorators
in their respective modules.
"""

# Импортируем все модули чтобы декораторы @admin.register() сработали
from . import base_admin
from . import user_admin
from . import sample_admin
from . import permissions_admin
from . import logs_admin
from . import client_hierarchy_admin