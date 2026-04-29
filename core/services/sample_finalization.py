"""
core/services/sample_finalization.py
v3.89.0/v3.92.0: Финализация подтверждённых черновиков.

Назначение
----------
Выпуск пула подтверждённых черновиков (status=DRAFT_REGISTERED) в основной
журнал: атомарное присвоение sequence_number / cipher / pi_number в заданном
порядке и переход в статус PENDING_VERIFICATION.

Поток (с v3.92.0):
    создание → DRAFT (черновик)
            → подтверждение регистратором → DRAFT_REGISTERED
            → выпуск (этот модуль) → PENDING_VERIFICATION
            → проверка → REGISTERED.

Архитектура синхронизации
-------------------------
Sample.sequence_number вычисляется как MAX(sequence_number) + 1 по всей
таблице samples. Без сериализации одновременные вызовы из двух процессов
прочитают одинаковый MAX и попытаются вставить одинаковый номер →
IntegrityError на UNIQUE.

Решение: PostgreSQL advisory lock с фиксированным ключом. Все процессы,
бронирующие номера, обязаны взять этот lock в начале своей транзакции;
PostgreSQL сериализует их в порядке поступления. Lock автоматически
освобождается на COMMIT/ROLLBACK (xact_lock).

Тот же ключ должен использоваться и при одиночной регистрации (если
там тоже бронируется sequence_number) — иначе одиночный вызов и пул
будут дёргать MAX() параллельно. На текущем этапе одиночная регистрация
идёт через Sample.save() напрямую и в этой развилке не защищена;
интеграция планируется отдельно.
"""

from datetime import date as date_cls

from django.db import connection, transaction
from django.db.models import Max

from core.models import Sample, SampleStatus

# Произвольная константа, общая для всех мест бронирования
# sequence_number. Менять только согласованно по всему проекту.
SAMPLE_SEQUENCE_LOCK_KEY = 7834521


def _route_status_after_release(sample):
    """
    Определяет целевой статус образца сразу после выпуска из черновика.

    ⭐ v3.92.0: Поскольку черновик уже был подтверждён (DRAFT_REGISTERED),
    шаг PENDING_VERIFICATION пропускается — образец сразу идёт в рабочий
    статус, в зависимости от флагов:

        0. uzk_required=True → UZK_TESTING (УЗК до всего)
        1. moisture_conditioning + moisture_sample_id → MOISTURE_CONDITIONING
        2. manufacturing=True → MANUFACTURING (нарезка)
        3. moisture_conditioning (без зависимости) → MOISTURE_CONDITIONING
        4. Иначе → REGISTERED

    Маршрутизация полностью совпадает с verify_sample (action='approve')
    в core/views/verification_views.py — это единственный другой способ
    попасть в эти статусы. Если меняете там, согласуйте здесь.
    """
    if sample.uzk_required:
        return SampleStatus.UZK_TESTING
    if sample.moisture_conditioning:
        return SampleStatus.MOISTURE_CONDITIONING
    if sample.manufacturing:
        return SampleStatus.MANUFACTURING
    return SampleStatus.REGISTERED


def finalize_drafts(draft_ids_in_order, released_by, registration_date=None):
    """
    Выпускает пул подтверждённых черновиков в основной журнал.

    Args:
        draft_ids_in_order: список ID черновиков (status=DRAFT_REGISTERED)
            в желаемом порядке присвоения номеров. Первый ID получит
            наименьший номер, последний — наибольший. Сортировка делается
            ВЫЗЫВАЮЩЕЙ стороной (UI: по created_at по умолчанию, либо
            после ручного drag-and-drop в модалке).
        released_by: User, инициировавший выпуск (для аудит-лога).
        registration_date: дата регистрации, проставляемая всем
            образцам пула. None → date.today().

    Returns:
        list[Sample]: финализированные образцы в том же порядке,
            что был передан, с присвоенными номерами и шифрами.

    Raises:
        ValueError: если в списке есть дубликаты ID; если какие-то
            ID не найдены в БД; если среди них есть не в статусе
            DRAFT_REGISTERED (например, ещё неподтверждённые DRAFT,
            или уже выпущенные в параллельной сессии).
    """
    if not draft_ids_in_order:
        return []

    if len(draft_ids_in_order) != len(set(draft_ids_in_order)):
        raise ValueError('В draft_ids_in_order есть дубликаты ID')

    if registration_date is None:
        registration_date = date_cls.today()

    with transaction.atomic():
        # 1) Сериализуем все выпуски через advisory lock.
        # Если параллельно идёт другой выпуск — ждём, пока тот закоммитится.
        with connection.cursor() as cur:
            cur.execute(
                'SELECT pg_advisory_xact_lock(%s)',
                [SAMPLE_SEQUENCE_LOCK_KEY],
            )

        # 2) Загружаем черновики, сохраняя желаемый порядок.
        drafts_by_id = {
            s.id: s
            for s in (
                Sample.objects
                .select_related('laboratory', 'acceptance_act')
                .filter(id__in=draft_ids_in_order)
            )
        }

        missing = set(draft_ids_in_order) - set(drafts_by_id.keys())
        if missing:
            raise ValueError(
                f'Не найдены черновики: {sorted(missing)}'
            )

        non_releasable = [
            sid for sid in draft_ids_in_order
            if drafts_by_id[sid].status != SampleStatus.DRAFT_REGISTERED
        ]
        if non_releasable:
            raise ValueError(
                f'В пуле есть образцы не в статусе DRAFT_REGISTERED: '
                f'{non_releasable}. Возможно, кто-то уже выпустил их в '
                f'параллельной сессии, или среди них есть неподтверждённые '
                f'черновики (DRAFT). Выпуск разрешён только для '
                f'подтверждённых черновиков.'
            )

        # ⭐ v3.92.0: Проверка и топологическая сортировка по protocol_leader_id.
        # Если в пуле есть follower (protocol_leader_id != NULL), нужно убедиться,
        # что лидер либо тоже в пуле (тогда выпускаем вместе, лидера первым),
        # либо уже выпущен ранее (его pi_number будет автоматически подхвачен
        # follower'ом через Sample.save()). Если лидер сам всё ещё DRAFT/
        # DRAFT_REGISTERED и не в пуле — ошибка с подсказкой.
        pool_set = set(draft_ids_in_order)
        for sid, draft in drafts_by_id.items():
            if not draft.protocol_leader_id:
                continue
            leader_id = draft.protocol_leader_id
            if leader_id in pool_set:
                # лидер в пуле — топологическая сортировка ниже разрулит порядок
                continue
            # Лидер не в пуле — проверим его статус
            try:
                leader_status = (
                    Sample.objects
                    .filter(pk=leader_id)
                    .values_list('status', flat=True)
                    .first()
                )
            except Exception:
                leader_status = None
            if leader_status in ('DRAFT', 'DRAFT_REGISTERED'):
                raise ValueError(
                    f'Образец #{sid} прикреплён к черновику-лидеру #{leader_id}, '
                    f'который ещё не выпущен. Сначала выпустите #{leader_id} '
                    f'или включите его в текущий пул.'
                )
            # Если leader_status — рабочий статус (REGISTERED и т.д.) или None
            # (лидера удалили, ON DELETE SET NULL уже отработал) — всё ок:
            # Sample.save() для follower'а либо подтянет leader.pi_number,
            # либо сгенерирует свой через generate_pi_number().

        # Топологическая сортировка пула: лидеры идут перед своими followers.
        # Граф плоский (лидер → followers, без вложенности — защита от цепочек
        # на уровне save_logic), поэтому сортируем простой стабильной перестановкой:
        # сначала все sample-id без лидера-в-пуле, потом sample-id с лидером-в-пуле.
        # Если бы граф был многоуровневый, понадобился бы Кана/DFS — но в нашей
        # бизнес-модели это избыточно.
        leaders_first = [
            sid for sid in draft_ids_in_order
            if drafts_by_id[sid].protocol_leader_id not in pool_set
        ]
        followers_after = [
            sid for sid in draft_ids_in_order
            if drafts_by_id[sid].protocol_leader_id in pool_set
        ]
        ordered_ids = leaders_first + followers_after

        # 3) Резервируем диапазон номеров.
        # Под advisory-lock'ом MAX() стабилен до конца транзакции:
        # никто другой не сможет вставить sequence_number, пока мы
        # не закоммитимся.
        max_num = Sample.objects.aggregate(m=Max('sequence_number'))['m'] or 0
        start_seq = max_num + 1

        # 4) Финализируем по одному, сохраняя порядок (с учётом топ-сортировки).
        # Через sample.save() — он сам перегенерит cipher/pi_number/panel_id
        # по актуальным реквизитам. Guard для DRAFT/DRAFT_REGISTERED в save()
        # сработает по старому состоянию объекта в памяти, поэтому СНАЧАЛА
        # меняем status, потом save().
        #
        # ⭐ v3.92.0: целевой статус — НЕ PENDING_VERIFICATION. Черновик
        # уже подтверждён вторым регистратором (DRAFT_REGISTERED), поэтому
        # шаг повторной проверки пропускается. Маршрутизация по флагам
        # (UZK / влагонасыщение / нарезка / просто REGISTERED) полностью
        # совпадает с тем, что делает verify_sample при approve.
        # ⭐ v3.92.0: лидер сохраняется первым → в БД появляется его pi_number;
        # следующий save() для follower'а подтянет этот pi_number из БД через
        # свежий запрос в Sample.save() (см. блок protocol_leader_id).
        finalized = []
        for offset, sid in enumerate(ordered_ids):
            draft = drafts_by_id[sid]
            draft.sequence_number = start_seq + offset
            draft.registration_date = registration_date
            draft.status = _route_status_after_release(draft)
            # cipher и pi_number проставит Sample.save():
            # cipher через generate_cipher() → требует sequence_number и
            #   registration_date — оба уже выставлены выше.
            # pi_number — приоритет: protocol_leader.pi_number, потом
            #   _use_existing_pi_number, потом generate_pi_number().
            draft.save()
            finalized.append(draft)

        # 5. Аудит — отдельная запись на каждый выпуск.
        # Пишем напрямую в AuditLog (не через log_action), потому что
        # log_action принимает request, а сервис намеренно request-free —
        # чтобы его можно было дёргать из management-команд и фоновых задач.
        # Импорты внутри функции — циклические импорты на старте Django.
        from core.models import AuditLog
        audit_records = [
            AuditLog(
                user=released_by,
                entity_type='sample',
                entity_id=draft.id,
                action='sample_finalized_from_draft',
                field_name='status',
                old_value='DRAFT_REGISTERED',
                new_value=draft.status,
                extra_data={
                    'sequence_number': draft.sequence_number,
                    'cipher': draft.cipher,
                    'registration_date': str(registration_date),
                },
            )
            for draft in finalized
        ]
        AuditLog.objects.bulk_create(audit_records)

    # COMMIT отпустил advisory-lock — следующий пул может стартовать.
    return finalized