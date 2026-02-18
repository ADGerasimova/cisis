"""
Модуль models разделён на логические группы для упрощения работы.

Импортируем всё здесь, чтобы Django и остальной код видел модели как раньше:
    from core.models import Sample, User, Laboratory  # работает!
"""

# ВАЖНО: Порядок импортов имеет значение из-за зависимостей между моделями

# 1. Сначала валидаторы (не зависят ни от чего)
from .base import validate_latin_only

# 2. Базовые справочники (минимум зависимостей)
from .base import (
    Laboratory,
    Client,
    ClientContact,
    Contract,
    ContractStatus,
    AccreditationArea,
    Standard,
    StandardAccreditationArea,
    Holiday,
)

# 3. Пользователи (зависят от Laboratory)
from .user import (
    User,
    UserRole,
)

# 4. Оборудование (зависит от Laboratory, User, AccreditationArea)
from .equipment import (
    Equipment,
    EquipmentType,
    EquipmentOwnership,
    EquipmentStatus,
    EquipmentAccreditationArea,
    EquipmentMaintenance,
    MaintenanceType,
)

# 5. Образцы (зависят от всех предыдущих)
from .sample import (
    Sample,
    SampleStatus,
    ReportType,
    ManufacturingStatus,
    SampleMeasuringInstrument,
    SampleTestingEquipment,
    SampleOperator,
)

# 6. Система прав доступа (зависит от User)
from .permissions import (
    Journal,
    JournalColumn,
    RolePermission,
    UserPermissionOverride,
    PermissionsLog,
    AccessLevel,
    PermissionType,
)

# 7. Журналы логов (зависят от Sample, User, Equipment, Laboratory)
from .logs import (
    ClimateLog,
    WeightLog,
    WorkshopLog,
    TimeLog,
)

# 8. Файлы (зависят от Sample, User)
from .files import (
    SampleFile,
)


# ═══════════════════════════════════════════════════════════════════
# __all__ — явно указываем что экспортируется при "from core.models import *"
# ═══════════════════════════════════════════════════════════════════

__all__ = [
    # Валидаторы
    'validate_latin_only',
    
    # Базовые справочники
    'Laboratory',
    'Client',
    'ClientContact',
    'Contract',
    'ContractStatus',
    'AccreditationArea',
    'Standard',
    'StandardAccreditationArea',
    'Holiday',
    
    # Пользователи
    'User',
    'UserRole',
    
    # Оборудование
    'Equipment',
    'EquipmentType',
    'EquipmentOwnership',
    'EquipmentStatus',
    'EquipmentAccreditationArea',
    'EquipmentMaintenance',
    'MaintenanceType',
    
    # Образцы
    'Sample',
    'SampleStatus',
    'ReportType',
    'ManufacturingStatus',
    'SampleMeasuringInstrument',
    'SampleTestingEquipment',
    'SampleOperator',
    
    # Система прав
    'Journal',
    'JournalColumn',
    'RolePermission',
    'UserPermissionOverride',
    'PermissionsLog',
    'AccessLevel',
    'PermissionType',
    
    # Журналы
    'ClimateLog',
    'WeightLog',
    'WorkshopLog',
    'TimeLog',
    
    # Файлы
    'SampleFile',
]
