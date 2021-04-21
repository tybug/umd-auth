from umdauth import UMDAuth
from config import username, password, auth_cookies, identity_jsession_id

auth = UMDAuth(username, password, auth_cookies, identity_jsession_id)
auth.send_daily_symptom_survey()
