import os
os.environ['FLASK_ENV'] = 'development'

from app import create_app
from app.models.user import HospitalSetting

app = create_app()
with app.app_context():
    HospitalSetting.set_value('razorpay_key_id',     'rzp_test_SauOWZ2CdhAfD4')
    HospitalSetting.set_value('razorpay_key_secret',  '4KF2HEXChj3CcECVsXiq93wx')
    print("✔ Razorpay keys saved to database")
