--
-- PostgreSQL database dump
--

\restrict 4ZJUAqpyDXfOiMiFX7OQRpgLtHG0uBt9I8I5QndOondkhmdRT8uVbrcg6Av2GmX

-- Dumped from database version 16.11
-- Dumped by pg_dump version 16.11

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: prevent_user_deletion(); Type: FUNCTION; Schema: public; Owner: cisis_user
--

CREATE FUNCTION public.prevent_user_deletion() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION 'Удаление пользователей запрещено! Используйте деактивацию (is_active = FALSE)';
    RETURN NULL;
END;
$$;


ALTER FUNCTION public.prevent_user_deletion() OWNER TO cisis_user;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: acceptance_act_laboratories; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.acceptance_act_laboratories (
    id integer NOT NULL,
    act_id integer NOT NULL,
    laboratory_id integer NOT NULL,
    completed_date date
);


ALTER TABLE public.acceptance_act_laboratories OWNER TO cisis_user;

--
-- Name: TABLE acceptance_act_laboratories; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON TABLE public.acceptance_act_laboratories IS 'Лаборатории, задействованные в акте';


--
-- Name: COLUMN acceptance_act_laboratories.completed_date; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.acceptance_act_laboratories.completed_date IS 'Авто: дата последнего протокола, когда все образцы по этой лабе закрыты';


--
-- Name: acceptance_act_laboratories_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.acceptance_act_laboratories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.acceptance_act_laboratories_id_seq OWNER TO cisis_user;

--
-- Name: acceptance_act_laboratories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.acceptance_act_laboratories_id_seq OWNED BY public.acceptance_act_laboratories.id;


--
-- Name: acceptance_acts; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.acceptance_acts (
    id integer NOT NULL,
    contract_id integer NOT NULL,
    created_by_id integer,
    doc_number character varying(100) DEFAULT ''::character varying NOT NULL,
    document_name character varying(500) DEFAULT ''::character varying NOT NULL,
    document_status character varying(30) DEFAULT ''::character varying NOT NULL,
    samples_received_date date,
    work_deadline date,
    payment_terms character varying(30) DEFAULT ''::character varying NOT NULL,
    has_subcontract boolean DEFAULT false NOT NULL,
    comment text DEFAULT ''::text NOT NULL,
    services_count integer,
    work_cost numeric(12,2),
    payment_invoice character varying(200) DEFAULT ''::character varying NOT NULL,
    advance_date date,
    full_payment_date date,
    completion_act character varying(200) DEFAULT ''::character varying NOT NULL,
    invoice_number character varying(200) DEFAULT ''::character varying NOT NULL,
    document_flow character varying(20) DEFAULT ''::character varying NOT NULL,
    closing_status character varying(30) DEFAULT ''::character varying NOT NULL,
    work_status character varying(20) DEFAULT 'IN_PROGRESS'::character varying NOT NULL,
    sending_method character varying(30) DEFAULT ''::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.acceptance_acts OWNER TO cisis_user;

--
-- Name: TABLE acceptance_acts; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON TABLE public.acceptance_acts IS 'Акты приёма-передачи (входящие документы)';


--
-- Name: COLUMN acceptance_acts.doc_number; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.acceptance_acts.doc_number IS 'Короткий код латиницей (M1092) — для шифра образца';


--
-- Name: COLUMN acceptance_acts.document_name; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.acceptance_acts.document_name IS 'Название документа как передано заказчиком';


--
-- Name: COLUMN acceptance_acts.document_status; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.acceptance_acts.document_status IS 'Статус: SCANS_RECEIVED, ORIGINALS_RECEIVED';


--
-- Name: COLUMN acceptance_acts.payment_terms; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.acceptance_acts.payment_terms IS 'Условия оплаты: PREPAID, POSTPAID, ADVANCE_50, ADVANCE_30, OTHER';


--
-- Name: COLUMN acceptance_acts.document_flow; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.acceptance_acts.document_flow IS 'Документооборот: PAPER, EDO';


--
-- Name: COLUMN acceptance_acts.closing_status; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.acceptance_acts.closing_status IS 'Статус закрывающих: PREPARED, SENT_TO_CLIENT, RECEIVED, CANCELLED, NONE';


--
-- Name: COLUMN acceptance_acts.work_status; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.acceptance_acts.work_status IS 'Статус работ: IN_PROGRESS, CLOSED, CANCELLED';


--
-- Name: COLUMN acceptance_acts.sending_method; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.acceptance_acts.sending_method IS 'Способ отправки: COURIER, EMAIL, RUSSIAN_POST, GARANTPOST, IN_PERSON';


--
-- Name: acceptance_acts_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.acceptance_acts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.acceptance_acts_id_seq OWNER TO cisis_user;

--
-- Name: acceptance_acts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.acceptance_acts_id_seq OWNED BY public.acceptance_acts.id;


--
-- Name: accreditation_areas; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.accreditation_areas (
    id integer NOT NULL,
    name character varying(200) NOT NULL,
    code character varying(20) NOT NULL,
    description text DEFAULT ''::text,
    is_active boolean DEFAULT true,
    is_default boolean DEFAULT false
);


ALTER TABLE public.accreditation_areas OWNER TO cisis_user;

--
-- Name: accreditation_areas_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.accreditation_areas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.accreditation_areas_id_seq OWNER TO cisis_user;

--
-- Name: accreditation_areas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.accreditation_areas_id_seq OWNED BY public.accreditation_areas.id;


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.audit_log (
    id integer NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    user_id integer,
    entity_type character varying(50) NOT NULL,
    entity_id integer NOT NULL,
    action character varying(30) NOT NULL,
    field_name character varying(100),
    old_value text,
    new_value text,
    ip_address inet,
    extra_data jsonb
);


ALTER TABLE public.audit_log OWNER TO cisis_user;

--
-- Name: TABLE audit_log; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON TABLE public.audit_log IS 'Единый журнал аудита всех действий в системе CISIS';


--
-- Name: COLUMN audit_log.entity_type; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.audit_log.entity_type IS 'Тип сущности: sample, equipment, climate_log и т.д.';


--
-- Name: COLUMN audit_log.action; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.audit_log.action IS 'Тип действия: create, update, status_change, delete, m2m_add, m2m_remove';


--
-- Name: COLUMN audit_log.extra_data; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.audit_log.extra_data IS 'JSON с доп. контекстом (например, список изменённых M2M-связей)';


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.audit_log_id_seq OWNER TO cisis_user;

--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;


--
-- Name: auth_group; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.auth_group (
    id integer NOT NULL,
    name character varying(150) NOT NULL
);


ALTER TABLE public.auth_group OWNER TO cisis_user;

--
-- Name: auth_group_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

ALTER TABLE public.auth_group ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_group_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_group_permissions; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.auth_group_permissions (
    id bigint NOT NULL,
    group_id integer NOT NULL,
    permission_id integer NOT NULL
);


ALTER TABLE public.auth_group_permissions OWNER TO cisis_user;

--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

ALTER TABLE public.auth_group_permissions ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_group_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_permission; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.auth_permission (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    content_type_id integer NOT NULL,
    codename character varying(100) NOT NULL
);


ALTER TABLE public.auth_permission OWNER TO cisis_user;

--
-- Name: auth_permission_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

ALTER TABLE public.auth_permission ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_permission_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: client_contacts; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.client_contacts (
    id integer NOT NULL,
    client_id integer NOT NULL,
    full_name character varying(200) NOT NULL,
    "position" character varying(200) DEFAULT ''::character varying,
    phone character varying(50) DEFAULT ''::character varying,
    email character varying(255) DEFAULT ''::character varying,
    is_primary boolean DEFAULT false
);


ALTER TABLE public.client_contacts OWNER TO cisis_user;

--
-- Name: client_contacts_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.client_contacts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.client_contacts_id_seq OWNER TO cisis_user;

--
-- Name: client_contacts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.client_contacts_id_seq OWNED BY public.client_contacts.id;


--
-- Name: clients; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.clients (
    id integer NOT NULL,
    name character varying(500) NOT NULL,
    inn character varying(12) DEFAULT ''::character varying,
    address text DEFAULT ''::text,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.clients OWNER TO cisis_user;

--
-- Name: clients_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.clients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.clients_id_seq OWNER TO cisis_user;

--
-- Name: clients_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.clients_id_seq OWNED BY public.clients.id;


--
-- Name: climate_log; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.climate_log (
    id integer NOT NULL,
    laboratory_id integer NOT NULL,
    measured_at timestamp without time zone NOT NULL,
    temperature numeric(5,1) NOT NULL,
    humidity numeric(5,1) NOT NULL,
    measured_by_id integer NOT NULL,
    notes text DEFAULT ''::text
);


ALTER TABLE public.climate_log OWNER TO cisis_user;

--
-- Name: climate_log_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.climate_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.climate_log_id_seq OWNER TO cisis_user;

--
-- Name: climate_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.climate_log_id_seq OWNED BY public.climate_log.id;


--
-- Name: contracts; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.contracts (
    id integer NOT NULL,
    client_id integer NOT NULL,
    number character varying(100) NOT NULL,
    date date NOT NULL,
    end_date date,
    status character varying(20) DEFAULT 'ACTIVE'::character varying NOT NULL,
    notes text DEFAULT ''::text
);


ALTER TABLE public.contracts OWNER TO cisis_user;

--
-- Name: contracts_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.contracts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.contracts_id_seq OWNER TO cisis_user;

--
-- Name: contracts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.contracts_id_seq OWNED BY public.contracts.id;


--
-- Name: django_admin_log; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.django_admin_log (
    id integer NOT NULL,
    action_time timestamp with time zone NOT NULL,
    object_id text,
    object_repr character varying(200) NOT NULL,
    action_flag smallint NOT NULL,
    change_message text NOT NULL,
    content_type_id integer,
    user_id bigint NOT NULL,
    CONSTRAINT django_admin_log_action_flag_check CHECK ((action_flag >= 0))
);


ALTER TABLE public.django_admin_log OWNER TO cisis_user;

--
-- Name: django_admin_log_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

ALTER TABLE public.django_admin_log ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_admin_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_content_type; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.django_content_type (
    id integer NOT NULL,
    app_label character varying(100) NOT NULL,
    model character varying(100) NOT NULL
);


ALTER TABLE public.django_content_type OWNER TO cisis_user;

--
-- Name: django_content_type_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

ALTER TABLE public.django_content_type ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_content_type_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_migrations; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.django_migrations (
    id bigint NOT NULL,
    app character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    applied timestamp with time zone NOT NULL
);


ALTER TABLE public.django_migrations OWNER TO cisis_user;

--
-- Name: django_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

ALTER TABLE public.django_migrations ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_migrations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_session; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.django_session (
    session_key character varying(40) NOT NULL,
    session_data text NOT NULL,
    expire_date timestamp with time zone NOT NULL
);


ALTER TABLE public.django_session OWNER TO cisis_user;

--
-- Name: equipment; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.equipment (
    id integer NOT NULL,
    accounting_number character varying(50) NOT NULL,
    equipment_type character varying(20) NOT NULL,
    name character varying(200) NOT NULL,
    inventory_number character varying(50) NOT NULL,
    ownership character varying(200) DEFAULT 'OWN'::character varying NOT NULL,
    ownership_doc_number character varying(200) DEFAULT ''::character varying,
    manufacturer character varying(200) DEFAULT ''::character varying,
    year_of_manufacture integer,
    factory_number character varying(100) DEFAULT ''::character varying,
    state_registry_number character varying(200) DEFAULT ''::character varying,
    technical_documentation text DEFAULT ''::text,
    intended_use text DEFAULT ''::character varying,
    metrology_doc text DEFAULT ''::text,
    technical_specs text DEFAULT ''::text,
    software text DEFAULT ''::text,
    operating_conditions text DEFAULT ''::text,
    commissioning_info text DEFAULT ''::text,
    condition_on_receipt text DEFAULT ''::text,
    laboratory_id integer NOT NULL,
    status character varying(20) DEFAULT 'OPERATIONAL'::character varying NOT NULL,
    metrology_interval integer,
    modifications text DEFAULT ''::text,
    notes text DEFAULT ''::text,
    files_path character varying(500) DEFAULT ''::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    responsible_person_id integer,
    substitute_person_id integer
);


ALTER TABLE public.equipment OWNER TO cisis_user;

--
-- Name: equipment_accreditation_areas; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.equipment_accreditation_areas (
    id integer NOT NULL,
    equipment_id integer NOT NULL,
    accreditation_area_id integer NOT NULL
);


ALTER TABLE public.equipment_accreditation_areas OWNER TO cisis_user;

--
-- Name: equipment_accreditation_areas_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.equipment_accreditation_areas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.equipment_accreditation_areas_id_seq OWNER TO cisis_user;

--
-- Name: equipment_accreditation_areas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.equipment_accreditation_areas_id_seq OWNED BY public.equipment_accreditation_areas.id;


--
-- Name: equipment_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.equipment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.equipment_id_seq OWNER TO cisis_user;

--
-- Name: equipment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.equipment_id_seq OWNED BY public.equipment.id;


--
-- Name: equipment_maintenance; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.equipment_maintenance (
    id integer NOT NULL,
    equipment_id integer NOT NULL,
    maintenance_date date NOT NULL,
    maintenance_type character varying(20) NOT NULL,
    document_name text DEFAULT ''::text,
    reason text DEFAULT ''::text,
    description text DEFAULT ''::text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    performed_by_id integer
);


ALTER TABLE public.equipment_maintenance OWNER TO cisis_user;

--
-- Name: equipment_maintenance_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.equipment_maintenance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.equipment_maintenance_id_seq OWNER TO cisis_user;

--
-- Name: equipment_maintenance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.equipment_maintenance_id_seq OWNED BY public.equipment_maintenance.id;


--
-- Name: equipment_maintenance_logs; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.equipment_maintenance_logs (
    id integer NOT NULL,
    plan_id integer NOT NULL,
    performed_date date NOT NULL,
    performed_by_id integer,
    verified_by_id integer,
    status character varying(20) DEFAULT 'COMPLETED'::character varying NOT NULL,
    verified_date date,
    notes text DEFAULT ''::text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT equipment_maintenance_logs_status_check CHECK (((status)::text = ANY ((ARRAY['COMPLETED'::character varying, 'SKIPPED'::character varying, 'PARTIAL'::character varying, 'OVERDUE'::character varying])::text[])))
);


ALTER TABLE public.equipment_maintenance_logs OWNER TO cisis_user;

--
-- Name: TABLE equipment_maintenance_logs; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON TABLE public.equipment_maintenance_logs IS 'Журнал выполнения планового ТО оборудования';


--
-- Name: COLUMN equipment_maintenance_logs.plan_id; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.equipment_maintenance_logs.plan_id IS 'Ссылка на вид ТО из equipment_maintenance_plans';


--
-- Name: COLUMN equipment_maintenance_logs.status; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.equipment_maintenance_logs.status IS 'COMPLETED, SKIPPED, PARTIAL, OVERDUE';


--
-- Name: equipment_maintenance_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.equipment_maintenance_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.equipment_maintenance_logs_id_seq OWNER TO cisis_user;

--
-- Name: equipment_maintenance_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.equipment_maintenance_logs_id_seq OWNED BY public.equipment_maintenance_logs.id;


--
-- Name: equipment_maintenance_plans; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.equipment_maintenance_plans (
    id integer NOT NULL,
    equipment_id integer NOT NULL,
    name character varying(300) NOT NULL,
    frequency_count integer,
    frequency_unit character varying(10),
    frequency_period_value integer,
    frequency_condition text DEFAULT ''::text,
    is_condition_based boolean DEFAULT false NOT NULL,
    next_due_date date,
    is_active boolean DEFAULT true NOT NULL,
    notes text DEFAULT ''::text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_calendar_frequency CHECK (((is_condition_based = true) OR ((frequency_count IS NOT NULL) AND (frequency_unit IS NOT NULL) AND (frequency_period_value IS NOT NULL)))),
    CONSTRAINT equipment_maintenance_plans_frequency_unit_check CHECK (((frequency_unit)::text = ANY ((ARRAY['DAY'::character varying, 'WEEK'::character varying, 'MONTH'::character varying, 'YEAR'::character varying])::text[])))
);


ALTER TABLE public.equipment_maintenance_plans OWNER TO cisis_user;

--
-- Name: TABLE equipment_maintenance_plans; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON TABLE public.equipment_maintenance_plans IS 'Планы (виды) регулярного ТО оборудования';


--
-- Name: COLUMN equipment_maintenance_plans.frequency_count; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.equipment_maintenance_plans.frequency_count IS 'Сколько раз за период (1 = один раз)';


--
-- Name: COLUMN equipment_maintenance_plans.frequency_unit; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.equipment_maintenance_plans.frequency_unit IS 'Единица периода: DAY, WEEK, MONTH, YEAR';


--
-- Name: COLUMN equipment_maintenance_plans.frequency_period_value; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.equipment_maintenance_plans.frequency_period_value IS 'За сколько единиц считается период (3 = раз в 3 месяца, 5 = раз в 5 лет)';


--
-- Name: COLUMN equipment_maintenance_plans.frequency_condition; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.equipment_maintenance_plans.frequency_condition IS 'Текстовое условие (при загрязнении, при поломке и т.д.)';


--
-- Name: COLUMN equipment_maintenance_plans.is_condition_based; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.equipment_maintenance_plans.is_condition_based IS 'TRUE = ТО по условию, FALSE = по календарю';


--
-- Name: COLUMN equipment_maintenance_plans.next_due_date; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.equipment_maintenance_plans.next_due_date IS 'Расчётная дата следующего ТО (обновляется после выполнения)';


--
-- Name: equipment_maintenance_plans_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.equipment_maintenance_plans_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.equipment_maintenance_plans_id_seq OWNER TO cisis_user;

--
-- Name: equipment_maintenance_plans_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.equipment_maintenance_plans_id_seq OWNED BY public.equipment_maintenance_plans.id;


--
-- Name: file_type_defaults; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.file_type_defaults (
    id integer NOT NULL,
    category character varying(50) NOT NULL,
    file_type character varying(50) NOT NULL,
    default_visibility character varying(20) DEFAULT 'ALL'::character varying NOT NULL,
    default_subfolder character varying(200) DEFAULT ''::character varying NOT NULL
);


ALTER TABLE public.file_type_defaults OWNER TO cisis_user;

--
-- Name: file_type_defaults_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.file_type_defaults_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.file_type_defaults_id_seq OWNER TO cisis_user;

--
-- Name: file_type_defaults_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.file_type_defaults_id_seq OWNED BY public.file_type_defaults.id;


--
-- Name: file_visibility_rules; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.file_visibility_rules (
    id integer NOT NULL,
    file_type character varying(50) NOT NULL,
    category character varying(50) NOT NULL,
    role character varying(50) NOT NULL
);


ALTER TABLE public.file_visibility_rules OWNER TO cisis_user;

--
-- Name: file_visibility_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.file_visibility_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.file_visibility_rules_id_seq OWNER TO cisis_user;

--
-- Name: file_visibility_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.file_visibility_rules_id_seq OWNED BY public.file_visibility_rules.id;


--
-- Name: files; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.files (
    id integer NOT NULL,
    file_path character varying(1000) NOT NULL,
    original_name character varying(500) NOT NULL,
    file_size bigint NOT NULL,
    mime_type character varying(100) DEFAULT ''::character varying NOT NULL,
    category character varying(50) NOT NULL,
    file_type character varying(50) DEFAULT ''::character varying NOT NULL,
    sample_id integer,
    acceptance_act_id integer,
    contract_id integer,
    equipment_id integer,
    standard_id integer,
    owner_id integer,
    visibility character varying(20) DEFAULT 'ALL'::character varying NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    current_version boolean DEFAULT true NOT NULL,
    replaces_id integer,
    thumbnail_path character varying(1000) DEFAULT NULL::character varying,
    description character varying(1000) DEFAULT ''::character varying NOT NULL,
    uploaded_by_id integer NOT NULL,
    uploaded_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp with time zone,
    deleted_by_id integer,
    CONSTRAINT chk_files_category CHECK (((category)::text = ANY ((ARRAY['SAMPLE'::character varying, 'CLIENT'::character varying, 'EQUIPMENT'::character varying, 'STANDARD'::character varying, 'QMS'::character varying, 'PERSONAL'::character varying, 'INBOX'::character varying])::text[]))),
    CONSTRAINT chk_files_visibility CHECK (((visibility)::text = ANY ((ARRAY['ALL'::character varying, 'RESTRICTED'::character varying, 'PRIVATE'::character varying])::text[])))
);


ALTER TABLE public.files OWNER TO cisis_user;

--
-- Name: files_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.files_id_seq OWNER TO cisis_user;

--
-- Name: files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.files_id_seq OWNED BY public.files.id;


--
-- Name: holidays; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.holidays (
    id integer NOT NULL,
    date date NOT NULL,
    name character varying(200) NOT NULL,
    is_working boolean DEFAULT false
);


ALTER TABLE public.holidays OWNER TO cisis_user;

--
-- Name: holidays_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.holidays_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.holidays_id_seq OWNER TO cisis_user;

--
-- Name: holidays_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.holidays_id_seq OWNED BY public.holidays.id;


--
-- Name: journal_columns; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.journal_columns (
    id integer NOT NULL,
    journal_id integer NOT NULL,
    code character varying(100) NOT NULL,
    name character varying(200) NOT NULL,
    is_active boolean DEFAULT true,
    display_order integer DEFAULT 0
);


ALTER TABLE public.journal_columns OWNER TO cisis_user;

--
-- Name: journal_columns_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.journal_columns_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.journal_columns_id_seq OWNER TO cisis_user;

--
-- Name: journal_columns_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.journal_columns_id_seq OWNED BY public.journal_columns.id;


--
-- Name: journals; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.journals (
    id integer NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(200) NOT NULL,
    is_active boolean DEFAULT true
);


ALTER TABLE public.journals OWNER TO cisis_user;

--
-- Name: journals_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.journals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.journals_id_seq OWNER TO cisis_user;

--
-- Name: journals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.journals_id_seq OWNED BY public.journals.id;


--
-- Name: laboratories; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.laboratories (
    id integer NOT NULL,
    name character varying(200) NOT NULL,
    code character varying(10) NOT NULL,
    is_active boolean DEFAULT true,
    head_id integer,
    code_display character varying(10),
    department_type character varying(20) DEFAULT 'LAB'::character varying
);


ALTER TABLE public.laboratories OWNER TO cisis_user;

--
-- Name: COLUMN laboratories.department_type; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.laboratories.department_type IS 'LAB = лаборатория, WORKSHOP = мастерская, DEPARTMENT = подразделение';


--
-- Name: laboratories_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.laboratories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.laboratories_id_seq OWNER TO cisis_user;

--
-- Name: laboratories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.laboratories_id_seq OWNED BY public.laboratories.id;


--
-- Name: parameters; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.parameters (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    name_en character varying(255),
    unit character varying(50),
    description text,
    category character varying(50) DEFAULT 'OTHER'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    display_order integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.parameters OWNER TO cisis_user;

--
-- Name: TABLE parameters; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON TABLE public.parameters IS 'Единый справочник определяемых показателей';


--
-- Name: COLUMN parameters.category; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.parameters.category IS 'MECHANICAL / THERMAL / CHEMICAL / DIMENSIONAL / OTHER';


--
-- Name: parameters_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.parameters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.parameters_id_seq OWNER TO cisis_user;

--
-- Name: parameters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.parameters_id_seq OWNED BY public.parameters.id;


--
-- Name: permissions_log; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.permissions_log (
    id integer NOT NULL,
    changed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    changed_by_id integer NOT NULL,
    target_user_id integer,
    role character varying(20) DEFAULT ''::character varying,
    journal_id integer NOT NULL,
    column_id integer,
    old_access_level character varying(10) NOT NULL,
    new_access_level character varying(10) NOT NULL,
    reason text DEFAULT ''::text,
    permission_type character varying(20) NOT NULL
);


ALTER TABLE public.permissions_log OWNER TO cisis_user;

--
-- Name: permissions_log_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.permissions_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.permissions_log_id_seq OWNER TO cisis_user;

--
-- Name: permissions_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.permissions_log_id_seq OWNED BY public.permissions_log.id;


--
-- Name: personal_folder_access; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.personal_folder_access (
    id integer NOT NULL,
    owner_id integer NOT NULL,
    granted_to_id integer NOT NULL,
    access_level character varying(10) DEFAULT 'VIEW'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_pfa_access_level CHECK (((access_level)::text = ANY ((ARRAY['VIEW'::character varying, 'EDIT'::character varying])::text[])))
);


ALTER TABLE public.personal_folder_access OWNER TO cisis_user;

--
-- Name: personal_folder_access_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.personal_folder_access_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.personal_folder_access_id_seq OWNER TO cisis_user;

--
-- Name: personal_folder_access_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.personal_folder_access_id_seq OWNED BY public.personal_folder_access.id;


--
-- Name: role_laboratory_access; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.role_laboratory_access (
    id integer NOT NULL,
    role character varying(20) NOT NULL,
    journal_id integer NOT NULL,
    laboratory_id integer
);


ALTER TABLE public.role_laboratory_access OWNER TO cisis_user;

--
-- Name: TABLE role_laboratory_access; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON TABLE public.role_laboratory_access IS 'Видимость лабораторий по ролям для каждого журнала';


--
-- Name: COLUMN role_laboratory_access.laboratory_id; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.role_laboratory_access.laboratory_id IS 'NULL = все лаборатории';


--
-- Name: role_laboratory_access_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.role_laboratory_access_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.role_laboratory_access_id_seq OWNER TO cisis_user;

--
-- Name: role_laboratory_access_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.role_laboratory_access_id_seq OWNED BY public.role_laboratory_access.id;


--
-- Name: role_permissions; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.role_permissions (
    id integer NOT NULL,
    role character varying(20) NOT NULL,
    journal_id integer NOT NULL,
    column_id integer,
    access_level character varying(10) DEFAULT 'NONE'::character varying NOT NULL
);


ALTER TABLE public.role_permissions OWNER TO cisis_user;

--
-- Name: role_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.role_permissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.role_permissions_id_seq OWNER TO cisis_user;

--
-- Name: role_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.role_permissions_id_seq OWNED BY public.role_permissions.id;


--
-- Name: sample_auxiliary_equipment; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.sample_auxiliary_equipment (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    equipment_id integer NOT NULL
);


ALTER TABLE public.sample_auxiliary_equipment OWNER TO cisis_user;

--
-- Name: sample_auxiliary_equipment_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.sample_auxiliary_equipment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_auxiliary_equipment_id_seq OWNER TO cisis_user;

--
-- Name: sample_auxiliary_equipment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.sample_auxiliary_equipment_id_seq OWNED BY public.sample_auxiliary_equipment.id;


--
-- Name: sample_manufacturing_auxiliary_equipment; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.sample_manufacturing_auxiliary_equipment (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    equipment_id integer NOT NULL
);


ALTER TABLE public.sample_manufacturing_auxiliary_equipment OWNER TO cisis_user;

--
-- Name: sample_manufacturing_auxiliary_equipment_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.sample_manufacturing_auxiliary_equipment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_manufacturing_auxiliary_equipment_id_seq OWNER TO cisis_user;

--
-- Name: sample_manufacturing_auxiliary_equipment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.sample_manufacturing_auxiliary_equipment_id_seq OWNED BY public.sample_manufacturing_auxiliary_equipment.id;


--
-- Name: sample_manufacturing_measuring_instruments; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.sample_manufacturing_measuring_instruments (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    equipment_id integer NOT NULL
);


ALTER TABLE public.sample_manufacturing_measuring_instruments OWNER TO cisis_user;

--
-- Name: TABLE sample_manufacturing_measuring_instruments; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON TABLE public.sample_manufacturing_measuring_instruments IS 'Связь образца со средствами измерений для изготовления';


--
-- Name: sample_manufacturing_measuring_instruments_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.sample_manufacturing_measuring_instruments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_manufacturing_measuring_instruments_id_seq OWNER TO cisis_user;

--
-- Name: sample_manufacturing_measuring_instruments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.sample_manufacturing_measuring_instruments_id_seq OWNED BY public.sample_manufacturing_measuring_instruments.id;


--
-- Name: sample_manufacturing_operators; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.sample_manufacturing_operators (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    user_id integer NOT NULL
);


ALTER TABLE public.sample_manufacturing_operators OWNER TO cisis_user;

--
-- Name: TABLE sample_manufacturing_operators; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON TABLE public.sample_manufacturing_operators IS 'Связь образца с операторами изготовления (мастерская)';


--
-- Name: sample_manufacturing_operators_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.sample_manufacturing_operators_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_manufacturing_operators_id_seq OWNER TO cisis_user;

--
-- Name: sample_manufacturing_operators_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.sample_manufacturing_operators_id_seq OWNED BY public.sample_manufacturing_operators.id;


--
-- Name: sample_manufacturing_testing_equipment; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.sample_manufacturing_testing_equipment (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    equipment_id integer NOT NULL
);


ALTER TABLE public.sample_manufacturing_testing_equipment OWNER TO cisis_user;

--
-- Name: TABLE sample_manufacturing_testing_equipment; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON TABLE public.sample_manufacturing_testing_equipment IS 'Связь образца с испытательным оборудованием для изготовления';


--
-- Name: sample_manufacturing_testing_equipment_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.sample_manufacturing_testing_equipment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_manufacturing_testing_equipment_id_seq OWNER TO cisis_user;

--
-- Name: sample_manufacturing_testing_equipment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.sample_manufacturing_testing_equipment_id_seq OWNED BY public.sample_manufacturing_testing_equipment.id;


--
-- Name: sample_measuring_instruments; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.sample_measuring_instruments (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    equipment_id integer NOT NULL
);


ALTER TABLE public.sample_measuring_instruments OWNER TO cisis_user;

--
-- Name: sample_measuring_instruments_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.sample_measuring_instruments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_measuring_instruments_id_seq OWNER TO cisis_user;

--
-- Name: sample_measuring_instruments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.sample_measuring_instruments_id_seq OWNED BY public.sample_measuring_instruments.id;


--
-- Name: sample_operators; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.sample_operators (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    user_id integer NOT NULL
);


ALTER TABLE public.sample_operators OWNER TO cisis_user;

--
-- Name: sample_operators_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.sample_operators_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_operators_id_seq OWNER TO cisis_user;

--
-- Name: sample_operators_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.sample_operators_id_seq OWNED BY public.sample_operators.id;


--
-- Name: sample_parameters; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.sample_parameters (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    standard_parameter_id integer,
    custom_name character varying(255),
    custom_unit character varying(50),
    is_selected boolean DEFAULT true NOT NULL,
    display_order integer DEFAULT 0 NOT NULL,
    result_numeric numeric(15,6),
    result_text character varying(500),
    result_status character varying(20),
    tested_by_id integer,
    tested_at timestamp with time zone,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_custom_or_standard CHECK (((standard_parameter_id IS NOT NULL) OR (custom_name IS NOT NULL)))
);


ALTER TABLE public.sample_parameters OWNER TO cisis_user;

--
-- Name: TABLE sample_parameters; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON TABLE public.sample_parameters IS 'Показатели конкретного образца (выбранные из стандарта или кастомные)';


--
-- Name: COLUMN sample_parameters.is_selected; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.sample_parameters.is_selected IS 'TRUE — виден в поле «определяемые параметры», FALSE — только в таблице результатов';


--
-- Name: COLUMN sample_parameters.result_status; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.sample_parameters.result_status IS 'PENDING / FILLED / VALIDATED (будущее)';


--
-- Name: sample_parameters_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.sample_parameters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_parameters_id_seq OWNER TO cisis_user;

--
-- Name: sample_parameters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.sample_parameters_id_seq OWNED BY public.sample_parameters.id;


--
-- Name: sample_standards; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.sample_standards (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    standard_id integer NOT NULL
);


ALTER TABLE public.sample_standards OWNER TO cisis_user;

--
-- Name: sample_standards_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.sample_standards_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_standards_id_seq OWNER TO cisis_user;

--
-- Name: sample_standards_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.sample_standards_id_seq OWNED BY public.sample_standards.id;


--
-- Name: sample_testing_equipment; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.sample_testing_equipment (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    equipment_id integer NOT NULL
);


ALTER TABLE public.sample_testing_equipment OWNER TO cisis_user;

--
-- Name: sample_testing_equipment_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.sample_testing_equipment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_testing_equipment_id_seq OWNER TO cisis_user;

--
-- Name: sample_testing_equipment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.sample_testing_equipment_id_seq OWNED BY public.sample_testing_equipment.id;


--
-- Name: samples; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.samples (
    id integer NOT NULL,
    sequence_number integer NOT NULL,
    cipher character varying(500) NOT NULL,
    registration_date date NOT NULL,
    client_id integer NOT NULL,
    contract_id integer,
    contract_date date,
    laboratory_id integer NOT NULL,
    accompanying_doc_number character varying(100) NOT NULL,
    accreditation_area_id integer NOT NULL,
    test_code character varying(20) DEFAULT ''::character varying,
    test_type character varying(200) DEFAULT ''::character varying,
    working_days integer NOT NULL,
    sample_received_date date NOT NULL,
    object_info text DEFAULT ''::text,
    object_id character varying(200) DEFAULT ''::character varying,
    cutting_direction character varying(200) DEFAULT ''::character varying,
    test_conditions character varying(100) DEFAULT ''::character varying,
    panel_id character varying(200) DEFAULT ''::character varying,
    material character varying(200) DEFAULT ''::character varying,
    determined_parameters text NOT NULL,
    admin_notes text DEFAULT ''::text,
    deadline date NOT NULL,
    report_type character varying(20) DEFAULT 'PROTOCOL'::character varying NOT NULL,
    pi_number character varying(200) DEFAULT ''::character varying,
    manufacturing_date date,
    uzk_required boolean DEFAULT false,
    further_movement character varying(200) DEFAULT ''::character varying,
    registered_by_id integer NOT NULL,
    replacement_protocol_required boolean DEFAULT false,
    replacement_pi_number character varying(200) DEFAULT ''::character varying,
    test_status character varying(50) DEFAULT ''::character varying,
    report_prepared_by_id integer,
    operator_notes text DEFAULT ''::text,
    protocol_issued_date date,
    protocol_printed_date date,
    replacement_protocol_issued_date date,
    status character varying(30) DEFAULT 'REGISTERED'::character varying NOT NULL,
    files_path character varying(500) DEFAULT ''::character varying,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    verified_by integer,
    verified_at timestamp with time zone,
    protocol_checked_by integer,
    protocol_checked_at timestamp with time zone,
    replacement_count integer DEFAULT 0,
    conditioning_start_datetime timestamp with time zone,
    conditioning_end_datetime timestamp with time zone,
    testing_start_datetime timestamp with time zone,
    testing_end_datetime timestamp with time zone,
    manufacturing_completion_date timestamp with time zone,
    report_prepared_date timestamp with time zone,
    manufacturing boolean DEFAULT false NOT NULL,
    workshop_status character varying(20),
    sample_count integer DEFAULT 1 NOT NULL,
    preparation text DEFAULT ''::text NOT NULL,
    notes text DEFAULT ''::text NOT NULL,
    manufacturing_deadline date,
    additional_sample_count integer DEFAULT 0 NOT NULL,
    workshop_notes text DEFAULT ''::text NOT NULL,
    moisture_conditioning boolean DEFAULT false NOT NULL,
    moisture_sample_id integer,
    cutting_standard_id integer,
    acceptance_act_id integer,
    CONSTRAINT samples_further_movement_check CHECK (((further_movement)::text = ANY (ARRAY[(''::character varying)::text, ('TO_MI'::character varying)::text, ('TO_CHA'::character varying)::text, ('TO_TA'::character varying)::text, ('TO_ACT'::character varying)::text, ('TO_CLIENT_DEPT'::character varying)::text]))),
    CONSTRAINT samples_status_check CHECK (((status)::text = ANY (ARRAY[('PENDING_VERIFICATION'::character varying)::text, ('REGISTERED'::character varying)::text, ('CANCELLED'::character varying)::text, ('MANUFACTURING'::character varying)::text, ('MANUFACTURED'::character varying)::text, ('TRANSFERRED'::character varying)::text, ('MOISTURE_CONDITIONING'::character varying)::text, ('MOISTURE_READY'::character varying)::text, ('CONDITIONING'::character varying)::text, ('READY_FOR_TEST'::character varying)::text, ('IN_TESTING'::character varying)::text, ('TESTED'::character varying)::text, ('DRAFT_READY'::character varying)::text, ('RESULTS_UPLOADED'::character varying)::text, ('PROTOCOL_ISSUED'::character varying)::text, ('COMPLETED'::character varying)::text, ('REPLACEMENT_PROTOCOL'::character varying)::text]))),
    CONSTRAINT samples_workshop_status_check CHECK ((((workshop_status)::text = ANY (ARRAY[('IN_WORKSHOP'::character varying)::text, ('COMPLETED'::character varying)::text, ('CANCELLED'::character varying)::text])) OR (workshop_status IS NULL)))
);


ALTER TABLE public.samples OWNER TO cisis_user;

--
-- Name: COLUMN samples.registered_by_id; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.registered_by_id IS 'Первый администратор, который зарегистрировал образец';


--
-- Name: COLUMN samples.status; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.status IS 'Статус образца: PENDING_VERIFICATION, REGISTERED, CANCELLED, CONDITIONING, READY_FOR_TEST, IN_TESTING, TESTED, DRAFT_READY, RESULTS_UPLOADED, PROTOCOL_ISSUED, COMPLETED';


--
-- Name: COLUMN samples.verified_by; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.verified_by IS 'Второй администратор, который проверил и подтвердил регистрацию';


--
-- Name: COLUMN samples.verified_at; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.verified_at IS 'Дата и время проверки регистрации';


--
-- Name: COLUMN samples.protocol_checked_by; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.protocol_checked_by IS 'Сотрудник СМК, который проверил протокол';


--
-- Name: COLUMN samples.protocol_checked_at; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.protocol_checked_at IS 'Дата и время проверки протокола';


--
-- Name: COLUMN samples.replacement_count; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.replacement_count IS 'Количество выпущенных замещающих протоколов';


--
-- Name: COLUMN samples.conditioning_start_datetime; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.conditioning_start_datetime IS 'Дата и время начала кондиционирования (для ХА, ТА)';


--
-- Name: COLUMN samples.conditioning_end_datetime; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.conditioning_end_datetime IS 'Дата и время окончания кондиционирования (для ХА, ТА)';


--
-- Name: COLUMN samples.testing_start_datetime; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.testing_start_datetime IS 'Дата и время начала испытания (для ХА, ТА, УКИ)';


--
-- Name: COLUMN samples.testing_end_datetime; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.testing_end_datetime IS 'Дата и время окончания испытания (для всех лабораторий)';


--
-- Name: COLUMN samples.manufacturing_completion_date; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.manufacturing_completion_date IS 'Дата и время завершения изготовления (заполняется при нажатии кнопки)';


--
-- Name: COLUMN samples.report_prepared_date; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.report_prepared_date IS 'Дата и время подготовки отчёта (изменено с DATE на TIMESTAMP в v3.2.4)';


--
-- Name: COLUMN samples.manufacturing; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.manufacturing IS 'Требуется изготовление (boolean: true = требуется, false = не требуется)';


--
-- Name: COLUMN samples.workshop_status; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.workshop_status IS 'Статус образца в мастерской: IN_WORKSHOP (В мастерской), COMPLETED (Готово), NULL (не требует изготовления)';


--
-- Name: COLUMN samples.sample_count; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.sample_count IS 'Количество образцов';


--
-- Name: COLUMN samples.manufacturing_deadline; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.manufacturing_deadline IS 'Срок изготовления (для мастерской)';


--
-- Name: COLUMN samples.moisture_conditioning; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.moisture_conditioning IS 'Требуется влагонасыщение перед испытанием';


--
-- Name: COLUMN samples.moisture_sample_id; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.moisture_sample_id IS 'FK на образец влагонасыщения (УКИ). Образец A, к которому привязан данный образец B';


--
-- Name: COLUMN samples.cutting_standard_id; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.cutting_standard_id IS 'Стандарт на нарезку (для мастерской). Если NULL — мастерская ориентируется на основные стандарты.';


--
-- Name: COLUMN samples.acceptance_act_id; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.samples.acceptance_act_id IS 'Привязка образца к акту приёма-передачи';


--
-- Name: CONSTRAINT samples_status_check ON samples; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON CONSTRAINT samples_status_check ON public.samples IS 'v3.15.0: Допустимые статусы образца, включая MOISTURE_CONDITIONING и MOISTURE_READY';


--
-- Name: samples_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.samples_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.samples_id_seq OWNER TO cisis_user;

--
-- Name: samples_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.samples_id_seq OWNED BY public.samples.id;


--
-- Name: standard_accreditation_areas; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.standard_accreditation_areas (
    id integer NOT NULL,
    standard_id integer NOT NULL,
    accreditation_area_id integer NOT NULL
);


ALTER TABLE public.standard_accreditation_areas OWNER TO cisis_user;

--
-- Name: standard_accreditation_areas_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.standard_accreditation_areas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.standard_accreditation_areas_id_seq OWNER TO cisis_user;

--
-- Name: standard_accreditation_areas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.standard_accreditation_areas_id_seq OWNED BY public.standard_accreditation_areas.id;


--
-- Name: standard_laboratories; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.standard_laboratories (
    id integer NOT NULL,
    standard_id integer NOT NULL,
    laboratory_id integer NOT NULL
);


ALTER TABLE public.standard_laboratories OWNER TO cisis_user;

--
-- Name: standard_laboratories_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.standard_laboratories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.standard_laboratories_id_seq OWNER TO cisis_user;

--
-- Name: standard_laboratories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.standard_laboratories_id_seq OWNED BY public.standard_laboratories.id;


--
-- Name: standard_parameters; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.standard_parameters (
    id integer NOT NULL,
    standard_id integer NOT NULL,
    parameter_id integer NOT NULL,
    parameter_role character varying(20) DEFAULT 'PRIMARY'::character varying NOT NULL,
    is_default boolean DEFAULT true NOT NULL,
    unit_override character varying(50),
    test_conditions character varying(500),
    "precision" integer,
    report_group character varying(100),
    report_order integer DEFAULT 0 NOT NULL,
    display_order integer DEFAULT 0 NOT NULL,
    formula text,
    depends_on jsonb,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_parameter_role CHECK (((parameter_role)::text = ANY ((ARRAY['PRIMARY'::character varying, 'AUXILIARY'::character varying, 'CALCULATED'::character varying])::text[])))
);


ALTER TABLE public.standard_parameters OWNER TO cisis_user;

--
-- Name: TABLE standard_parameters; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON TABLE public.standard_parameters IS 'Привязка показателей к стандартам с настройками';


--
-- Name: COLUMN standard_parameters.parameter_role; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.standard_parameters.parameter_role IS 'PRIMARY — основной, AUXILIARY — вспомогательный, CALCULATED — расчётный';


--
-- Name: COLUMN standard_parameters.is_default; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.standard_parameters.is_default IS 'Автоматически включать при выборе стандарта';


--
-- Name: COLUMN standard_parameters.unit_override; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.standard_parameters.unit_override IS 'Если единица отличается от parameters.unit';


--
-- Name: COLUMN standard_parameters.report_group; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.standard_parameters.report_group IS 'Группа в протоколе (Механические, Размеры и т.д.)';


--
-- Name: COLUMN standard_parameters.formula; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.standard_parameters.formula IS 'Формула расчёта для CALCULATED (будущее)';


--
-- Name: COLUMN standard_parameters.depends_on; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.standard_parameters.depends_on IS 'JSON-массив parameter_id для CALCULATED (будущее)';


--
-- Name: standard_parameters_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.standard_parameters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.standard_parameters_id_seq OWNER TO cisis_user;

--
-- Name: standard_parameters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.standard_parameters_id_seq OWNED BY public.standard_parameters.id;


--
-- Name: standards; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.standards (
    id integer NOT NULL,
    code character varying(100) NOT NULL,
    name character varying(500) NOT NULL,
    is_active boolean DEFAULT true,
    test_code character varying(20) DEFAULT ''::character varying,
    test_type character varying(200) DEFAULT ''::character varying
);


ALTER TABLE public.standards OWNER TO cisis_user;

--
-- Name: standards_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.standards_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.standards_id_seq OWNER TO cisis_user;

--
-- Name: standards_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.standards_id_seq OWNED BY public.standards.id;


--
-- Name: time_log; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.time_log (
    id integer NOT NULL,
    employee_id integer NOT NULL,
    date date NOT NULL,
    start_time time without time zone NOT NULL,
    end_time time without time zone NOT NULL,
    work_type character varying(200) NOT NULL,
    sample_id integer,
    notes text DEFAULT ''::text
);


ALTER TABLE public.time_log OWNER TO cisis_user;

--
-- Name: time_log_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.time_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.time_log_id_seq OWNER TO cisis_user;

--
-- Name: time_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.time_log_id_seq OWNED BY public.time_log.id;


--
-- Name: user_additional_laboratories; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.user_additional_laboratories (
    id integer NOT NULL,
    user_id integer NOT NULL,
    laboratory_id integer NOT NULL
);


ALTER TABLE public.user_additional_laboratories OWNER TO cisis_user;

--
-- Name: user_additional_laboratories_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.user_additional_laboratories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_additional_laboratories_id_seq OWNER TO cisis_user;

--
-- Name: user_additional_laboratories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.user_additional_laboratories_id_seq OWNED BY public.user_additional_laboratories.id;


--
-- Name: user_permissions_override; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.user_permissions_override (
    id integer NOT NULL,
    user_id integer NOT NULL,
    journal_id integer NOT NULL,
    column_id integer,
    access_level character varying(10) DEFAULT 'NONE'::character varying NOT NULL,
    reason text NOT NULL,
    granted_by_id integer NOT NULL,
    granted_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    valid_until date,
    is_active boolean DEFAULT true
);


ALTER TABLE public.user_permissions_override OWNER TO cisis_user;

--
-- Name: user_permissions_override_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.user_permissions_override_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_permissions_override_id_seq OWNER TO cisis_user;

--
-- Name: user_permissions_override_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.user_permissions_override_id_seq OWNED BY public.user_permissions_override.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying(100) NOT NULL,
    password_hash character varying(255) NOT NULL,
    email character varying(255) DEFAULT ''::character varying,
    first_name character varying(100) DEFAULT ''::character varying,
    last_name character varying(100) DEFAULT ''::character varying,
    role character varying(20) DEFAULT 'OTHER'::character varying NOT NULL,
    laboratory_id integer,
    is_active boolean DEFAULT true,
    is_staff boolean DEFAULT false,
    is_superuser boolean DEFAULT false,
    ui_preferences jsonb DEFAULT '{}'::jsonb,
    last_login timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    is_trainee boolean DEFAULT false NOT NULL,
    mentor_id integer,
    sur_name character varying(100) DEFAULT ''::character varying,
    CONSTRAINT chk_mentor_not_self CHECK (((mentor_id IS NULL) OR (mentor_id <> id)))
);


ALTER TABLE public.users OWNER TO cisis_user;

--
-- Name: COLUMN users.role; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.users.role IS 'Роль пользователя: CEO, CTO, SYSADMIN, LAB_HEAD, TESTER, CLIENT_DEPT_HEAD, CLIENT_MANAGER, CONTRACT_SPEC, QMS_HEAD, QMS_ADMIN, METROLOGIST, WORKSHOP, ACCOUNTANT, OTHER';


--
-- Name: COLUMN users.sur_name; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON COLUMN public.users.sur_name IS 'Отчество пользователя';


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO cisis_user;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: weight_log; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.weight_log (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    measured_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    weight numeric(10,4) NOT NULL,
    test_type character varying(50) NOT NULL,
    measured_by_id integer NOT NULL,
    equipment_id integer NOT NULL,
    notes text DEFAULT ''::text
);


ALTER TABLE public.weight_log OWNER TO cisis_user;

--
-- Name: weight_log_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.weight_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.weight_log_id_seq OWNER TO cisis_user;

--
-- Name: weight_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.weight_log_id_seq OWNED BY public.weight_log.id;


--
-- Name: workshop_log; Type: TABLE; Schema: public; Owner: cisis_user
--

CREATE TABLE public.workshop_log (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    operator_id integer NOT NULL,
    operation_date date NOT NULL,
    operation_type character varying(200) NOT NULL,
    equipment_id integer NOT NULL,
    cutting_params text DEFAULT ''::text,
    quantity integer DEFAULT 1,
    quality_check boolean DEFAULT true,
    notes text DEFAULT ''::text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.workshop_log OWNER TO cisis_user;

--
-- Name: workshop_log_id_seq; Type: SEQUENCE; Schema: public; Owner: cisis_user
--

CREATE SEQUENCE public.workshop_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.workshop_log_id_seq OWNER TO cisis_user;

--
-- Name: workshop_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cisis_user
--

ALTER SEQUENCE public.workshop_log_id_seq OWNED BY public.workshop_log.id;


--
-- Name: acceptance_act_laboratories id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.acceptance_act_laboratories ALTER COLUMN id SET DEFAULT nextval('public.acceptance_act_laboratories_id_seq'::regclass);


--
-- Name: acceptance_acts id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.acceptance_acts ALTER COLUMN id SET DEFAULT nextval('public.acceptance_acts_id_seq'::regclass);


--
-- Name: accreditation_areas id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.accreditation_areas ALTER COLUMN id SET DEFAULT nextval('public.accreditation_areas_id_seq'::regclass);


--
-- Name: audit_log id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);


--
-- Name: client_contacts id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.client_contacts ALTER COLUMN id SET DEFAULT nextval('public.client_contacts_id_seq'::regclass);


--
-- Name: clients id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.clients ALTER COLUMN id SET DEFAULT nextval('public.clients_id_seq'::regclass);


--
-- Name: climate_log id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.climate_log ALTER COLUMN id SET DEFAULT nextval('public.climate_log_id_seq'::regclass);


--
-- Name: contracts id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.contracts ALTER COLUMN id SET DEFAULT nextval('public.contracts_id_seq'::regclass);


--
-- Name: equipment id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment ALTER COLUMN id SET DEFAULT nextval('public.equipment_id_seq'::regclass);


--
-- Name: equipment_accreditation_areas id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_accreditation_areas ALTER COLUMN id SET DEFAULT nextval('public.equipment_accreditation_areas_id_seq'::regclass);


--
-- Name: equipment_maintenance id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_maintenance ALTER COLUMN id SET DEFAULT nextval('public.equipment_maintenance_id_seq'::regclass);


--
-- Name: equipment_maintenance_logs id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_maintenance_logs ALTER COLUMN id SET DEFAULT nextval('public.equipment_maintenance_logs_id_seq'::regclass);


--
-- Name: equipment_maintenance_plans id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_maintenance_plans ALTER COLUMN id SET DEFAULT nextval('public.equipment_maintenance_plans_id_seq'::regclass);


--
-- Name: file_type_defaults id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.file_type_defaults ALTER COLUMN id SET DEFAULT nextval('public.file_type_defaults_id_seq'::regclass);


--
-- Name: file_visibility_rules id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.file_visibility_rules ALTER COLUMN id SET DEFAULT nextval('public.file_visibility_rules_id_seq'::regclass);


--
-- Name: files id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.files ALTER COLUMN id SET DEFAULT nextval('public.files_id_seq'::regclass);


--
-- Name: holidays id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.holidays ALTER COLUMN id SET DEFAULT nextval('public.holidays_id_seq'::regclass);


--
-- Name: journal_columns id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.journal_columns ALTER COLUMN id SET DEFAULT nextval('public.journal_columns_id_seq'::regclass);


--
-- Name: journals id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.journals ALTER COLUMN id SET DEFAULT nextval('public.journals_id_seq'::regclass);


--
-- Name: laboratories id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.laboratories ALTER COLUMN id SET DEFAULT nextval('public.laboratories_id_seq'::regclass);


--
-- Name: parameters id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.parameters ALTER COLUMN id SET DEFAULT nextval('public.parameters_id_seq'::regclass);


--
-- Name: permissions_log id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.permissions_log ALTER COLUMN id SET DEFAULT nextval('public.permissions_log_id_seq'::regclass);


--
-- Name: personal_folder_access id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.personal_folder_access ALTER COLUMN id SET DEFAULT nextval('public.personal_folder_access_id_seq'::regclass);


--
-- Name: role_laboratory_access id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.role_laboratory_access ALTER COLUMN id SET DEFAULT nextval('public.role_laboratory_access_id_seq'::regclass);


--
-- Name: role_permissions id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.role_permissions ALTER COLUMN id SET DEFAULT nextval('public.role_permissions_id_seq'::regclass);


--
-- Name: sample_auxiliary_equipment id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_auxiliary_equipment ALTER COLUMN id SET DEFAULT nextval('public.sample_auxiliary_equipment_id_seq'::regclass);


--
-- Name: sample_manufacturing_auxiliary_equipment id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_auxiliary_equipment ALTER COLUMN id SET DEFAULT nextval('public.sample_manufacturing_auxiliary_equipment_id_seq'::regclass);


--
-- Name: sample_manufacturing_measuring_instruments id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_measuring_instruments ALTER COLUMN id SET DEFAULT nextval('public.sample_manufacturing_measuring_instruments_id_seq'::regclass);


--
-- Name: sample_manufacturing_operators id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_operators ALTER COLUMN id SET DEFAULT nextval('public.sample_manufacturing_operators_id_seq'::regclass);


--
-- Name: sample_manufacturing_testing_equipment id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_testing_equipment ALTER COLUMN id SET DEFAULT nextval('public.sample_manufacturing_testing_equipment_id_seq'::regclass);


--
-- Name: sample_measuring_instruments id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_measuring_instruments ALTER COLUMN id SET DEFAULT nextval('public.sample_measuring_instruments_id_seq'::regclass);


--
-- Name: sample_operators id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_operators ALTER COLUMN id SET DEFAULT nextval('public.sample_operators_id_seq'::regclass);


--
-- Name: sample_parameters id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_parameters ALTER COLUMN id SET DEFAULT nextval('public.sample_parameters_id_seq'::regclass);


--
-- Name: sample_standards id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_standards ALTER COLUMN id SET DEFAULT nextval('public.sample_standards_id_seq'::regclass);


--
-- Name: sample_testing_equipment id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_testing_equipment ALTER COLUMN id SET DEFAULT nextval('public.sample_testing_equipment_id_seq'::regclass);


--
-- Name: samples id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.samples ALTER COLUMN id SET DEFAULT nextval('public.samples_id_seq'::regclass);


--
-- Name: standard_accreditation_areas id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standard_accreditation_areas ALTER COLUMN id SET DEFAULT nextval('public.standard_accreditation_areas_id_seq'::regclass);


--
-- Name: standard_laboratories id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standard_laboratories ALTER COLUMN id SET DEFAULT nextval('public.standard_laboratories_id_seq'::regclass);


--
-- Name: standard_parameters id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standard_parameters ALTER COLUMN id SET DEFAULT nextval('public.standard_parameters_id_seq'::regclass);


--
-- Name: standards id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standards ALTER COLUMN id SET DEFAULT nextval('public.standards_id_seq'::regclass);


--
-- Name: time_log id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.time_log ALTER COLUMN id SET DEFAULT nextval('public.time_log_id_seq'::regclass);


--
-- Name: user_additional_laboratories id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.user_additional_laboratories ALTER COLUMN id SET DEFAULT nextval('public.user_additional_laboratories_id_seq'::regclass);


--
-- Name: user_permissions_override id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.user_permissions_override ALTER COLUMN id SET DEFAULT nextval('public.user_permissions_override_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: weight_log id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.weight_log ALTER COLUMN id SET DEFAULT nextval('public.weight_log_id_seq'::regclass);


--
-- Name: workshop_log id; Type: DEFAULT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.workshop_log ALTER COLUMN id SET DEFAULT nextval('public.workshop_log_id_seq'::regclass);


--
-- Name: acceptance_act_laboratories acceptance_act_laboratories_act_id_laboratory_id_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.acceptance_act_laboratories
    ADD CONSTRAINT acceptance_act_laboratories_act_id_laboratory_id_key UNIQUE (act_id, laboratory_id);


--
-- Name: acceptance_act_laboratories acceptance_act_laboratories_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.acceptance_act_laboratories
    ADD CONSTRAINT acceptance_act_laboratories_pkey PRIMARY KEY (id);


--
-- Name: acceptance_acts acceptance_acts_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.acceptance_acts
    ADD CONSTRAINT acceptance_acts_pkey PRIMARY KEY (id);


--
-- Name: accreditation_areas accreditation_areas_code_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.accreditation_areas
    ADD CONSTRAINT accreditation_areas_code_key UNIQUE (code);


--
-- Name: accreditation_areas accreditation_areas_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.accreditation_areas
    ADD CONSTRAINT accreditation_areas_pkey PRIMARY KEY (id);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: auth_group auth_group_name_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_name_key UNIQUE (name);


--
-- Name: auth_group_permissions auth_group_permissions_group_id_permission_id_0cd325b0_uniq; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_permission_id_0cd325b0_uniq UNIQUE (group_id, permission_id);


--
-- Name: auth_group_permissions auth_group_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_group auth_group_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_pkey PRIMARY KEY (id);


--
-- Name: auth_permission auth_permission_content_type_id_codename_01ab375a_uniq; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_codename_01ab375a_uniq UNIQUE (content_type_id, codename);


--
-- Name: auth_permission auth_permission_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_pkey PRIMARY KEY (id);


--
-- Name: client_contacts client_contacts_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.client_contacts
    ADD CONSTRAINT client_contacts_pkey PRIMARY KEY (id);


--
-- Name: clients clients_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_pkey PRIMARY KEY (id);


--
-- Name: climate_log climate_log_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.climate_log
    ADD CONSTRAINT climate_log_pkey PRIMARY KEY (id);


--
-- Name: contracts contracts_client_id_number_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT contracts_client_id_number_key UNIQUE (client_id, number);


--
-- Name: contracts contracts_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT contracts_pkey PRIMARY KEY (id);


--
-- Name: django_admin_log django_admin_log_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_pkey PRIMARY KEY (id);


--
-- Name: django_content_type django_content_type_app_label_model_76bd3d3b_uniq; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_app_label_model_76bd3d3b_uniq UNIQUE (app_label, model);


--
-- Name: django_content_type django_content_type_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_pkey PRIMARY KEY (id);


--
-- Name: django_migrations django_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.django_migrations
    ADD CONSTRAINT django_migrations_pkey PRIMARY KEY (id);


--
-- Name: django_session django_session_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.django_session
    ADD CONSTRAINT django_session_pkey PRIMARY KEY (session_key);


--
-- Name: equipment_accreditation_areas equipment_accreditation_areas_equipment_id_accreditation_ar_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_accreditation_areas
    ADD CONSTRAINT equipment_accreditation_areas_equipment_id_accreditation_ar_key UNIQUE (equipment_id, accreditation_area_id);


--
-- Name: equipment_accreditation_areas equipment_accreditation_areas_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_accreditation_areas
    ADD CONSTRAINT equipment_accreditation_areas_pkey PRIMARY KEY (id);


--
-- Name: equipment_maintenance_logs equipment_maintenance_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_maintenance_logs
    ADD CONSTRAINT equipment_maintenance_logs_pkey PRIMARY KEY (id);


--
-- Name: equipment_maintenance equipment_maintenance_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_maintenance
    ADD CONSTRAINT equipment_maintenance_pkey PRIMARY KEY (id);


--
-- Name: equipment_maintenance_plans equipment_maintenance_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_maintenance_plans
    ADD CONSTRAINT equipment_maintenance_plans_pkey PRIMARY KEY (id);


--
-- Name: equipment equipment_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment
    ADD CONSTRAINT equipment_pkey PRIMARY KEY (id);


--
-- Name: file_type_defaults file_type_defaults_category_file_type_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.file_type_defaults
    ADD CONSTRAINT file_type_defaults_category_file_type_key UNIQUE (category, file_type);


--
-- Name: file_type_defaults file_type_defaults_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.file_type_defaults
    ADD CONSTRAINT file_type_defaults_pkey PRIMARY KEY (id);


--
-- Name: file_visibility_rules file_visibility_rules_file_type_category_role_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.file_visibility_rules
    ADD CONSTRAINT file_visibility_rules_file_type_category_role_key UNIQUE (file_type, category, role);


--
-- Name: file_visibility_rules file_visibility_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.file_visibility_rules
    ADD CONSTRAINT file_visibility_rules_pkey PRIMARY KEY (id);


--
-- Name: files files_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_pkey PRIMARY KEY (id);


--
-- Name: holidays holidays_date_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.holidays
    ADD CONSTRAINT holidays_date_key UNIQUE (date);


--
-- Name: holidays holidays_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.holidays
    ADD CONSTRAINT holidays_pkey PRIMARY KEY (id);


--
-- Name: journal_columns journal_columns_journal_id_code_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.journal_columns
    ADD CONSTRAINT journal_columns_journal_id_code_key UNIQUE (journal_id, code);


--
-- Name: journal_columns journal_columns_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.journal_columns
    ADD CONSTRAINT journal_columns_pkey PRIMARY KEY (id);


--
-- Name: journals journals_code_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.journals
    ADD CONSTRAINT journals_code_key UNIQUE (code);


--
-- Name: journals journals_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.journals
    ADD CONSTRAINT journals_pkey PRIMARY KEY (id);


--
-- Name: laboratories laboratories_code_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.laboratories
    ADD CONSTRAINT laboratories_code_key UNIQUE (code);


--
-- Name: laboratories laboratories_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.laboratories
    ADD CONSTRAINT laboratories_pkey PRIMARY KEY (id);


--
-- Name: parameters parameters_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.parameters
    ADD CONSTRAINT parameters_pkey PRIMARY KEY (id);


--
-- Name: permissions_log permissions_log_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.permissions_log
    ADD CONSTRAINT permissions_log_pkey PRIMARY KEY (id);


--
-- Name: personal_folder_access personal_folder_access_owner_id_granted_to_id_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.personal_folder_access
    ADD CONSTRAINT personal_folder_access_owner_id_granted_to_id_key UNIQUE (owner_id, granted_to_id);


--
-- Name: personal_folder_access personal_folder_access_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.personal_folder_access
    ADD CONSTRAINT personal_folder_access_pkey PRIMARY KEY (id);


--
-- Name: role_laboratory_access role_laboratory_access_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.role_laboratory_access
    ADD CONSTRAINT role_laboratory_access_pkey PRIMARY KEY (id);


--
-- Name: role_permissions role_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (id);


--
-- Name: role_permissions role_permissions_role_journal_id_column_id_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_role_journal_id_column_id_key UNIQUE (role, journal_id, column_id);


--
-- Name: sample_auxiliary_equipment sample_auxiliary_equipment_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_auxiliary_equipment
    ADD CONSTRAINT sample_auxiliary_equipment_pkey PRIMARY KEY (id);


--
-- Name: sample_auxiliary_equipment sample_auxiliary_equipment_sample_id_equipment_id_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_auxiliary_equipment
    ADD CONSTRAINT sample_auxiliary_equipment_sample_id_equipment_id_key UNIQUE (sample_id, equipment_id);


--
-- Name: sample_manufacturing_auxiliary_equipment sample_manufacturing_auxiliary_equip_sample_id_equipment_id_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_auxiliary_equipment
    ADD CONSTRAINT sample_manufacturing_auxiliary_equip_sample_id_equipment_id_key UNIQUE (sample_id, equipment_id);


--
-- Name: sample_manufacturing_auxiliary_equipment sample_manufacturing_auxiliary_equipment_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_auxiliary_equipment
    ADD CONSTRAINT sample_manufacturing_auxiliary_equipment_pkey PRIMARY KEY (id);


--
-- Name: sample_manufacturing_measuring_instruments sample_manufacturing_measuring_instr_sample_id_equipment_id_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_measuring_instruments
    ADD CONSTRAINT sample_manufacturing_measuring_instr_sample_id_equipment_id_key UNIQUE (sample_id, equipment_id);


--
-- Name: sample_manufacturing_measuring_instruments sample_manufacturing_measuring_instruments_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_measuring_instruments
    ADD CONSTRAINT sample_manufacturing_measuring_instruments_pkey PRIMARY KEY (id);


--
-- Name: sample_manufacturing_operators sample_manufacturing_operators_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_operators
    ADD CONSTRAINT sample_manufacturing_operators_pkey PRIMARY KEY (id);


--
-- Name: sample_manufacturing_operators sample_manufacturing_operators_sample_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_operators
    ADD CONSTRAINT sample_manufacturing_operators_sample_id_user_id_key UNIQUE (sample_id, user_id);


--
-- Name: sample_manufacturing_testing_equipment sample_manufacturing_testing_equipme_sample_id_equipment_id_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_testing_equipment
    ADD CONSTRAINT sample_manufacturing_testing_equipme_sample_id_equipment_id_key UNIQUE (sample_id, equipment_id);


--
-- Name: sample_manufacturing_testing_equipment sample_manufacturing_testing_equipment_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_testing_equipment
    ADD CONSTRAINT sample_manufacturing_testing_equipment_pkey PRIMARY KEY (id);


--
-- Name: sample_measuring_instruments sample_measuring_instruments_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_measuring_instruments
    ADD CONSTRAINT sample_measuring_instruments_pkey PRIMARY KEY (id);


--
-- Name: sample_measuring_instruments sample_measuring_instruments_sample_id_equipment_id_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_measuring_instruments
    ADD CONSTRAINT sample_measuring_instruments_sample_id_equipment_id_key UNIQUE (sample_id, equipment_id);


--
-- Name: sample_operators sample_operators_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_operators
    ADD CONSTRAINT sample_operators_pkey PRIMARY KEY (id);


--
-- Name: sample_operators sample_operators_sample_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_operators
    ADD CONSTRAINT sample_operators_sample_id_user_id_key UNIQUE (sample_id, user_id);


--
-- Name: sample_parameters sample_parameters_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_parameters
    ADD CONSTRAINT sample_parameters_pkey PRIMARY KEY (id);


--
-- Name: sample_standards sample_standards_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_standards
    ADD CONSTRAINT sample_standards_pkey PRIMARY KEY (id);


--
-- Name: sample_standards sample_standards_sample_id_standard_id_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_standards
    ADD CONSTRAINT sample_standards_sample_id_standard_id_key UNIQUE (sample_id, standard_id);


--
-- Name: sample_testing_equipment sample_testing_equipment_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_testing_equipment
    ADD CONSTRAINT sample_testing_equipment_pkey PRIMARY KEY (id);


--
-- Name: sample_testing_equipment sample_testing_equipment_sample_id_equipment_id_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_testing_equipment
    ADD CONSTRAINT sample_testing_equipment_sample_id_equipment_id_key UNIQUE (sample_id, equipment_id);


--
-- Name: samples samples_cipher_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_cipher_key UNIQUE (cipher);


--
-- Name: samples samples_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_pkey PRIMARY KEY (id);


--
-- Name: samples samples_sequence_number_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_sequence_number_key UNIQUE (sequence_number);


--
-- Name: standard_accreditation_areas standard_accreditation_areas_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standard_accreditation_areas
    ADD CONSTRAINT standard_accreditation_areas_pkey PRIMARY KEY (id);


--
-- Name: standard_accreditation_areas standard_accreditation_areas_standard_id_accreditation_area_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standard_accreditation_areas
    ADD CONSTRAINT standard_accreditation_areas_standard_id_accreditation_area_key UNIQUE (standard_id, accreditation_area_id);


--
-- Name: standard_laboratories standard_laboratories_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standard_laboratories
    ADD CONSTRAINT standard_laboratories_pkey PRIMARY KEY (id);


--
-- Name: standard_laboratories standard_laboratories_standard_id_laboratory_id_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standard_laboratories
    ADD CONSTRAINT standard_laboratories_standard_id_laboratory_id_key UNIQUE (standard_id, laboratory_id);


--
-- Name: standard_parameters standard_parameters_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standard_parameters
    ADD CONSTRAINT standard_parameters_pkey PRIMARY KEY (id);


--
-- Name: standards standards_code_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standards
    ADD CONSTRAINT standards_code_key UNIQUE (code);


--
-- Name: standards standards_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standards
    ADD CONSTRAINT standards_pkey PRIMARY KEY (id);


--
-- Name: time_log time_log_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.time_log
    ADD CONSTRAINT time_log_pkey PRIMARY KEY (id);


--
-- Name: parameters uq_parameters_name_unit; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.parameters
    ADD CONSTRAINT uq_parameters_name_unit UNIQUE (name, unit);


--
-- Name: sample_parameters uq_sample_std_parameter; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_parameters
    ADD CONSTRAINT uq_sample_std_parameter UNIQUE (sample_id, standard_parameter_id);


--
-- Name: standard_parameters uq_standard_parameter; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standard_parameters
    ADD CONSTRAINT uq_standard_parameter UNIQUE (standard_id, parameter_id);


--
-- Name: user_additional_laboratories uq_user_additional_lab; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.user_additional_laboratories
    ADD CONSTRAINT uq_user_additional_lab UNIQUE (user_id, laboratory_id);


--
-- Name: user_additional_laboratories user_additional_laboratories_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.user_additional_laboratories
    ADD CONSTRAINT user_additional_laboratories_pkey PRIMARY KEY (id);


--
-- Name: user_permissions_override user_permissions_override_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.user_permissions_override
    ADD CONSTRAINT user_permissions_override_pkey PRIMARY KEY (id);


--
-- Name: user_permissions_override user_permissions_override_user_id_journal_id_column_id_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.user_permissions_override
    ADD CONSTRAINT user_permissions_override_user_id_journal_id_column_id_key UNIQUE (user_id, journal_id, column_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: weight_log weight_log_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.weight_log
    ADD CONSTRAINT weight_log_pkey PRIMARY KEY (id);


--
-- Name: workshop_log workshop_log_pkey; Type: CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.workshop_log
    ADD CONSTRAINT workshop_log_pkey PRIMARY KEY (id);


--
-- Name: auth_group_name_a6ea08ec_like; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX auth_group_name_a6ea08ec_like ON public.auth_group USING btree (name varchar_pattern_ops);


--
-- Name: auth_group_permissions_group_id_b120cbf9; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX auth_group_permissions_group_id_b120cbf9 ON public.auth_group_permissions USING btree (group_id);


--
-- Name: auth_group_permissions_permission_id_84c5c92e; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX auth_group_permissions_permission_id_84c5c92e ON public.auth_group_permissions USING btree (permission_id);


--
-- Name: auth_permission_content_type_id_2f476e4b; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX auth_permission_content_type_id_2f476e4b ON public.auth_permission USING btree (content_type_id);


--
-- Name: django_admin_log_content_type_id_c4bce8eb; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX django_admin_log_content_type_id_c4bce8eb ON public.django_admin_log USING btree (content_type_id);


--
-- Name: django_admin_log_user_id_c564eba6; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX django_admin_log_user_id_c564eba6 ON public.django_admin_log USING btree (user_id);


--
-- Name: django_session_expire_date_a5c62663; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX django_session_expire_date_a5c62663 ON public.django_session USING btree (expire_date);


--
-- Name: django_session_session_key_c0390e0f_like; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX django_session_session_key_c0390e0f_like ON public.django_session USING btree (session_key varchar_pattern_ops);


--
-- Name: idx_aal_act; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_aal_act ON public.acceptance_act_laboratories USING btree (act_id);


--
-- Name: idx_aal_lab; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_aal_lab ON public.acceptance_act_laboratories USING btree (laboratory_id);


--
-- Name: idx_acceptance_acts_contract; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_acceptance_acts_contract ON public.acceptance_acts USING btree (contract_id);


--
-- Name: idx_acceptance_acts_work_deadline; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_acceptance_acts_work_deadline ON public.acceptance_acts USING btree (work_deadline);


--
-- Name: idx_acceptance_acts_work_status; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_acceptance_acts_work_status ON public.acceptance_acts USING btree (work_status);


--
-- Name: idx_audit_log_entity; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_audit_log_entity ON public.audit_log USING btree (entity_type, entity_id);


--
-- Name: idx_audit_log_timestamp; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_audit_log_timestamp ON public.audit_log USING btree ("timestamp" DESC);


--
-- Name: idx_audit_log_type_time; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_audit_log_type_time ON public.audit_log USING btree (entity_type, "timestamp" DESC);


--
-- Name: idx_audit_log_user; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_audit_log_user ON public.audit_log USING btree (user_id);


--
-- Name: idx_audit_log_user_time; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_audit_log_user_time ON public.audit_log USING btree (user_id, "timestamp" DESC);


--
-- Name: idx_climate_log_date; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_climate_log_date ON public.climate_log USING btree (measured_at);


--
-- Name: idx_climate_log_laboratory; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_climate_log_laboratory ON public.climate_log USING btree (laboratory_id);


--
-- Name: idx_contracts_client; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_contracts_client ON public.contracts USING btree (client_id);


--
-- Name: idx_contracts_status; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_contracts_status ON public.contracts USING btree (status);


--
-- Name: idx_equipment_laboratory; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_equipment_laboratory ON public.equipment USING btree (laboratory_id);


--
-- Name: idx_equipment_maintenance_date; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_equipment_maintenance_date ON public.equipment_maintenance USING btree (maintenance_date);


--
-- Name: idx_equipment_maintenance_equipment; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_equipment_maintenance_equipment ON public.equipment_maintenance USING btree (equipment_id);


--
-- Name: idx_equipment_maintenance_type; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_equipment_maintenance_type ON public.equipment_maintenance USING btree (maintenance_type);


--
-- Name: idx_equipment_status; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_equipment_status ON public.equipment USING btree (status);


--
-- Name: idx_equipment_type; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_equipment_type ON public.equipment USING btree (equipment_type);


--
-- Name: idx_files_act; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_files_act ON public.files USING btree (acceptance_act_id) WHERE (acceptance_act_id IS NOT NULL);


--
-- Name: idx_files_active; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_files_active ON public.files USING btree (is_deleted, current_version) WHERE ((is_deleted = false) AND (current_version = true));


--
-- Name: idx_files_category; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_files_category ON public.files USING btree (category);


--
-- Name: idx_files_contract; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_files_contract ON public.files USING btree (contract_id) WHERE (contract_id IS NOT NULL);


--
-- Name: idx_files_equipment; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_files_equipment ON public.files USING btree (equipment_id) WHERE (equipment_id IS NOT NULL);


--
-- Name: idx_files_owner; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_files_owner ON public.files USING btree (owner_id) WHERE (owner_id IS NOT NULL);


--
-- Name: idx_files_replaces; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_files_replaces ON public.files USING btree (replaces_id) WHERE (replaces_id IS NOT NULL);


--
-- Name: idx_files_sample; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_files_sample ON public.files USING btree (sample_id) WHERE (sample_id IS NOT NULL);


--
-- Name: idx_files_standard; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_files_standard ON public.files USING btree (standard_id) WHERE (standard_id IS NOT NULL);


--
-- Name: idx_maint_log_date; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_maint_log_date ON public.equipment_maintenance_logs USING btree (performed_date);


--
-- Name: idx_maint_log_performed_by; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_maint_log_performed_by ON public.equipment_maintenance_logs USING btree (performed_by_id);


--
-- Name: idx_maint_log_plan; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_maint_log_plan ON public.equipment_maintenance_logs USING btree (plan_id);


--
-- Name: idx_maint_log_status; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_maint_log_status ON public.equipment_maintenance_logs USING btree (status);


--
-- Name: idx_maint_plan_equipment; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_maint_plan_equipment ON public.equipment_maintenance_plans USING btree (equipment_id);


--
-- Name: idx_maint_plan_next_due; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_maint_plan_next_due ON public.equipment_maintenance_plans USING btree (next_due_date) WHERE (is_active = true);


--
-- Name: idx_parameters_category; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_parameters_category ON public.parameters USING btree (category) WHERE (is_active = true);


--
-- Name: idx_parameters_name; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_parameters_name ON public.parameters USING btree (name);


--
-- Name: idx_role_lab_access_lookup; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_role_lab_access_lookup ON public.role_laboratory_access USING btree (role, journal_id);


--
-- Name: idx_role_permissions_role; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_role_permissions_role ON public.role_permissions USING btree (role);


--
-- Name: idx_sae_equipment; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_sae_equipment ON public.sample_auxiliary_equipment USING btree (equipment_id);


--
-- Name: idx_sae_sample; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_sae_sample ON public.sample_auxiliary_equipment USING btree (sample_id);


--
-- Name: idx_sample_manufacturing_mi_equipment; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_sample_manufacturing_mi_equipment ON public.sample_manufacturing_measuring_instruments USING btree (equipment_id);


--
-- Name: idx_sample_manufacturing_mi_sample; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_sample_manufacturing_mi_sample ON public.sample_manufacturing_measuring_instruments USING btree (sample_id);


--
-- Name: idx_sample_manufacturing_op_sample; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_sample_manufacturing_op_sample ON public.sample_manufacturing_operators USING btree (sample_id);


--
-- Name: idx_sample_manufacturing_op_user; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_sample_manufacturing_op_user ON public.sample_manufacturing_operators USING btree (user_id);


--
-- Name: idx_sample_manufacturing_te_equipment; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_sample_manufacturing_te_equipment ON public.sample_manufacturing_testing_equipment USING btree (equipment_id);


--
-- Name: idx_sample_manufacturing_te_sample; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_sample_manufacturing_te_sample ON public.sample_manufacturing_testing_equipment USING btree (sample_id);


--
-- Name: idx_sample_params_sample; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_sample_params_sample ON public.sample_parameters USING btree (sample_id);


--
-- Name: idx_sample_params_selected; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_sample_params_selected ON public.sample_parameters USING btree (sample_id) WHERE (is_selected = true);


--
-- Name: idx_sample_params_std_param; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_sample_params_std_param ON public.sample_parameters USING btree (standard_parameter_id) WHERE (standard_parameter_id IS NOT NULL);


--
-- Name: idx_sample_standards_sample; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_sample_standards_sample ON public.sample_standards USING btree (sample_id);


--
-- Name: idx_sample_standards_standard; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_sample_standards_standard ON public.sample_standards USING btree (standard_id);


--
-- Name: idx_samples_acceptance_act; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_acceptance_act ON public.samples USING btree (acceptance_act_id);


--
-- Name: idx_samples_cipher; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_cipher ON public.samples USING btree (cipher);


--
-- Name: idx_samples_client; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_client ON public.samples USING btree (client_id);


--
-- Name: idx_samples_conditioning_start_datetime; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_conditioning_start_datetime ON public.samples USING btree (conditioning_start_datetime);


--
-- Name: idx_samples_cutting_standard_id; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_cutting_standard_id ON public.samples USING btree (cutting_standard_id);


--
-- Name: idx_samples_deadline; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_deadline ON public.samples USING btree (deadline);


--
-- Name: idx_samples_laboratory; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_laboratory ON public.samples USING btree (laboratory_id);


--
-- Name: idx_samples_manufacturing; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_manufacturing ON public.samples USING btree (manufacturing) WHERE (manufacturing = true);


--
-- Name: INDEX idx_samples_manufacturing; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON INDEX public.idx_samples_manufacturing IS 'Индекс для журнала мастерской';


--
-- Name: idx_samples_manufacturing_completion_date; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_manufacturing_completion_date ON public.samples USING btree (manufacturing_completion_date) WHERE (manufacturing_completion_date IS NOT NULL);


--
-- Name: idx_samples_moisture_sample_id; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_moisture_sample_id ON public.samples USING btree (moisture_sample_id) WHERE (moisture_sample_id IS NOT NULL);


--
-- Name: idx_samples_protocol_checked_by; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_protocol_checked_by ON public.samples USING btree (protocol_checked_by);


--
-- Name: idx_samples_qms_check; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_qms_check ON public.samples USING btree (status) WHERE ((status)::text = ANY (ARRAY[('DRAFT_READY'::character varying)::text, ('RESULTS_UPLOADED'::character varying)::text]));


--
-- Name: idx_samples_registered_by_id; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_registered_by_id ON public.samples USING btree (registered_by_id);


--
-- Name: idx_samples_registration_date; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_registration_date ON public.samples USING btree (registration_date);


--
-- Name: idx_samples_status; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_status ON public.samples USING btree (status);


--
-- Name: idx_samples_testing_end_datetime; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_testing_end_datetime ON public.samples USING btree (testing_end_datetime);


--
-- Name: idx_samples_verified_by; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_verified_by ON public.samples USING btree (verified_by);


--
-- Name: idx_samples_workshop_status; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_samples_workshop_status ON public.samples USING btree (workshop_status) WHERE (workshop_status IS NOT NULL);


--
-- Name: INDEX idx_samples_workshop_status; Type: COMMENT; Schema: public; Owner: cisis_user
--

COMMENT ON INDEX public.idx_samples_workshop_status IS 'Индекс для быстрой фильтрации образцов мастерской в журнале';


--
-- Name: idx_smae_equipment; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_smae_equipment ON public.sample_manufacturing_auxiliary_equipment USING btree (equipment_id);


--
-- Name: idx_smae_sample; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_smae_sample ON public.sample_manufacturing_auxiliary_equipment USING btree (sample_id);


--
-- Name: idx_standard_laboratories_laboratory; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_standard_laboratories_laboratory ON public.standard_laboratories USING btree (laboratory_id);


--
-- Name: idx_standard_laboratories_standard; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_standard_laboratories_standard ON public.standard_laboratories USING btree (standard_id);


--
-- Name: idx_std_params_parameter; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_std_params_parameter ON public.standard_parameters USING btree (parameter_id);


--
-- Name: idx_std_params_standard; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_std_params_standard ON public.standard_parameters USING btree (standard_id) WHERE (is_active = true);


--
-- Name: idx_ual_laboratory_id; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_ual_laboratory_id ON public.user_additional_laboratories USING btree (laboratory_id);


--
-- Name: idx_ual_user_id; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_ual_user_id ON public.user_additional_laboratories USING btree (user_id);


--
-- Name: idx_user_permissions_user; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_user_permissions_user ON public.user_permissions_override USING btree (user_id);


--
-- Name: idx_users_is_trainee; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_users_is_trainee ON public.users USING btree (is_trainee) WHERE (is_trainee = true);


--
-- Name: idx_users_mentor_id; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_users_mentor_id ON public.users USING btree (mentor_id) WHERE (mentor_id IS NOT NULL);


--
-- Name: idx_weight_log_date; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_weight_log_date ON public.weight_log USING btree (measured_at);


--
-- Name: idx_weight_log_sample; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE INDEX idx_weight_log_sample ON public.weight_log USING btree (sample_id);


--
-- Name: uq_role_lab_access_all; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE UNIQUE INDEX uq_role_lab_access_all ON public.role_laboratory_access USING btree (role, journal_id) WHERE (laboratory_id IS NULL);


--
-- Name: uq_role_lab_access_specific; Type: INDEX; Schema: public; Owner: cisis_user
--

CREATE UNIQUE INDEX uq_role_lab_access_specific ON public.role_laboratory_access USING btree (role, journal_id, laboratory_id) WHERE (laboratory_id IS NOT NULL);


--
-- Name: users block_user_delete; Type: TRIGGER; Schema: public; Owner: cisis_user
--

CREATE TRIGGER block_user_delete BEFORE DELETE ON public.users FOR EACH ROW EXECUTE FUNCTION public.prevent_user_deletion();


--
-- Name: acceptance_act_laboratories acceptance_act_laboratories_act_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.acceptance_act_laboratories
    ADD CONSTRAINT acceptance_act_laboratories_act_id_fkey FOREIGN KEY (act_id) REFERENCES public.acceptance_acts(id) ON DELETE CASCADE;


--
-- Name: acceptance_act_laboratories acceptance_act_laboratories_laboratory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.acceptance_act_laboratories
    ADD CONSTRAINT acceptance_act_laboratories_laboratory_id_fkey FOREIGN KEY (laboratory_id) REFERENCES public.laboratories(id) ON DELETE RESTRICT;


--
-- Name: acceptance_acts acceptance_acts_contract_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.acceptance_acts
    ADD CONSTRAINT acceptance_acts_contract_id_fkey FOREIGN KEY (contract_id) REFERENCES public.contracts(id) ON DELETE RESTRICT;


--
-- Name: acceptance_acts acceptance_acts_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.acceptance_acts
    ADD CONSTRAINT acceptance_acts_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: audit_log audit_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: auth_group_permissions auth_group_permissio_permission_id_84c5c92e_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissio_permission_id_84c5c92e_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_group_permissions auth_group_permissions_group_id_b120cbf9_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_b120cbf9_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_permission auth_permission_content_type_id_2f476e4b_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_2f476e4b_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: client_contacts client_contacts_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.client_contacts
    ADD CONSTRAINT client_contacts_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- Name: climate_log climate_log_laboratory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.climate_log
    ADD CONSTRAINT climate_log_laboratory_id_fkey FOREIGN KEY (laboratory_id) REFERENCES public.laboratories(id) ON DELETE RESTRICT;


--
-- Name: climate_log climate_log_measured_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.climate_log
    ADD CONSTRAINT climate_log_measured_by_id_fkey FOREIGN KEY (measured_by_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: contracts contracts_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT contracts_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- Name: django_admin_log django_admin_log_content_type_id_c4bce8eb_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_content_type_id_c4bce8eb_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: django_admin_log django_admin_log_user_id_c564eba6_fk_users_id; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_user_id_c564eba6_fk_users_id FOREIGN KEY (user_id) REFERENCES public.users(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: equipment_accreditation_areas equipment_accreditation_areas_accreditation_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_accreditation_areas
    ADD CONSTRAINT equipment_accreditation_areas_accreditation_area_id_fkey FOREIGN KEY (accreditation_area_id) REFERENCES public.accreditation_areas(id) ON DELETE CASCADE;


--
-- Name: equipment_accreditation_areas equipment_accreditation_areas_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_accreditation_areas
    ADD CONSTRAINT equipment_accreditation_areas_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE CASCADE;


--
-- Name: equipment equipment_laboratory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment
    ADD CONSTRAINT equipment_laboratory_id_fkey FOREIGN KEY (laboratory_id) REFERENCES public.laboratories(id) ON DELETE RESTRICT;


--
-- Name: equipment_maintenance equipment_maintenance_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_maintenance
    ADD CONSTRAINT equipment_maintenance_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE CASCADE;


--
-- Name: equipment_maintenance_logs equipment_maintenance_logs_performed_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_maintenance_logs
    ADD CONSTRAINT equipment_maintenance_logs_performed_by_id_fkey FOREIGN KEY (performed_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: equipment_maintenance_logs equipment_maintenance_logs_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_maintenance_logs
    ADD CONSTRAINT equipment_maintenance_logs_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES public.equipment_maintenance_plans(id) ON DELETE CASCADE;


--
-- Name: equipment_maintenance_logs equipment_maintenance_logs_verified_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_maintenance_logs
    ADD CONSTRAINT equipment_maintenance_logs_verified_by_id_fkey FOREIGN KEY (verified_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: equipment_maintenance equipment_maintenance_performed_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_maintenance
    ADD CONSTRAINT equipment_maintenance_performed_by_id_fkey FOREIGN KEY (performed_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: equipment_maintenance_plans equipment_maintenance_plans_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment_maintenance_plans
    ADD CONSTRAINT equipment_maintenance_plans_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE CASCADE;


--
-- Name: equipment equipment_responsible_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment
    ADD CONSTRAINT equipment_responsible_person_id_fkey FOREIGN KEY (responsible_person_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: equipment equipment_substitute_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.equipment
    ADD CONSTRAINT equipment_substitute_person_id_fkey FOREIGN KEY (substitute_person_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: files files_acceptance_act_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_acceptance_act_id_fkey FOREIGN KEY (acceptance_act_id) REFERENCES public.acceptance_acts(id) ON DELETE SET NULL;


--
-- Name: files files_contract_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_contract_id_fkey FOREIGN KEY (contract_id) REFERENCES public.contracts(id) ON DELETE SET NULL;


--
-- Name: files files_deleted_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_deleted_by_id_fkey FOREIGN KEY (deleted_by_id) REFERENCES public.users(id);


--
-- Name: files files_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE SET NULL;


--
-- Name: files files_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: files files_replaces_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_replaces_id_fkey FOREIGN KEY (replaces_id) REFERENCES public.files(id) ON DELETE SET NULL;


--
-- Name: files files_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE SET NULL;


--
-- Name: files files_standard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_standard_id_fkey FOREIGN KEY (standard_id) REFERENCES public.standards(id) ON DELETE SET NULL;


--
-- Name: files files_uploaded_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_uploaded_by_id_fkey FOREIGN KEY (uploaded_by_id) REFERENCES public.users(id);


--
-- Name: user_additional_laboratories fk_ual_laboratory; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.user_additional_laboratories
    ADD CONSTRAINT fk_ual_laboratory FOREIGN KEY (laboratory_id) REFERENCES public.laboratories(id) ON DELETE CASCADE;


--
-- Name: user_additional_laboratories fk_ual_user; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.user_additional_laboratories
    ADD CONSTRAINT fk_ual_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: users fk_users_mentor; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_mentor FOREIGN KEY (mentor_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: journal_columns journal_columns_journal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.journal_columns
    ADD CONSTRAINT journal_columns_journal_id_fkey FOREIGN KEY (journal_id) REFERENCES public.journals(id) ON DELETE CASCADE;


--
-- Name: laboratories laboratories_head_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.laboratories
    ADD CONSTRAINT laboratories_head_id_fkey FOREIGN KEY (head_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: permissions_log permissions_log_changed_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.permissions_log
    ADD CONSTRAINT permissions_log_changed_by_id_fkey FOREIGN KEY (changed_by_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: permissions_log permissions_log_column_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.permissions_log
    ADD CONSTRAINT permissions_log_column_id_fkey FOREIGN KEY (column_id) REFERENCES public.journal_columns(id) ON DELETE CASCADE;


--
-- Name: permissions_log permissions_log_journal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.permissions_log
    ADD CONSTRAINT permissions_log_journal_id_fkey FOREIGN KEY (journal_id) REFERENCES public.journals(id) ON DELETE CASCADE;


--
-- Name: permissions_log permissions_log_target_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.permissions_log
    ADD CONSTRAINT permissions_log_target_user_id_fkey FOREIGN KEY (target_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: personal_folder_access personal_folder_access_granted_to_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.personal_folder_access
    ADD CONSTRAINT personal_folder_access_granted_to_id_fkey FOREIGN KEY (granted_to_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: personal_folder_access personal_folder_access_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.personal_folder_access
    ADD CONSTRAINT personal_folder_access_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: role_laboratory_access role_laboratory_access_journal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.role_laboratory_access
    ADD CONSTRAINT role_laboratory_access_journal_id_fkey FOREIGN KEY (journal_id) REFERENCES public.journals(id) ON DELETE CASCADE;


--
-- Name: role_laboratory_access role_laboratory_access_laboratory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.role_laboratory_access
    ADD CONSTRAINT role_laboratory_access_laboratory_id_fkey FOREIGN KEY (laboratory_id) REFERENCES public.laboratories(id) ON DELETE CASCADE;


--
-- Name: role_permissions role_permissions_column_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_column_id_fkey FOREIGN KEY (column_id) REFERENCES public.journal_columns(id) ON DELETE CASCADE;


--
-- Name: role_permissions role_permissions_journal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_journal_id_fkey FOREIGN KEY (journal_id) REFERENCES public.journals(id) ON DELETE CASCADE;


--
-- Name: sample_auxiliary_equipment sample_auxiliary_equipment_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_auxiliary_equipment
    ADD CONSTRAINT sample_auxiliary_equipment_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE RESTRICT;


--
-- Name: sample_auxiliary_equipment sample_auxiliary_equipment_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_auxiliary_equipment
    ADD CONSTRAINT sample_auxiliary_equipment_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- Name: sample_manufacturing_auxiliary_equipment sample_manufacturing_auxiliary_equipment_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_auxiliary_equipment
    ADD CONSTRAINT sample_manufacturing_auxiliary_equipment_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE RESTRICT;


--
-- Name: sample_manufacturing_auxiliary_equipment sample_manufacturing_auxiliary_equipment_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_auxiliary_equipment
    ADD CONSTRAINT sample_manufacturing_auxiliary_equipment_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- Name: sample_manufacturing_measuring_instruments sample_manufacturing_measuring_instruments_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_measuring_instruments
    ADD CONSTRAINT sample_manufacturing_measuring_instruments_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE RESTRICT;


--
-- Name: sample_manufacturing_measuring_instruments sample_manufacturing_measuring_instruments_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_measuring_instruments
    ADD CONSTRAINT sample_manufacturing_measuring_instruments_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- Name: sample_manufacturing_operators sample_manufacturing_operators_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_operators
    ADD CONSTRAINT sample_manufacturing_operators_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- Name: sample_manufacturing_operators sample_manufacturing_operators_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_operators
    ADD CONSTRAINT sample_manufacturing_operators_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: sample_manufacturing_testing_equipment sample_manufacturing_testing_equipment_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_testing_equipment
    ADD CONSTRAINT sample_manufacturing_testing_equipment_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE RESTRICT;


--
-- Name: sample_manufacturing_testing_equipment sample_manufacturing_testing_equipment_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_manufacturing_testing_equipment
    ADD CONSTRAINT sample_manufacturing_testing_equipment_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- Name: sample_measuring_instruments sample_measuring_instruments_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_measuring_instruments
    ADD CONSTRAINT sample_measuring_instruments_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE RESTRICT;


--
-- Name: sample_measuring_instruments sample_measuring_instruments_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_measuring_instruments
    ADD CONSTRAINT sample_measuring_instruments_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- Name: sample_operators sample_operators_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_operators
    ADD CONSTRAINT sample_operators_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- Name: sample_operators sample_operators_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_operators
    ADD CONSTRAINT sample_operators_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: sample_parameters sample_parameters_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_parameters
    ADD CONSTRAINT sample_parameters_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- Name: sample_parameters sample_parameters_standard_parameter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_parameters
    ADD CONSTRAINT sample_parameters_standard_parameter_id_fkey FOREIGN KEY (standard_parameter_id) REFERENCES public.standard_parameters(id) ON DELETE SET NULL;


--
-- Name: sample_parameters sample_parameters_tested_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_parameters
    ADD CONSTRAINT sample_parameters_tested_by_id_fkey FOREIGN KEY (tested_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: sample_standards sample_standards_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_standards
    ADD CONSTRAINT sample_standards_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- Name: sample_standards sample_standards_standard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_standards
    ADD CONSTRAINT sample_standards_standard_id_fkey FOREIGN KEY (standard_id) REFERENCES public.standards(id) ON DELETE RESTRICT;


--
-- Name: sample_testing_equipment sample_testing_equipment_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_testing_equipment
    ADD CONSTRAINT sample_testing_equipment_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE RESTRICT;


--
-- Name: sample_testing_equipment sample_testing_equipment_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.sample_testing_equipment
    ADD CONSTRAINT sample_testing_equipment_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- Name: samples samples_acceptance_act_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_acceptance_act_id_fkey FOREIGN KEY (acceptance_act_id) REFERENCES public.acceptance_acts(id) ON DELETE SET NULL;


--
-- Name: samples samples_accreditation_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_accreditation_area_id_fkey FOREIGN KEY (accreditation_area_id) REFERENCES public.accreditation_areas(id) ON DELETE RESTRICT;


--
-- Name: samples samples_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE RESTRICT;


--
-- Name: samples samples_contract_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_contract_id_fkey FOREIGN KEY (contract_id) REFERENCES public.contracts(id) ON DELETE RESTRICT;


--
-- Name: samples samples_cutting_standard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_cutting_standard_id_fkey FOREIGN KEY (cutting_standard_id) REFERENCES public.standards(id) ON DELETE SET NULL;


--
-- Name: samples samples_laboratory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_laboratory_id_fkey FOREIGN KEY (laboratory_id) REFERENCES public.laboratories(id) ON DELETE RESTRICT;


--
-- Name: samples samples_moisture_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_moisture_sample_id_fkey FOREIGN KEY (moisture_sample_id) REFERENCES public.samples(id) ON DELETE SET NULL;


--
-- Name: samples samples_protocol_checked_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_protocol_checked_by_fkey FOREIGN KEY (protocol_checked_by) REFERENCES public.users(id);


--
-- Name: samples samples_registered_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_registered_by_id_fkey FOREIGN KEY (registered_by_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: samples samples_report_prepared_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_report_prepared_by_id_fkey FOREIGN KEY (report_prepared_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: samples samples_verified_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_verified_by_fkey FOREIGN KEY (verified_by) REFERENCES public.users(id);


--
-- Name: standard_accreditation_areas standard_accreditation_areas_accreditation_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standard_accreditation_areas
    ADD CONSTRAINT standard_accreditation_areas_accreditation_area_id_fkey FOREIGN KEY (accreditation_area_id) REFERENCES public.accreditation_areas(id) ON DELETE CASCADE;


--
-- Name: standard_accreditation_areas standard_accreditation_areas_standard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standard_accreditation_areas
    ADD CONSTRAINT standard_accreditation_areas_standard_id_fkey FOREIGN KEY (standard_id) REFERENCES public.standards(id) ON DELETE CASCADE;


--
-- Name: standard_laboratories standard_laboratories_laboratory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standard_laboratories
    ADD CONSTRAINT standard_laboratories_laboratory_id_fkey FOREIGN KEY (laboratory_id) REFERENCES public.laboratories(id) ON DELETE CASCADE;


--
-- Name: standard_laboratories standard_laboratories_standard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standard_laboratories
    ADD CONSTRAINT standard_laboratories_standard_id_fkey FOREIGN KEY (standard_id) REFERENCES public.standards(id) ON DELETE CASCADE;


--
-- Name: standard_parameters standard_parameters_parameter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standard_parameters
    ADD CONSTRAINT standard_parameters_parameter_id_fkey FOREIGN KEY (parameter_id) REFERENCES public.parameters(id) ON DELETE CASCADE;


--
-- Name: standard_parameters standard_parameters_standard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.standard_parameters
    ADD CONSTRAINT standard_parameters_standard_id_fkey FOREIGN KEY (standard_id) REFERENCES public.standards(id) ON DELETE CASCADE;


--
-- Name: time_log time_log_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.time_log
    ADD CONSTRAINT time_log_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: time_log time_log_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.time_log
    ADD CONSTRAINT time_log_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE SET NULL;


--
-- Name: user_permissions_override user_permissions_override_column_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.user_permissions_override
    ADD CONSTRAINT user_permissions_override_column_id_fkey FOREIGN KEY (column_id) REFERENCES public.journal_columns(id) ON DELETE CASCADE;


--
-- Name: user_permissions_override user_permissions_override_granted_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.user_permissions_override
    ADD CONSTRAINT user_permissions_override_granted_by_id_fkey FOREIGN KEY (granted_by_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: user_permissions_override user_permissions_override_journal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.user_permissions_override
    ADD CONSTRAINT user_permissions_override_journal_id_fkey FOREIGN KEY (journal_id) REFERENCES public.journals(id) ON DELETE CASCADE;


--
-- Name: user_permissions_override user_permissions_override_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.user_permissions_override
    ADD CONSTRAINT user_permissions_override_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: users users_laboratory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_laboratory_id_fkey FOREIGN KEY (laboratory_id) REFERENCES public.laboratories(id) ON DELETE SET NULL;


--
-- Name: weight_log weight_log_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.weight_log
    ADD CONSTRAINT weight_log_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE RESTRICT;


--
-- Name: weight_log weight_log_measured_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.weight_log
    ADD CONSTRAINT weight_log_measured_by_id_fkey FOREIGN KEY (measured_by_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: weight_log weight_log_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.weight_log
    ADD CONSTRAINT weight_log_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- Name: workshop_log workshop_log_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.workshop_log
    ADD CONSTRAINT workshop_log_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE RESTRICT;


--
-- Name: workshop_log workshop_log_operator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.workshop_log
    ADD CONSTRAINT workshop_log_operator_id_fkey FOREIGN KEY (operator_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: workshop_log workshop_log_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cisis_user
--

ALTER TABLE ONLY public.workshop_log
    ADD CONSTRAINT workshop_log_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict 4ZJUAqpyDXfOiMiFX7OQRpgLtHG0uBt9I8I5QndOondkhmdRT8uVbrcg6Av2GmX

