-- ============================================================
--   MediCore HMS — Complete MySQL Database Schema
--   Run this file in MySQL Workbench
--   Database: medicore_hms
-- ============================================================

CREATE DATABASE IF NOT EXISTS medicore_hms
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE medicore_hms;

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- 1. ROLES & USERS (Auth)
-- ============================================================

CREATE TABLE IF NOT EXISTS roles (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    uhid             VARCHAR(20) UNIQUE,
    username         VARCHAR(80) NOT NULL UNIQUE,
    email            VARCHAR(120) NOT NULL UNIQUE,
    phone            VARCHAR(20),
    password_hash    VARCHAR(255) NOT NULL,
    role_id          INT NOT NULL,
    first_name       VARCHAR(80),
    last_name        VARCHAR(80),
    gender           ENUM('male','female','other'),
    date_of_birth    DATE,
    profile_photo    VARCHAR(255),
    is_active        TINYINT(1) DEFAULT 1,
    is_verified      TINYINT(1) DEFAULT 0,
    two_fa_enabled   TINYINT(1) DEFAULT 0,
    two_fa_secret    VARCHAR(64),
    login_attempts   INT DEFAULT 0,
    locked_until     DATETIME,
    last_login       DATETIME,
    password_changed DATETIME,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT,
    action      VARCHAR(100) NOT NULL,
    module      VARCHAR(50),
    description TEXT,
    ip_address  VARCHAR(45),
    user_agent  VARCHAR(255),
    old_value   JSON,
    new_value   JSON,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id           VARCHAR(128) PRIMARY KEY,
    user_id      INT NOT NULL,
    ip_address   VARCHAR(45),
    user_agent   VARCHAR(255),
    is_active    TINYINT(1) DEFAULT 1,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at   DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============================================================
-- 2. HOSPITAL SETTINGS
-- ============================================================

CREATE TABLE IF NOT EXISTS hospital_settings (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    setting_key     VARCHAR(100) NOT NULL UNIQUE,
    setting_value   TEXT,
    setting_type    ENUM('text','number','boolean','json') DEFAULT 'text',
    description     VARCHAR(255),
    updated_by      INT,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
);

-- ============================================================
-- 3. DEPARTMENTS & DOCTORS
-- ============================================================

CREATE TABLE IF NOT EXISTS departments (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    head_doctor INT,
    floor       VARCHAR(20),
    phone_ext   VARCHAR(10),
    is_active   TINYINT(1) DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS doctors (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    user_id            INT NOT NULL UNIQUE,
    department_id      INT,
    employee_id        VARCHAR(30) UNIQUE,
    specialization     VARCHAR(150),
    qualification      VARCHAR(255),
    experience_years   INT DEFAULT 0,
    registration_no    VARCHAR(80),
    consultation_fee   DECIMAL(10,2) DEFAULT 0.00,
    bio                TEXT,
    signature_image    VARCHAR(255),
    is_available       TINYINT(1) DEFAULT 1,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS doctor_schedules (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id     INT NOT NULL,
    day_of_week   ENUM('monday','tuesday','wednesday','thursday','friday','saturday','sunday'),
    start_time    TIME NOT NULL,
    end_time      TIME NOT NULL,
    slot_duration INT DEFAULT 15,
    max_patients  INT DEFAULT 20,
    is_active     TINYINT(1) DEFAULT 1,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS doctor_leaves (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id   INT NOT NULL,
    leave_date  DATE NOT NULL,
    reason      VARCHAR(255),
    approved_by INT,
    status      ENUM('pending','approved','rejected') DEFAULT 'pending',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE SET NULL
);

-- ============================================================
-- 4. PATIENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS patients (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    user_id          INT UNIQUE,
    uhid             VARCHAR(20) NOT NULL UNIQUE,
    first_name       VARCHAR(80) NOT NULL,
    last_name        VARCHAR(80) NOT NULL,
    date_of_birth    DATE,
    gender           ENUM('male','female','other'),
    blood_group      ENUM('A+','A-','B+','B-','O+','O-','AB+','AB-','unknown') DEFAULT 'unknown',
    phone            VARCHAR(20),
    emergency_phone  VARCHAR(20),
    email            VARCHAR(120),
    address          TEXT,
    city             VARCHAR(80),
    state            VARCHAR(80),
    pincode          VARCHAR(10),
    nationality      VARCHAR(50) DEFAULT 'Indian',
    marital_status   ENUM('single','married','divorced','widowed','other'),
    occupation       VARCHAR(100),
    religion         VARCHAR(50),
    photo            VARCHAR(255),
    insurance_provider VARCHAR(100),
    insurance_id     VARCHAR(80),
    tpa_name         VARCHAR(100),
    referred_by      VARCHAR(100),
    registration_date DATE DEFAULT (CURRENT_DATE),
    is_active        TINYINT(1) DEFAULT 1,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS patient_allergies (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    patient_id    INT NOT NULL,
    allergen      VARCHAR(100) NOT NULL,
    reaction      VARCHAR(255),
    severity      ENUM('mild','moderate','severe') DEFAULT 'moderate',
    noted_by      INT,
    noted_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (noted_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS patient_chronic_conditions (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    patient_id    INT NOT NULL,
    condition     VARCHAR(150) NOT NULL,
    icd10_code    VARCHAR(20),
    diagnosed_on  DATE,
    notes         TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
);

-- ============================================================
-- 5. APPOINTMENTS & OPD
-- ============================================================

CREATE TABLE IF NOT EXISTS appointments (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    appointment_no   VARCHAR(30) UNIQUE,
    patient_id       INT NOT NULL,
    doctor_id        INT NOT NULL,
    department_id    INT,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    token_number     INT,
    type             ENUM('new','follow_up','emergency','teleconsult') DEFAULT 'new',
    status           ENUM('scheduled','confirmed','checked_in','in_progress','completed','cancelled','no_show') DEFAULT 'scheduled',
    reason           TEXT,
    notes            TEXT,
    booked_by        INT,
    cancelled_by     INT,
    cancel_reason    VARCHAR(255),
    reminder_sent    TINYINT(1) DEFAULT 0,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL,
    FOREIGN KEY (booked_by) REFERENCES users(id) ON DELETE SET NULL
);

-- ============================================================
-- 6. EMR — VISITS, SOAP, VITALS
-- ============================================================

CREATE TABLE IF NOT EXISTS visits (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    visit_no        VARCHAR(30) UNIQUE,
    patient_id      INT NOT NULL,
    doctor_id       INT NOT NULL,
    appointment_id  INT,
    visit_type      ENUM('opd','ipd','emergency','teleconsult') DEFAULT 'opd',
    visit_date      DATETIME DEFAULT CURRENT_TIMESTAMP,
    chief_complaint TEXT,
    status          ENUM('open','closed') DEFAULT 'open',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS soap_notes (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    visit_id        INT NOT NULL,
    subjective      TEXT,
    objective       TEXT,
    assessment      TEXT,
    plan            TEXT,
    icd10_code      VARCHAR(20),
    icd10_desc      VARCHAR(255),
    follow_up_days  INT,
    follow_up_date  DATE,
    written_by      INT NOT NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE CASCADE,
    FOREIGN KEY (written_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS vitals (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    patient_id        INT NOT NULL,
    visit_id          INT,
    systolic_bp       INT,
    diastolic_bp      INT,
    pulse_rate        INT,
    temperature       DECIMAL(4,1),
    temperature_unit  ENUM('C','F') DEFAULT 'F',
    respiratory_rate  INT,
    spo2              INT,
    weight_kg         DECIMAL(5,2),
    height_cm         DECIMAL(5,1),
    bmi               DECIMAL(4,1),
    blood_sugar       DECIMAL(6,1),
    blood_sugar_type  ENUM('fasting','random','pp') DEFAULT 'random',
    notes             TEXT,
    recorded_by       INT,
    recorded_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE SET NULL,
    FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE SET NULL
);

-- ============================================================
-- 7. PRESCRIPTIONS & DRUGS
-- ============================================================

CREATE TABLE IF NOT EXISTS drugs (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    name             VARCHAR(150) NOT NULL,
    generic_name     VARCHAR(150),
    brand_name       VARCHAR(150),
    category         VARCHAR(80),
    drug_type        ENUM('tablet','capsule','syrup','injection','cream','drops','inhaler','other') DEFAULT 'tablet',
    manufacturer     VARCHAR(100),
    unit             VARCHAR(30),
    description      TEXT,
    contraindications TEXT,
    side_effects     TEXT,
    is_active        TINYINT(1) DEFAULT 1,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS drug_interactions (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    drug_id_1   INT NOT NULL,
    drug_id_2   INT NOT NULL,
    severity    ENUM('mild','moderate','severe','contraindicated') DEFAULT 'moderate',
    description TEXT,
    FOREIGN KEY (drug_id_1) REFERENCES drugs(id) ON DELETE CASCADE,
    FOREIGN KEY (drug_id_2) REFERENCES drugs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prescriptions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    prescription_no VARCHAR(30) UNIQUE,
    visit_id        INT NOT NULL,
    patient_id      INT NOT NULL,
    doctor_id       INT NOT_NULL,
    notes           TEXT,
    status          ENUM('active','dispensed','cancelled','partial') DEFAULT 'active',
    dispensed_by    INT,
    dispensed_at    DATETIME,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    FOREIGN KEY (dispensed_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS prescription_items (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    prescription_id  INT NOT NULL,
    drug_id          INT NOT NULL,
    dosage           VARCHAR(50),
    frequency        VARCHAR(80),
    duration         VARCHAR(50),
    quantity         INT DEFAULT 1,
    instructions     TEXT,
    is_dispensed     TINYINT(1) DEFAULT 0,
    FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE,
    FOREIGN KEY (drug_id) REFERENCES drugs(id) ON DELETE CASCADE
);

-- ============================================================
-- 8. PHARMACY & INVENTORY
-- ============================================================

CREATE TABLE IF NOT EXISTS drug_inventory (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    drug_id         INT NOT NULL,
    batch_number    VARCHAR(50),
    quantity        INT DEFAULT 0,
    unit_cost       DECIMAL(10,2) DEFAULT 0.00,
    selling_price   DECIMAL(10,2) DEFAULT 0.00,
    expiry_date     DATE,
    manufacture_date DATE,
    reorder_level   INT DEFAULT 10,
    location        VARCHAR(50),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (drug_id) REFERENCES drugs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS suppliers (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(150) NOT NULL,
    contact_name VARCHAR(100),
    phone        VARCHAR(20),
    email        VARCHAR(120),
    address      TEXT,
    gst_number   VARCHAR(30),
    is_active    TINYINT(1) DEFAULT 1,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    po_number    VARCHAR(30) UNIQUE,
    supplier_id  INT,
    status       ENUM('draft','sent','received','cancelled') DEFAULT 'draft',
    total_amount DECIMAL(12,2) DEFAULT 0.00,
    ordered_by   INT,
    ordered_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    received_at  DATETIME,
    notes        TEXT,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL,
    FOREIGN KEY (ordered_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS purchase_order_items (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    po_id         INT NOT NULL,
    drug_id       INT NOT NULL,
    quantity      INT NOT NULL,
    unit_cost     DECIMAL(10,2),
    total_cost    DECIMAL(12,2),
    received_qty  INT DEFAULT 0,
    FOREIGN KEY (po_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (drug_id) REFERENCES drugs(id) ON DELETE CASCADE
);

-- ============================================================
-- 9. LABORATORY
-- ============================================================

CREATE TABLE IF NOT EXISTS lab_tests (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    code            VARCHAR(30) UNIQUE,
    category        VARCHAR(80),
    sample_type     VARCHAR(80),
    turnaround_hrs  INT DEFAULT 24,
    cost            DECIMAL(10,2) DEFAULT 0.00,
    normal_range    TEXT,
    unit            VARCHAR(30),
    description     TEXT,
    is_active       TINYINT(1) DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lab_orders (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    order_no        VARCHAR(30) UNIQUE,
    patient_id      INT NOT NULL,
    doctor_id       INT NOT NULL,
    visit_id        INT,
    priority        ENUM('routine','urgent','stat') DEFAULT 'routine',
    status          ENUM('ordered','sample_collected','processing','completed','cancelled') DEFAULT 'ordered',
    notes           TEXT,
    ordered_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    sample_collected_at DATETIME,
    completed_at    DATETIME,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS lab_order_items (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    order_id     INT NOT NULL,
    test_id      INT NOT NULL,
    status       ENUM('pending','processing','completed') DEFAULT 'pending',
    result_value VARCHAR(255),
    result_unit  VARCHAR(30),
    normal_range VARCHAR(100),
    is_critical  TINYINT(1) DEFAULT 0,
    flag         ENUM('normal','high','low','critical') DEFAULT 'normal',
    notes        TEXT,
    done_by      INT,
    done_at      DATETIME,
    FOREIGN KEY (order_id) REFERENCES lab_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (test_id) REFERENCES lab_tests(id) ON DELETE CASCADE,
    FOREIGN KEY (done_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS lab_reports (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    order_id     INT NOT NULL UNIQUE,
    patient_id   INT NOT NULL,
    report_path  VARCHAR(255),
    generated_by INT,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    sent_to_patient TINYINT(1) DEFAULT 0,
    sent_at      DATETIME,
    FOREIGN KEY (order_id) REFERENCES lab_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (generated_by) REFERENCES users(id) ON DELETE SET NULL
);

-- ============================================================
-- 10. RADIOLOGY
-- ============================================================

CREATE TABLE IF NOT EXISTS radiology_tests (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    code        VARCHAR(30) UNIQUE,
    category    ENUM('xray','mri','ct','ultrasound','other') DEFAULT 'other',
    cost        DECIMAL(10,2) DEFAULT 0.00,
    description TEXT,
    is_active   TINYINT(1) DEFAULT 1
);

CREATE TABLE IF NOT EXISTS radiology_orders (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    order_no        VARCHAR(30) UNIQUE,
    patient_id      INT NOT NULL,
    doctor_id       INT NOT NULL,
    test_id         INT NOT NULL,
    visit_id        INT,
    priority        ENUM('routine','urgent') DEFAULT 'routine',
    status          ENUM('ordered','in_progress','completed','cancelled') DEFAULT 'ordered',
    findings        TEXT,
    report_path     VARCHAR(255),
    radiologist_id  INT,
    ordered_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at    DATETIME,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    FOREIGN KEY (test_id) REFERENCES radiology_tests(id) ON DELETE CASCADE,
    FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE SET NULL,
    FOREIGN KEY (radiologist_id) REFERENCES users(id) ON DELETE SET NULL
);

-- ============================================================
-- 11. WARDS & BEDS
-- ============================================================

CREATE TABLE IF NOT EXISTS wards (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(80) NOT NULL,
    ward_type     ENUM('general','private','semi_private','icu','nicu','ot','emergency') DEFAULT 'general',
    floor         VARCHAR(20),
    total_beds    INT DEFAULT 0,
    charge_per_day DECIMAL(10,2) DEFAULT 0.00,
    description   TEXT,
    is_active     TINYINT(1) DEFAULT 1,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS beds (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    bed_number  VARCHAR(20) NOT NULL,
    ward_id     INT NOT NULL,
    bed_type    ENUM('standard','electric','icu','nicu') DEFAULT 'standard',
    status      ENUM('available','occupied','cleaning','maintenance','reserved') DEFAULT 'available',
    features    VARCHAR(255),
    is_active   TINYINT(1) DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_bed (bed_number, ward_id),
    FOREIGN KEY (ward_id) REFERENCES wards(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admissions (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    admission_no      VARCHAR(30) UNIQUE,
    patient_id        INT NOT NULL,
    doctor_id         INT NOT NULL,
    bed_id            INT NOT NULL,
    ward_id           INT NOT NULL,
    admission_date    DATETIME DEFAULT CURRENT_TIMESTAMP,
    expected_discharge DATE,
    actual_discharge  DATETIME,
    admission_reason  TEXT,
    diagnosis         TEXT,
    status            ENUM('admitted','discharged','transferred','absconded') DEFAULT 'admitted',
    discharge_summary TEXT,
    admitted_by       INT,
    discharged_by     INT,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    FOREIGN KEY (bed_id) REFERENCES beds(id) ON DELETE RESTRICT,
    FOREIGN KEY (ward_id) REFERENCES wards(id) ON DELETE RESTRICT,
    FOREIGN KEY (admitted_by) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (discharged_by) REFERENCES users(id) ON DELETE SET NULL
);

-- ============================================================
-- 12. OPERATION THEATRE
-- ============================================================

CREATE TABLE IF NOT EXISTS ot_rooms (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(80) NOT NULL,
    room_type   ENUM('major','minor','emergency','cardiac','neuro') DEFAULT 'major',
    floor       VARCHAR(20),
    status      ENUM('available','in_use','cleaning','maintenance') DEFAULT 'available',
    equipment   TEXT,
    is_active   TINYINT(1) DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ot_schedules (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    schedule_no      VARCHAR(30) UNIQUE,
    patient_id       INT NOT NULL,
    surgeon_id       INT NOT NULL,
    anesthetist_id   INT,
    ot_room_id       INT NOT NULL,
    admission_id     INT,
    surgery_name     VARCHAR(200) NOT NULL,
    surgery_type     ENUM('elective','emergency','day_care') DEFAULT 'elective',
    scheduled_date   DATE NOT NULL,
    scheduled_time   TIME NOT NULL,
    duration_mins    INT DEFAULT 60,
    status           ENUM('scheduled','in_progress','completed','postponed','cancelled') DEFAULT 'scheduled',
    pre_op_notes     TEXT,
    post_op_notes    TEXT,
    complications    TEXT,
    actual_start     DATETIME,
    actual_end       DATETIME,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (surgeon_id) REFERENCES doctors(id) ON DELETE CASCADE,
    FOREIGN KEY (anesthetist_id) REFERENCES doctors(id) ON DELETE SET NULL,
    FOREIGN KEY (ot_room_id) REFERENCES ot_rooms(id) ON DELETE RESTRICT,
    FOREIGN KEY (admission_id) REFERENCES admissions(id) ON DELETE SET NULL
);

-- ============================================================
-- 13. EMERGENCY & TRIAGE
-- ============================================================

CREATE TABLE IF NOT EXISTS emergency_cases (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    case_no          VARCHAR(30) UNIQUE,
    patient_id       INT,
    patient_name     VARCHAR(150),
    patient_age      INT,
    patient_gender   ENUM('male','female','unknown') DEFAULT 'unknown',
    triage_color     ENUM('red','yellow','green','black') DEFAULT 'yellow',
    chief_complaint  TEXT NOT NULL,
    arrival_mode     ENUM('walk_in','ambulance','referred','police') DEFAULT 'walk_in',
    is_mlc           TINYINT(1) DEFAULT 0,
    mlc_number       VARCHAR(30),
    police_station   VARCHAR(100),
    assigned_doctor  INT,
    assigned_bed     INT,
    status           ENUM('waiting','under_treatment','admitted','discharged','expired') DEFAULT 'waiting',
    arrived_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    treated_at       DATETIME,
    discharged_at    DATETIME,
    registered_by    INT,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE SET NULL,
    FOREIGN KEY (assigned_doctor) REFERENCES doctors(id) ON DELETE SET NULL,
    FOREIGN KEY (assigned_bed) REFERENCES beds(id) ON DELETE SET NULL,
    FOREIGN KEY (registered_by) REFERENCES users(id) ON DELETE SET NULL
);

-- ============================================================
-- 14. BLOOD BANK
-- ============================================================

CREATE TABLE IF NOT EXISTS blood_inventory (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    blood_group  ENUM('A+','A-','B+','B-','O+','O-','AB+','AB-') NOT NULL,
    component    ENUM('whole_blood','packed_rbc','plasma','platelets','cryo') DEFAULT 'whole_blood',
    units        INT DEFAULT 0,
    expiry_date  DATE,
    collected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    bag_number   VARCHAR(50) UNIQUE,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS blood_donors (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    donor_id     VARCHAR(20) UNIQUE,
    name         VARCHAR(150) NOT NULL,
    blood_group  ENUM('A+','A-','B+','B-','O+','O-','AB+','AB-') NOT NULL,
    phone        VARCHAR(20),
    email        VARCHAR(120),
    date_of_birth DATE,
    address      TEXT,
    last_donated DATE,
    total_donations INT DEFAULT 0,
    is_eligible  TINYINT(1) DEFAULT 1,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS blood_requests (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    request_no      VARCHAR(30) UNIQUE,
    patient_id      INT NOT NULL,
    doctor_id       INT NOT NULL,
    blood_group     ENUM('A+','A-','B+','B-','O+','O-','AB+','AB-') NOT NULL,
    component       ENUM('whole_blood','packed_rbc','plasma','platelets','cryo') DEFAULT 'whole_blood',
    units_required  INT DEFAULT 1,
    units_issued    INT DEFAULT 0,
    priority        ENUM('routine','urgent','emergency') DEFAULT 'routine',
    status          ENUM('pending','approved','issued','rejected') DEFAULT 'pending',
    reason          TEXT,
    requested_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    issued_at       DATETIME,
    issued_by       INT,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    FOREIGN KEY (issued_by) REFERENCES users(id) ON DELETE SET NULL
);

-- ============================================================
-- 15. BILLING & PAYMENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS invoices (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    invoice_no       VARCHAR(30) UNIQUE,
    patient_id       INT NOT NULL,
    visit_id         INT,
    admission_id     INT,
    invoice_date     DATE DEFAULT (CURRENT_DATE),
    due_date         DATE,
    subtotal         DECIMAL(12,2) DEFAULT 0.00,
    discount_pct     DECIMAL(5,2) DEFAULT 0.00,
    discount_amt     DECIMAL(12,2) DEFAULT 0.00,
    gst_pct          DECIMAL(5,2) DEFAULT 18.00,
    gst_amount       DECIMAL(12,2) DEFAULT 0.00,
    total_amount     DECIMAL(12,2) DEFAULT 0.00,
    paid_amount      DECIMAL(12,2) DEFAULT 0.00,
    balance          DECIMAL(12,2) DEFAULT 0.00,
    status           ENUM('draft','pending','partial','paid','cancelled','refunded') DEFAULT 'pending',
    payment_mode     ENUM('cash','card','upi','net_banking','insurance','razorpay') DEFAULT 'cash',
    notes            TEXT,
    created_by       INT,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE SET NULL,
    FOREIGN KEY (admission_id) REFERENCES admissions(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    invoice_id   INT NOT NULL,
    item_type    ENUM('consultation','lab','radiology','pharmacy','room','procedure','other') NOT NULL,
    description  VARCHAR(255) NOT NULL,
    quantity     INT DEFAULT 1,
    unit_price   DECIMAL(10,2) DEFAULT 0.00,
    total_price  DECIMAL(12,2) DEFAULT 0.00,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS payments (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    payment_no       VARCHAR(30) UNIQUE,
    invoice_id       INT NOT NULL,
    patient_id       INT NOT NULL,
    amount           DECIMAL(12,2) NOT NULL,
    payment_mode     ENUM('cash','card','upi','net_banking','insurance','razorpay') DEFAULT 'cash',
    transaction_id   VARCHAR(100),
    razorpay_order_id VARCHAR(100),
    razorpay_payment_id VARCHAR(100),
    status           ENUM('pending','success','failed','refunded') DEFAULT 'pending',
    receipt_path     VARCHAR(255),
    paid_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    collected_by     INT,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (collected_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS insurance_claims (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    claim_no        VARCHAR(30) UNIQUE,
    invoice_id      INT NOT NULL,
    patient_id      INT NOT NULL,
    tpa_name        VARCHAR(100),
    insurance_provider VARCHAR(100),
    policy_number   VARCHAR(80),
    claim_amount    DECIMAL(12,2) DEFAULT 0.00,
    approved_amount DECIMAL(12,2) DEFAULT 0.00,
    status          ENUM('submitted','under_review','approved','rejected','partial','settled') DEFAULT 'submitted',
    pre_auth_number VARCHAR(80),
    pre_auth_date   DATE,
    submitted_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    settled_at      DATETIME,
    remarks         TEXT,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
);

-- ============================================================
-- 16. GENERAL INVENTORY & ASSETS
-- ============================================================

CREATE TABLE IF NOT EXISTS inventory_categories (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS inventory_items (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    item_code       VARCHAR(30) UNIQUE,
    name            VARCHAR(150) NOT NULL,
    category_id     INT,
    unit            VARCHAR(30),
    current_stock   INT DEFAULT 0,
    reorder_level   INT DEFAULT 5,
    unit_cost       DECIMAL(10,2) DEFAULT 0.00,
    location        VARCHAR(80),
    is_active       TINYINT(1) DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES inventory_categories(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS equipment (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    asset_code       VARCHAR(30) UNIQUE,
    name             VARCHAR(150) NOT NULL,
    category         VARCHAR(80),
    serial_number    VARCHAR(80) UNIQUE,
    manufacturer     VARCHAR(100),
    model            VARCHAR(80),
    purchase_date    DATE,
    purchase_cost    DECIMAL(12,2),
    warranty_expiry  DATE,
    amc_expiry       DATE,
    location         VARCHAR(80),
    status           ENUM('active','under_maintenance','disposed') DEFAULT 'active',
    last_service     DATE,
    next_service     DATE,
    notes            TEXT,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 17. STAFF HR & ROSTER
-- ============================================================

CREATE TABLE IF NOT EXISTS staff (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL UNIQUE,
    employee_id     VARCHAR(30) UNIQUE,
    department_id   INT,
    designation     VARCHAR(100),
    join_date       DATE,
    basic_salary    DECIMAL(10,2) DEFAULT 0.00,
    is_active       TINYINT(1) DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS shifts (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(50) NOT NULL,
    start_time  TIME NOT NULL,
    end_time    TIME NOT NULL,
    description VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS staff_roster (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    staff_id    INT NOT NULL,
    shift_id    INT NOT NULL,
    roster_date DATE NOT NULL,
    status      ENUM('scheduled','present','absent','leave','half_day') DEFAULT 'scheduled',
    notes       VARCHAR(255),
    UNIQUE KEY unique_roster (staff_id, roster_date),
    FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE,
    FOREIGN KEY (shift_id) REFERENCES shifts(id) ON DELETE CASCADE
);

-- ============================================================
-- 18. REFERRALS
-- ============================================================

CREATE TABLE IF NOT EXISTS referrals (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    referral_no     VARCHAR(30) UNIQUE,
    patient_id      INT NOT NULL,
    from_doctor_id  INT NOT NULL,
    to_doctor_id    INT,
    to_hospital     VARCHAR(150),
    reason          TEXT,
    type            ENUM('internal','external') DEFAULT 'internal',
    status          ENUM('pending','accepted','completed','rejected') DEFAULT 'pending',
    notes           TEXT,
    referral_letter VARCHAR(255),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (from_doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    FOREIGN KEY (to_doctor_id) REFERENCES doctors(id) ON DELETE SET NULL
);

-- ============================================================
-- 19. NOTIFICATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS notification_templates (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    type        ENUM('email','sms','whatsapp','in_app') DEFAULT 'in_app',
    subject     VARCHAR(255),
    body        TEXT NOT NULL,
    variables   JSON,
    is_active   TINYINT(1) DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL,
    title         VARCHAR(255) NOT NULL,
    message       TEXT,
    type          ENUM('info','success','warning','danger') DEFAULT 'info',
    module        VARCHAR(50),
    reference_id  INT,
    is_read       TINYINT(1) DEFAULT 0,
    read_at       DATETIME,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notification_logs (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    recipient_id INT,
    channel      ENUM('email','sms','whatsapp','in_app') NOT NULL,
    recipient    VARCHAR(120),
    subject      VARCHAR(255),
    message      TEXT,
    status       ENUM('pending','sent','failed') DEFAULT 'pending',
    error        TEXT,
    sent_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE SET NULL
);

-- ============================================================
-- 20. ICD-10 CODES
-- ============================================================

CREATE TABLE IF NOT EXISTS icd10_codes (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    code        VARCHAR(10) NOT NULL UNIQUE,
    description VARCHAR(255) NOT NULL,
    category    VARCHAR(100),
    INDEX idx_code (code),
    FULLTEXT INDEX ft_desc (description)
);

-- ============================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================

CREATE INDEX idx_users_email        ON users(email);
CREATE INDEX idx_users_role         ON users(role_id);
CREATE INDEX idx_patients_uhid      ON patients(uhid);
CREATE INDEX idx_patients_phone     ON patients(phone);
CREATE INDEX idx_appt_date          ON appointments(appointment_date);
CREATE INDEX idx_appt_doctor        ON appointments(doctor_id);
CREATE INDEX idx_appt_patient       ON appointments(patient_id);
CREATE INDEX idx_appt_status        ON appointments(status);
CREATE INDEX idx_visits_patient     ON visits(patient_id);
CREATE INDEX idx_visits_doctor      ON visits(doctor_id);
CREATE INDEX idx_lab_orders_patient ON lab_orders(patient_id);
CREATE INDEX idx_lab_orders_status  ON lab_orders(status);
CREATE INDEX idx_invoices_patient   ON invoices(patient_id);
CREATE INDEX idx_invoices_status    ON invoices(status);
CREATE INDEX idx_audit_user         ON audit_logs(user_id);
CREATE INDEX idx_audit_created      ON audit_logs(created_at);
CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notif_read         ON notifications(is_read);

-- ============================================================
-- SEED DATA — Roles
-- ============================================================

INSERT INTO roles (name, description) VALUES
('admin',        'Full system access — manages everything'),
('doctor',       'Clinical access — EMR, prescriptions, lab requests'),
('receptionist', 'Front desk — appointments, patient registration, billing'),
('pharmacist',   'Pharmacy — drug inventory, dispensing'),
('lab_tech',     'Laboratory — test processing, result entry'),
('patient',      'Patient portal — view own records');

-- ============================================================
-- SEED DATA — Admin User
-- Password: Admin@123 (bcrypt hashed — change on first login)
-- ============================================================

INSERT INTO users (username, email, phone, password_hash, role_id, first_name, last_name, is_active, is_verified)
VALUES (
    'admin',
    'admin@medicorehms.com',
    '+91-9876543210',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBpj2IYFHWL.Oa',
    1,
    'System',
    'Administrator',
    1,
    1
);

-- ============================================================
-- SEED DATA — Departments
-- ============================================================

INSERT INTO departments (name, description, floor) VALUES
('General Medicine',      'General OPD and internal medicine',      'Ground Floor'),
('Cardiology',            'Heart and cardiovascular care',           '1st Floor'),
('Orthopedics',           'Bone, joint and muscle care',             '2nd Floor'),
('Pediatrics',            'Child healthcare (0-18 years)',           '1st Floor'),
('Gynecology',            'Women''s health and maternity',           '2nd Floor'),
('Neurology',             'Brain, spine and nervous system',         '3rd Floor'),
('Dermatology',           'Skin, hair and nail conditions',          'Ground Floor'),
('ENT',                   'Ear, nose and throat',                    'Ground Floor'),
('Ophthalmology',         'Eye care',                                '1st Floor'),
('Oncology',              'Cancer care and treatment',               '3rd Floor'),
('Emergency',             '24/7 emergency and trauma care',          'Ground Floor'),
('Laboratory',            'Diagnostic laboratory services',          'Ground Floor'),
('Radiology',             'Imaging and radiology',                   'Ground Floor'),
('Pharmacy',              'Hospital pharmacy',                       'Ground Floor');

-- ============================================================
-- SEED DATA — Wards & Beds
-- ============================================================

INSERT INTO wards (name, ward_type, floor, total_beds, charge_per_day) VALUES
('General Ward A',   'general',       'Ground Floor', 20, 500.00),
('General Ward B',   'general',       'Ground Floor', 20, 500.00),
('Private Ward',     'private',       '1st Floor',    10, 2000.00),
('Semi-Private Ward','semi_private',  '1st Floor',    15, 1200.00),
('ICU',              'icu',           '2nd Floor',    10, 5000.00),
('NICU',             'nicu',          '2nd Floor',    6,  6000.00),
('Emergency Ward',   'emergency',     'Ground Floor', 10, 1000.00);

-- Beds for General Ward A (first 6 for demo)
INSERT INTO beds (bed_number, ward_id, status) VALUES
('A-01', 1, 'occupied'), ('A-02', 1, 'occupied'), ('A-03', 1, 'available'),
('A-04', 1, 'cleaning'), ('A-05', 1, 'available'), ('A-06', 1, 'reserved'),
('A-07', 1, 'available'), ('A-08', 1, 'occupied'), ('A-09', 1, 'available'),
('A-10', 1, 'available'),
-- Beds for ICU
('ICU-01', 5, 'occupied'), ('ICU-02', 5, 'available'), ('ICU-03', 5, 'available'),
('ICU-04', 5, 'occupied'), ('ICU-05', 5, 'maintenance');

-- ============================================================
-- SEED DATA — OT Rooms
-- ============================================================

INSERT INTO ot_rooms (name, room_type, floor, status) VALUES
('OT-1 (Major)',   'major',     '3rd Floor', 'available'),
('OT-2 (Minor)',   'minor',     '3rd Floor', 'available'),
('OT-3 (Cardiac)', 'cardiac',   '3rd Floor', 'available'),
('OT-4 (Emergency)','emergency','Ground Floor','available');

-- ============================================================
-- SEED DATA — Shifts
-- ============================================================

INSERT INTO shifts (name, start_time, end_time, description) VALUES
('Morning',   '08:00:00', '16:00:00', '8am to 4pm shift'),
('Evening',   '16:00:00', '00:00:00', '4pm to midnight shift'),
('Night',     '00:00:00', '08:00:00', 'Midnight to 8am shift'),
('Full Day',  '09:00:00', '18:00:00', '9am to 6pm full day');

-- ============================================================
-- SEED DATA — Hospital Settings
-- ============================================================

INSERT INTO hospital_settings (setting_key, setting_value, setting_type, description) VALUES
('hospital_name',     'MediCore Hospital',           'text',    'Hospital display name'),
('hospital_address',  '123 Medical Lane, HC City',   'text',    'Full address'),
('hospital_phone',    '+91-9876543210',               'text',    'Main phone number'),
('hospital_email',    'info@medicorehospital.com',    'text',    'Main email'),
('gst_number',        '27AABCU9603R1ZX',              'text',    'GST registration number'),
('gst_rate',          '18',                           'number',  'Default GST rate in percent'),
('uhid_prefix',       'MED',                          'text',    'Prefix for UHID generation'),
('appointment_slot',  '15',                           'number',  'Appointment slot duration in minutes'),
('razorpay_enabled',  'false',                        'boolean', 'Enable Razorpay payments'),
('sms_enabled',       'false',                        'boolean', 'Enable SMS notifications'),
('whatsapp_enabled',  'false',                        'boolean', 'Enable WhatsApp notifications'),
('email_enabled',     'false',                        'boolean', 'Enable email notifications'),
('currency',          'INR',                          'text',    'Default currency'),
('currency_symbol',   '₹',                            'text',    'Currency symbol');

-- ============================================================
-- SEED DATA — Lab Tests (Common)
-- ============================================================

INSERT INTO lab_tests (name, code, category, sample_type, turnaround_hrs, cost, unit) VALUES
('Complete Blood Count (CBC)',   'CBC',   'Haematology', 'Blood', 4,  350.00, ''),
('Blood Glucose (Fasting)',      'FBS',   'Biochemistry', 'Blood', 2, 80.00,  'mg/dL'),
('Blood Glucose (Random)',       'RBS',   'Biochemistry', 'Blood', 1, 60.00,  'mg/dL'),
('HbA1c',                        'HBA1C','Biochemistry', 'Blood', 6, 400.00, '%'),
('Lipid Profile',                'LIPID', 'Biochemistry', 'Blood', 6, 600.00, ''),
('Liver Function Test (LFT)',    'LFT',   'Biochemistry', 'Blood', 8, 700.00, ''),
('Kidney Function Test (KFT)',   'KFT',   'Biochemistry', 'Blood', 8, 600.00, ''),
('Thyroid Function Test (TFT)',  'TFT',   'Endocrinology','Blood',24, 800.00, ''),
('Urine Routine',                'URE',   'Urine',       'Urine', 2, 120.00, ''),
('Serum Electrolytes',           'ELEC',  'Biochemistry', 'Blood', 4, 400.00, ''),
('HIV Test',                     'HIV',   'Serology',    'Blood', 4, 300.00, ''),
('HBsAg',                        'HBSAG','Serology',    'Blood', 4, 250.00, ''),
('Widal Test',                   'WIDAL', 'Serology',    'Blood', 8, 200.00, ''),
('Dengue NS1 Antigen',           'DENG',  'Serology',    'Blood',12, 800.00, ''),
('COVID-19 RT-PCR',              'COVID', 'Molecular',   'Swab', 24,1200.00, '');

-- ============================================================
-- SEED DATA — Radiology Tests
-- ============================================================

INSERT INTO radiology_tests (name, code, category, cost) VALUES
('Chest X-Ray (PA View)',       'CXR',    'xray',       400.00),
('X-Ray - Left Hand',           'XRLH',   'xray',       350.00),
('X-Ray - Spine (Lumbar)',      'XRLS',   'xray',       450.00),
('Ultrasound - Abdomen',        'USAB',   'ultrasound', 900.00),
('Ultrasound - Pelvis',         'USPV',   'ultrasound', 800.00),
('CT Scan - Brain',             'CTBR',   'ct',        3500.00),
('CT Scan - Chest',             'CTCH',   'ct',        4000.00),
('MRI - Brain',                 'MRIBR',  'mri',       6000.00),
('MRI - Spine',                 'MRISP',  'mri',       6500.00),
('2D Echo',                     '2DECHO', 'ultrasound',1800.00);

-- ============================================================
-- SEED DATA — Notification Templates
-- ============================================================

INSERT INTO notification_templates (name, type, subject, body) VALUES
('appointment_confirmed', 'sms',   NULL,
 'Dear {{patient_name}}, your appointment with Dr. {{doctor_name}} is confirmed on {{date}} at {{time}}. Token: {{token}}. MediCore HMS'),
('appointment_reminder', 'whatsapp', NULL,
 'Reminder: Your appointment at MediCore Hospital is tomorrow, {{date}} at {{time}} with Dr. {{doctor_name}}. Please arrive 10 mins early.'),
('lab_report_ready', 'sms', NULL,
 'Dear {{patient_name}}, your lab report for {{test_name}} is ready. Download from patient portal or collect from lab. MediCore HMS'),
('invoice_generated', 'email', 'Invoice #{{invoice_no}} from MediCore Hospital',
 'Dear {{patient_name}},\n\nYour invoice #{{invoice_no}} for ₹{{amount}} has been generated.\n\nPlease pay online or at the billing counter.\n\nMediCore HMS'),
('password_reset', 'email', 'Reset your MediCore HMS password',
 'Dear {{name}},\n\nClick the link below to reset your password:\n{{reset_link}}\n\nThis link expires in 1 hour.\n\nMediCore HMS');

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- DONE! Database setup complete.
-- Default admin login:
--   Username : admin
--   Email    : admin@medicorehms.com
--   Password : Admin@123
-- ============================================================
