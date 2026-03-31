-- ============================================================
--   MediCore HMS — Schema Fix
--   Run this in MySQL Workbench AFTER the main schema
--   This fixes the errors from the first run
-- ============================================================

USE medicore_hms;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- FIX 1: patient_chronic_conditions
-- 'condition' is a reserved word in MySQL — renamed to condition_name
-- ============================================================

CREATE TABLE IF NOT EXISTS patient_chronic_conditions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      INT NOT NULL,
    condition_name  VARCHAR(150) NOT NULL,
    icd10_code      VARCHAR(20),
    diagnosed_on    DATE,
    notes           TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
);

-- ============================================================
-- FIX 2: prescriptions
-- 'NOT_NULL' typo fix on doctor_id
-- ============================================================

CREATE TABLE IF NOT EXISTS prescriptions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    prescription_no VARCHAR(30) UNIQUE,
    visit_id        INT NOT NULL,
    patient_id      INT NOT NULL,
    doctor_id       INT NOT NULL,
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

-- ============================================================
-- ALL REMAINING TABLES (paste below if they didn't run yet)
-- ============================================================

CREATE TABLE IF NOT EXISTS prescription_items (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    prescription_id  INT NOT NULL,
    drug_id          INT NOT NULL,
    dosage           VARCHAR(50),
    frequency        VARCHAR(80),
    duration         VARCHAR(50),
    quantity         INT DEFAULT 1,
    instructions     TEXT,
    is_dispensed     TINYINT DEFAULT 0,
    FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE,
    FOREIGN KEY (drug_id) REFERENCES drugs(id) ON DELETE CASCADE
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

CREATE TABLE IF NOT EXISTS drug_inventory (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    drug_id          INT NOT NULL,
    batch_number     VARCHAR(50),
    quantity         INT DEFAULT 0,
    unit_cost        DECIMAL(10,2) DEFAULT 0.00,
    selling_price    DECIMAL(10,2) DEFAULT 0.00,
    expiry_date      DATE,
    manufacture_date DATE,
    reorder_level    INT DEFAULT 10,
    location         VARCHAR(50),
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
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
    is_active    TINYINT DEFAULT 1,
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

CREATE TABLE IF NOT EXISTS lab_orders (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    order_no            VARCHAR(30) UNIQUE,
    patient_id          INT NOT NULL,
    doctor_id           INT NOT NULL,
    visit_id            INT,
    priority            ENUM('routine','urgent','stat') DEFAULT 'routine',
    status              ENUM('ordered','sample_collected','processing','completed','cancelled') DEFAULT 'ordered',
    notes               TEXT,
    ordered_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    sample_collected_at DATETIME,
    completed_at        DATETIME,
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
    is_critical  TINYINT DEFAULT 0,
    flag         ENUM('normal','high','low','critical') DEFAULT 'normal',
    notes        TEXT,
    done_by      INT,
    done_at      DATETIME,
    FOREIGN KEY (order_id) REFERENCES lab_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (test_id) REFERENCES lab_tests(id) ON DELETE CASCADE,
    FOREIGN KEY (done_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS lab_reports (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    order_id        INT NOT NULL UNIQUE,
    patient_id      INT NOT NULL,
    report_path     VARCHAR(255),
    generated_by    INT,
    generated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    sent_to_patient TINYINT DEFAULT 0,
    sent_at         DATETIME,
    FOREIGN KEY (order_id) REFERENCES lab_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (generated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS radiology_tests (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    code        VARCHAR(30) UNIQUE,
    category    ENUM('xray','mri','ct','ultrasound','other') DEFAULT 'other',
    cost        DECIMAL(10,2) DEFAULT 0.00,
    description TEXT,
    is_active   TINYINT DEFAULT 1
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

CREATE TABLE IF NOT EXISTS ot_rooms (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(80) NOT NULL,
    room_type   ENUM('major','minor','emergency','cardiac','neuro') DEFAULT 'major',
    floor       VARCHAR(20),
    status      ENUM('available','in_use','cleaning','maintenance') DEFAULT 'available',
    equipment   TEXT,
    is_active   TINYINT DEFAULT 1,
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
    is_mlc           TINYINT DEFAULT 0,
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
    id              INT AUTO_INCREMENT PRIMARY KEY,
    donor_id        VARCHAR(20) UNIQUE,
    name            VARCHAR(150) NOT NULL,
    blood_group     ENUM('A+','A-','B+','B-','O+','O-','AB+','AB-') NOT NULL,
    phone           VARCHAR(20),
    email           VARCHAR(120),
    date_of_birth   DATE,
    address         TEXT,
    last_donated    DATE,
    total_donations INT DEFAULT 0,
    is_eligible     TINYINT DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
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
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    payment_no          VARCHAR(30) UNIQUE,
    invoice_id          INT NOT NULL,
    patient_id          INT NOT NULL,
    amount              DECIMAL(12,2) NOT NULL,
    payment_mode        ENUM('cash','card','upi','net_banking','insurance','razorpay') DEFAULT 'cash',
    transaction_id      VARCHAR(100),
    razorpay_order_id   VARCHAR(100),
    razorpay_payment_id VARCHAR(100),
    status              ENUM('pending','success','failed','refunded') DEFAULT 'pending',
    receipt_path        VARCHAR(255),
    paid_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    collected_by        INT,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (collected_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS insurance_claims (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    claim_no           VARCHAR(30) UNIQUE,
    invoice_id         INT NOT NULL,
    patient_id         INT NOT NULL,
    tpa_name           VARCHAR(100),
    insurance_provider VARCHAR(100),
    policy_number      VARCHAR(80),
    claim_amount       DECIMAL(12,2) DEFAULT 0.00,
    approved_amount    DECIMAL(12,2) DEFAULT 0.00,
    status             ENUM('submitted','under_review','approved','rejected','partial','settled') DEFAULT 'submitted',
    pre_auth_number    VARCHAR(80),
    pre_auth_date      DATE,
    submitted_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    settled_at         DATETIME,
    remarks            TEXT,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS inventory_categories (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS inventory_items (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    item_code     VARCHAR(30) UNIQUE,
    name          VARCHAR(150) NOT NULL,
    category_id   INT,
    unit          VARCHAR(30),
    current_stock INT DEFAULT 0,
    reorder_level INT DEFAULT 5,
    unit_cost     DECIMAL(10,2) DEFAULT 0.00,
    location      VARCHAR(80),
    is_active     TINYINT DEFAULT 1,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES inventory_categories(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS equipment (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    asset_code      VARCHAR(30) UNIQUE,
    name            VARCHAR(150) NOT NULL,
    category        VARCHAR(80),
    serial_number   VARCHAR(80) UNIQUE,
    manufacturer    VARCHAR(100),
    model           VARCHAR(80),
    purchase_date   DATE,
    purchase_cost   DECIMAL(12,2),
    warranty_expiry DATE,
    amc_expiry      DATE,
    location        VARCHAR(80),
    status          ENUM('active','under_maintenance','disposed') DEFAULT 'active',
    last_service    DATE,
    next_service    DATE,
    notes           TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staff (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL UNIQUE,
    employee_id   VARCHAR(30) UNIQUE,
    department_id INT,
    designation   VARCHAR(100),
    join_date     DATE,
    basic_salary  DECIMAL(10,2) DEFAULT 0.00,
    is_active     TINYINT DEFAULT 1,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
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

CREATE TABLE IF NOT EXISTS referrals (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    referral_no    VARCHAR(30) UNIQUE,
    patient_id     INT NOT NULL,
    from_doctor_id INT NOT NULL,
    to_doctor_id   INT,
    to_hospital    VARCHAR(150),
    reason         TEXT,
    ref_type       ENUM('internal','external') DEFAULT 'internal',
    status         ENUM('pending','accepted','completed','rejected') DEFAULT 'pending',
    notes          TEXT,
    referral_letter VARCHAR(255),
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (from_doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    FOREIGN KEY (to_doctor_id) REFERENCES doctors(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS notification_templates (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    type        ENUM('email','sms','whatsapp','in_app') DEFAULT 'in_app',
    subject     VARCHAR(255),
    body        TEXT NOT NULL,
    variables   JSON,
    is_active   TINYINT DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT NOT NULL,
    title        VARCHAR(255) NOT NULL,
    message      TEXT,
    notif_type   ENUM('info','success','warning','danger') DEFAULT 'info',
    module       VARCHAR(50),
    reference_id INT,
    is_read      TINYINT DEFAULT 0,
    read_at      DATETIME,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
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

CREATE TABLE IF NOT EXISTS icd10_codes (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    code        VARCHAR(10) NOT NULL UNIQUE,
    description VARCHAR(255) NOT NULL,
    category    VARCHAR(100),
    INDEX idx_icd_code (code),
    FULLTEXT INDEX ft_icd_desc (description)
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_users_email        ON users(email);
CREATE INDEX IF NOT EXISTS idx_patients_uhid      ON patients(uhid);
CREATE INDEX IF NOT EXISTS idx_patients_phone     ON patients(phone);
CREATE INDEX IF NOT EXISTS idx_appt_date          ON appointments(appointment_date);
CREATE INDEX IF NOT EXISTS idx_appt_doctor        ON appointments(doctor_id);
CREATE INDEX IF NOT EXISTS idx_appt_patient       ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_invoices_patient   ON invoices(patient_id);
CREATE INDEX IF NOT EXISTS idx_audit_user         ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);

-- ============================================================
-- SEED DATA (only if not already inserted)
-- ============================================================

INSERT IGNORE INTO ot_rooms (name, room_type, floor, status) VALUES
('OT-1 (Major)',    'major',     '3rd Floor',    'available'),
('OT-2 (Minor)',    'minor',     '3rd Floor',    'available'),
('OT-3 (Cardiac)',  'cardiac',   '3rd Floor',    'available'),
('OT-4 (Emergency)','emergency', 'Ground Floor', 'available');

INSERT IGNORE INTO shifts (name, start_time, end_time, description) VALUES
('Morning', '08:00:00', '16:00:00', '8am to 4pm'),
('Evening', '16:00:00', '00:00:00', '4pm to midnight'),
('Night',   '00:00:00', '08:00:00', 'Midnight to 8am'),
('Full Day','09:00:00', '18:00:00', '9am to 6pm');

INSERT IGNORE INTO notification_templates (name, type, subject, body) VALUES
('appointment_confirmed', 'sms', NULL,
 'Dear {{patient_name}}, your appointment with Dr. {{doctor_name}} is confirmed on {{date}} at {{time}}. Token: {{token}}. MediCore HMS'),
('appointment_reminder', 'whatsapp', NULL,
 'Reminder: Your appointment at MediCore Hospital is tomorrow {{date}} at {{time}} with Dr. {{doctor_name}}.'),
('lab_report_ready', 'sms', NULL,
 'Dear {{patient_name}}, your lab report for {{test_name}} is ready. MediCore HMS'),
('invoice_generated', 'email', 'Invoice #{{invoice_no}} from MediCore Hospital',
 'Dear {{patient_name}}, your invoice #{{invoice_no}} for Rs.{{amount}} is ready. MediCore HMS'),
('password_reset', 'email', 'Reset your MediCore HMS password',
 'Dear {{name}}, click here to reset your password: {{reset_link}}. Expires in 1 hour.');

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- Done! All tables created successfully.
-- ============================================================
SELECT 'MediCore HMS database setup complete!' AS status;
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'medicore_hms'
ORDER BY table_name;
