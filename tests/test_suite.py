"""
MediCore HMS — White Box Test Suite
=====================================
Module 1 : generate_password()   — app/services/auth_service.py
Module 2 : generate_username()   — app/services/auth_service.py

Coverage : Statement, Branch, Loop, Path

Run:
  python tests/test_suite.py
  python -m pytest tests/test_suite.py -v
"""

import unittest
import secrets
import string
import sys
import os
import threading
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# ═══════════════════════════════════════════════════════════════
#  STANDALONE COPIES OF FUNCTIONS UNDER TEST
#  Copied from app/services/auth_service.py so tests run
#  without any Flask / DB / application-context dependency.
# ═══════════════════════════════════════════════════════════════

def generate_password(length=10):
    """
    SOURCE: app/services/auth_service.py
    Generate a strong alphanumeric password.
    No special chars (%, $, @, #) — they break DATABASE_URL.

    Internal structure:
        chars  = [a-zA-Z0-9]
        LOOP:
            pwd = random chars of `length`
            IF any uppercase  (Branch A)
            AND any lowercase (Branch B)
            AND any digit     (Branch C)
            THEN return pwd
    """
    chars = string.ascii_letters + string.digits          # Statement 1
    while True:                                            # Loop start
        pwd = ''.join(secrets.choice(chars)               # Statement 2
                      for _ in range(length))
        if (any(c.isupper() for c in pwd) and             # Branch A
                any(c.islower() for c in pwd) and         # Branch B
                any(c.isdigit() for c in pwd)):           # Branch C
            return pwd                                     # Loop exit


def generate_username(first_name, last_name, role_name,
                      existing_usernames=None):
    """
    SOURCE: app/services/auth_service.py (adapted for standalone testing)
    Generate username like dr.sharma, rec.patel etc.
    existing_usernames replaces the DB query — no Flask context needed.

    Internal structure:
        prefix = role map lookup
        base   = prefix + '.' + last_name (alphanumeric + dot only)
        LOOP: while collision → append counter
    """
    existing = set(existing_usernames or [])
    prefixes = {
        'doctor':        'dr',
        'receptionist':  'rec',
        'pharmacist':    'ph',
        'lab_tech':      'lab',
        'admin':         'admin',
        'patient':       'pt',
    }
    prefix   = prefixes.get(role_name, 'user')            # Statement 3
    base     = f'{prefix}.{(last_name or first_name or "user").lower()}'
    base     = ''.join(c for c in base                    # Statement 4
                       if c.isalnum() or c == '.')
    username = base
    counter  = 1
    while username in existing:                            # Collision loop
        username = f'{base}{counter}'
        counter += 1
    return username


# ═══════════════════════════════════════════════════════════════
#  WHITE BOX MODULE 1 — generate_password()
#  Techniques: Branch, Loop, Statement Coverage
# ═══════════════════════════════════════════════════════════════

class WhiteBoxPasswordGenerator(unittest.TestCase):
    """
    WHITE BOX testing of generate_password()
    Source: app/services/auth_service.py

    Code map:
    ┌──────────────────────────────────────────────────────────┐
    │ S1: chars = ascii_letters + digits                        │
    │ LOOP:                                                     │
    │   S2: pwd = random sample of `length` chars              │
    │   Branch A: if any(upper)                                 │
    │   Branch B: and any(lower)                                │
    │   Branch C: and any(digit) → return pwd                  │
    └──────────────────────────────────────────────────────────┘
    """

    # ── WB-PG-01: Statement — default parameter path ──────────
    def test_WB_PG_01_default_length_is_ten(self):
        """[Statement] Default length=10 produces exactly 10 characters."""
        pwd = generate_password()
        self.assertEqual(len(pwd), 10,
            f"Expected length=10, got {len(pwd)}")

    # ── WB-PG-02: Statement — custom length path ──────────────
    def test_WB_PG_02_custom_length_six(self):
        """[Statement] length=6 produces exactly 6 characters."""
        pwd = generate_password(length=6)
        self.assertEqual(len(pwd), 6,
            f"Expected length=6, got {len(pwd)}")

    # ── WB-PG-03: Statement — upper boundary length ───────────
    def test_WB_PG_03_custom_length_sixteen(self):
        """[Statement] length=16 produces exactly 16 characters."""
        pwd = generate_password(length=16)
        self.assertEqual(len(pwd), 16,
            f"Expected length=16, got {len(pwd)}")

    # ── WB-PG-04: Branch A — uppercase must be present ────────
    def test_WB_PG_04_branch_A_contains_uppercase(self):
        """
        [Branch A] any(c.isupper()) must be True before returning.
        If False, the loop continues — return is unreachable without uppercase.
        """
        for i in range(20):
            with self.subTest(run=i+1):
                pwd = generate_password()
                self.assertTrue(any(c.isupper() for c in pwd),
                    f"Branch A failed: no uppercase in '{pwd}'")

    # ── WB-PG-05: Branch B — lowercase must be present ────────
    def test_WB_PG_05_branch_B_contains_lowercase(self):
        """
        [Branch B] any(c.islower()) must be True before returning.
        If False, the loop continues — return is unreachable without lowercase.
        """
        for i in range(20):
            with self.subTest(run=i+1):
                pwd = generate_password()
                self.assertTrue(any(c.islower() for c in pwd),
                    f"Branch B failed: no lowercase in '{pwd}'")

    # ── WB-PG-06: Branch C — digit must be present ────────────
    def test_WB_PG_06_branch_C_contains_digit(self):
        """
        [Branch C] any(c.isdigit()) must be True before returning.
        If False, the loop continues — return is unreachable without digit.
        """
        for i in range(20):
            with self.subTest(run=i+1):
                pwd = generate_password()
                self.assertTrue(any(c.isdigit() for c in pwd),
                    f"Branch C failed: no digit in '{pwd}'")

    # ── WB-PG-07: Statement S1 — charset alphanumeric only ────
    def test_WB_PG_07_charset_alphanumeric_only(self):
        """
        [Statement S1] chars = ascii_letters + digits only.
        No character outside [a-zA-Z0-9] can ever appear.
        """
        valid = set(string.ascii_letters + string.digits)
        for i in range(50):
            with self.subTest(run=i+1):
                pwd = generate_password()
                bad = set(pwd) - valid
                self.assertEqual(len(bad), 0,
                    f"Non-alphanumeric chars {bad} found in '{pwd}'")

    # ── WB-PG-08: Statement S1 — URL-breaking chars absent ────
    def test_WB_PG_08_no_url_breaking_chars(self):
        """
        [Statement S1] %, $, @, # must NEVER appear.
        REGRESSION: original bug required these chars (not in charset)
        → infinite loop → server crash → 'Network error' on login.
        """
        forbidden = {'%', '$', '@', '#'}
        for i in range(100):
            with self.subTest(run=i+1):
                pwd = generate_password()
                found = forbidden & set(pwd)
                self.assertEqual(len(found), 0,
                    f"URL-breaking chars {found} in '{pwd}'")

    # ── WB-PG-09: Loop — uniqueness / randomness check ────────
    def test_WB_PG_09_loop_produces_unique_passwords(self):
        """
        [Loop] Each loop iteration must produce a statistically unique result.
        100 calls → expect > 95 unique passwords (secrets.choice is random).
        """
        passwords = [generate_password() for _ in range(100)]
        unique = set(passwords)
        self.assertGreater(len(unique), 95,
            f"Too many duplicates: only {len(unique)} unique out of 100")

    # ── WB-PG-10: Loop — termination, no infinite loop ────────
    def test_WB_PG_10_loop_terminates_within_one_second(self):
        """
        [Loop Termination] The while-loop must exit in < 1.5 seconds.
        REGRESSION TEST: original code had impossible loop condition
        (required special chars not in charset) → infinite loop.
        Uses threading.Timer — works on Windows (no SIGALRM needed).
        """
        completed = [False]

        def _run():
            for _ in range(200):
                generate_password()
            completed[0] = True

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=1.5)

        self.assertTrue(completed[0],
            "generate_password() did not finish in 1.5s — INFINITE LOOP detected!")


# ═══════════════════════════════════════════════════════════════
#  WHITE BOX MODULE 2 — generate_username()
#  Techniques: Branch, Loop, Path Coverage
# ═══════════════════════════════════════════════════════════════

class WhiteBoxUsernameGenerator(unittest.TestCase):
    """
    WHITE BOX testing of generate_username()
    Source: app/services/auth_service.py

    Code map:
    ┌──────────────────────────────────────────────────────────┐
    │ S3: prefix = prefixes.get(role, 'user')                   │
    │ S4: base   = prefix + '.' + last_name.lower()            │
    │     base   = filter(isalnum or '.')   ← char filter      │
    │     username = base                                        │
    │ LOOP: while username in existing:                          │
    │     username = base + counter                              │
    │     counter += 1                                           │
    │ return username                                            │
    └──────────────────────────────────────────────────────────┘
    """

    # ── WB-UN-01: Branch — doctor prefix ──────────────────────
    def test_WB_UN_01_doctor_maps_to_dr_prefix(self):
        """[Branch] role='doctor' → prefixes['doctor']='dr' → starts 'dr.'"""
        uname = generate_username('Kavanashree', 'BA', 'doctor')
        self.assertTrue(uname.startswith('dr.'),
            f"Expected 'dr.' prefix, got: '{uname}'")

    # ── WB-UN-02: Branch — receptionist prefix ─────────────────
    def test_WB_UN_02_receptionist_maps_to_rec_prefix(self):
        """[Branch] role='receptionist' → prefix='rec' → starts 'rec.'"""
        uname = generate_username('Riya', 'Shah', 'receptionist')
        self.assertTrue(uname.startswith('rec.'),
            f"Expected 'rec.' prefix, got: '{uname}'")

    # ── WB-UN-03: Branch — pharmacist prefix ───────────────────
    def test_WB_UN_03_pharmacist_maps_to_ph_prefix(self):
        """[Branch] role='pharmacist' → prefix='ph' → starts 'ph.'"""
        uname = generate_username('Priya', 'Nair', 'pharmacist')
        self.assertTrue(uname.startswith('ph.'),
            f"Expected 'ph.' prefix, got: '{uname}'")

    # ── WB-UN-04: Branch — lab_tech prefix ─────────────────────
    def test_WB_UN_04_lab_tech_maps_to_lab_prefix(self):
        """[Branch] role='lab_tech' → prefix='lab' → starts 'lab.'"""
        uname = generate_username('Arun', 'Kumar', 'lab_tech')
        self.assertTrue(uname.startswith('lab.'),
            f"Expected 'lab.' prefix, got: '{uname}'")

    # ── WB-UN-05: Branch — unknown role default ─────────────────
    def test_WB_UN_05_unknown_role_uses_user_default(self):
        """[Branch] Unknown role → prefixes.get(role, 'user') → starts 'user.'"""
        uname = generate_username('Test', 'Person', 'unknown_xyz')
        self.assertTrue(uname.startswith('user.'),
            f"Expected 'user.' for unknown role, got: '{uname}'")

    # ── WB-UN-06: Statement S4 — special chars stripped ────────
    def test_WB_UN_06_special_chars_stripped(self):
        """
        [Statement S4] Char filter: only isalnum() or '.' passes.
        Input: last_name="O'Brien" → apostrophe stripped → safe username.
        """
        uname = generate_username('Aarav', "O'Brien", 'doctor')
        allowed = set('abcdefghijklmnopqrstuvwxyz0123456789.')
        bad = set(uname.lower()) - allowed
        self.assertEqual(len(bad), 0,
            f"Unsafe chars {bad} in username: '{uname}'")

    # ── WB-UN-07: Statement S4 — lowercase enforced ─────────────
    def test_WB_UN_07_username_is_all_lowercase(self):
        """[Statement S4] last_name.lower() → username must be all lowercase."""
        uname = generate_username('Raj', 'SHARMA', 'doctor')
        self.assertEqual(uname, uname.lower(),
            f"Username has uppercase: '{uname}'")

    # ── WB-UN-08: Loop 0 iterations — no collision ──────────────
    def test_WB_UN_08_zero_iterations_no_collision(self):
        """
        [Loop — 0 iterations] existing=[] → while condition is False immediately.
        Loop body never executes. Username = base with no suffix.
        """
        uname = generate_username('Test', 'User', 'doctor',
                                  existing_usernames=[])
        self.assertEqual(uname, 'dr.user',
            f"Expected 'dr.user' (no collision), got: '{uname}'")

    # ── WB-UN-09: Loop 1 iteration — one collision ──────────────
    def test_WB_UN_09_one_iteration_one_collision(self):
        """
        [Loop — 1 iteration] 'dr.user' is taken.
        Loop runs once: username = 'dr.user' + '1' = 'dr.user1'.
        """
        uname = generate_username('Test', 'User', 'doctor',
                                  existing_usernames=['dr.user'])
        self.assertEqual(uname, 'dr.user1',
            f"Expected 'dr.user1' after 1 collision, got: '{uname}'")

    # ── WB-UN-10: Loop 3 iterations — multiple collisions ───────
    def test_WB_UN_10_three_iterations_multiple_collisions(self):
        """
        [Loop — 3 iterations] 'dr.user', 'dr.user1', 'dr.user2' all taken.
        Loop runs 3 times, counter increments 1→2→3.
        Result must be 'dr.user3'.
        """
        taken = ['dr.user', 'dr.user1', 'dr.user2']
        uname = generate_username('Test', 'User', 'doctor',
                                  existing_usernames=taken)
        self.assertEqual(uname, 'dr.user3',
            f"Expected 'dr.user3' after 3 collisions, got: '{uname}'")


# ═══════════════════════════════════════════════════════════════
#  PRETTY TEST RUNNER
# ═══════════════════════════════════════════════════════════════

class PrettyResult(unittest.TextTestResult):
    GR = '\033[92m'; RD = '\033[91m'; YL = '\033[93m'; RS = '\033[0m'

    def addSuccess(self, test):
        super().addSuccess(test)
        if self.showAll:
            self.stream.writeln(
                f"  {self.GR}✓ PASS{self.RS}  {test.shortDescription()}")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        if self.showAll:
            self.stream.writeln(
                f"  {self.RD}✗ FAIL{self.RS}  {test.shortDescription()}")

    def addError(self, test, err):
        super().addError(test, err)
        if self.showAll:
            self.stream.writeln(
                f"  {self.RD}! ERROR{self.RS} {test.shortDescription()}")


def run_tests():
    B = '\033[1m'; R = '\033[0m'
    GR = '\033[92m'; RD = '\033[91m'; BL = '\033[94m'; YL = '\033[93m'; CY = '\033[96m'

    print(f"\n{B}{'═'*65}{R}")
    print(f"{BL}{B}    MediCore HMS — White Box Test Suite{R}")
    print(f"{B}{'═'*65}{R}")
    print(f"\n  {CY}Project  :{R} MediCore HMS — Hospital Management System")
    print(f"  {CY}Method   :{R} White Box Testing")
    print(f"  {CY}Coverage :{R} Statement · Branch · Loop · Path")
    print(f"  {CY}Modules  :{R} app/services/auth_service.py")

    suite = unittest.TestSuite()

    print(f"\n{B}{YL}MODULE 1 — generate_password()  [10 tests]{R}")
    print(f"{'─'*65}")
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        WhiteBoxPasswordGenerator))

    print(f"\n{B}{YL}MODULE 2 — generate_username()  [10 tests]{R}")
    print(f"{'─'*65}")
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        WhiteBoxUsernameGenerator))

    print()
    runner = unittest.TextTestRunner(
        resultclass=PrettyResult, verbosity=2, stream=sys.stdout)
    result = runner.run(suite)

    total  = result.testsRun
    failed = len(result.failures) + len(result.errors)
    passed = total - failed - len(result.skipped)
    pct    = round(passed / total * 100) if total else 0
    color  = GR if pct == 100 else (YL if pct >= 80 else RD)

    print(f"\n{B}{'═'*65}{R}")
    print(f"{B}  RESULTS{R}")
    print(f"{'─'*65}")
    print(f"  Module 1 │ generate_password() │ 10 tests")
    print(f"  Module 2 │ generate_username() │ 10 tests")
    print(f"{'─'*65}")
    print(f"  Total    : {total}")
    print(f"  {GR}Passed   : {passed}{R}")
    if failed:
        print(f"  {RD}Failed   : {failed}{R}")
    print(f"\n  {color}{B}Score : {pct}%  {'✓ ALL TESTS PASSED' if pct==100 else '✗ SOME TESTS FAILED'}{R}")
    print(f"{'═'*65}\n")

    if result.failures or result.errors:
        print(f"{RD}{B}FAILURES:{R}")
        for test, err in result.failures + result.errors:
            print(f"  • {test.shortDescription()}")
            last = [l for l in err.strip().split('\n') if l.strip()][-1]
            print(f"    → {last}\n")

    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(run_tests())
