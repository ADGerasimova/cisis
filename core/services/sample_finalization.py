"""
core/services/sample_finalization.py
v3.89.0: Финализация черновиков параллельной регистрации.

Назначение
----------
Выпуск пула черновиков (status=DRAFT) в основной журнал: атомарное
присвоение sequence_number / cipher / pi_number в заданном порядке
и переход в статус PENDING_VERIFICATION.

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


def finalize_drafts(draft_ids_in_order, released_by, registration_date=None):
    """
    Выпускает пул черновиков в основной журнал.

    Args:
        draft_ids_in_order: список ID черновиков в желаемом порядке
            присвоения номеров. Первый ID получит наименьший номер,
            последний — наибольший. Сортировка делается ВЫЗЫВАЮЩЕЙ
            стороной (UI: по created_at по умолчанию, либо после
            ручного drag-and-drop в модалке).
        released_by: User, инициировавший выпуск (для аудит-лога).
        registration_date: дата регистрации, проставляемая всем
            образцам пула. None → date.today().

    Returns:
        list[Sample]: финализированные образцы в том же порядке,
            что был передан, с присвоенными номерами и шифрами.

    Raises:
        ValueError: если в списке есть дубликаты ID; если какие-то
            ID не найдены в БД; если среди них есть не-DRAFT.
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

        non_draft = [
            sid for sid in draft_ids_in_order
            if drafts_by_id[sid].status != SampleStatus.DRAFT
        ]
        if non_draft:
            raise ValueError(
                f'В пуле есть образцы не в статусе DRAFT: {non_draft}. '
                f'Возможно, кто-то уже выпустил их в параллельной сессии.'
            )

        # 3) Резервируем диапазон номеров.
        # Под advisory-lock'ом MAX() стабилен до конца транзакции:
        # никто другой не сможет вставить sequence_number, пока мы
        # не закоммитимся.
        max_num = Sample.objects.aggregate(m=Max('sequence_number'))['m'] or 0
        start_seq = max_num + 1

        # 4) Финализируем по одному, сохраняя порядок из draft_ids_in_order.
        # Через sample.save() — он сам перегенерит cipher/pi_number/panel_id
        # по актуальным реквизитам. Guard для DRAFT в save() сработает по
        # старому состоянию объекта в памяти, поэтому СНАЧАЛА меняем status,
        # потом save().
        finalized = []
        for offset, sid in enumerate(draft_ids_in_order):
            draft = drafts_by_id[sid]
            draft.sequence_number = start_seq + offset
            draft.registration_date = registration_date
            draft.status = SampleStatus.PENDING_VERIFICATION
            # cipher и pi_number проставит Sample.save():
            # cipher через generate_cipher() → требует sequence_number и
            #   registration_date — оба уже выставлены выше.
            # pi_number через generate_pi_number() — только если
            #   'PROTOCOL' в report_type и pi_number ещё пустой.
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
                old_value='DRAFT',
                new_value=SampleStatus.PENDING_VERIFICATION,
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
