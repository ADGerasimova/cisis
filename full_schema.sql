--
-- PostgreSQL database dump
--

\restrict xLTqrmgdUTzBqiKQpCLTA9eQFcwQAQompVwrEFXmplV7rlkBtGilu5vnfuHdCkm

-- Dumped from database version 18.1
-- Dumped by pg_dump version 18.1

-- Started on 2026-03-03 22:57:21

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 320 (class 1255 OID 18306)
-- Name: prevent_user_deletion(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.prevent_user_deletion() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION 'Удаление пользователей запрещено! Используйте деактивацию (is_active = FALSE)';
    RETURN NULL;
END;
$$;


ALTER FUNCTION public.prevent_user_deletion() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 305 (class 1259 OID 19189)
-- Name: acceptance_act_laboratories; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.acceptance_act_laboratories (
    id integer NOT NULL,
    act_id integer NOT NULL,
    laboratory_id integer NOT NULL,
    completed_date date
);


ALTER TABLE public.acceptance_act_laboratories OWNER TO postgres;

--
-- TOC entry 5919 (class 0 OID 0)
-- Dependencies: 305
-- Name: TABLE acceptance_act_laboratories; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.acceptance_act_laboratories IS 'Лаборатории, задействованные в акте';


--
-- TOC entry 5920 (class 0 OID 0)
-- Dependencies: 305
-- Name: COLUMN acceptance_act_laboratories.completed_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.acceptance_act_laboratories.completed_date IS 'Авто: дата последнего протокола, когда все образцы по этой лабе закрыты';


--
-- TOC entry 304 (class 1259 OID 19188)
-- Name: acceptance_act_laboratories_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.acceptance_act_laboratories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.acceptance_act_laboratories_id_seq OWNER TO postgres;

--
-- TOC entry 5921 (class 0 OID 0)
-- Dependencies: 304
-- Name: acceptance_act_laboratories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.acceptance_act_laboratories_id_seq OWNED BY public.acceptance_act_laboratories.id;


--
-- TOC entry 303 (class 1259 OID 19139)
-- Name: acceptance_acts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.acceptance_acts (
    id integer NOT NULL,
    contract_id integer NOT NULL,
    created_by_id integer,
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
    updated_at timestamp with time zone DEFAULT now(),
    doc_number character varying(100) DEFAULT ''::character varying NOT NULL
);


ALTER TABLE public.acceptance_acts OWNER TO postgres;

--
-- TOC entry 5922 (class 0 OID 0)
-- Dependencies: 303
-- Name: TABLE acceptance_acts; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.acceptance_acts IS 'Акты приёма-передачи (входящие документы)';


--
-- TOC entry 5923 (class 0 OID 0)
-- Dependencies: 303
-- Name: COLUMN acceptance_acts.document_name; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.acceptance_acts.document_name IS 'Название документа как передано заказчиком';


--
-- TOC entry 5924 (class 0 OID 0)
-- Dependencies: 303
-- Name: COLUMN acceptance_acts.document_status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.acceptance_acts.document_status IS 'Статус: SCANS_RECEIVED, ORIGINALS_RECEIVED';


--
-- TOC entry 5925 (class 0 OID 0)
-- Dependencies: 303
-- Name: COLUMN acceptance_acts.payment_terms; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.acceptance_acts.payment_terms IS 'Условия оплаты: PREPAID, POSTPAID, ADVANCE_50, ADVANCE_30, OTHER';


--
-- TOC entry 5926 (class 0 OID 0)
-- Dependencies: 303
-- Name: COLUMN acceptance_acts.document_flow; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.acceptance_acts.document_flow IS 'Документооборот: PAPER, EDO';


--
-- TOC entry 5927 (class 0 OID 0)
-- Dependencies: 303
-- Name: COLUMN acceptance_acts.closing_status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.acceptance_acts.closing_status IS 'Статус закрывающих: PREPARED, SENT_TO_CLIENT, RECEIVED, CANCELLED, NONE';


--
-- TOC entry 5928 (class 0 OID 0)
-- Dependencies: 303
-- Name: COLUMN acceptance_acts.work_status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.acceptance_acts.work_status IS 'Статус работ: IN_PROGRESS, CLOSED, CANCELLED';


--
-- TOC entry 5929 (class 0 OID 0)
-- Dependencies: 303
-- Name: COLUMN acceptance_acts.sending_method; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.acceptance_acts.sending_method IS 'Способ отправки: COURIER, EMAIL, RUSSIAN_POST, GARANTPOST, IN_PERSON';


--
-- TOC entry 5930 (class 0 OID 0)
-- Dependencies: 303
-- Name: COLUMN acceptance_acts.doc_number; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.acceptance_acts.doc_number IS 'Короткий код латиницей (M1092) — для шифра образца';


--
-- TOC entry 302 (class 1259 OID 19138)
-- Name: acceptance_acts_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.acceptance_acts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.acceptance_acts_id_seq OWNER TO postgres;

--
-- TOC entry 5931 (class 0 OID 0)
-- Dependencies: 302
-- Name: acceptance_acts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.acceptance_acts_id_seq OWNED BY public.acceptance_acts.id;


--
-- TOC entry 228 (class 1259 OID 17506)
-- Name: accreditation_areas; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.accreditation_areas (
    id integer NOT NULL,
    name character varying(200) NOT NULL,
    code character varying(20) NOT NULL,
    description text DEFAULT ''::text,
    is_active boolean DEFAULT true,
    is_default boolean DEFAULT false
);


ALTER TABLE public.accreditation_areas OWNER TO postgres;

--
-- TOC entry 227 (class 1259 OID 17505)
-- Name: accreditation_areas_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.accreditation_areas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.accreditation_areas_id_seq OWNER TO postgres;

--
-- TOC entry 5932 (class 0 OID 0)
-- Dependencies: 227
-- Name: accreditation_areas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.accreditation_areas_id_seq OWNED BY public.accreditation_areas.id;


--
-- TOC entry 299 (class 1259 OID 18916)
-- Name: audit_log; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.audit_log OWNER TO postgres;

--
-- TOC entry 5933 (class 0 OID 0)
-- Dependencies: 299
-- Name: TABLE audit_log; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.audit_log IS 'Единый журнал аудита всех действий в системе CISIS';


--
-- TOC entry 5934 (class 0 OID 0)
-- Dependencies: 299
-- Name: COLUMN audit_log.entity_type; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.audit_log.entity_type IS 'Тип сущности: sample, equipment, climate_log и т.д.';


--
-- TOC entry 5935 (class 0 OID 0)
-- Dependencies: 299
-- Name: COLUMN audit_log.action; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.audit_log.action IS 'Тип действия: create, update, status_change, delete, m2m_add, m2m_remove';


--
-- TOC entry 5936 (class 0 OID 0)
-- Dependencies: 299
-- Name: COLUMN audit_log.extra_data; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.audit_log.extra_data IS 'JSON с доп. контекстом (например, список изменённых M2M-связей)';


--
-- TOC entry 298 (class 1259 OID 18915)
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.audit_log_id_seq OWNER TO postgres;

--
-- TOC entry 5937 (class 0 OID 0)
-- Dependencies: 298
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;


--
-- TOC entry 278 (class 1259 OID 18219)
-- Name: auth_group; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.auth_group (
    id integer NOT NULL,
    name character varying(150) NOT NULL
);


ALTER TABLE public.auth_group OWNER TO postgres;

--
-- TOC entry 277 (class 1259 OID 18218)
-- Name: auth_group_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
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
-- TOC entry 280 (class 1259 OID 18229)
-- Name: auth_group_permissions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.auth_group_permissions (
    id bigint NOT NULL,
    group_id integer NOT NULL,
    permission_id integer NOT NULL
);


ALTER TABLE public.auth_group_permissions OWNER TO postgres;

--
-- TOC entry 279 (class 1259 OID 18228)
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
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
-- TOC entry 276 (class 1259 OID 18209)
-- Name: auth_permission; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.auth_permission (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    content_type_id integer NOT NULL,
    codename character varying(100) NOT NULL
);


ALTER TABLE public.auth_permission OWNER TO postgres;

--
-- TOC entry 275 (class 1259 OID 18208)
-- Name: auth_permission_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
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
-- TOC entry 224 (class 1259 OID 17462)
-- Name: client_contacts; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.client_contacts OWNER TO postgres;

--
-- TOC entry 223 (class 1259 OID 17461)
-- Name: client_contacts_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.client_contacts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.client_contacts_id_seq OWNER TO postgres;

--
-- TOC entry 5938 (class 0 OID 0)
-- Dependencies: 223
-- Name: client_contacts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.client_contacts_id_seq OWNED BY public.client_contacts.id;


--
-- TOC entry 222 (class 1259 OID 17446)
-- Name: clients; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.clients OWNER TO postgres;

--
-- TOC entry 221 (class 1259 OID 17445)
-- Name: clients_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.clients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.clients_id_seq OWNER TO postgres;

--
-- TOC entry 5939 (class 0 OID 0)
-- Dependencies: 221
-- Name: clients_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.clients_id_seq OWNED BY public.clients.id;


--
-- TOC entry 260 (class 1259 OID 17995)
-- Name: climate_log; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.climate_log OWNER TO postgres;

--
-- TOC entry 259 (class 1259 OID 17994)
-- Name: climate_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.climate_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.climate_log_id_seq OWNER TO postgres;

--
-- TOC entry 5940 (class 0 OID 0)
-- Dependencies: 259
-- Name: climate_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.climate_log_id_seq OWNED BY public.climate_log.id;


--
-- TOC entry 226 (class 1259 OID 17483)
-- Name: contracts; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.contracts OWNER TO postgres;

--
-- TOC entry 225 (class 1259 OID 17482)
-- Name: contracts_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.contracts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.contracts_id_seq OWNER TO postgres;

--
-- TOC entry 5941 (class 0 OID 0)
-- Dependencies: 225
-- Name: contracts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.contracts_id_seq OWNED BY public.contracts.id;


--
-- TOC entry 274 (class 1259 OID 18182)
-- Name: django_admin_log; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.django_admin_log OWNER TO postgres;

--
-- TOC entry 273 (class 1259 OID 18181)
-- Name: django_admin_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
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
-- TOC entry 272 (class 1259 OID 18170)
-- Name: django_content_type; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.django_content_type (
    id integer NOT NULL,
    app_label character varying(100) NOT NULL,
    model character varying(100) NOT NULL
);


ALTER TABLE public.django_content_type OWNER TO postgres;

--
-- TOC entry 271 (class 1259 OID 18169)
-- Name: django_content_type_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
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
-- TOC entry 270 (class 1259 OID 18158)
-- Name: django_migrations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.django_migrations (
    id bigint NOT NULL,
    app character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    applied timestamp with time zone NOT NULL
);


ALTER TABLE public.django_migrations OWNER TO postgres;

--
-- TOC entry 269 (class 1259 OID 18157)
-- Name: django_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
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
-- TOC entry 281 (class 1259 OID 18265)
-- Name: django_session; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.django_session (
    session_key character varying(40) NOT NULL,
    session_data text NOT NULL,
    expire_date timestamp with time zone NOT NULL
);


ALTER TABLE public.django_session OWNER TO postgres;

--
-- TOC entry 236 (class 1259 OID 17575)
-- Name: equipment; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.equipment OWNER TO postgres;

--
-- TOC entry 238 (class 1259 OID 17620)
-- Name: equipment_accreditation_areas; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.equipment_accreditation_areas (
    id integer NOT NULL,
    equipment_id integer NOT NULL,
    accreditation_area_id integer NOT NULL
);


ALTER TABLE public.equipment_accreditation_areas OWNER TO postgres;

--
-- TOC entry 237 (class 1259 OID 17619)
-- Name: equipment_accreditation_areas_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.equipment_accreditation_areas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.equipment_accreditation_areas_id_seq OWNER TO postgres;

--
-- TOC entry 5942 (class 0 OID 0)
-- Dependencies: 237
-- Name: equipment_accreditation_areas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.equipment_accreditation_areas_id_seq OWNED BY public.equipment_accreditation_areas.id;


--
-- TOC entry 235 (class 1259 OID 17574)
-- Name: equipment_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.equipment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.equipment_id_seq OWNER TO postgres;

--
-- TOC entry 5943 (class 0 OID 0)
-- Dependencies: 235
-- Name: equipment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.equipment_id_seq OWNED BY public.equipment.id;


--
-- TOC entry 240 (class 1259 OID 17642)
-- Name: equipment_maintenance; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.equipment_maintenance OWNER TO postgres;

--
-- TOC entry 239 (class 1259 OID 17641)
-- Name: equipment_maintenance_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.equipment_maintenance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.equipment_maintenance_id_seq OWNER TO postgres;

--
-- TOC entry 5944 (class 0 OID 0)
-- Dependencies: 239
-- Name: equipment_maintenance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.equipment_maintenance_id_seq OWNED BY public.equipment_maintenance.id;


--
-- TOC entry 309 (class 1259 OID 19458)
-- Name: file_type_defaults; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.file_type_defaults (
    id integer NOT NULL,
    category character varying(50) NOT NULL,
    file_type character varying(50) NOT NULL,
    default_visibility character varying(20) DEFAULT 'ALL'::character varying NOT NULL,
    default_subfolder character varying(200) DEFAULT ''::character varying NOT NULL
);


ALTER TABLE public.file_type_defaults OWNER TO postgres;

--
-- TOC entry 308 (class 1259 OID 19457)
-- Name: file_type_defaults_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.file_type_defaults_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.file_type_defaults_id_seq OWNER TO postgres;

--
-- TOC entry 5945 (class 0 OID 0)
-- Dependencies: 308
-- Name: file_type_defaults_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.file_type_defaults_id_seq OWNED BY public.file_type_defaults.id;


--
-- TOC entry 311 (class 1259 OID 19474)
-- Name: file_visibility_rules; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.file_visibility_rules (
    id integer NOT NULL,
    file_type character varying(50) NOT NULL,
    category character varying(50) NOT NULL,
    role character varying(50) NOT NULL
);


ALTER TABLE public.file_visibility_rules OWNER TO postgres;

--
-- TOC entry 310 (class 1259 OID 19473)
-- Name: file_visibility_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.file_visibility_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.file_visibility_rules_id_seq OWNER TO postgres;

--
-- TOC entry 5946 (class 0 OID 0)
-- Dependencies: 310
-- Name: file_visibility_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.file_visibility_rules_id_seq OWNED BY public.file_visibility_rules.id;


--
-- TOC entry 307 (class 1259 OID 19368)
-- Name: files; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.files OWNER TO postgres;

--
-- TOC entry 306 (class 1259 OID 19367)
-- Name: files_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.files_id_seq OWNER TO postgres;

--
-- TOC entry 5947 (class 0 OID 0)
-- Dependencies: 306
-- Name: files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.files_id_seq OWNED BY public.files.id;


--
-- TOC entry 234 (class 1259 OID 17562)
-- Name: holidays; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.holidays (
    id integer NOT NULL,
    date date NOT NULL,
    name character varying(200) NOT NULL,
    is_working boolean DEFAULT false
);


ALTER TABLE public.holidays OWNER TO postgres;

--
-- TOC entry 233 (class 1259 OID 17561)
-- Name: holidays_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.holidays_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.holidays_id_seq OWNER TO postgres;

--
-- TOC entry 5948 (class 0 OID 0)
-- Dependencies: 233
-- Name: holidays_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.holidays_id_seq OWNED BY public.holidays.id;


--
-- TOC entry 252 (class 1259 OID 17873)
-- Name: journal_columns; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.journal_columns (
    id integer NOT NULL,
    journal_id integer NOT NULL,
    code character varying(100) NOT NULL,
    name character varying(200) NOT NULL,
    is_active boolean DEFAULT true,
    display_order integer DEFAULT 0
);


ALTER TABLE public.journal_columns OWNER TO postgres;

--
-- TOC entry 251 (class 1259 OID 17872)
-- Name: journal_columns_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.journal_columns_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.journal_columns_id_seq OWNER TO postgres;

--
-- TOC entry 5949 (class 0 OID 0)
-- Dependencies: 251
-- Name: journal_columns_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.journal_columns_id_seq OWNED BY public.journal_columns.id;


--
-- TOC entry 250 (class 1259 OID 17860)
-- Name: journals; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.journals (
    id integer NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(200) NOT NULL,
    is_active boolean DEFAULT true
);


ALTER TABLE public.journals OWNER TO postgres;

--
-- TOC entry 249 (class 1259 OID 17859)
-- Name: journals_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.journals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.journals_id_seq OWNER TO postgres;

--
-- TOC entry 5950 (class 0 OID 0)
-- Dependencies: 249
-- Name: journals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.journals_id_seq OWNED BY public.journals.id;


--
-- TOC entry 220 (class 1259 OID 17433)
-- Name: laboratories; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.laboratories OWNER TO postgres;

--
-- TOC entry 5951 (class 0 OID 0)
-- Dependencies: 220
-- Name: COLUMN laboratories.department_type; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.laboratories.department_type IS 'LAB = лаборатория, WORKSHOP = мастерская, DEPARTMENT = подразделение';


--
-- TOC entry 219 (class 1259 OID 17432)
-- Name: laboratories_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.laboratories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.laboratories_id_seq OWNER TO postgres;

--
-- TOC entry 5952 (class 0 OID 0)
-- Dependencies: 219
-- Name: laboratories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.laboratories_id_seq OWNED BY public.laboratories.id;


--
-- TOC entry 315 (class 1259 OID 19516)
-- Name: parameters; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.parameters OWNER TO postgres;

--
-- TOC entry 5953 (class 0 OID 0)
-- Dependencies: 315
-- Name: TABLE parameters; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.parameters IS 'Единый справочник определяемых показателей';


--
-- TOC entry 5954 (class 0 OID 0)
-- Dependencies: 315
-- Name: COLUMN parameters.category; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.parameters.category IS 'MECHANICAL / THERMAL / CHEMICAL / DIMENSIONAL / OTHER';


--
-- TOC entry 314 (class 1259 OID 19515)
-- Name: parameters_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.parameters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.parameters_id_seq OWNER TO postgres;

--
-- TOC entry 5955 (class 0 OID 0)
-- Dependencies: 314
-- Name: parameters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.parameters_id_seq OWNED BY public.parameters.id;


--
-- TOC entry 258 (class 1259 OID 17957)
-- Name: permissions_log; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.permissions_log OWNER TO postgres;

--
-- TOC entry 257 (class 1259 OID 17956)
-- Name: permissions_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.permissions_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.permissions_log_id_seq OWNER TO postgres;

--
-- TOC entry 5956 (class 0 OID 0)
-- Dependencies: 257
-- Name: permissions_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.permissions_log_id_seq OWNED BY public.permissions_log.id;


--
-- TOC entry 313 (class 1259 OID 19487)
-- Name: personal_folder_access; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.personal_folder_access (
    id integer NOT NULL,
    owner_id integer NOT NULL,
    granted_to_id integer NOT NULL,
    access_level character varying(10) DEFAULT 'VIEW'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_pfa_access_level CHECK (((access_level)::text = ANY ((ARRAY['VIEW'::character varying, 'EDIT'::character varying])::text[])))
);


ALTER TABLE public.personal_folder_access OWNER TO postgres;

--
-- TOC entry 312 (class 1259 OID 19486)
-- Name: personal_folder_access_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.personal_folder_access_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.personal_folder_access_id_seq OWNER TO postgres;

--
-- TOC entry 5957 (class 0 OID 0)
-- Dependencies: 312
-- Name: personal_folder_access_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.personal_folder_access_id_seq OWNED BY public.personal_folder_access.id;


--
-- TOC entry 301 (class 1259 OID 19036)
-- Name: role_laboratory_access; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.role_laboratory_access (
    id integer NOT NULL,
    role character varying(20) NOT NULL,
    journal_id integer NOT NULL,
    laboratory_id integer
);


ALTER TABLE public.role_laboratory_access OWNER TO postgres;

--
-- TOC entry 5958 (class 0 OID 0)
-- Dependencies: 301
-- Name: TABLE role_laboratory_access; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.role_laboratory_access IS 'Видимость лабораторий по ролям для каждого журнала';


--
-- TOC entry 5959 (class 0 OID 0)
-- Dependencies: 301
-- Name: COLUMN role_laboratory_access.laboratory_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.role_laboratory_access.laboratory_id IS 'NULL = все лаборатории';


--
-- TOC entry 300 (class 1259 OID 19035)
-- Name: role_laboratory_access_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.role_laboratory_access_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.role_laboratory_access_id_seq OWNER TO postgres;

--
-- TOC entry 5960 (class 0 OID 0)
-- Dependencies: 300
-- Name: role_laboratory_access_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.role_laboratory_access_id_seq OWNED BY public.role_laboratory_access.id;


--
-- TOC entry 254 (class 1259 OID 17893)
-- Name: role_permissions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.role_permissions (
    id integer NOT NULL,
    role character varying(20) NOT NULL,
    journal_id integer NOT NULL,
    column_id integer,
    access_level character varying(10) DEFAULT 'NONE'::character varying NOT NULL
);


ALTER TABLE public.role_permissions OWNER TO postgres;

--
-- TOC entry 253 (class 1259 OID 17892)
-- Name: role_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.role_permissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.role_permissions_id_seq OWNER TO postgres;

--
-- TOC entry 5961 (class 0 OID 0)
-- Dependencies: 253
-- Name: role_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.role_permissions_id_seq OWNED BY public.role_permissions.id;


--
-- TOC entry 293 (class 1259 OID 18841)
-- Name: sample_auxiliary_equipment; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sample_auxiliary_equipment (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    equipment_id integer NOT NULL
);


ALTER TABLE public.sample_auxiliary_equipment OWNER TO postgres;

--
-- TOC entry 292 (class 1259 OID 18840)
-- Name: sample_auxiliary_equipment_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sample_auxiliary_equipment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_auxiliary_equipment_id_seq OWNER TO postgres;

--
-- TOC entry 5962 (class 0 OID 0)
-- Dependencies: 292
-- Name: sample_auxiliary_equipment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sample_auxiliary_equipment_id_seq OWNED BY public.sample_auxiliary_equipment.id;


--
-- TOC entry 291 (class 1259 OID 18817)
-- Name: sample_manufacturing_auxiliary_equipment; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sample_manufacturing_auxiliary_equipment (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    equipment_id integer NOT NULL
);


ALTER TABLE public.sample_manufacturing_auxiliary_equipment OWNER TO postgres;

--
-- TOC entry 290 (class 1259 OID 18816)
-- Name: sample_manufacturing_auxiliary_equipment_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sample_manufacturing_auxiliary_equipment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_manufacturing_auxiliary_equipment_id_seq OWNER TO postgres;

--
-- TOC entry 5963 (class 0 OID 0)
-- Dependencies: 290
-- Name: sample_manufacturing_auxiliary_equipment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sample_manufacturing_auxiliary_equipment_id_seq OWNED BY public.sample_manufacturing_auxiliary_equipment.id;


--
-- TOC entry 283 (class 1259 OID 18576)
-- Name: sample_manufacturing_measuring_instruments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sample_manufacturing_measuring_instruments (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    equipment_id integer CONSTRAINT sample_manufacturing_measuring_instrument_equipment_id_not_null NOT NULL
);


ALTER TABLE public.sample_manufacturing_measuring_instruments OWNER TO postgres;

--
-- TOC entry 5964 (class 0 OID 0)
-- Dependencies: 283
-- Name: TABLE sample_manufacturing_measuring_instruments; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.sample_manufacturing_measuring_instruments IS 'Связь образца со средствами измерений для изготовления';


--
-- TOC entry 282 (class 1259 OID 18575)
-- Name: sample_manufacturing_measuring_instruments_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sample_manufacturing_measuring_instruments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_manufacturing_measuring_instruments_id_seq OWNER TO postgres;

--
-- TOC entry 5965 (class 0 OID 0)
-- Dependencies: 282
-- Name: sample_manufacturing_measuring_instruments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sample_manufacturing_measuring_instruments_id_seq OWNED BY public.sample_manufacturing_measuring_instruments.id;


--
-- TOC entry 287 (class 1259 OID 18620)
-- Name: sample_manufacturing_operators; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sample_manufacturing_operators (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    user_id integer NOT NULL
);


ALTER TABLE public.sample_manufacturing_operators OWNER TO postgres;

--
-- TOC entry 5966 (class 0 OID 0)
-- Dependencies: 287
-- Name: TABLE sample_manufacturing_operators; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.sample_manufacturing_operators IS 'Связь образца с операторами изготовления (мастерская)';


--
-- TOC entry 286 (class 1259 OID 18619)
-- Name: sample_manufacturing_operators_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sample_manufacturing_operators_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_manufacturing_operators_id_seq OWNER TO postgres;

--
-- TOC entry 5967 (class 0 OID 0)
-- Dependencies: 286
-- Name: sample_manufacturing_operators_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sample_manufacturing_operators_id_seq OWNED BY public.sample_manufacturing_operators.id;


--
-- TOC entry 285 (class 1259 OID 18598)
-- Name: sample_manufacturing_testing_equipment; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sample_manufacturing_testing_equipment (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    equipment_id integer NOT NULL
);


ALTER TABLE public.sample_manufacturing_testing_equipment OWNER TO postgres;

--
-- TOC entry 5968 (class 0 OID 0)
-- Dependencies: 285
-- Name: TABLE sample_manufacturing_testing_equipment; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.sample_manufacturing_testing_equipment IS 'Связь образца с испытательным оборудованием для изготовления';


--
-- TOC entry 284 (class 1259 OID 18597)
-- Name: sample_manufacturing_testing_equipment_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sample_manufacturing_testing_equipment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_manufacturing_testing_equipment_id_seq OWNER TO postgres;

--
-- TOC entry 5969 (class 0 OID 0)
-- Dependencies: 284
-- Name: sample_manufacturing_testing_equipment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sample_manufacturing_testing_equipment_id_seq OWNED BY public.sample_manufacturing_testing_equipment.id;


--
-- TOC entry 246 (class 1259 OID 17816)
-- Name: sample_measuring_instruments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sample_measuring_instruments (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    equipment_id integer NOT NULL
);


ALTER TABLE public.sample_measuring_instruments OWNER TO postgres;

--
-- TOC entry 245 (class 1259 OID 17815)
-- Name: sample_measuring_instruments_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sample_measuring_instruments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_measuring_instruments_id_seq OWNER TO postgres;

--
-- TOC entry 5970 (class 0 OID 0)
-- Dependencies: 245
-- Name: sample_measuring_instruments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sample_measuring_instruments_id_seq OWNED BY public.sample_measuring_instruments.id;


--
-- TOC entry 268 (class 1259 OID 18136)
-- Name: sample_operators; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sample_operators (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    user_id integer NOT NULL
);


ALTER TABLE public.sample_operators OWNER TO postgres;

--
-- TOC entry 267 (class 1259 OID 18135)
-- Name: sample_operators_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sample_operators_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_operators_id_seq OWNER TO postgres;

--
-- TOC entry 5971 (class 0 OID 0)
-- Dependencies: 267
-- Name: sample_operators_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sample_operators_id_seq OWNED BY public.sample_operators.id;


--
-- TOC entry 319 (class 1259 OID 19582)
-- Name: sample_parameters; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.sample_parameters OWNER TO postgres;

--
-- TOC entry 5972 (class 0 OID 0)
-- Dependencies: 319
-- Name: TABLE sample_parameters; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.sample_parameters IS 'Показатели конкретного образца (выбранные из стандарта или кастомные)';


--
-- TOC entry 5973 (class 0 OID 0)
-- Dependencies: 319
-- Name: COLUMN sample_parameters.is_selected; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.sample_parameters.is_selected IS 'TRUE — виден в поле «определяемые параметры», FALSE — только в таблице результатов';


--
-- TOC entry 5974 (class 0 OID 0)
-- Dependencies: 319
-- Name: COLUMN sample_parameters.result_status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.sample_parameters.result_status IS 'PENDING / FILLED / VALIDATED (будущее)';


--
-- TOC entry 318 (class 1259 OID 19581)
-- Name: sample_parameters_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sample_parameters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_parameters_id_seq OWNER TO postgres;

--
-- TOC entry 5975 (class 0 OID 0)
-- Dependencies: 318
-- Name: sample_parameters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sample_parameters_id_seq OWNED BY public.sample_parameters.id;


--
-- TOC entry 297 (class 1259 OID 18890)
-- Name: sample_standards; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sample_standards (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    standard_id integer NOT NULL
);


ALTER TABLE public.sample_standards OWNER TO postgres;

--
-- TOC entry 296 (class 1259 OID 18889)
-- Name: sample_standards_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sample_standards_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_standards_id_seq OWNER TO postgres;

--
-- TOC entry 5976 (class 0 OID 0)
-- Dependencies: 296
-- Name: sample_standards_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sample_standards_id_seq OWNED BY public.sample_standards.id;


--
-- TOC entry 248 (class 1259 OID 17838)
-- Name: sample_testing_equipment; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sample_testing_equipment (
    id integer NOT NULL,
    sample_id integer NOT NULL,
    equipment_id integer NOT NULL
);


ALTER TABLE public.sample_testing_equipment OWNER TO postgres;

--
-- TOC entry 247 (class 1259 OID 17837)
-- Name: sample_testing_equipment_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sample_testing_equipment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_testing_equipment_id_seq OWNER TO postgres;

--
-- TOC entry 5977 (class 0 OID 0)
-- Dependencies: 247
-- Name: sample_testing_equipment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sample_testing_equipment_id_seq OWNED BY public.sample_testing_equipment.id;


--
-- TOC entry 244 (class 1259 OID 17715)
-- Name: samples; Type: TABLE; Schema: public; Owner: postgres
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
    CONSTRAINT samples_further_movement_check CHECK (((further_movement)::text = ANY ((ARRAY[''::character varying, 'TO_MI'::character varying, 'TO_CHA'::character varying, 'TO_TA'::character varying, 'TO_ACT'::character varying, 'TO_CLIENT_DEPT'::character varying])::text[]))),
    CONSTRAINT samples_status_check CHECK (((status)::text = ANY ((ARRAY['PENDING_VERIFICATION'::character varying, 'REGISTERED'::character varying, 'CANCELLED'::character varying, 'MANUFACTURING'::character varying, 'MANUFACTURED'::character varying, 'TRANSFERRED'::character varying, 'MOISTURE_CONDITIONING'::character varying, 'MOISTURE_READY'::character varying, 'CONDITIONING'::character varying, 'READY_FOR_TEST'::character varying, 'IN_TESTING'::character varying, 'TESTED'::character varying, 'DRAFT_READY'::character varying, 'RESULTS_UPLOADED'::character varying, 'PROTOCOL_ISSUED'::character varying, 'COMPLETED'::character varying, 'REPLACEMENT_PROTOCOL'::character varying])::text[]))),
    CONSTRAINT samples_workshop_status_check CHECK ((((workshop_status)::text = ANY ((ARRAY['IN_WORKSHOP'::character varying, 'COMPLETED'::character varying, 'CANCELLED'::character varying])::text[])) OR (workshop_status IS NULL)))
);


ALTER TABLE public.samples OWNER TO postgres;

--
-- TOC entry 5978 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.registered_by_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.registered_by_id IS 'Первый администратор, который зарегистрировал образец';


--
-- TOC entry 5979 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.status IS 'Статус образца: PENDING_VERIFICATION, REGISTERED, CANCELLED, CONDITIONING, READY_FOR_TEST, IN_TESTING, TESTED, DRAFT_READY, RESULTS_UPLOADED, PROTOCOL_ISSUED, COMPLETED';


--
-- TOC entry 5980 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.verified_by; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.verified_by IS 'Второй администратор, который проверил и подтвердил регистрацию';


--
-- TOC entry 5981 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.verified_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.verified_at IS 'Дата и время проверки регистрации';


--
-- TOC entry 5982 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.protocol_checked_by; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.protocol_checked_by IS 'Сотрудник СМК, который проверил протокол';


--
-- TOC entry 5983 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.protocol_checked_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.protocol_checked_at IS 'Дата и время проверки протокола';


--
-- TOC entry 5984 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.replacement_count; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.replacement_count IS 'Количество выпущенных замещающих протоколов';


--
-- TOC entry 5985 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.conditioning_start_datetime; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.conditioning_start_datetime IS 'Дата и время начала кондиционирования (для ХА, ТА)';


--
-- TOC entry 5986 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.conditioning_end_datetime; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.conditioning_end_datetime IS 'Дата и время окончания кондиционирования (для ХА, ТА)';


--
-- TOC entry 5987 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.testing_start_datetime; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.testing_start_datetime IS 'Дата и время начала испытания (для ХА, ТА, УКИ)';


--
-- TOC entry 5988 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.testing_end_datetime; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.testing_end_datetime IS 'Дата и время окончания испытания (для всех лабораторий)';


--
-- TOC entry 5989 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.manufacturing_completion_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.manufacturing_completion_date IS 'Дата и время завершения изготовления (заполняется при нажатии кнопки)';


--
-- TOC entry 5990 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.report_prepared_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.report_prepared_date IS 'Дата и время подготовки отчёта (изменено с DATE на TIMESTAMP в v3.2.4)';


--
-- TOC entry 5991 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.manufacturing; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.manufacturing IS 'Требуется изготовление (boolean: true = требуется, false = не требуется)';


--
-- TOC entry 5992 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.workshop_status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.workshop_status IS 'Статус образца в мастерской: IN_WORKSHOP (В мастерской), COMPLETED (Готово), NULL (не требует изготовления)';


--
-- TOC entry 5993 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.sample_count; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.sample_count IS 'Количество образцов';


--
-- TOC entry 5994 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.manufacturing_deadline; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.manufacturing_deadline IS 'Срок изготовления (для мастерской)';


--
-- TOC entry 5995 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.moisture_conditioning; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.moisture_conditioning IS 'Требуется влагонасыщение перед испытанием';


--
-- TOC entry 5996 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.moisture_sample_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.moisture_sample_id IS 'FK на образец влагонасыщения (УКИ). Образец A, к которому привязан данный образец B';


--
-- TOC entry 5997 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.cutting_standard_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.cutting_standard_id IS 'Стандарт на нарезку (для мастерской). Если NULL — мастерская ориентируется на основные стандарты.';


--
-- TOC entry 5998 (class 0 OID 0)
-- Dependencies: 244
-- Name: COLUMN samples.acceptance_act_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.samples.acceptance_act_id IS 'Привязка образца к акту приёма-передачи';


--
-- TOC entry 5999 (class 0 OID 0)
-- Dependencies: 244
-- Name: CONSTRAINT samples_status_check ON samples; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON CONSTRAINT samples_status_check ON public.samples IS 'v3.15.0: Допустимые статусы образца, включая MOISTURE_CONDITIONING и MOISTURE_READY';


--
-- TOC entry 243 (class 1259 OID 17714)
-- Name: samples_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.samples_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.samples_id_seq OWNER TO postgres;

--
-- TOC entry 6000 (class 0 OID 0)
-- Dependencies: 243
-- Name: samples_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.samples_id_seq OWNED BY public.samples.id;


--
-- TOC entry 232 (class 1259 OID 17538)
-- Name: standard_accreditation_areas; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.standard_accreditation_areas (
    id integer NOT NULL,
    standard_id integer NOT NULL,
    accreditation_area_id integer NOT NULL
);


ALTER TABLE public.standard_accreditation_areas OWNER TO postgres;

--
-- TOC entry 231 (class 1259 OID 17537)
-- Name: standard_accreditation_areas_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.standard_accreditation_areas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.standard_accreditation_areas_id_seq OWNER TO postgres;

--
-- TOC entry 6001 (class 0 OID 0)
-- Dependencies: 231
-- Name: standard_accreditation_areas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.standard_accreditation_areas_id_seq OWNED BY public.standard_accreditation_areas.id;


--
-- TOC entry 295 (class 1259 OID 18866)
-- Name: standard_laboratories; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.standard_laboratories (
    id integer NOT NULL,
    standard_id integer NOT NULL,
    laboratory_id integer NOT NULL
);


ALTER TABLE public.standard_laboratories OWNER TO postgres;

--
-- TOC entry 294 (class 1259 OID 18865)
-- Name: standard_laboratories_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.standard_laboratories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.standard_laboratories_id_seq OWNER TO postgres;

--
-- TOC entry 6002 (class 0 OID 0)
-- Dependencies: 294
-- Name: standard_laboratories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.standard_laboratories_id_seq OWNED BY public.standard_laboratories.id;


--
-- TOC entry 317 (class 1259 OID 19541)
-- Name: standard_parameters; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.standard_parameters OWNER TO postgres;

--
-- TOC entry 6003 (class 0 OID 0)
-- Dependencies: 317
-- Name: TABLE standard_parameters; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.standard_parameters IS 'Привязка показателей к стандартам с настройками';


--
-- TOC entry 6004 (class 0 OID 0)
-- Dependencies: 317
-- Name: COLUMN standard_parameters.parameter_role; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.standard_parameters.parameter_role IS 'PRIMARY — основной, AUXILIARY — вспомогательный, CALCULATED — расчётный';


--
-- TOC entry 6005 (class 0 OID 0)
-- Dependencies: 317
-- Name: COLUMN standard_parameters.is_default; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.standard_parameters.is_default IS 'Автоматически включать при выборе стандарта';


--
-- TOC entry 6006 (class 0 OID 0)
-- Dependencies: 317
-- Name: COLUMN standard_parameters.unit_override; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.standard_parameters.unit_override IS 'Если единица отличается от parameters.unit';


--
-- TOC entry 6007 (class 0 OID 0)
-- Dependencies: 317
-- Name: COLUMN standard_parameters.report_group; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.standard_parameters.report_group IS 'Группа в протоколе (Механические, Размеры и т.д.)';


--
-- TOC entry 6008 (class 0 OID 0)
-- Dependencies: 317
-- Name: COLUMN standard_parameters.formula; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.standard_parameters.formula IS 'Формула расчёта для CALCULATED (будущее)';


--
-- TOC entry 6009 (class 0 OID 0)
-- Dependencies: 317
-- Name: COLUMN standard_parameters.depends_on; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.standard_parameters.depends_on IS 'JSON-массив parameter_id для CALCULATED (будущее)';


--
-- TOC entry 316 (class 1259 OID 19540)
-- Name: standard_parameters_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.standard_parameters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.standard_parameters_id_seq OWNER TO postgres;

--
-- TOC entry 6010 (class 0 OID 0)
-- Dependencies: 316
-- Name: standard_parameters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.standard_parameters_id_seq OWNED BY public.standard_parameters.id;


--
-- TOC entry 230 (class 1259 OID 17523)
-- Name: standards; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.standards (
    id integer NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(500) NOT NULL,
    is_active boolean DEFAULT true,
    test_code character varying(20) DEFAULT ''::character varying,
    test_type character varying(200) DEFAULT ''::character varying
);


ALTER TABLE public.standards OWNER TO postgres;

--
-- TOC entry 229 (class 1259 OID 17522)
-- Name: standards_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.standards_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.standards_id_seq OWNER TO postgres;

--
-- TOC entry 6011 (class 0 OID 0)
-- Dependencies: 229
-- Name: standards_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.standards_id_seq OWNED BY public.standards.id;


--
-- TOC entry 266 (class 1259 OID 18089)
-- Name: time_log; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.time_log OWNER TO postgres;

--
-- TOC entry 265 (class 1259 OID 18088)
-- Name: time_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.time_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.time_log_id_seq OWNER TO postgres;

--
-- TOC entry 6012 (class 0 OID 0)
-- Dependencies: 265
-- Name: time_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.time_log_id_seq OWNED BY public.time_log.id;


--
-- TOC entry 289 (class 1259 OID 18685)
-- Name: user_additional_laboratories; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_additional_laboratories (
    id integer NOT NULL,
    user_id integer NOT NULL,
    laboratory_id integer NOT NULL
);


ALTER TABLE public.user_additional_laboratories OWNER TO postgres;

--
-- TOC entry 288 (class 1259 OID 18684)
-- Name: user_additional_laboratories_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_additional_laboratories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_additional_laboratories_id_seq OWNER TO postgres;

--
-- TOC entry 6013 (class 0 OID 0)
-- Dependencies: 288
-- Name: user_additional_laboratories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_additional_laboratories_id_seq OWNED BY public.user_additional_laboratories.id;


--
-- TOC entry 256 (class 1259 OID 17917)
-- Name: user_permissions_override; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.user_permissions_override OWNER TO postgres;

--
-- TOC entry 255 (class 1259 OID 17916)
-- Name: user_permissions_override_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_permissions_override_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_permissions_override_id_seq OWNER TO postgres;

--
-- TOC entry 6014 (class 0 OID 0)
-- Dependencies: 255
-- Name: user_permissions_override_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_permissions_override_id_seq OWNED BY public.user_permissions_override.id;


--
-- TOC entry 242 (class 1259 OID 17664)
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.users OWNER TO postgres;

--
-- TOC entry 6015 (class 0 OID 0)
-- Dependencies: 242
-- Name: COLUMN users.role; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.users.role IS 'Роль пользователя: CEO, CTO, SYSADMIN, LAB_HEAD, TESTER, CLIENT_DEPT_HEAD, CLIENT_MANAGER, CONTRACT_SPEC, QMS_HEAD, QMS_ADMIN, METROLOGIST, WORKSHOP, ACCOUNTANT, OTHER';


--
-- TOC entry 6016 (class 0 OID 0)
-- Dependencies: 242
-- Name: COLUMN users.sur_name; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.users.sur_name IS 'Отчество пользователя';


--
-- TOC entry 241 (class 1259 OID 17663)
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO postgres;

--
-- TOC entry 6017 (class 0 OID 0)
-- Dependencies: 241
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- TOC entry 262 (class 1259 OID 18021)
-- Name: weight_log; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.weight_log OWNER TO postgres;

--
-- TOC entry 261 (class 1259 OID 18020)
-- Name: weight_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.weight_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.weight_log_id_seq OWNER TO postgres;

--
-- TOC entry 6018 (class 0 OID 0)
-- Dependencies: 261
-- Name: weight_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.weight_log_id_seq OWNED BY public.weight_log.id;


--
-- TOC entry 264 (class 1259 OID 18054)
-- Name: workshop_log; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.workshop_log OWNER TO postgres;

--
-- TOC entry 263 (class 1259 OID 18053)
-- Name: workshop_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.workshop_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.workshop_log_id_seq OWNER TO postgres;

--
-- TOC entry 6019 (class 0 OID 0)
-- Dependencies: 263
-- Name: workshop_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.workshop_log_id_seq OWNED BY public.workshop_log.id;


--
-- TOC entry 5261 (class 2604 OID 19192)
-- Name: acceptance_act_laboratories id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.acceptance_act_laboratories ALTER COLUMN id SET DEFAULT nextval('public.acceptance_act_laboratories_id_seq'::regclass);


--
-- TOC entry 5245 (class 2604 OID 19142)
-- Name: acceptance_acts id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.acceptance_acts ALTER COLUMN id SET DEFAULT nextval('public.acceptance_acts_id_seq'::regclass);


--
-- TOC entry 5123 (class 2604 OID 17509)
-- Name: accreditation_areas id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.accreditation_areas ALTER COLUMN id SET DEFAULT nextval('public.accreditation_areas_id_seq'::regclass);


--
-- TOC entry 5242 (class 2604 OID 18919)
-- Name: audit_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);


--
-- TOC entry 5115 (class 2604 OID 17465)
-- Name: client_contacts id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.client_contacts ALTER COLUMN id SET DEFAULT nextval('public.client_contacts_id_seq'::regclass);


--
-- TOC entry 5109 (class 2604 OID 17449)
-- Name: clients id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clients ALTER COLUMN id SET DEFAULT nextval('public.clients_id_seq'::regclass);


--
-- TOC entry 5220 (class 2604 OID 17998)
-- Name: climate_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.climate_log ALTER COLUMN id SET DEFAULT nextval('public.climate_log_id_seq'::regclass);


--
-- TOC entry 5120 (class 2604 OID 17486)
-- Name: contracts id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.contracts ALTER COLUMN id SET DEFAULT nextval('public.contracts_id_seq'::regclass);


--
-- TOC entry 5134 (class 2604 OID 17578)
-- Name: equipment id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipment ALTER COLUMN id SET DEFAULT nextval('public.equipment_id_seq'::regclass);


--
-- TOC entry 5154 (class 2604 OID 17623)
-- Name: equipment_accreditation_areas id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipment_accreditation_areas ALTER COLUMN id SET DEFAULT nextval('public.equipment_accreditation_areas_id_seq'::regclass);


--
-- TOC entry 5155 (class 2604 OID 17645)
-- Name: equipment_maintenance id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipment_maintenance ALTER COLUMN id SET DEFAULT nextval('public.equipment_maintenance_id_seq'::regclass);


--
-- TOC entry 5273 (class 2604 OID 19461)
-- Name: file_type_defaults id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.file_type_defaults ALTER COLUMN id SET DEFAULT nextval('public.file_type_defaults_id_seq'::regclass);


--
-- TOC entry 5276 (class 2604 OID 19477)
-- Name: file_visibility_rules id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.file_visibility_rules ALTER COLUMN id SET DEFAULT nextval('public.file_visibility_rules_id_seq'::regclass);


--
-- TOC entry 5262 (class 2604 OID 19371)
-- Name: files id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.files ALTER COLUMN id SET DEFAULT nextval('public.files_id_seq'::regclass);


--
-- TOC entry 5132 (class 2604 OID 17565)
-- Name: holidays id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.holidays ALTER COLUMN id SET DEFAULT nextval('public.holidays_id_seq'::regclass);


--
-- TOC entry 5207 (class 2604 OID 17876)
-- Name: journal_columns id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.journal_columns ALTER COLUMN id SET DEFAULT nextval('public.journal_columns_id_seq'::regclass);


--
-- TOC entry 5205 (class 2604 OID 17863)
-- Name: journals id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.journals ALTER COLUMN id SET DEFAULT nextval('public.journals_id_seq'::regclass);


--
-- TOC entry 5106 (class 2604 OID 17436)
-- Name: laboratories id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laboratories ALTER COLUMN id SET DEFAULT nextval('public.laboratories_id_seq'::regclass);


--
-- TOC entry 5280 (class 2604 OID 19519)
-- Name: parameters id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.parameters ALTER COLUMN id SET DEFAULT nextval('public.parameters_id_seq'::regclass);


--
-- TOC entry 5216 (class 2604 OID 17960)
-- Name: permissions_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.permissions_log ALTER COLUMN id SET DEFAULT nextval('public.permissions_log_id_seq'::regclass);


--
-- TOC entry 5277 (class 2604 OID 19490)
-- Name: personal_folder_access id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.personal_folder_access ALTER COLUMN id SET DEFAULT nextval('public.personal_folder_access_id_seq'::regclass);


--
-- TOC entry 5244 (class 2604 OID 19039)
-- Name: role_laboratory_access id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.role_laboratory_access ALTER COLUMN id SET DEFAULT nextval('public.role_laboratory_access_id_seq'::regclass);


--
-- TOC entry 5210 (class 2604 OID 17896)
-- Name: role_permissions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.role_permissions ALTER COLUMN id SET DEFAULT nextval('public.role_permissions_id_seq'::regclass);


--
-- TOC entry 5239 (class 2604 OID 18844)
-- Name: sample_auxiliary_equipment id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_auxiliary_equipment ALTER COLUMN id SET DEFAULT nextval('public.sample_auxiliary_equipment_id_seq'::regclass);


--
-- TOC entry 5238 (class 2604 OID 18820)
-- Name: sample_manufacturing_auxiliary_equipment id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_auxiliary_equipment ALTER COLUMN id SET DEFAULT nextval('public.sample_manufacturing_auxiliary_equipment_id_seq'::regclass);


--
-- TOC entry 5234 (class 2604 OID 18579)
-- Name: sample_manufacturing_measuring_instruments id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_measuring_instruments ALTER COLUMN id SET DEFAULT nextval('public.sample_manufacturing_measuring_instruments_id_seq'::regclass);


--
-- TOC entry 5236 (class 2604 OID 18623)
-- Name: sample_manufacturing_operators id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_operators ALTER COLUMN id SET DEFAULT nextval('public.sample_manufacturing_operators_id_seq'::regclass);


--
-- TOC entry 5235 (class 2604 OID 18601)
-- Name: sample_manufacturing_testing_equipment id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_testing_equipment ALTER COLUMN id SET DEFAULT nextval('public.sample_manufacturing_testing_equipment_id_seq'::regclass);


--
-- TOC entry 5203 (class 2604 OID 17819)
-- Name: sample_measuring_instruments id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_measuring_instruments ALTER COLUMN id SET DEFAULT nextval('public.sample_measuring_instruments_id_seq'::regclass);


--
-- TOC entry 5233 (class 2604 OID 18139)
-- Name: sample_operators id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_operators ALTER COLUMN id SET DEFAULT nextval('public.sample_operators_id_seq'::regclass);


--
-- TOC entry 5294 (class 2604 OID 19585)
-- Name: sample_parameters id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_parameters ALTER COLUMN id SET DEFAULT nextval('public.sample_parameters_id_seq'::regclass);


--
-- TOC entry 5241 (class 2604 OID 18893)
-- Name: sample_standards id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_standards ALTER COLUMN id SET DEFAULT nextval('public.sample_standards_id_seq'::regclass);


--
-- TOC entry 5204 (class 2604 OID 17841)
-- Name: sample_testing_equipment id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_testing_equipment ALTER COLUMN id SET DEFAULT nextval('public.sample_testing_equipment_id_seq'::regclass);


--
-- TOC entry 5173 (class 2604 OID 17718)
-- Name: samples id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.samples ALTER COLUMN id SET DEFAULT nextval('public.samples_id_seq'::regclass);


--
-- TOC entry 5131 (class 2604 OID 17541)
-- Name: standard_accreditation_areas id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standard_accreditation_areas ALTER COLUMN id SET DEFAULT nextval('public.standard_accreditation_areas_id_seq'::regclass);


--
-- TOC entry 5240 (class 2604 OID 18869)
-- Name: standard_laboratories id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standard_laboratories ALTER COLUMN id SET DEFAULT nextval('public.standard_laboratories_id_seq'::regclass);


--
-- TOC entry 5286 (class 2604 OID 19544)
-- Name: standard_parameters id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standard_parameters ALTER COLUMN id SET DEFAULT nextval('public.standard_parameters_id_seq'::regclass);


--
-- TOC entry 5127 (class 2604 OID 17526)
-- Name: standards id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standards ALTER COLUMN id SET DEFAULT nextval('public.standards_id_seq'::regclass);


--
-- TOC entry 5231 (class 2604 OID 18092)
-- Name: time_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.time_log ALTER COLUMN id SET DEFAULT nextval('public.time_log_id_seq'::regclass);


--
-- TOC entry 5237 (class 2604 OID 18688)
-- Name: user_additional_laboratories id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_additional_laboratories ALTER COLUMN id SET DEFAULT nextval('public.user_additional_laboratories_id_seq'::regclass);


--
-- TOC entry 5212 (class 2604 OID 17920)
-- Name: user_permissions_override id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_permissions_override ALTER COLUMN id SET DEFAULT nextval('public.user_permissions_override_id_seq'::regclass);


--
-- TOC entry 5160 (class 2604 OID 17667)
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- TOC entry 5222 (class 2604 OID 18024)
-- Name: weight_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.weight_log ALTER COLUMN id SET DEFAULT nextval('public.weight_log_id_seq'::regclass);


--
-- TOC entry 5225 (class 2604 OID 18057)
-- Name: workshop_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workshop_log ALTER COLUMN id SET DEFAULT nextval('public.workshop_log_id_seq'::regclass);


--
-- TOC entry 5899 (class 0 OID 19189)
-- Dependencies: 305
-- Data for Name: acceptance_act_laboratories; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5897 (class 0 OID 19139)
-- Dependencies: 303
-- Data for Name: acceptance_acts; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5822 (class 0 OID 17506)
-- Dependencies: 228
-- Data for Name: accreditation_areas; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5893 (class 0 OID 18916)
-- Dependencies: 299
-- Data for Name: audit_log; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5872 (class 0 OID 18219)
-- Dependencies: 278
-- Data for Name: auth_group; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5874 (class 0 OID 18229)
-- Dependencies: 280
-- Data for Name: auth_group_permissions; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5870 (class 0 OID 18209)
-- Dependencies: 276
-- Data for Name: auth_permission; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5818 (class 0 OID 17462)
-- Dependencies: 224
-- Data for Name: client_contacts; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5816 (class 0 OID 17446)
-- Dependencies: 222
-- Data for Name: clients; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5854 (class 0 OID 17995)
-- Dependencies: 260
-- Data for Name: climate_log; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5820 (class 0 OID 17483)
-- Dependencies: 226
-- Data for Name: contracts; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5868 (class 0 OID 18182)
-- Dependencies: 274
-- Data for Name: django_admin_log; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5866 (class 0 OID 18170)
-- Dependencies: 272
-- Data for Name: django_content_type; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5864 (class 0 OID 18158)
-- Dependencies: 270
-- Data for Name: django_migrations; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5875 (class 0 OID 18265)
-- Dependencies: 281
-- Data for Name: django_session; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5830 (class 0 OID 17575)
-- Dependencies: 236
-- Data for Name: equipment; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5832 (class 0 OID 17620)
-- Dependencies: 238
-- Data for Name: equipment_accreditation_areas; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5834 (class 0 OID 17642)
-- Dependencies: 240
-- Data for Name: equipment_maintenance; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5903 (class 0 OID 19458)
-- Dependencies: 309
-- Data for Name: file_type_defaults; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5905 (class 0 OID 19474)
-- Dependencies: 311
-- Data for Name: file_visibility_rules; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5901 (class 0 OID 19368)
-- Dependencies: 307
-- Data for Name: files; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5828 (class 0 OID 17562)
-- Dependencies: 234
-- Data for Name: holidays; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5846 (class 0 OID 17873)
-- Dependencies: 252
-- Data for Name: journal_columns; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5844 (class 0 OID 17860)
-- Dependencies: 250
-- Data for Name: journals; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5814 (class 0 OID 17433)
-- Dependencies: 220
-- Data for Name: laboratories; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5909 (class 0 OID 19516)
-- Dependencies: 315
-- Data for Name: parameters; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5852 (class 0 OID 17957)
-- Dependencies: 258
-- Data for Name: permissions_log; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5907 (class 0 OID 19487)
-- Dependencies: 313
-- Data for Name: personal_folder_access; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5895 (class 0 OID 19036)
-- Dependencies: 301
-- Data for Name: role_laboratory_access; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5848 (class 0 OID 17893)
-- Dependencies: 254
-- Data for Name: role_permissions; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5887 (class 0 OID 18841)
-- Dependencies: 293
-- Data for Name: sample_auxiliary_equipment; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5885 (class 0 OID 18817)
-- Dependencies: 291
-- Data for Name: sample_manufacturing_auxiliary_equipment; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5877 (class 0 OID 18576)
-- Dependencies: 283
-- Data for Name: sample_manufacturing_measuring_instruments; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5881 (class 0 OID 18620)
-- Dependencies: 287
-- Data for Name: sample_manufacturing_operators; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5879 (class 0 OID 18598)
-- Dependencies: 285
-- Data for Name: sample_manufacturing_testing_equipment; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5840 (class 0 OID 17816)
-- Dependencies: 246
-- Data for Name: sample_measuring_instruments; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5862 (class 0 OID 18136)
-- Dependencies: 268
-- Data for Name: sample_operators; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5913 (class 0 OID 19582)
-- Dependencies: 319
-- Data for Name: sample_parameters; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5891 (class 0 OID 18890)
-- Dependencies: 297
-- Data for Name: sample_standards; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5842 (class 0 OID 17838)
-- Dependencies: 248
-- Data for Name: sample_testing_equipment; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5838 (class 0 OID 17715)
-- Dependencies: 244
-- Data for Name: samples; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5826 (class 0 OID 17538)
-- Dependencies: 232
-- Data for Name: standard_accreditation_areas; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5889 (class 0 OID 18866)
-- Dependencies: 295
-- Data for Name: standard_laboratories; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5911 (class 0 OID 19541)
-- Dependencies: 317
-- Data for Name: standard_parameters; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5824 (class 0 OID 17523)
-- Dependencies: 230
-- Data for Name: standards; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5860 (class 0 OID 18089)
-- Dependencies: 266
-- Data for Name: time_log; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5883 (class 0 OID 18685)
-- Dependencies: 289
-- Data for Name: user_additional_laboratories; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5850 (class 0 OID 17917)
-- Dependencies: 256
-- Data for Name: user_permissions_override; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5836 (class 0 OID 17664)
-- Dependencies: 242
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5856 (class 0 OID 18021)
-- Dependencies: 262
-- Data for Name: weight_log; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 5858 (class 0 OID 18054)
-- Dependencies: 264
-- Data for Name: workshop_log; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- TOC entry 6020 (class 0 OID 0)
-- Dependencies: 304
-- Name: acceptance_act_laboratories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.acceptance_act_laboratories_id_seq', 5, true);


--
-- TOC entry 6021 (class 0 OID 0)
-- Dependencies: 302
-- Name: acceptance_acts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.acceptance_acts_id_seq', 3, true);


--
-- TOC entry 6022 (class 0 OID 0)
-- Dependencies: 227
-- Name: accreditation_areas_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.accreditation_areas_id_seq', 5, true);


--
-- TOC entry 6023 (class 0 OID 0)
-- Dependencies: 298
-- Name: audit_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.audit_log_id_seq', 134, true);


--
-- TOC entry 6024 (class 0 OID 0)
-- Dependencies: 277
-- Name: auth_group_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.auth_group_id_seq', 1, false);


--
-- TOC entry 6025 (class 0 OID 0)
-- Dependencies: 279
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.auth_group_permissions_id_seq', 1, false);


--
-- TOC entry 6026 (class 0 OID 0)
-- Dependencies: 275
-- Name: auth_permission_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.auth_permission_id_seq', 124, true);


--
-- TOC entry 6027 (class 0 OID 0)
-- Dependencies: 223
-- Name: client_contacts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.client_contacts_id_seq', 6, true);


--
-- TOC entry 6028 (class 0 OID 0)
-- Dependencies: 221
-- Name: clients_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.clients_id_seq', 4, true);


--
-- TOC entry 6029 (class 0 OID 0)
-- Dependencies: 259
-- Name: climate_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.climate_log_id_seq', 1, false);


--
-- TOC entry 6030 (class 0 OID 0)
-- Dependencies: 225
-- Name: contracts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.contracts_id_seq', 6, true);


--
-- TOC entry 6031 (class 0 OID 0)
-- Dependencies: 273
-- Name: django_admin_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.django_admin_log_id_seq', 83, true);


--
-- TOC entry 6032 (class 0 OID 0)
-- Dependencies: 271
-- Name: django_content_type_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.django_content_type_id_seq', 32, true);


--
-- TOC entry 6033 (class 0 OID 0)
-- Dependencies: 269
-- Name: django_migrations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.django_migrations_id_seq', 20, true);


--
-- TOC entry 6034 (class 0 OID 0)
-- Dependencies: 237
-- Name: equipment_accreditation_areas_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.equipment_accreditation_areas_id_seq', 1155, true);


--
-- TOC entry 6035 (class 0 OID 0)
-- Dependencies: 235
-- Name: equipment_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.equipment_id_seq', 405, true);


--
-- TOC entry 6036 (class 0 OID 0)
-- Dependencies: 239
-- Name: equipment_maintenance_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.equipment_maintenance_id_seq', 1, false);


--
-- TOC entry 6037 (class 0 OID 0)
-- Dependencies: 308
-- Name: file_type_defaults_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.file_type_defaults_id_seq', 20, true);


--
-- TOC entry 6038 (class 0 OID 0)
-- Dependencies: 310
-- Name: file_visibility_rules_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.file_visibility_rules_id_seq', 6, true);


--
-- TOC entry 6039 (class 0 OID 0)
-- Dependencies: 306
-- Name: files_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.files_id_seq', 9, true);


--
-- TOC entry 6040 (class 0 OID 0)
-- Dependencies: 233
-- Name: holidays_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.holidays_id_seq', 15, true);


--
-- TOC entry 6041 (class 0 OID 0)
-- Dependencies: 251
-- Name: journal_columns_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.journal_columns_id_seq', 173, true);


--
-- TOC entry 6042 (class 0 OID 0)
-- Dependencies: 249
-- Name: journals_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.journals_id_seq', 18, true);


--
-- TOC entry 6043 (class 0 OID 0)
-- Dependencies: 219
-- Name: laboratories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.laboratories_id_seq', 9, true);


--
-- TOC entry 6044 (class 0 OID 0)
-- Dependencies: 314
-- Name: parameters_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.parameters_id_seq', 2, true);


--
-- TOC entry 6045 (class 0 OID 0)
-- Dependencies: 257
-- Name: permissions_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.permissions_log_id_seq', 146, true);


--
-- TOC entry 6046 (class 0 OID 0)
-- Dependencies: 312
-- Name: personal_folder_access_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.personal_folder_access_id_seq', 1, false);


--
-- TOC entry 6047 (class 0 OID 0)
-- Dependencies: 300
-- Name: role_laboratory_access_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.role_laboratory_access_id_seq', 36, true);


--
-- TOC entry 6048 (class 0 OID 0)
-- Dependencies: 253
-- Name: role_permissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.role_permissions_id_seq', 1714, true);


--
-- TOC entry 6049 (class 0 OID 0)
-- Dependencies: 292
-- Name: sample_auxiliary_equipment_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.sample_auxiliary_equipment_id_seq', 1, false);


--
-- TOC entry 6050 (class 0 OID 0)
-- Dependencies: 290
-- Name: sample_manufacturing_auxiliary_equipment_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.sample_manufacturing_auxiliary_equipment_id_seq', 6, true);


--
-- TOC entry 6051 (class 0 OID 0)
-- Dependencies: 282
-- Name: sample_manufacturing_measuring_instruments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.sample_manufacturing_measuring_instruments_id_seq', 4, true);


--
-- TOC entry 6052 (class 0 OID 0)
-- Dependencies: 286
-- Name: sample_manufacturing_operators_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.sample_manufacturing_operators_id_seq', 20, true);


--
-- TOC entry 6053 (class 0 OID 0)
-- Dependencies: 284
-- Name: sample_manufacturing_testing_equipment_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.sample_manufacturing_testing_equipment_id_seq', 5, true);


--
-- TOC entry 6054 (class 0 OID 0)
-- Dependencies: 245
-- Name: sample_measuring_instruments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.sample_measuring_instruments_id_seq', 12, true);


--
-- TOC entry 6055 (class 0 OID 0)
-- Dependencies: 267
-- Name: sample_operators_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.sample_operators_id_seq', 44, true);


--
-- TOC entry 6056 (class 0 OID 0)
-- Dependencies: 318
-- Name: sample_parameters_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.sample_parameters_id_seq', 1, false);


--
-- TOC entry 6057 (class 0 OID 0)
-- Dependencies: 296
-- Name: sample_standards_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.sample_standards_id_seq', 86, true);


--
-- TOC entry 6058 (class 0 OID 0)
-- Dependencies: 247
-- Name: sample_testing_equipment_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.sample_testing_equipment_id_seq', 7, true);


--
-- TOC entry 6059 (class 0 OID 0)
-- Dependencies: 243
-- Name: samples_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.samples_id_seq', 88, true);


--
-- TOC entry 6060 (class 0 OID 0)
-- Dependencies: 231
-- Name: standard_accreditation_areas_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.standard_accreditation_areas_id_seq', 27, true);


--
-- TOC entry 6061 (class 0 OID 0)
-- Dependencies: 294
-- Name: standard_laboratories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.standard_laboratories_id_seq', 14, true);


--
-- TOC entry 6062 (class 0 OID 0)
-- Dependencies: 316
-- Name: standard_parameters_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.standard_parameters_id_seq', 2, true);


--
-- TOC entry 6063 (class 0 OID 0)
-- Dependencies: 229
-- Name: standards_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.standards_id_seq', 7, true);


--
-- TOC entry 6064 (class 0 OID 0)
-- Dependencies: 265
-- Name: time_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.time_log_id_seq', 1, false);


--
-- TOC entry 6065 (class 0 OID 0)
-- Dependencies: 288
-- Name: user_additional_laboratories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.user_additional_laboratories_id_seq', 2, true);


--
-- TOC entry 6066 (class 0 OID 0)
-- Dependencies: 255
-- Name: user_permissions_override_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.user_permissions_override_id_seq', 8, true);


--
-- TOC entry 6067 (class 0 OID 0)
-- Dependencies: 241
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 65, true);


--
-- TOC entry 6068 (class 0 OID 0)
-- Dependencies: 261
-- Name: weight_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.weight_log_id_seq', 1, false);


--
-- TOC entry 6069 (class 0 OID 0)
-- Dependencies: 263
-- Name: workshop_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.workshop_log_id_seq', 1, false);


--
-- TOC entry 5522 (class 2606 OID 19199)
-- Name: acceptance_act_laboratories acceptance_act_laboratories_act_id_laboratory_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.acceptance_act_laboratories
    ADD CONSTRAINT acceptance_act_laboratories_act_id_laboratory_id_key UNIQUE (act_id, laboratory_id);


--
-- TOC entry 5524 (class 2606 OID 19197)
-- Name: acceptance_act_laboratories acceptance_act_laboratories_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.acceptance_act_laboratories
    ADD CONSTRAINT acceptance_act_laboratories_pkey PRIMARY KEY (id);


--
-- TOC entry 5517 (class 2606 OID 19174)
-- Name: acceptance_acts acceptance_acts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.acceptance_acts
    ADD CONSTRAINT acceptance_acts_pkey PRIMARY KEY (id);


--
-- TOC entry 5323 (class 2606 OID 17521)
-- Name: accreditation_areas accreditation_areas_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.accreditation_areas
    ADD CONSTRAINT accreditation_areas_code_key UNIQUE (code);


--
-- TOC entry 5325 (class 2606 OID 17519)
-- Name: accreditation_areas accreditation_areas_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.accreditation_areas
    ADD CONSTRAINT accreditation_areas_pkey PRIMARY KEY (id);


--
-- TOC entry 5505 (class 2606 OID 18929)
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- TOC entry 5443 (class 2606 OID 18262)
-- Name: auth_group auth_group_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_name_key UNIQUE (name);


--
-- TOC entry 5448 (class 2606 OID 18247)
-- Name: auth_group_permissions auth_group_permissions_group_id_permission_id_0cd325b0_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_permission_id_0cd325b0_uniq UNIQUE (group_id, permission_id);


--
-- TOC entry 5451 (class 2606 OID 18236)
-- Name: auth_group_permissions auth_group_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_pkey PRIMARY KEY (id);


--
-- TOC entry 5445 (class 2606 OID 18225)
-- Name: auth_group auth_group_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_pkey PRIMARY KEY (id);


--
-- TOC entry 5438 (class 2606 OID 18238)
-- Name: auth_permission auth_permission_content_type_id_codename_01ab375a_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_codename_01ab375a_uniq UNIQUE (content_type_id, codename);


--
-- TOC entry 5440 (class 2606 OID 18217)
-- Name: auth_permission auth_permission_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_pkey PRIMARY KEY (id);


--
-- TOC entry 5315 (class 2606 OID 17476)
-- Name: client_contacts client_contacts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.client_contacts
    ADD CONSTRAINT client_contacts_pkey PRIMARY KEY (id);


--
-- TOC entry 5313 (class 2606 OID 17460)
-- Name: clients clients_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_pkey PRIMARY KEY (id);


--
-- TOC entry 5411 (class 2606 OID 18009)
-- Name: climate_log climate_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.climate_log
    ADD CONSTRAINT climate_log_pkey PRIMARY KEY (id);


--
-- TOC entry 5317 (class 2606 OID 17499)
-- Name: contracts contracts_client_id_number_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT contracts_client_id_number_key UNIQUE (client_id, number);


--
-- TOC entry 5319 (class 2606 OID 17497)
-- Name: contracts contracts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT contracts_pkey PRIMARY KEY (id);


--
-- TOC entry 5434 (class 2606 OID 18195)
-- Name: django_admin_log django_admin_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_pkey PRIMARY KEY (id);


--
-- TOC entry 5429 (class 2606 OID 18180)
-- Name: django_content_type django_content_type_app_label_model_76bd3d3b_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_app_label_model_76bd3d3b_uniq UNIQUE (app_label, model);


--
-- TOC entry 5431 (class 2606 OID 18178)
-- Name: django_content_type django_content_type_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_pkey PRIMARY KEY (id);


--
-- TOC entry 5427 (class 2606 OID 18168)
-- Name: django_migrations django_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.django_migrations
    ADD CONSTRAINT django_migrations_pkey PRIMARY KEY (id);


--
-- TOC entry 5454 (class 2606 OID 18274)
-- Name: django_session django_session_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.django_session
    ADD CONSTRAINT django_session_pkey PRIMARY KEY (session_key);


--
-- TOC entry 5344 (class 2606 OID 17630)
-- Name: equipment_accreditation_areas equipment_accreditation_areas_equipment_id_accreditation_ar_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipment_accreditation_areas
    ADD CONSTRAINT equipment_accreditation_areas_equipment_id_accreditation_ar_key UNIQUE (equipment_id, accreditation_area_id);


--
-- TOC entry 5346 (class 2606 OID 17628)
-- Name: equipment_accreditation_areas equipment_accreditation_areas_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipment_accreditation_areas
    ADD CONSTRAINT equipment_accreditation_areas_pkey PRIMARY KEY (id);


--
-- TOC entry 5348 (class 2606 OID 17657)
-- Name: equipment_maintenance equipment_maintenance_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipment_maintenance
    ADD CONSTRAINT equipment_maintenance_pkey PRIMARY KEY (id);


--
-- TOC entry 5339 (class 2606 OID 17609)
-- Name: equipment equipment_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipment
    ADD CONSTRAINT equipment_pkey PRIMARY KEY (id);


--
-- TOC entry 5539 (class 2606 OID 19472)
-- Name: file_type_defaults file_type_defaults_category_file_type_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.file_type_defaults
    ADD CONSTRAINT file_type_defaults_category_file_type_key UNIQUE (category, file_type);


--
-- TOC entry 5541 (class 2606 OID 19470)
-- Name: file_type_defaults file_type_defaults_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.file_type_defaults
    ADD CONSTRAINT file_type_defaults_pkey PRIMARY KEY (id);


--
-- TOC entry 5543 (class 2606 OID 19485)
-- Name: file_visibility_rules file_visibility_rules_file_type_category_role_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.file_visibility_rules
    ADD CONSTRAINT file_visibility_rules_file_type_category_role_key UNIQUE (file_type, category, role);


--
-- TOC entry 5545 (class 2606 OID 19483)
-- Name: file_visibility_rules file_visibility_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.file_visibility_rules
    ADD CONSTRAINT file_visibility_rules_pkey PRIMARY KEY (id);


--
-- TOC entry 5528 (class 2606 OID 19400)
-- Name: files files_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_pkey PRIMARY KEY (id);


--
-- TOC entry 5335 (class 2606 OID 17573)
-- Name: holidays holidays_date_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.holidays
    ADD CONSTRAINT holidays_date_key UNIQUE (date);


--
-- TOC entry 5337 (class 2606 OID 17571)
-- Name: holidays holidays_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.holidays
    ADD CONSTRAINT holidays_pkey PRIMARY KEY (id);


--
-- TOC entry 5395 (class 2606 OID 17886)
-- Name: journal_columns journal_columns_journal_id_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.journal_columns
    ADD CONSTRAINT journal_columns_journal_id_code_key UNIQUE (journal_id, code);


--
-- TOC entry 5397 (class 2606 OID 17884)
-- Name: journal_columns journal_columns_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.journal_columns
    ADD CONSTRAINT journal_columns_pkey PRIMARY KEY (id);


--
-- TOC entry 5391 (class 2606 OID 17871)
-- Name: journals journals_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.journals
    ADD CONSTRAINT journals_code_key UNIQUE (code);


--
-- TOC entry 5393 (class 2606 OID 17869)
-- Name: journals journals_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.journals
    ADD CONSTRAINT journals_pkey PRIMARY KEY (id);


--
-- TOC entry 5309 (class 2606 OID 17444)
-- Name: laboratories laboratories_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laboratories
    ADD CONSTRAINT laboratories_code_key UNIQUE (code);


--
-- TOC entry 5311 (class 2606 OID 17442)
-- Name: laboratories laboratories_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laboratories
    ADD CONSTRAINT laboratories_pkey PRIMARY KEY (id);


--
-- TOC entry 5553 (class 2606 OID 19535)
-- Name: parameters parameters_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.parameters
    ADD CONSTRAINT parameters_pkey PRIMARY KEY (id);


--
-- TOC entry 5409 (class 2606 OID 17973)
-- Name: permissions_log permissions_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.permissions_log
    ADD CONSTRAINT permissions_log_pkey PRIMARY KEY (id);


--
-- TOC entry 5547 (class 2606 OID 19501)
-- Name: personal_folder_access personal_folder_access_owner_id_granted_to_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.personal_folder_access
    ADD CONSTRAINT personal_folder_access_owner_id_granted_to_id_key UNIQUE (owner_id, granted_to_id);


--
-- TOC entry 5549 (class 2606 OID 19499)
-- Name: personal_folder_access personal_folder_access_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.personal_folder_access
    ADD CONSTRAINT personal_folder_access_pkey PRIMARY KEY (id);


--
-- TOC entry 5513 (class 2606 OID 19044)
-- Name: role_laboratory_access role_laboratory_access_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.role_laboratory_access
    ADD CONSTRAINT role_laboratory_access_pkey PRIMARY KEY (id);


--
-- TOC entry 5400 (class 2606 OID 17903)
-- Name: role_permissions role_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (id);


--
-- TOC entry 5402 (class 2606 OID 17905)
-- Name: role_permissions role_permissions_role_journal_id_column_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_role_journal_id_column_id_key UNIQUE (role, journal_id, column_id);


--
-- TOC entry 5489 (class 2606 OID 18849)
-- Name: sample_auxiliary_equipment sample_auxiliary_equipment_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_auxiliary_equipment
    ADD CONSTRAINT sample_auxiliary_equipment_pkey PRIMARY KEY (id);


--
-- TOC entry 5491 (class 2606 OID 18851)
-- Name: sample_auxiliary_equipment sample_auxiliary_equipment_sample_id_equipment_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_auxiliary_equipment
    ADD CONSTRAINT sample_auxiliary_equipment_sample_id_equipment_id_key UNIQUE (sample_id, equipment_id);


--
-- TOC entry 5483 (class 2606 OID 18827)
-- Name: sample_manufacturing_auxiliary_equipment sample_manufacturing_auxiliary_equip_sample_id_equipment_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_auxiliary_equipment
    ADD CONSTRAINT sample_manufacturing_auxiliary_equip_sample_id_equipment_id_key UNIQUE (sample_id, equipment_id);


--
-- TOC entry 5485 (class 2606 OID 18825)
-- Name: sample_manufacturing_auxiliary_equipment sample_manufacturing_auxiliary_equipment_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_auxiliary_equipment
    ADD CONSTRAINT sample_manufacturing_auxiliary_equipment_pkey PRIMARY KEY (id);


--
-- TOC entry 5459 (class 2606 OID 18586)
-- Name: sample_manufacturing_measuring_instruments sample_manufacturing_measuring_instr_sample_id_equipment_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_measuring_instruments
    ADD CONSTRAINT sample_manufacturing_measuring_instr_sample_id_equipment_id_key UNIQUE (sample_id, equipment_id);


--
-- TOC entry 5461 (class 2606 OID 18584)
-- Name: sample_manufacturing_measuring_instruments sample_manufacturing_measuring_instruments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_measuring_instruments
    ADD CONSTRAINT sample_manufacturing_measuring_instruments_pkey PRIMARY KEY (id);


--
-- TOC entry 5471 (class 2606 OID 18628)
-- Name: sample_manufacturing_operators sample_manufacturing_operators_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_operators
    ADD CONSTRAINT sample_manufacturing_operators_pkey PRIMARY KEY (id);


--
-- TOC entry 5473 (class 2606 OID 18630)
-- Name: sample_manufacturing_operators sample_manufacturing_operators_sample_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_operators
    ADD CONSTRAINT sample_manufacturing_operators_sample_id_user_id_key UNIQUE (sample_id, user_id);


--
-- TOC entry 5465 (class 2606 OID 18608)
-- Name: sample_manufacturing_testing_equipment sample_manufacturing_testing_equipme_sample_id_equipment_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_testing_equipment
    ADD CONSTRAINT sample_manufacturing_testing_equipme_sample_id_equipment_id_key UNIQUE (sample_id, equipment_id);


--
-- TOC entry 5467 (class 2606 OID 18606)
-- Name: sample_manufacturing_testing_equipment sample_manufacturing_testing_equipment_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_testing_equipment
    ADD CONSTRAINT sample_manufacturing_testing_equipment_pkey PRIMARY KEY (id);


--
-- TOC entry 5383 (class 2606 OID 17824)
-- Name: sample_measuring_instruments sample_measuring_instruments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_measuring_instruments
    ADD CONSTRAINT sample_measuring_instruments_pkey PRIMARY KEY (id);


--
-- TOC entry 5385 (class 2606 OID 17826)
-- Name: sample_measuring_instruments sample_measuring_instruments_sample_id_equipment_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_measuring_instruments
    ADD CONSTRAINT sample_measuring_instruments_sample_id_equipment_id_key UNIQUE (sample_id, equipment_id);


--
-- TOC entry 5423 (class 2606 OID 18144)
-- Name: sample_operators sample_operators_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_operators
    ADD CONSTRAINT sample_operators_pkey PRIMARY KEY (id);


--
-- TOC entry 5425 (class 2606 OID 18146)
-- Name: sample_operators sample_operators_sample_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_operators
    ADD CONSTRAINT sample_operators_sample_id_user_id_key UNIQUE (sample_id, user_id);


--
-- TOC entry 5566 (class 2606 OID 19598)
-- Name: sample_parameters sample_parameters_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_parameters
    ADD CONSTRAINT sample_parameters_pkey PRIMARY KEY (id);


--
-- TOC entry 5501 (class 2606 OID 18898)
-- Name: sample_standards sample_standards_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_standards
    ADD CONSTRAINT sample_standards_pkey PRIMARY KEY (id);


--
-- TOC entry 5503 (class 2606 OID 18900)
-- Name: sample_standards sample_standards_sample_id_standard_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_standards
    ADD CONSTRAINT sample_standards_sample_id_standard_id_key UNIQUE (sample_id, standard_id);


--
-- TOC entry 5387 (class 2606 OID 17846)
-- Name: sample_testing_equipment sample_testing_equipment_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_testing_equipment
    ADD CONSTRAINT sample_testing_equipment_pkey PRIMARY KEY (id);


--
-- TOC entry 5389 (class 2606 OID 17848)
-- Name: sample_testing_equipment sample_testing_equipment_sample_id_equipment_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_testing_equipment
    ADD CONSTRAINT sample_testing_equipment_sample_id_equipment_id_key UNIQUE (sample_id, equipment_id);


--
-- TOC entry 5377 (class 2606 OID 17769)
-- Name: samples samples_cipher_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_cipher_key UNIQUE (cipher);


--
-- TOC entry 5379 (class 2606 OID 17765)
-- Name: samples samples_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_pkey PRIMARY KEY (id);


--
-- TOC entry 5381 (class 2606 OID 17767)
-- Name: samples samples_sequence_number_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_sequence_number_key UNIQUE (sequence_number);


--
-- TOC entry 5331 (class 2606 OID 17546)
-- Name: standard_accreditation_areas standard_accreditation_areas_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standard_accreditation_areas
    ADD CONSTRAINT standard_accreditation_areas_pkey PRIMARY KEY (id);


--
-- TOC entry 5333 (class 2606 OID 17548)
-- Name: standard_accreditation_areas standard_accreditation_areas_standard_id_accreditation_area_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standard_accreditation_areas
    ADD CONSTRAINT standard_accreditation_areas_standard_id_accreditation_area_key UNIQUE (standard_id, accreditation_area_id);


--
-- TOC entry 5495 (class 2606 OID 18874)
-- Name: standard_laboratories standard_laboratories_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standard_laboratories
    ADD CONSTRAINT standard_laboratories_pkey PRIMARY KEY (id);


--
-- TOC entry 5497 (class 2606 OID 18876)
-- Name: standard_laboratories standard_laboratories_standard_id_laboratory_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standard_laboratories
    ADD CONSTRAINT standard_laboratories_standard_id_laboratory_id_key UNIQUE (standard_id, laboratory_id);


--
-- TOC entry 5559 (class 2606 OID 19566)
-- Name: standard_parameters standard_parameters_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standard_parameters
    ADD CONSTRAINT standard_parameters_pkey PRIMARY KEY (id);


--
-- TOC entry 5327 (class 2606 OID 17536)
-- Name: standards standards_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standards
    ADD CONSTRAINT standards_code_key UNIQUE (code);


--
-- TOC entry 5329 (class 2606 OID 17534)
-- Name: standards standards_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standards
    ADD CONSTRAINT standards_pkey PRIMARY KEY (id);


--
-- TOC entry 5421 (class 2606 OID 18103)
-- Name: time_log time_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.time_log
    ADD CONSTRAINT time_log_pkey PRIMARY KEY (id);


--
-- TOC entry 5555 (class 2606 OID 19537)
-- Name: parameters uq_parameters_name_unit; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.parameters
    ADD CONSTRAINT uq_parameters_name_unit UNIQUE (name, unit);


--
-- TOC entry 5568 (class 2606 OID 19600)
-- Name: sample_parameters uq_sample_std_parameter; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_parameters
    ADD CONSTRAINT uq_sample_std_parameter UNIQUE (sample_id, standard_parameter_id);


--
-- TOC entry 5561 (class 2606 OID 19568)
-- Name: standard_parameters uq_standard_parameter; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standard_parameters
    ADD CONSTRAINT uq_standard_parameter UNIQUE (standard_id, parameter_id);


--
-- TOC entry 5477 (class 2606 OID 18695)
-- Name: user_additional_laboratories uq_user_additional_lab; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_additional_laboratories
    ADD CONSTRAINT uq_user_additional_lab UNIQUE (user_id, laboratory_id);


--
-- TOC entry 5479 (class 2606 OID 18693)
-- Name: user_additional_laboratories user_additional_laboratories_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_additional_laboratories
    ADD CONSTRAINT user_additional_laboratories_pkey PRIMARY KEY (id);


--
-- TOC entry 5405 (class 2606 OID 17933)
-- Name: user_permissions_override user_permissions_override_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_permissions_override
    ADD CONSTRAINT user_permissions_override_pkey PRIMARY KEY (id);


--
-- TOC entry 5407 (class 2606 OID 17935)
-- Name: user_permissions_override user_permissions_override_user_id_journal_id_column_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_permissions_override
    ADD CONSTRAINT user_permissions_override_user_id_journal_id_column_id_key UNIQUE (user_id, journal_id, column_id);


--
-- TOC entry 5355 (class 2606 OID 17685)
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- TOC entry 5357 (class 2606 OID 17687)
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- TOC entry 5417 (class 2606 OID 18037)
-- Name: weight_log weight_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.weight_log
    ADD CONSTRAINT weight_log_pkey PRIMARY KEY (id);


--
-- TOC entry 5419 (class 2606 OID 18072)
-- Name: workshop_log workshop_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workshop_log
    ADD CONSTRAINT workshop_log_pkey PRIMARY KEY (id);


--
-- TOC entry 5441 (class 1259 OID 18263)
-- Name: auth_group_name_a6ea08ec_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX auth_group_name_a6ea08ec_like ON public.auth_group USING btree (name varchar_pattern_ops);


--
-- TOC entry 5446 (class 1259 OID 18258)
-- Name: auth_group_permissions_group_id_b120cbf9; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX auth_group_permissions_group_id_b120cbf9 ON public.auth_group_permissions USING btree (group_id);


--
-- TOC entry 5449 (class 1259 OID 18259)
-- Name: auth_group_permissions_permission_id_84c5c92e; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX auth_group_permissions_permission_id_84c5c92e ON public.auth_group_permissions USING btree (permission_id);


--
-- TOC entry 5436 (class 1259 OID 18244)
-- Name: auth_permission_content_type_id_2f476e4b; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX auth_permission_content_type_id_2f476e4b ON public.auth_permission USING btree (content_type_id);


--
-- TOC entry 5432 (class 1259 OID 18206)
-- Name: django_admin_log_content_type_id_c4bce8eb; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX django_admin_log_content_type_id_c4bce8eb ON public.django_admin_log USING btree (content_type_id);


--
-- TOC entry 5435 (class 1259 OID 18207)
-- Name: django_admin_log_user_id_c564eba6; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX django_admin_log_user_id_c564eba6 ON public.django_admin_log USING btree (user_id);


--
-- TOC entry 5452 (class 1259 OID 18276)
-- Name: django_session_expire_date_a5c62663; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX django_session_expire_date_a5c62663 ON public.django_session USING btree (expire_date);


--
-- TOC entry 5455 (class 1259 OID 18275)
-- Name: django_session_session_key_c0390e0f_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX django_session_session_key_c0390e0f_like ON public.django_session USING btree (session_key varchar_pattern_ops);


--
-- TOC entry 5525 (class 1259 OID 19210)
-- Name: idx_aal_act; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_aal_act ON public.acceptance_act_laboratories USING btree (act_id);


--
-- TOC entry 5526 (class 1259 OID 19211)
-- Name: idx_aal_lab; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_aal_lab ON public.acceptance_act_laboratories USING btree (laboratory_id);


--
-- TOC entry 5518 (class 1259 OID 19185)
-- Name: idx_acceptance_acts_contract; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_acceptance_acts_contract ON public.acceptance_acts USING btree (contract_id);


--
-- TOC entry 5519 (class 1259 OID 19187)
-- Name: idx_acceptance_acts_work_deadline; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_acceptance_acts_work_deadline ON public.acceptance_acts USING btree (work_deadline);


--
-- TOC entry 5520 (class 1259 OID 19186)
-- Name: idx_acceptance_acts_work_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_acceptance_acts_work_status ON public.acceptance_acts USING btree (work_status);


--
-- TOC entry 5506 (class 1259 OID 18935)
-- Name: idx_audit_log_entity; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_audit_log_entity ON public.audit_log USING btree (entity_type, entity_id);


--
-- TOC entry 5507 (class 1259 OID 18937)
-- Name: idx_audit_log_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_audit_log_timestamp ON public.audit_log USING btree ("timestamp" DESC);


--
-- TOC entry 5508 (class 1259 OID 18938)
-- Name: idx_audit_log_type_time; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_audit_log_type_time ON public.audit_log USING btree (entity_type, "timestamp" DESC);


--
-- TOC entry 5509 (class 1259 OID 18936)
-- Name: idx_audit_log_user; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_audit_log_user ON public.audit_log USING btree (user_id);


--
-- TOC entry 5510 (class 1259 OID 18939)
-- Name: idx_audit_log_user_time; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_audit_log_user_time ON public.audit_log USING btree (user_id, "timestamp" DESC);


--
-- TOC entry 5412 (class 1259 OID 18130)
-- Name: idx_climate_log_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_climate_log_date ON public.climate_log USING btree (measured_at);


--
-- TOC entry 5413 (class 1259 OID 18129)
-- Name: idx_climate_log_laboratory; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_climate_log_laboratory ON public.climate_log USING btree (laboratory_id);


--
-- TOC entry 5320 (class 1259 OID 18121)
-- Name: idx_contracts_client; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_contracts_client ON public.contracts USING btree (client_id);


--
-- TOC entry 5321 (class 1259 OID 18122)
-- Name: idx_contracts_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_contracts_status ON public.contracts USING btree (status);


--
-- TOC entry 5340 (class 1259 OID 18123)
-- Name: idx_equipment_laboratory; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_equipment_laboratory ON public.equipment USING btree (laboratory_id);


--
-- TOC entry 5349 (class 1259 OID 18127)
-- Name: idx_equipment_maintenance_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_equipment_maintenance_date ON public.equipment_maintenance USING btree (maintenance_date);


--
-- TOC entry 5350 (class 1259 OID 18126)
-- Name: idx_equipment_maintenance_equipment; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_equipment_maintenance_equipment ON public.equipment_maintenance USING btree (equipment_id);


--
-- TOC entry 5351 (class 1259 OID 18128)
-- Name: idx_equipment_maintenance_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_equipment_maintenance_type ON public.equipment_maintenance USING btree (maintenance_type);


--
-- TOC entry 5341 (class 1259 OID 18125)
-- Name: idx_equipment_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_equipment_status ON public.equipment USING btree (status);


--
-- TOC entry 5342 (class 1259 OID 18124)
-- Name: idx_equipment_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_equipment_type ON public.equipment USING btree (equipment_type);


--
-- TOC entry 5529 (class 1259 OID 19447)
-- Name: idx_files_act; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_files_act ON public.files USING btree (acceptance_act_id) WHERE (acceptance_act_id IS NOT NULL);


--
-- TOC entry 5530 (class 1259 OID 19453)
-- Name: idx_files_active; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_files_active ON public.files USING btree (is_deleted, current_version) WHERE ((is_deleted = false) AND (current_version = true));


--
-- TOC entry 5531 (class 1259 OID 19452)
-- Name: idx_files_category; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_files_category ON public.files USING btree (category);


--
-- TOC entry 5532 (class 1259 OID 19448)
-- Name: idx_files_contract; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_files_contract ON public.files USING btree (contract_id) WHERE (contract_id IS NOT NULL);


--
-- TOC entry 5533 (class 1259 OID 19449)
-- Name: idx_files_equipment; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_files_equipment ON public.files USING btree (equipment_id) WHERE (equipment_id IS NOT NULL);


--
-- TOC entry 5534 (class 1259 OID 19451)
-- Name: idx_files_owner; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_files_owner ON public.files USING btree (owner_id) WHERE (owner_id IS NOT NULL);


--
-- TOC entry 5535 (class 1259 OID 19454)
-- Name: idx_files_replaces; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_files_replaces ON public.files USING btree (replaces_id) WHERE (replaces_id IS NOT NULL);


--
-- TOC entry 5536 (class 1259 OID 19446)
-- Name: idx_files_sample; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_files_sample ON public.files USING btree (sample_id) WHERE (sample_id IS NOT NULL);


--
-- TOC entry 5537 (class 1259 OID 19450)
-- Name: idx_files_standard; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_files_standard ON public.files USING btree (standard_id) WHERE (standard_id IS NOT NULL);


--
-- TOC entry 5550 (class 1259 OID 19538)
-- Name: idx_parameters_category; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_parameters_category ON public.parameters USING btree (category) WHERE (is_active = true);


--
-- TOC entry 5551 (class 1259 OID 19539)
-- Name: idx_parameters_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_parameters_name ON public.parameters USING btree (name);


--
-- TOC entry 5511 (class 1259 OID 19057)
-- Name: idx_role_lab_access_lookup; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_role_lab_access_lookup ON public.role_laboratory_access USING btree (role, journal_id);


--
-- TOC entry 5398 (class 1259 OID 18133)
-- Name: idx_role_permissions_role; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_role_permissions_role ON public.role_permissions USING btree (role);


--
-- TOC entry 5486 (class 1259 OID 18863)
-- Name: idx_sae_equipment; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sae_equipment ON public.sample_auxiliary_equipment USING btree (equipment_id);


--
-- TOC entry 5487 (class 1259 OID 18862)
-- Name: idx_sae_sample; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sae_sample ON public.sample_auxiliary_equipment USING btree (sample_id);


--
-- TOC entry 5456 (class 1259 OID 18646)
-- Name: idx_sample_manufacturing_mi_equipment; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sample_manufacturing_mi_equipment ON public.sample_manufacturing_measuring_instruments USING btree (equipment_id);


--
-- TOC entry 5457 (class 1259 OID 18645)
-- Name: idx_sample_manufacturing_mi_sample; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sample_manufacturing_mi_sample ON public.sample_manufacturing_measuring_instruments USING btree (sample_id);


--
-- TOC entry 5468 (class 1259 OID 18649)
-- Name: idx_sample_manufacturing_op_sample; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sample_manufacturing_op_sample ON public.sample_manufacturing_operators USING btree (sample_id);


--
-- TOC entry 5469 (class 1259 OID 18650)
-- Name: idx_sample_manufacturing_op_user; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sample_manufacturing_op_user ON public.sample_manufacturing_operators USING btree (user_id);


--
-- TOC entry 5462 (class 1259 OID 18648)
-- Name: idx_sample_manufacturing_te_equipment; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sample_manufacturing_te_equipment ON public.sample_manufacturing_testing_equipment USING btree (equipment_id);


--
-- TOC entry 5463 (class 1259 OID 18647)
-- Name: idx_sample_manufacturing_te_sample; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sample_manufacturing_te_sample ON public.sample_manufacturing_testing_equipment USING btree (sample_id);


--
-- TOC entry 5562 (class 1259 OID 19616)
-- Name: idx_sample_params_sample; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sample_params_sample ON public.sample_parameters USING btree (sample_id);


--
-- TOC entry 5563 (class 1259 OID 19618)
-- Name: idx_sample_params_selected; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sample_params_selected ON public.sample_parameters USING btree (sample_id) WHERE (is_selected = true);


--
-- TOC entry 5564 (class 1259 OID 19617)
-- Name: idx_sample_params_std_param; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sample_params_std_param ON public.sample_parameters USING btree (standard_parameter_id) WHERE (standard_parameter_id IS NOT NULL);


--
-- TOC entry 5498 (class 1259 OID 18911)
-- Name: idx_sample_standards_sample; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sample_standards_sample ON public.sample_standards USING btree (sample_id);


--
-- TOC entry 5499 (class 1259 OID 18912)
-- Name: idx_sample_standards_standard; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sample_standards_standard ON public.sample_standards USING btree (standard_id);


--
-- TOC entry 5358 (class 1259 OID 19217)
-- Name: idx_samples_acceptance_act; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_acceptance_act ON public.samples USING btree (acceptance_act_id);


--
-- TOC entry 5359 (class 1259 OID 18115)
-- Name: idx_samples_cipher; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_cipher ON public.samples USING btree (cipher);


--
-- TOC entry 5360 (class 1259 OID 18119)
-- Name: idx_samples_client; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_client ON public.samples USING btree (client_id);


--
-- TOC entry 5361 (class 1259 OID 18405)
-- Name: idx_samples_conditioning_start_datetime; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_conditioning_start_datetime ON public.samples USING btree (conditioning_start_datetime);


--
-- TOC entry 5362 (class 1259 OID 18961)
-- Name: idx_samples_cutting_standard_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_cutting_standard_id ON public.samples USING btree (cutting_standard_id);


--
-- TOC entry 5363 (class 1259 OID 18117)
-- Name: idx_samples_deadline; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_deadline ON public.samples USING btree (deadline);


--
-- TOC entry 5364 (class 1259 OID 18118)
-- Name: idx_samples_laboratory; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_laboratory ON public.samples USING btree (laboratory_id);


--
-- TOC entry 5365 (class 1259 OID 18657)
-- Name: idx_samples_manufacturing; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_manufacturing ON public.samples USING btree (manufacturing) WHERE (manufacturing = true);


--
-- TOC entry 6070 (class 0 OID 0)
-- Dependencies: 5365
-- Name: INDEX idx_samples_manufacturing; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON INDEX public.idx_samples_manufacturing IS 'Индекс для журнала мастерской';


--
-- TOC entry 5366 (class 1259 OID 18643)
-- Name: idx_samples_manufacturing_completion_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_manufacturing_completion_date ON public.samples USING btree (manufacturing_completion_date) WHERE (manufacturing_completion_date IS NOT NULL);


--
-- TOC entry 5367 (class 1259 OID 18947)
-- Name: idx_samples_moisture_sample_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_moisture_sample_id ON public.samples USING btree (moisture_sample_id) WHERE (moisture_sample_id IS NOT NULL);


--
-- TOC entry 5368 (class 1259 OID 18397)
-- Name: idx_samples_protocol_checked_by; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_protocol_checked_by ON public.samples USING btree (protocol_checked_by);


--
-- TOC entry 5369 (class 1259 OID 18950)
-- Name: idx_samples_qms_check; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_qms_check ON public.samples USING btree (status) WHERE ((status)::text = ANY (ARRAY[('DRAFT_READY'::character varying)::text, ('RESULTS_UPLOADED'::character varying)::text]));


--
-- TOC entry 5370 (class 1259 OID 18389)
-- Name: idx_samples_registered_by_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_registered_by_id ON public.samples USING btree (registered_by_id);


--
-- TOC entry 5371 (class 1259 OID 18120)
-- Name: idx_samples_registration_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_registration_date ON public.samples USING btree (registration_date);


--
-- TOC entry 5372 (class 1259 OID 18949)
-- Name: idx_samples_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_status ON public.samples USING btree (status);


--
-- TOC entry 5373 (class 1259 OID 18466)
-- Name: idx_samples_testing_end_datetime; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_testing_end_datetime ON public.samples USING btree (testing_end_datetime);


--
-- TOC entry 5374 (class 1259 OID 18388)
-- Name: idx_samples_verified_by; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_verified_by ON public.samples USING btree (verified_by);


--
-- TOC entry 5375 (class 1259 OID 18661)
-- Name: idx_samples_workshop_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_samples_workshop_status ON public.samples USING btree (workshop_status) WHERE (workshop_status IS NOT NULL);


--
-- TOC entry 6071 (class 0 OID 0)
-- Dependencies: 5375
-- Name: INDEX idx_samples_workshop_status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON INDEX public.idx_samples_workshop_status IS 'Индекс для быстрой фильтрации образцов мастерской в журнале';


--
-- TOC entry 5480 (class 1259 OID 18839)
-- Name: idx_smae_equipment; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_smae_equipment ON public.sample_manufacturing_auxiliary_equipment USING btree (equipment_id);


--
-- TOC entry 5481 (class 1259 OID 18838)
-- Name: idx_smae_sample; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_smae_sample ON public.sample_manufacturing_auxiliary_equipment USING btree (sample_id);


--
-- TOC entry 5492 (class 1259 OID 18888)
-- Name: idx_standard_laboratories_laboratory; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_standard_laboratories_laboratory ON public.standard_laboratories USING btree (laboratory_id);


--
-- TOC entry 5493 (class 1259 OID 18887)
-- Name: idx_standard_laboratories_standard; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_standard_laboratories_standard ON public.standard_laboratories USING btree (standard_id);


--
-- TOC entry 5556 (class 1259 OID 19580)
-- Name: idx_std_params_parameter; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_std_params_parameter ON public.standard_parameters USING btree (parameter_id);


--
-- TOC entry 5557 (class 1259 OID 19579)
-- Name: idx_std_params_standard; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_std_params_standard ON public.standard_parameters USING btree (standard_id) WHERE (is_active = true);


--
-- TOC entry 5474 (class 1259 OID 18707)
-- Name: idx_ual_laboratory_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ual_laboratory_id ON public.user_additional_laboratories USING btree (laboratory_id);


--
-- TOC entry 5475 (class 1259 OID 18706)
-- Name: idx_ual_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ual_user_id ON public.user_additional_laboratories USING btree (user_id);


--
-- TOC entry 5403 (class 1259 OID 18134)
-- Name: idx_user_permissions_user; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_permissions_user ON public.user_permissions_override USING btree (user_id);


--
-- TOC entry 5352 (class 1259 OID 18683)
-- Name: idx_users_is_trainee; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_is_trainee ON public.users USING btree (is_trainee) WHERE (is_trainee = true);


--
-- TOC entry 5353 (class 1259 OID 18682)
-- Name: idx_users_mentor_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_mentor_id ON public.users USING btree (mentor_id) WHERE (mentor_id IS NOT NULL);


--
-- TOC entry 5414 (class 1259 OID 18132)
-- Name: idx_weight_log_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_weight_log_date ON public.weight_log USING btree (measured_at);


--
-- TOC entry 5415 (class 1259 OID 18131)
-- Name: idx_weight_log_sample; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_weight_log_sample ON public.weight_log USING btree (sample_id);


--
-- TOC entry 5514 (class 1259 OID 19056)
-- Name: uq_role_lab_access_all; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_role_lab_access_all ON public.role_laboratory_access USING btree (role, journal_id) WHERE (laboratory_id IS NULL);


--
-- TOC entry 5515 (class 1259 OID 19055)
-- Name: uq_role_lab_access_specific; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_role_lab_access_specific ON public.role_laboratory_access USING btree (role, journal_id, laboratory_id) WHERE (laboratory_id IS NOT NULL);


--
-- TOC entry 5665 (class 2620 OID 18307)
-- Name: users block_user_delete; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER block_user_delete BEFORE DELETE ON public.users FOR EACH ROW EXECUTE FUNCTION public.prevent_user_deletion();


--
-- TOC entry 5647 (class 2606 OID 19200)
-- Name: acceptance_act_laboratories acceptance_act_laboratories_act_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.acceptance_act_laboratories
    ADD CONSTRAINT acceptance_act_laboratories_act_id_fkey FOREIGN KEY (act_id) REFERENCES public.acceptance_acts(id) ON DELETE CASCADE;


--
-- TOC entry 5648 (class 2606 OID 19205)
-- Name: acceptance_act_laboratories acceptance_act_laboratories_laboratory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.acceptance_act_laboratories
    ADD CONSTRAINT acceptance_act_laboratories_laboratory_id_fkey FOREIGN KEY (laboratory_id) REFERENCES public.laboratories(id) ON DELETE RESTRICT;


--
-- TOC entry 5645 (class 2606 OID 19175)
-- Name: acceptance_acts acceptance_acts_contract_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.acceptance_acts
    ADD CONSTRAINT acceptance_acts_contract_id_fkey FOREIGN KEY (contract_id) REFERENCES public.contracts(id) ON DELETE RESTRICT;


--
-- TOC entry 5646 (class 2606 OID 19180)
-- Name: acceptance_acts acceptance_acts_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.acceptance_acts
    ADD CONSTRAINT acceptance_acts_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- TOC entry 5642 (class 2606 OID 18930)
-- Name: audit_log audit_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- TOC entry 5624 (class 2606 OID 18253)
-- Name: auth_group_permissions auth_group_permissio_permission_id_84c5c92e_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissio_permission_id_84c5c92e_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 5625 (class 2606 OID 18248)
-- Name: auth_group_permissions auth_group_permissions_group_id_b120cbf9_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_b120cbf9_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 5623 (class 2606 OID 18239)
-- Name: auth_permission auth_permission_content_type_id_2f476e4b_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_2f476e4b_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 5570 (class 2606 OID 17477)
-- Name: client_contacts client_contacts_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.client_contacts
    ADD CONSTRAINT client_contacts_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- TOC entry 5609 (class 2606 OID 18010)
-- Name: climate_log climate_log_laboratory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.climate_log
    ADD CONSTRAINT climate_log_laboratory_id_fkey FOREIGN KEY (laboratory_id) REFERENCES public.laboratories(id) ON DELETE RESTRICT;


--
-- TOC entry 5610 (class 2606 OID 18015)
-- Name: climate_log climate_log_measured_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.climate_log
    ADD CONSTRAINT climate_log_measured_by_id_fkey FOREIGN KEY (measured_by_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- TOC entry 5571 (class 2606 OID 17500)
-- Name: contracts contracts_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT contracts_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- TOC entry 5621 (class 2606 OID 18196)
-- Name: django_admin_log django_admin_log_content_type_id_c4bce8eb_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_content_type_id_c4bce8eb_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 5622 (class 2606 OID 18201)
-- Name: django_admin_log django_admin_log_user_id_c564eba6_fk_users_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_user_id_c564eba6_fk_users_id FOREIGN KEY (user_id) REFERENCES public.users(id) DEFERRABLE INITIALLY DEFERRED;


--
-- TOC entry 5577 (class 2606 OID 17636)
-- Name: equipment_accreditation_areas equipment_accreditation_areas_accreditation_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipment_accreditation_areas
    ADD CONSTRAINT equipment_accreditation_areas_accreditation_area_id_fkey FOREIGN KEY (accreditation_area_id) REFERENCES public.accreditation_areas(id) ON DELETE CASCADE;


--
-- TOC entry 5578 (class 2606 OID 17631)
-- Name: equipment_accreditation_areas equipment_accreditation_areas_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipment_accreditation_areas
    ADD CONSTRAINT equipment_accreditation_areas_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE CASCADE;


--
-- TOC entry 5574 (class 2606 OID 17614)
-- Name: equipment equipment_laboratory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipment
    ADD CONSTRAINT equipment_laboratory_id_fkey FOREIGN KEY (laboratory_id) REFERENCES public.laboratories(id) ON DELETE RESTRICT;


--
-- TOC entry 5579 (class 2606 OID 17658)
-- Name: equipment_maintenance equipment_maintenance_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipment_maintenance
    ADD CONSTRAINT equipment_maintenance_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE CASCADE;


--
-- TOC entry 5580 (class 2606 OID 17709)
-- Name: equipment_maintenance equipment_maintenance_performed_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipment_maintenance
    ADD CONSTRAINT equipment_maintenance_performed_by_id_fkey FOREIGN KEY (performed_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- TOC entry 5575 (class 2606 OID 17699)
-- Name: equipment equipment_responsible_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipment
    ADD CONSTRAINT equipment_responsible_person_id_fkey FOREIGN KEY (responsible_person_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- TOC entry 5576 (class 2606 OID 17704)
-- Name: equipment equipment_substitute_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipment
    ADD CONSTRAINT equipment_substitute_person_id_fkey FOREIGN KEY (substitute_person_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- TOC entry 5649 (class 2606 OID 19406)
-- Name: files files_acceptance_act_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_acceptance_act_id_fkey FOREIGN KEY (acceptance_act_id) REFERENCES public.acceptance_acts(id) ON DELETE SET NULL;


--
-- TOC entry 5650 (class 2606 OID 19411)
-- Name: files files_contract_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_contract_id_fkey FOREIGN KEY (contract_id) REFERENCES public.contracts(id) ON DELETE SET NULL;


--
-- TOC entry 5651 (class 2606 OID 19441)
-- Name: files files_deleted_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_deleted_by_id_fkey FOREIGN KEY (deleted_by_id) REFERENCES public.users(id);


--
-- TOC entry 5652 (class 2606 OID 19416)
-- Name: files files_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE SET NULL;


--
-- TOC entry 5653 (class 2606 OID 19426)
-- Name: files files_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- TOC entry 5654 (class 2606 OID 19431)
-- Name: files files_replaces_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_replaces_id_fkey FOREIGN KEY (replaces_id) REFERENCES public.files(id) ON DELETE SET NULL;


--
-- TOC entry 5655 (class 2606 OID 19401)
-- Name: files files_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE SET NULL;


--
-- TOC entry 5656 (class 2606 OID 19421)
-- Name: files files_standard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_standard_id_fkey FOREIGN KEY (standard_id) REFERENCES public.standards(id) ON DELETE SET NULL;


--
-- TOC entry 5657 (class 2606 OID 19436)
-- Name: files files_uploaded_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_uploaded_by_id_fkey FOREIGN KEY (uploaded_by_id) REFERENCES public.users(id);


--
-- TOC entry 5632 (class 2606 OID 18701)
-- Name: user_additional_laboratories fk_ual_laboratory; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_additional_laboratories
    ADD CONSTRAINT fk_ual_laboratory FOREIGN KEY (laboratory_id) REFERENCES public.laboratories(id) ON DELETE CASCADE;


--
-- TOC entry 5633 (class 2606 OID 18696)
-- Name: user_additional_laboratories fk_ual_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_additional_laboratories
    ADD CONSTRAINT fk_ual_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- TOC entry 5581 (class 2606 OID 18677)
-- Name: users fk_users_mentor; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_mentor FOREIGN KEY (mentor_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- TOC entry 5598 (class 2606 OID 17887)
-- Name: journal_columns journal_columns_journal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.journal_columns
    ADD CONSTRAINT journal_columns_journal_id_fkey FOREIGN KEY (journal_id) REFERENCES public.journals(id) ON DELETE CASCADE;


--
-- TOC entry 5569 (class 2606 OID 17694)
-- Name: laboratories laboratories_head_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.laboratories
    ADD CONSTRAINT laboratories_head_id_fkey FOREIGN KEY (head_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- TOC entry 5605 (class 2606 OID 17974)
-- Name: permissions_log permissions_log_changed_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.permissions_log
    ADD CONSTRAINT permissions_log_changed_by_id_fkey FOREIGN KEY (changed_by_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- TOC entry 5606 (class 2606 OID 17989)
-- Name: permissions_log permissions_log_column_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.permissions_log
    ADD CONSTRAINT permissions_log_column_id_fkey FOREIGN KEY (column_id) REFERENCES public.journal_columns(id) ON DELETE CASCADE;


--
-- TOC entry 5607 (class 2606 OID 17984)
-- Name: permissions_log permissions_log_journal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.permissions_log
    ADD CONSTRAINT permissions_log_journal_id_fkey FOREIGN KEY (journal_id) REFERENCES public.journals(id) ON DELETE CASCADE;


--
-- TOC entry 5608 (class 2606 OID 17979)
-- Name: permissions_log permissions_log_target_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.permissions_log
    ADD CONSTRAINT permissions_log_target_user_id_fkey FOREIGN KEY (target_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- TOC entry 5658 (class 2606 OID 19507)
-- Name: personal_folder_access personal_folder_access_granted_to_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.personal_folder_access
    ADD CONSTRAINT personal_folder_access_granted_to_id_fkey FOREIGN KEY (granted_to_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- TOC entry 5659 (class 2606 OID 19502)
-- Name: personal_folder_access personal_folder_access_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.personal_folder_access
    ADD CONSTRAINT personal_folder_access_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- TOC entry 5643 (class 2606 OID 19045)
-- Name: role_laboratory_access role_laboratory_access_journal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.role_laboratory_access
    ADD CONSTRAINT role_laboratory_access_journal_id_fkey FOREIGN KEY (journal_id) REFERENCES public.journals(id) ON DELETE CASCADE;


--
-- TOC entry 5644 (class 2606 OID 19050)
-- Name: role_laboratory_access role_laboratory_access_laboratory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.role_laboratory_access
    ADD CONSTRAINT role_laboratory_access_laboratory_id_fkey FOREIGN KEY (laboratory_id) REFERENCES public.laboratories(id) ON DELETE CASCADE;


--
-- TOC entry 5599 (class 2606 OID 17911)
-- Name: role_permissions role_permissions_column_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_column_id_fkey FOREIGN KEY (column_id) REFERENCES public.journal_columns(id) ON DELETE CASCADE;


--
-- TOC entry 5600 (class 2606 OID 17906)
-- Name: role_permissions role_permissions_journal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_journal_id_fkey FOREIGN KEY (journal_id) REFERENCES public.journals(id) ON DELETE CASCADE;


--
-- TOC entry 5636 (class 2606 OID 18857)
-- Name: sample_auxiliary_equipment sample_auxiliary_equipment_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_auxiliary_equipment
    ADD CONSTRAINT sample_auxiliary_equipment_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE RESTRICT;


--
-- TOC entry 5637 (class 2606 OID 18852)
-- Name: sample_auxiliary_equipment sample_auxiliary_equipment_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_auxiliary_equipment
    ADD CONSTRAINT sample_auxiliary_equipment_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- TOC entry 5634 (class 2606 OID 18833)
-- Name: sample_manufacturing_auxiliary_equipment sample_manufacturing_auxiliary_equipment_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_auxiliary_equipment
    ADD CONSTRAINT sample_manufacturing_auxiliary_equipment_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE RESTRICT;


--
-- TOC entry 5635 (class 2606 OID 18828)
-- Name: sample_manufacturing_auxiliary_equipment sample_manufacturing_auxiliary_equipment_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_auxiliary_equipment
    ADD CONSTRAINT sample_manufacturing_auxiliary_equipment_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- TOC entry 5626 (class 2606 OID 18592)
-- Name: sample_manufacturing_measuring_instruments sample_manufacturing_measuring_instruments_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_measuring_instruments
    ADD CONSTRAINT sample_manufacturing_measuring_instruments_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE RESTRICT;


--
-- TOC entry 5627 (class 2606 OID 18587)
-- Name: sample_manufacturing_measuring_instruments sample_manufacturing_measuring_instruments_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_measuring_instruments
    ADD CONSTRAINT sample_manufacturing_measuring_instruments_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- TOC entry 5630 (class 2606 OID 18631)
-- Name: sample_manufacturing_operators sample_manufacturing_operators_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_operators
    ADD CONSTRAINT sample_manufacturing_operators_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- TOC entry 5631 (class 2606 OID 18636)
-- Name: sample_manufacturing_operators sample_manufacturing_operators_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_operators
    ADD CONSTRAINT sample_manufacturing_operators_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- TOC entry 5628 (class 2606 OID 18614)
-- Name: sample_manufacturing_testing_equipment sample_manufacturing_testing_equipment_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_testing_equipment
    ADD CONSTRAINT sample_manufacturing_testing_equipment_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE RESTRICT;


--
-- TOC entry 5629 (class 2606 OID 18609)
-- Name: sample_manufacturing_testing_equipment sample_manufacturing_testing_equipment_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_manufacturing_testing_equipment
    ADD CONSTRAINT sample_manufacturing_testing_equipment_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- TOC entry 5594 (class 2606 OID 17832)
-- Name: sample_measuring_instruments sample_measuring_instruments_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_measuring_instruments
    ADD CONSTRAINT sample_measuring_instruments_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE RESTRICT;


--
-- TOC entry 5595 (class 2606 OID 17827)
-- Name: sample_measuring_instruments sample_measuring_instruments_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_measuring_instruments
    ADD CONSTRAINT sample_measuring_instruments_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- TOC entry 5619 (class 2606 OID 18147)
-- Name: sample_operators sample_operators_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_operators
    ADD CONSTRAINT sample_operators_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- TOC entry 5620 (class 2606 OID 18152)
-- Name: sample_operators sample_operators_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_operators
    ADD CONSTRAINT sample_operators_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- TOC entry 5662 (class 2606 OID 19601)
-- Name: sample_parameters sample_parameters_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_parameters
    ADD CONSTRAINT sample_parameters_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- TOC entry 5663 (class 2606 OID 19606)
-- Name: sample_parameters sample_parameters_standard_parameter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_parameters
    ADD CONSTRAINT sample_parameters_standard_parameter_id_fkey FOREIGN KEY (standard_parameter_id) REFERENCES public.standard_parameters(id) ON DELETE SET NULL;


--
-- TOC entry 5664 (class 2606 OID 19611)
-- Name: sample_parameters sample_parameters_tested_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_parameters
    ADD CONSTRAINT sample_parameters_tested_by_id_fkey FOREIGN KEY (tested_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- TOC entry 5640 (class 2606 OID 18901)
-- Name: sample_standards sample_standards_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_standards
    ADD CONSTRAINT sample_standards_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- TOC entry 5641 (class 2606 OID 18906)
-- Name: sample_standards sample_standards_standard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_standards
    ADD CONSTRAINT sample_standards_standard_id_fkey FOREIGN KEY (standard_id) REFERENCES public.standards(id) ON DELETE RESTRICT;


--
-- TOC entry 5596 (class 2606 OID 17854)
-- Name: sample_testing_equipment sample_testing_equipment_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_testing_equipment
    ADD CONSTRAINT sample_testing_equipment_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE RESTRICT;


--
-- TOC entry 5597 (class 2606 OID 17849)
-- Name: sample_testing_equipment sample_testing_equipment_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sample_testing_equipment
    ADD CONSTRAINT sample_testing_equipment_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- TOC entry 5583 (class 2606 OID 19212)
-- Name: samples samples_acceptance_act_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_acceptance_act_id_fkey FOREIGN KEY (acceptance_act_id) REFERENCES public.acceptance_acts(id) ON DELETE SET NULL;


--
-- TOC entry 5584 (class 2606 OID 17785)
-- Name: samples samples_accreditation_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_accreditation_area_id_fkey FOREIGN KEY (accreditation_area_id) REFERENCES public.accreditation_areas(id) ON DELETE RESTRICT;


--
-- TOC entry 5585 (class 2606 OID 17770)
-- Name: samples samples_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE RESTRICT;


--
-- TOC entry 5586 (class 2606 OID 17775)
-- Name: samples samples_contract_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_contract_id_fkey FOREIGN KEY (contract_id) REFERENCES public.contracts(id) ON DELETE RESTRICT;


--
-- TOC entry 5587 (class 2606 OID 18956)
-- Name: samples samples_cutting_standard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_cutting_standard_id_fkey FOREIGN KEY (cutting_standard_id) REFERENCES public.standards(id) ON DELETE SET NULL;


--
-- TOC entry 5588 (class 2606 OID 17780)
-- Name: samples samples_laboratory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_laboratory_id_fkey FOREIGN KEY (laboratory_id) REFERENCES public.laboratories(id) ON DELETE RESTRICT;


--
-- TOC entry 5589 (class 2606 OID 18942)
-- Name: samples samples_moisture_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_moisture_sample_id_fkey FOREIGN KEY (moisture_sample_id) REFERENCES public.samples(id) ON DELETE SET NULL;


--
-- TOC entry 5590 (class 2606 OID 18391)
-- Name: samples samples_protocol_checked_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_protocol_checked_by_fkey FOREIGN KEY (protocol_checked_by) REFERENCES public.users(id);


--
-- TOC entry 5591 (class 2606 OID 17795)
-- Name: samples samples_registered_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_registered_by_id_fkey FOREIGN KEY (registered_by_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- TOC entry 5592 (class 2606 OID 17805)
-- Name: samples samples_report_prepared_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_report_prepared_by_id_fkey FOREIGN KEY (report_prepared_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- TOC entry 5593 (class 2606 OID 18383)
-- Name: samples samples_verified_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.samples
    ADD CONSTRAINT samples_verified_by_fkey FOREIGN KEY (verified_by) REFERENCES public.users(id);


--
-- TOC entry 5572 (class 2606 OID 17554)
-- Name: standard_accreditation_areas standard_accreditation_areas_accreditation_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standard_accreditation_areas
    ADD CONSTRAINT standard_accreditation_areas_accreditation_area_id_fkey FOREIGN KEY (accreditation_area_id) REFERENCES public.accreditation_areas(id) ON DELETE CASCADE;


--
-- TOC entry 5573 (class 2606 OID 17549)
-- Name: standard_accreditation_areas standard_accreditation_areas_standard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standard_accreditation_areas
    ADD CONSTRAINT standard_accreditation_areas_standard_id_fkey FOREIGN KEY (standard_id) REFERENCES public.standards(id) ON DELETE CASCADE;


--
-- TOC entry 5638 (class 2606 OID 18882)
-- Name: standard_laboratories standard_laboratories_laboratory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standard_laboratories
    ADD CONSTRAINT standard_laboratories_laboratory_id_fkey FOREIGN KEY (laboratory_id) REFERENCES public.laboratories(id) ON DELETE CASCADE;


--
-- TOC entry 5639 (class 2606 OID 18877)
-- Name: standard_laboratories standard_laboratories_standard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standard_laboratories
    ADD CONSTRAINT standard_laboratories_standard_id_fkey FOREIGN KEY (standard_id) REFERENCES public.standards(id) ON DELETE CASCADE;


--
-- TOC entry 5660 (class 2606 OID 19574)
-- Name: standard_parameters standard_parameters_parameter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standard_parameters
    ADD CONSTRAINT standard_parameters_parameter_id_fkey FOREIGN KEY (parameter_id) REFERENCES public.parameters(id) ON DELETE CASCADE;


--
-- TOC entry 5661 (class 2606 OID 19569)
-- Name: standard_parameters standard_parameters_standard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.standard_parameters
    ADD CONSTRAINT standard_parameters_standard_id_fkey FOREIGN KEY (standard_id) REFERENCES public.standards(id) ON DELETE CASCADE;


--
-- TOC entry 5617 (class 2606 OID 18104)
-- Name: time_log time_log_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.time_log
    ADD CONSTRAINT time_log_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- TOC entry 5618 (class 2606 OID 18109)
-- Name: time_log time_log_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.time_log
    ADD CONSTRAINT time_log_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE SET NULL;


--
-- TOC entry 5601 (class 2606 OID 17946)
-- Name: user_permissions_override user_permissions_override_column_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_permissions_override
    ADD CONSTRAINT user_permissions_override_column_id_fkey FOREIGN KEY (column_id) REFERENCES public.journal_columns(id) ON DELETE CASCADE;


--
-- TOC entry 5602 (class 2606 OID 17951)
-- Name: user_permissions_override user_permissions_override_granted_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_permissions_override
    ADD CONSTRAINT user_permissions_override_granted_by_id_fkey FOREIGN KEY (granted_by_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- TOC entry 5603 (class 2606 OID 17941)
-- Name: user_permissions_override user_permissions_override_journal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_permissions_override
    ADD CONSTRAINT user_permissions_override_journal_id_fkey FOREIGN KEY (journal_id) REFERENCES public.journals(id) ON DELETE CASCADE;


--
-- TOC entry 5604 (class 2606 OID 17936)
-- Name: user_permissions_override user_permissions_override_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_permissions_override
    ADD CONSTRAINT user_permissions_override_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- TOC entry 5582 (class 2606 OID 17688)
-- Name: users users_laboratory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_laboratory_id_fkey FOREIGN KEY (laboratory_id) REFERENCES public.laboratories(id) ON DELETE SET NULL;


--
-- TOC entry 5611 (class 2606 OID 18048)
-- Name: weight_log weight_log_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.weight_log
    ADD CONSTRAINT weight_log_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE RESTRICT;


--
-- TOC entry 5612 (class 2606 OID 18043)
-- Name: weight_log weight_log_measured_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.weight_log
    ADD CONSTRAINT weight_log_measured_by_id_fkey FOREIGN KEY (measured_by_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- TOC entry 5613 (class 2606 OID 18038)
-- Name: weight_log weight_log_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.weight_log
    ADD CONSTRAINT weight_log_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


--
-- TOC entry 5614 (class 2606 OID 18083)
-- Name: workshop_log workshop_log_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workshop_log
    ADD CONSTRAINT workshop_log_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(id) ON DELETE RESTRICT;


--
-- TOC entry 5615 (class 2606 OID 18078)
-- Name: workshop_log workshop_log_operator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workshop_log
    ADD CONSTRAINT workshop_log_operator_id_fkey FOREIGN KEY (operator_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- TOC entry 5616 (class 2606 OID 18073)
-- Name: workshop_log workshop_log_sample_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workshop_log
    ADD CONSTRAINT workshop_log_sample_id_fkey FOREIGN KEY (sample_id) REFERENCES public.samples(id) ON DELETE CASCADE;


-- Completed on 2026-03-03 22:57:21

--
-- PostgreSQL database dump complete
--

\unrestrict xLTqrmgdUTzBqiKQpCLTA9eQFcwQAQompVwrEFXmplV7rlkBtGilu5vnfuHdCkm

