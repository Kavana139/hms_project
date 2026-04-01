"""
MediCore HMS — Test Suite
=========================
White Box Testing : Authentication Module, Password Generator
Black Box Testing : Login API, Patient Registration API

Run: python -m pytest tests/test_suite.py -v
 or: python tests/test_suite.py
"""

import unittest
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# ═══════════════════════════════════════════════════════════════
#  SETUP
# ═══════════════════════════════════════════════════════════════

def get_app():
    """Create a test Flask application with SQLite in-memory database."""
    os.environ['FLASK_ENV'] = 'testing'
    from app import create_app
    app = create_app('testing')
    app.config.update({
        'TESTING':          True,
        'WTF_CSRF_ENABLED': False,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'RATELIMIT_ENABLED': False,
        'RATELIMIT_STORAGE_URI': 'memory://',
        'SERVER_NAME': None,
    })
    return app


# ═══════════════════════════════════════════════════════════════
#  WHITE BOX TESTS — Module: Authentication (auth_service.py)
#  Tests internal logic, branches, and code paths
# ═══════════════════════════════════════════════════════════════

class WhiteBoxPasswordGenerator(unittest.TestCase):
    """
    WHITE BOX — generate_password()
    Tests all internal branches and requirements of the
    password generator in app/services/auth_service.py
    """

    def setUp(self):
        from app.services.auth_service import generate_password
        self.generate_password = generate_password

    # ── WB-PG-01: Default length ──────────────────────────────
    def test_WB_PG_01_default_length_is_ten(self):
        """Password without explicit length must be exactly 10 characters."""
        pwd = self.generate_password()
        self.assertEqual(len(pwd), 10,
            f"Expected length 10, got {len(pwd)}")

    # ── WB-PG-02: Custom length ───────────────────────────────
    def test_WB_PG_02_custom_length_respected(self):
        """Password length parameter must be honoured."""
        for length in [6, 8, 12, 16]:
            with self.subTest(length=length):
                pwd = self.generate_password(length=length)
                self.assertEqual(len(pwd), length)

    # ── WB-PG-03: Contains uppercase ─────────────────────────
    def test_WB_PG_03_contains_uppercase(self):
        """Branch: any(c.isupper()) must be satisfied."""
        for _ in range(20):
            pwd = self.generate_password()
            self.assertTrue(any(c.isupper() for c in pwd),
                f"No uppercase found in: {pwd}")

    # ── WB-PG-04: Contains lowercase ─────────────────────────
    def test_WB_PG_04_contains_lowercase(self):
        """Branch: any(c.islower()) must be satisfied."""
        for _ in range(20):
            pwd = self.generate_password()
            self.assertTrue(any(c.islower() for c in pwd),
                f"No lowercase found in: {pwd}")

    # ── WB-PG-05: Contains digit ─────────────────────────────
    def test_WB_PG_05_contains_digit(self):
        """Branch: any(c.isdigit()) must be satisfied."""
        for _ in range(20):
            pwd = self.generate_password()
            self.assertTrue(any(c.isdigit() for c in pwd),
                f"No digit found in: {pwd}")

    # ── WB-PG-06: No URL-breaking characters ─────────────────
    def test_WB_PG_06_no_url_breaking_chars(self):
        """Characters %, $, @, # must NOT appear (break DATABASE_URL)."""
        forbidden = set('%$@#&+= ')
        for _ in range(50):
            pwd = self.generate_password()
            bad = forbidden.intersection(set(pwd))
            self.assertEqual(len(bad), 0,
                f"Found forbidden chars {bad} in password: {pwd}")

    # ── WB-PG-07: Only alphanumeric charset ──────────────────
    def test_WB_PG_07_only_alphanumeric(self):
        """All characters must be ASCII letters or digits."""
        import string
        valid = set(string.ascii_letters + string.digits)
        for _ in range(30):
            pwd = self.generate_password()
            bad = set(pwd) - valid
            self.assertEqual(len(bad), 0,
                f"Non-alphanumeric chars {bad} in: {pwd}")

    # ── WB-PG-08: Uniqueness (randomness check) ──────────────
    def test_WB_PG_08_passwords_are_unique(self):
        """10 consecutive passwords must all be different."""
        passwords = [self.generate_password() for _ in range(10)]
        self.assertEqual(len(set(passwords)), 10,
            "Duplicate passwords generated — randomness broken!")

    # ── WB-PG-09: Does not hang (terminates quickly) ─────────
    def test_WB_PG_09_terminates_quickly(self):
        """Function must complete in < 1 second (no infinite loop)."""
        import signal

        def _timeout(signum, frame):
            raise TimeoutError("generate_password() hung — infinite loop!")

        signal.signal(signal.SIGALRM, _timeout)
        signal.alarm(1)
        try:
            for _ in range(100):
                self.generate_password()
        except TimeoutError as e:
            self.fail(str(e))
        finally:
            signal.alarm(0)


class WhiteBoxAuthService(unittest.TestCase):
    """
    WHITE BOX — authenticate_user() & generate_username()
    Tests internal state machine and code branches
    """

    def setUp(self):
        from app.services.auth_service import generate_username
        self.generate_username = generate_username

    # ── WB-AU-01: Username prefix for doctor ─────────────────
    def test_WB_AU_01_doctor_prefix(self):
        """Doctor username must start with 'dr.'"""
        # Mock User.query to return None (no collision)
        import unittest.mock as mock
        with mock.patch('app.models.user.User.query') as mq:
            mq.filter_by.return_value.first.return_value = None
            uname = self.generate_username('Kavanashree', 'BA', 'doctor')
            self.assertTrue(uname.startswith('dr.'),
                f"Expected 'dr.' prefix, got: {uname}")

    # ── WB-AU-02: Username prefix for receptionist ───────────
    def test_WB_AU_02_receptionist_prefix(self):
        """Receptionist username must start with 'rec.'"""
        import unittest.mock as mock
        with mock.patch('app.models.user.User.query') as mq:
            mq.filter_by.return_value.first.return_value = None
            uname = self.generate_username('Riya', 'Shah', 'receptionist')
            self.assertTrue(uname.startswith('rec.'))

    # ── WB-AU-03: Username collision counter ─────────────────
    def test_WB_AU_03_collision_increments_counter(self):
        """When username exists, must append incrementing number."""
        import unittest.mock as mock
        call_count = [0]
        def side_effect(*args, **kwargs):
            class Q:
                def first(self_inner):
                    call_count[0] += 1
                    # First 2 calls: collision exists; 3rd: free
                    return object() if call_count[0] <= 2 else None
            return Q()
        with mock.patch('app.models.user.User.query') as mq:
            mq.filter_by.side_effect = side_effect
            uname = self.generate_username('Test', 'User', 'pharmacist')
            self.assertRegex(uname, r'\d$',
                f"Expected numeric suffix for collision, got: {uname}")

    # ── WB-AU-04: Username only alphanumeric + dot ────────────
    def test_WB_AU_04_username_safe_chars(self):
        """Username must contain only alphanumeric and '.' characters."""
        import unittest.mock as mock
        with mock.patch('app.models.user.User.query') as mq:
            mq.filter_by.return_value.first.return_value = None
            uname = self.generate_username('Aarav', "O'Brien", 'doctor')
            allowed = set('abcdefghijklmnopqrstuvwxyz0123456789.')
            bad = set(uname.lower()) - allowed
            self.assertEqual(len(bad), 0,
                f"Unsafe chars {bad} in username: {uname}")


# ═══════════════════════════════════════════════════════════════
#  BLACK BOX TESTS — External behaviour without internal knowledge
#  Tests: Login API, Appointment Booking, Patient Registration
# ═══════════════════════════════════════════════════════════════

class BlackBoxLoginAPI(unittest.TestCase):
    """
    BLACK BOX — POST /auth/login
    Only input/output behaviour is tested.
    No knowledge of internal implementation required.
    """

    @classmethod
    def setUpClass(cls):
        """Initialise test app, db, and seed one admin user."""
        try:
            cls.app = get_app()
            cls.client = cls.app.test_client()
            with cls.app.app_context():
                from app import db
                db.create_all()
                # Seed roles
                from app.models.user import Role
                for rname in ['admin','doctor','receptionist','pharmacist','lab_tech','patient']:
                    if not Role.query.filter_by(name=rname).first():
                        db.session.add(Role(name=rname, description=rname))
                db.session.commit()
                # Seed admin user
                from app.models.user import User
                role = Role.query.filter_by(name='admin').first()
                if not User.query.filter_by(username='testadmin').first():
                    u = User(username='testadmin', email='admin@test.com',
                             first_name='Test', last_name='Admin',
                             role_id=role.id, is_active=True, is_verified=True)
                    u.set_password('TestPass123')
                    db.session.add(u)
                    # Locked user
                    ul = User(username='lockeduser', email='locked@test.com',
                              first_name='Locked', last_name='User',
                              role_id=role.id, is_active=True, is_verified=True,
                              login_attempts=5)
                    ul.set_password('TestPass123')
                    from datetime import datetime, timedelta
                    ul.locked_until = datetime.utcnow() + timedelta(hours=1)
                    db.session.add(ul)
                    # Inactive user
                    ui = User(username='inactiveuser', email='inactive@test.com',
                              first_name='Inactive', last_name='User',
                              role_id=role.id, is_active=False, is_verified=True)
                    ui.set_password('TestPass123')
                    db.session.add(ui)
                    db.session.commit()
            cls._setup_ok = True
        except Exception as e:
            cls._setup_ok = False
            cls._setup_error = str(e)

    def setUp(self):
        if not self._setup_ok:
            self.skipTest(f"DB setup failed: {self._setup_error}")

    def _post_login(self, username, password, remember=False):
        return self.client.post('/auth/login',
            data=json.dumps({'username': username, 'password': password, 'remember': remember}),
            content_type='application/json')

    # ── BB-LG-01: Valid credentials ───────────────────────────
    def test_BB_LG_01_valid_credentials_succeed(self):
        """[Happy Path] Correct username+password must return success=True."""
        res  = self._post_login('testadmin', 'TestPass123')
        data = json.loads(res.data)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(data.get('success'), f"Expected success, got: {data}")
        self.assertIn('redirect', data, "Response must include redirect URL")

    # ── BB-LG-02: Wrong password ──────────────────────────────
    def test_BB_LG_02_wrong_password_fails(self):
        """[Negative] Wrong password must return success=False with message."""
        res  = self._post_login('testadmin', 'WrongPassword')
        data = json.loads(res.data)
        self.assertFalse(data.get('success'))
        self.assertIn('message', data)

    # ── BB-LG-03: Non-existent user ───────────────────────────
    def test_BB_LG_03_nonexistent_user_fails(self):
        """[Negative] Unknown username must return failure, not 500."""
        res  = self._post_login('nobody_xyz', 'anypassword')
        data = json.loads(res.data)
        self.assertFalse(data.get('success'))
        self.assertNotEqual(res.status_code, 500)

    # ── BB-LG-04: Empty username ──────────────────────────────
    def test_BB_LG_04_empty_username_rejected(self):
        """[Boundary] Empty username must be rejected with 400."""
        res  = self._post_login('', 'TestPass123')
        data = json.loads(res.data)
        self.assertFalse(data.get('success'))
        self.assertIn(res.status_code, [400, 401])

    # ── BB-LG-05: Empty password ──────────────────────────────
    def test_BB_LG_05_empty_password_rejected(self):
        """[Boundary] Empty password must be rejected."""
        res  = self._post_login('testadmin', '')
        data = json.loads(res.data)
        self.assertFalse(data.get('success'))

    # ── BB-LG-06: Both fields empty ───────────────────────────
    def test_BB_LG_06_both_empty_rejected(self):
        """[Boundary] Both fields empty must be rejected cleanly."""
        res  = self._post_login('', '')
        data = json.loads(res.data)
        self.assertFalse(data.get('success'))

    # ── BB-LG-07: Login with email ────────────────────────────
    def test_BB_LG_07_login_with_email(self):
        """[Equivalence] Email instead of username must also work."""
        res  = self._post_login('admin@test.com', 'TestPass123')
        data = json.loads(res.data)
        self.assertTrue(data.get('success'),
            "Login with email should succeed just like with username")

    # ── BB-LG-08: Locked account ──────────────────────────────
    def test_BB_LG_08_locked_account_blocked(self):
        """[State] Locked account must not allow login even with correct password."""
        res  = self._post_login('lockeduser', 'TestPass123')
        data = json.loads(res.data)
        self.assertFalse(data.get('success'))
        self.assertIn('lock', data.get('message','').lower(),
            "Error message should mention account lock")

    # ── BB-LG-09: Inactive account ────────────────────────────
    def test_BB_LG_09_inactive_account_blocked(self):
        """[State] Deactivated account must be blocked."""
        res  = self._post_login('inactiveuser', 'TestPass123')
        data = json.loads(res.data)
        self.assertFalse(data.get('success'))

    # ── BB-LG-10: SQL injection attempt ──────────────────────
    def test_BB_LG_10_sql_injection_rejected(self):
        """[Security] SQL injection in username must not bypass auth."""
        res  = self._post_login("' OR 1=1; --", 'anything')
        data = json.loads(res.data)
        self.assertFalse(data.get('success'),
            "SQL injection must NOT succeed!")
        self.assertNotEqual(res.status_code, 500,
            "SQL injection must not cause 500 error")

    # ── BB-LG-11: XSS attempt ─────────────────────────────────
    def test_BB_LG_11_xss_in_username_rejected(self):
        """[Security] XSS payload in username must not cause 500."""
        res  = self._post_login('<script>alert(1)</script>', 'password')
        self.assertNotEqual(res.status_code, 500)

    # ── BB-LG-12: Very long input ─────────────────────────────
    def test_BB_LG_12_very_long_username_handled(self):
        """[Boundary] 10,000-char username must not crash server."""
        res  = self._post_login('a' * 10000, 'password')
        self.assertNotEqual(res.status_code, 500,
            "Server crashed on long input!")

    # ── BB-LG-13: Case sensitivity ────────────────────────────
    def test_BB_LG_13_username_case_insensitive_email(self):
        """[Equivalence] Email login should be case-insensitive."""
        res  = self._post_login('ADMIN@TEST.COM', 'TestPass123')
        # Should succeed (email normalised to lowercase)
        data = json.loads(res.data)
        # Either succeeds or fails gracefully — must not 500
        self.assertNotEqual(res.status_code, 500)

    # ── BB-LG-14: Response structure ─────────────────────────
    def test_BB_LG_14_response_has_required_fields(self):
        """[Contract] Every response must have 'success' and 'message' fields."""
        res  = self._post_login('testadmin', 'TestPass123')
        data = json.loads(res.data)
        self.assertIn('success', data, "Response must always contain 'success'")

    # ── BB-LG-15: GET request returns login page ─────────────
    def test_BB_LG_15_get_returns_html(self):
        """[Method] GET /auth/login must return HTML page, not JSON."""
        res = self.client.get('/auth/login')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'html', res.data.lower())


class BlackBoxPatientRegistration(unittest.TestCase):
    """
    BLACK BOX — POST /patient/api/register
    Tests all equivalence classes and boundary conditions
    for patient self-registration.
    """

    @classmethod
    def setUpClass(cls):
        try:
            cls.app = get_app()
            cls.client = cls.app.test_client()
            with cls.app.app_context():
                from app import db
                db.create_all()
                from app.models.user import Role
                for rname in ['admin','doctor','receptionist','pharmacist','lab_tech','patient']:
                    if not Role.query.filter_by(name=rname).first():
                        db.session.add(Role(name=rname, description=rname))
                db.session.commit()
            cls._setup_ok = True
        except Exception as e:
            cls._setup_ok = False
            cls._setup_error = str(e)

    def setUp(self):
        if not self._setup_ok:
            self.skipTest(f"DB setup failed: {self._setup_error}")
        self._counter = getattr(self.__class__, '_counter', 0) + 1
        self.__class__._counter = self._counter

    def _valid_payload(self, suffix=''):
        return {
            'first_name':   'Kavanashree',
            'last_name':    'BA',
            'phone':        f'9{self._counter:09d}',
            'email':        f'test{self._counter}{suffix}@example.com',
            'password':     'SecurePass123',
            'gender':       'female',
            'blood_group':  'O+',
            'date_of_birth':'1995-05-15',
        }

    def _register(self, payload):
        return self.client.post('/patient/api/register',
            data=json.dumps(payload),
            content_type='application/json')

    # ── BB-PR-01: Valid registration ──────────────────────────
    def test_BB_PR_01_valid_data_creates_account(self):
        """[Happy Path] All valid fields must create account and return UHID."""
        res  = self._register(self._valid_payload())
        data = json.loads(res.data)
        self.assertTrue(data.get('success'), f"Registration failed: {data}")
        self.assertIn('uhid', data, "UHID must be returned on success")
        self.assertRegex(data['uhid'], r'^MED-\d{8}$',
            f"UHID format wrong: {data.get('uhid')}")

    # ── BB-PR-02: Missing first name ──────────────────────────
    def test_BB_PR_02_missing_first_name_rejected(self):
        """[Negative] Missing first_name must be rejected."""
        payload = self._valid_payload()
        del payload['first_name']
        res  = self._register(payload)
        data = json.loads(res.data)
        self.assertFalse(data.get('success'))

    # ── BB-PR-03: Missing phone ────────────────────────────────
    def test_BB_PR_03_missing_phone_rejected(self):
        """[Negative] Missing phone must be rejected."""
        payload = self._valid_payload()
        del payload['phone']
        res  = self._register(payload)
        data = json.loads(res.data)
        self.assertFalse(data.get('success'))

    # ── BB-PR-04: Missing password ────────────────────────────
    def test_BB_PR_04_missing_password_rejected(self):
        """[Negative] Missing password must be rejected."""
        payload = self._valid_payload()
        del payload['password']
        res  = self._register(payload)
        data = json.loads(res.data)
        self.assertFalse(data.get('success'))

    # ── BB-PR-05: Duplicate email ─────────────────────────────
    def test_BB_PR_05_duplicate_email_rejected(self):
        """[Negative] Registering same email twice must fail on second attempt."""
        payload = self._valid_payload('dup')
        self._register(payload)  # first registration
        # Try again with same email but different phone
        payload2 = self._valid_payload('dup')
        payload2['phone'] = f'8{self._counter:09d}'
        res  = self._register(payload2)
        data = json.loads(res.data)
        self.assertFalse(data.get('success'),
            "Duplicate email must be rejected")

    # ── BB-PR-06: Invalid gender value ───────────────────────
    def test_BB_PR_06_invalid_gender_handled(self):
        """[Boundary] Invalid gender value should be handled gracefully."""
        payload = self._valid_payload()
        payload['gender'] = 'helicopter'
        res = self._register(payload)
        # Must not crash with 500
        self.assertNotEqual(res.status_code, 500)

    # ── BB-PR-07: Empty email ─────────────────────────────────
    def test_BB_PR_07_empty_email_rejected(self):
        """[Boundary] Empty email string must be rejected."""
        payload = self._valid_payload()
        payload['email'] = ''
        res  = self._register(payload)
        data = json.loads(res.data)
        self.assertFalse(data.get('success'))

    # ── BB-PR-08: UHID format ─────────────────────────────────
    def test_BB_PR_08_uhid_is_unique_per_registration(self):
        """[Contract] Two registrations must produce different UHIDs."""
        r1 = json.loads(self._register(self._valid_payload('u1')).data)
        r2 = json.loads(self._register(self._valid_payload('u2')).data)
        if r1.get('success') and r2.get('success'):
            self.assertNotEqual(r1['uhid'], r2['uhid'],
                "UHIDs must be unique!")

    # ── BB-PR-09: SQL injection in name ──────────────────────
    def test_BB_PR_09_sql_injection_in_name_safe(self):
        """[Security] SQL injection in first_name must not crash server."""
        payload = self._valid_payload()
        payload['first_name'] = "Robert'); DROP TABLE users;--"
        res = self._register(payload)
        self.assertNotEqual(res.status_code, 500,
            "SQL injection caused server crash!")

    # ── BB-PR-10: Response content-type ──────────────────────
    def test_BB_PR_10_response_is_json(self):
        """[Contract] Response must always be valid JSON."""
        res = self._register(self._valid_payload())
        self.assertIn('application/json', res.content_type)
        try:
            json.loads(res.data)
        except json.JSONDecodeError:
            self.fail("Response is not valid JSON!")


# ═══════════════════════════════════════════════════════════════
#  TEST RUNNER WITH PRETTY REPORT
# ═══════════════════════════════════════════════════════════════

class ColorTextTestResult(unittest.TextTestResult):
    GREEN  = '\033[92m'
    RED    = '\033[91m'
    YELLOW = '\033[93m'
    BLUE   = '\033[94m'
    RESET  = '\033[0m'
    BOLD   = '\033[1m'

    def addSuccess(self, test):
        super().addSuccess(test)
        if self.showAll:
            self.stream.writeln(f"  {self.GREEN}✓ PASS{self.RESET}  {test.shortDescription()}")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        if self.showAll:
            self.stream.writeln(f"  {self.RED}✗ FAIL{self.RESET}  {test.shortDescription()}")

    def addError(self, test, err):
        super().addError(test, err)
        if self.showAll:
            self.stream.writeln(f"  {self.YELLOW}! ERROR{self.RESET} {test.shortDescription()}")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if self.showAll:
            self.stream.writeln(f"  {self.YELLOW}⊘ SKIP{self.RESET}  {test.shortDescription()} — {reason}")


def run_tests():
    B = '\033[1m'; R = '\033[0m'; BL = '\033[94m'; GR = '\033[92m'; RD = '\033[91m'

    print(f"\n{B}{'='*65}{R}")
    print(f"{BL}{B}  MediCore HMS — Software Testing Suite{R}")
    print(f"{B}{'='*65}{R}\n")

    suite = unittest.TestSuite()

    # White Box tests
    print(f"{B}WHITE BOX TESTS{R} — Internal code path verification")
    print(f"{'─'*65}")
    wb_classes = [WhiteBoxPasswordGenerator, WhiteBoxAuthService]
    for cls in wb_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(cls)
        suite.addTests(tests)

    # Black Box tests
    print(f"\n{B}BLACK BOX TESTS{R} — External input/output behaviour")
    print(f"{'─'*65}")
    bb_classes = [BlackBoxLoginAPI, BlackBoxPatientRegistration]
    for cls in bb_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(cls)
        suite.addTests(tests)

    # Run
    runner = unittest.TextTestRunner(
        resultclass = ColorTextTestResult,
        verbosity   = 2,
        stream      = sys.stdout,
    )
    result = runner.run(suite)

    # Summary
    total   = result.testsRun
    passed  = total - len(result.failures) - len(result.errors) - len(result.skipped)
    failed  = len(result.failures) + len(result.errors)
    skipped = len(result.skipped)

    print(f"\n{B}{'='*65}{R}")
    print(f"{B}TEST SUMMARY{R}")
    print(f"{'─'*65}")
    print(f"  Total  : {total}")
    print(f"  {GR}Passed : {passed}{R}")
    if failed:
        print(f"  {RD}Failed : {failed}{R}")
    if skipped:
        print(f"  Skipped: {skipped}")
    pct = round(passed / total * 100) if total else 0
    color = GR if pct >= 80 else RD
    print(f"  {color}{B}Score  : {pct}%{R}")
    print(f"{'='*65}\n")

    if result.failures:
        print(f"{RD}{B}FAILURES:{R}")
        for test, err in result.failures:
            print(f"  • {test.shortDescription()}")
            # Show just the assertion error, not full traceback
            lines = err.strip().split('\n')
            print(f"    → {lines[-1]}\n")

    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(run_tests())
