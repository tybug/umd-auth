from umdauth import UMDAuth
from config import username, password, auth_cookies, identity_jsession_id

auth = UMDAuth(username, password, auth_cookies, identity_jsession_id)

# get your current dining dollars balance
dd = auth.get_dining_dollars()
print(dd.total_amount, dd.current_amount, dd.rollover_amount)

# Tell umd you have no covid symptoms - equivalent to filling out the daily
# symptom survey manually.
# fair warning: this is submitting a survey on your behalf. I do not guarantee
# that it won't accidentally mark you as having symptoms (though it works
# properly for myself).
# auth.send_daily_symptom_survey()
