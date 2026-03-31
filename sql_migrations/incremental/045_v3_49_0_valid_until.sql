-- Заполнить valid_until для старых записей поверок/аттестаций
UPDATE equipment_maintenance em
SET valid_until = em.maintenance_date + (e.metrology_interval || ' months')::interval
FROM equipment e
WHERE em.equipment_id = e.id
  AND em.valid_until IS NULL
  AND em.maintenance_type IN ('VERIFICATION', 'ATTESTATION')
  AND e.metrology_interval IS NOT NULL
  AND e.metrology_interval > 0;