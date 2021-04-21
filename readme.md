## Umd Auth

Provides methods to programmatically take actions with umd on your behalf.

Currently you can submit a daily covid symptom survey (telling them you have no symptoms) or get your dining dollars balance. Adding new functionality is easy (and will be implemented mostly as I am either interested in it or need it).

### Usage

To authenticate with umd, you need two things: your username and password, and a method of passing the 2fa check. We will use backup 2fa codes to pass the 2fa check automatically.

To get backup codes, go to <https://identity.umd.edu/mfaprofile> and click "Generate Codes" under "One Time Use Codes". We will refer to these as "auth codes".

Now create a file called "codes.txt" in this directory and copy your auth codes into the file, one code per line. Technically, you only need to give umdauth a single auth code - we automatically request new auth codes when only a single auth code remains, so this is the only time you will have to manually give umdauth backup codes.

One auth code is consumed each time you instantiate umdauth.
(TODO: document how to cache your authentication, and not consume an auth code upon instantiation, by passing `auth_cookies` to `UMDAuth`. This functionality already exists).

And that's it. Example usage follows. Obviously, fill in your username and password.

```python
from umdauth import UMDAuth

# the same username and password you use to log on to testudo
username = ""
password = ""

auth = UMDAuth(username, password)

# get your current dining dollars balance
dd = auth.get_dining_dollars()
print(dd.total_amount, dd.current_amount, dd.rollover_amount)

# Tell umd you have no covid symptoms - equivalent to filling out the daily
# symptom survey manually.
# fair warning: this is submitting a survey on your behalf. I do not guarantee
# that it won't accidentally mark you as having symptoms (though it works
# properly for myself).
# auth.send_daily_symptom_survey()
```


### Disclaimer

I'm releasing this in case others who are similarly inclined towards automation of their umd account are interested in using it or referencing my implementation.

However - this is obviously an abuse of umd's auth system. Especially when dealing with POSTing data to umd on your behalf, things get sketchy quickly.

This risk is present with any library that automates access to priveledged data like course schedules or canvas. If you're not willing to accept that risk, please don't use this library.
