BEGIN;

ALTER TABLE samples DROP CONSTRAINT samples_status_check;

ALTER TABLE samples ADD CONSTRAINT samples_status_check CHECK (
    status::text = ANY (ARRAY[
        'PENDING_VERIFICATION'::character varying,
        'REGISTERED'::character varying,
        'CANCELLED'::character varying,
        'MANUFACTURING'::character varying,
        'MANUFACTURED'::character varying,
        'TRANSFERRED'::character varying,
        'UZK_TESTING'::character varying,
        'UZK_READY'::character varying,
        'MOISTURE_CONDITIONING'::character varying,
        'MOISTURE_READY'::character varying,
        'ACCEPTED_IN_LAB'::character varying,
        'CONDITIONING'::character varying,
        'READY_FOR_TEST'::character varying,
        'IN_TESTING'::character varying,
        'TESTED'::character varying,
        'PENDING_MENTOR_REVIEW'::character varying,
        'DRAFT_READY'::character varying,
        'RESULTS_UPLOADED'::character varying,
        'PROTOCOL_ISSUED'::character varying,
        'COMPLETED'::character varying,
        'REPLACEMENT_PROTOCOL'::character varying
    ]::text[])
);

COMMIT;