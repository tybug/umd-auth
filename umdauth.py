from pathlib import Path
import urllib
import json
import re
from dataclasses import dataclass, field

import requests
from requests.utils import add_dict_to_cookiejar
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


class UMDAuth:
    """
    Provides methods to take actions with umd on your behalf. You can, for
    instance, submit a daily covid symptom survey (telling them you have no
    symptoms), or get your dining dollars balance.

    Authentication happens automatically. You must provide at least one auth
    code (ie backup code) in a ``codes.txt`` file in the same directory as this
    file to kickstart the authentication. From there, we will automatically
    request new auth codes as necessary, and write them back to ``codes.txt``.
    We consume one auth code each time we authenticate.

    """
    CODES_PATH = Path(__file__).parent / "codes.txt"

    def __init__(self, username, password, auth_cookies=None,
        identity_jsession_id=None):
        self.username = username
        self.password = password
        # the cookies we get after we auth, which is all we need to get access
        # to other umd websites.
        self.auth_cookies = auth_cookies
        self.identity_jsession_id = identity_jsession_id

        if not self.CODES_PATH.exists():
            raise FileNotFoundError("Could not find a codes.txt file at "
                f"{self.CODES_PATH}.")

        self.codes = []
        with open(self.CODES_PATH) as f:
            for line in f.readlines():
                # allow empty lines
                if line.isspace():
                    continue
                code = line.strip()
                self.codes.append(code)

        print(f"initialized with codes {self.codes}")


    def _new_session(self):
        """
        A new `requests.Session` which is authenticated with umd and can be
        used to access umd websites.

        "authenticated" here just means that this session has the `auth_cookies`
        we retrieved set, which is all being authenticated means to umd.
        """
        print("creating a new session")
        if not self.auth_cookies:
            self.authenticate()
        session = requests.Session()
        add_dict_to_cookiejar(session.cookies, self.auth_cookies)
        session.cookies.set("JSESSION", self.identity_jsession_id,
            domain="identity.umd.edu", path="/")
        return session

    def authenticate(self):
        """
        Authenticates with umd using https://identity.umd.edu/mfaprofile as
        the base request. Authenticating with identity.umd.edu gives us the most
        access to other sites (except notably
        https://app.testudo.umd.edu/main/profile), which is why it was chosen.

        Notes
        -----
        Interestingly, websites under umd control seem to have a hierarchy of
        some kind. My best current approximation of this hierarchy is a
        partially ordered set. In the notation below, (a, b) means that "a
        grants access to b". So, the "higher up" in the hierarchy a website is,
        the more sites it grants access to.

        By "grants access" I mean that if you use CAS to log into website a,
        then you can freely access website b without needing ot re-authenticate.
        Note that the opposite is not necessarily true.

        1 = https://identity.umd.edu/mfaprofile
        2 = https://app.testudo.umd.edu/main/profile
        3 = http://umd.instructure.com/
        4 = https://return.umd.edu/covid/returnstatus
        5 = https://dsonline2.umd.edu/dpms/cas.do

        (1, 3)
        (1, 4)
        (1, 5)
        (2, 3)
        (2, 4)
        (2, 5)
        (3, 5)
        (4, 5)

        Sites 1 and 2 are equally high up in the hierarchy, but neither grants
        access to the other. So we have to pick one to authenticate with. I
        chose 1. In the future we may authenticate with both (or only as
        necessary for 2) for maximum coverage.

        Warnings
        --------
        We're making more than a few requests in this method, so this could take
        multiple seconds to complete (around 5-6 seconds for me).
        """
        generate_codes_after = False
        if len(self.codes) == 0:
            raise ValueError("Need at least one authentication code to log in.")
        if len(self.codes) == 1:
            # we're down to our last code - authenticate and then generate
            # another set.
            print("down to our last code, generating more after this "
                "authentication")
            generate_codes_after = True

        # use up the first code available (starting from the front of the list)
        code = self.codes.pop(0)
        print(f"authenticating with code {code}")

        # A useful reference: "Detailed Trace of a Shibboleth Login".
        # https://docs.shib.ncsu.edu/docs/shiblogindetails.html

        r = requests.get("https://identity.umd.edu/mfaprofile")
        jsession_id = r.history[2].cookies["JSESSIONID"]

        cookies = {"JSESSIONID": jsession_id}
        data = {
            "j_username": self.username,
            "j_password": self.password,
            "_eventId_proceed": ""
        }
        r = requests.post("https://shib.idm.umd.edu/shibboleth-idp/profile/cas"
            "/login?execution=e1s1", data=data, cookies=cookies)
        # sanity check to ensure our request / jsession id was accepted
        assert ("Please complete your multi-factor authentication "
            "using Duo.") in r.text

        umd_shib_url = r.url

        # There's an iframe on this page (the duo mobile 2fa element) which
        # makes some requests for us. We need to get the source code of that
        # iframe in order to replicate the requests by hand. Duo has a js
        # library that sets the iframe source based on some parameters in the
        # source code of this page, so we replicate that js code here to create
        # the iframe url and retrieve its source.
        #
        # The duo js code is minified on the umd page, but an unmified version
        # (that seems to be accurate as far as I can tell) can be found here:
        # http://shibboleth.net/pipermail/commits/2017-September/031081.html.
        soup = BeautifulSoup(r.text, features="lxml")
        duo_iframe = soup.find(id="duo_iframe")
        duo_host = duo_iframe.get("data-host")
        duo_sig_request = duo_iframe.get("data-sig-request")

        duo_sig = duo_sig_request.split(":")[0]
        app_sig = duo_sig_request.split(":")[1]


        # Apparently javascript's encodeURIComponent function (which we are
        # replicating here) replaces "/" as well, so we pass `safe=""`` to
        # emulate this.
        current_url_encoded = urllib.parse.quote(umd_shib_url, safe="")

        duo_iframe_source_url = (f"https://{duo_host}/frame/web/v1/auth?tx="
            f"{duo_sig}&parent={current_url_encoded}&v=2.6")

        options = Options()
        options.headless = True
        driver = webdriver.Chrome(Path(__file__).parent / "chromedriver",
            options=options)
        driver.get(duo_iframe_source_url)
        # TODO this errors with "list index out of range" randomly - race
        # condition somewhere? I just retry whenever I hit that error currently.
        sid = driver.current_url.split("sid=")[1]
        sid = urllib.parse.unquote(sid)

        data = {
            "sid": sid,
            "device": "phone1",
            "factor": "Passcode",
            "passcode": f"{code}",
            "out_of_date": "False",
            "days_out_of_date": "0",
            "days_to_block": "None"
        }
        r = requests.post(f"https://{duo_host}/frame/prompt", data=data)
        txid = json.loads(r.content)["response"]["txid"]

        data = {"sid": sid, "txid": txid}
        r = requests.post(f"https://{duo_host}/frame/status", data=data)

        data = {"sid": sid}
        r = requests.post(f"https://{duo_host}/frame/status/{txid}", data=data)
        auth_sig = json.loads(r.content)["response"]["cookie"]

        sig_response = f"{auth_sig}:{app_sig}"
        data = {"_eventId": "proceed", "sig_response": sig_response}

        session = requests.Session()
        add_dict_to_cookiejar(session.cookies, cookies)

        r = session.post(umd_shib_url, data=data, cookies=cookies)

        # ``len(history)`` used to be 2, but umd recently introduced a screen
        # which would show if you haven't completed the daily symptom survey.
        # The ``if``` branch deals with this scenario. the ``else`` branch deals
        # with the 'normal' scenario of having your daily symptom survey
        # completed (which the login process will presumably go back to by
        # default when the survey is no longer a thing).
        assert len(r.history) != 0
        print(f"len(r.history): {len(r.history)}")
        if len(r.history) == 1:
            shib_idp_session = (r.history[0].headers["set-cookie"]
                                    .split("shib_idp_session=")[1]
                                    .split(";")[0])

            umd_shib_url_ = umd_shib_url[:-1] + "3&_eventId_proceed=1"
            r = session.get(umd_shib_url_)

            cookie = r.history[1].headers["set-cookie"]
            cookie = cookie.split("JSESSIONID=")[1]
            cookie = cookie.split(";")[0]

            self.identity_jsession_id = cookie
        else:
            shib_idp_session = (r.history[0].headers["set-cookie"]
                                           .split("shib_idp_session=")[1]
                                           .split(";")[0])

            # we're actually issued a *new* JSESSIONID just for the identity.umd.edu
            # site. If we attempt to make requests with our first (and still valid)
            # JSESSSIONID, they will be rejected, so store this new JSESSIONID for
            # later use (if we want to make requests to identity.umd.edu later).
            #
            # As far as I can tell, this doesn't occur for other websites. They will
            # still accept the original JSESSIONID and don't issue a new one to us.
            identity_jsession_id = (r.history[1].headers["set-cookie"]
                                                   .split("JSESSIONID=")[1]
                                                   .split(";")[0])
            self.identity_jsession_id = identity_jsession_id


        # With these two cookies, we are basically a god. We can make a request
        # to any umd website with full authentication permissions.
        cookies = {
            "JSESSIONID": jsession_id,
            "shib_idp_session": shib_idp_session
        }
        self.auth_cookies = cookies

        print("Authenticated. Creds: ", self.auth_cookies,
            self.identity_jsession_id)

        # we popped a code off our codes list at the beginning of this method,
        # so we need to remove it from our codes file as wll.
        self._write_codes()

        if generate_codes_after:
            self.generate_new_codes()

    def generate_new_codes(self):
        print("generating new codes")
        session = self._new_session()

        data = {
            "printBypassCodes": "Generate Codes",
            "duoAttributes.bypassCount": "10"
        }

        session.cookies.set("JSESSIONID", self.identity_jsession_id)
        r = session.post("https://identity.umd.edu/mfaprofile", data=data)
        soup = BeautifulSoup(r.content, features="lxml")
        print_window = soup.find(id="printWindow")

        codes = []
        for code_div in print_window.find_all("div",
            class_="SubDisplayElementFlex"):
            codes.append(code_div.text)

        # our old codes are invalidate now, so overwrite them, both in the file
        # and in our `self.codes`.
        self.codes = codes
        self._write_codes()

        return codes

    def send_daily_symptom_survey(self):
        print("sending daily symptom survey")
        session = self._new_session()

        r = session.get("https://return.umd.edu/api/daily/")
        data = json.loads(r.content)
        print(f"received data {data} from return.umd.edu/api/daily")
        data["survey"]["symptomNone"] = True
        print(f"sending response of {data} to daily symptom survey")

        # we have to set the x-xsrf-token header for our POST to be accepted,
        # even though it's already set in the cookie header.
        headers = {
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json;charset=UTF-8',
            "x-xsrf-token": session.cookies.get("XSRF-TOKEN")
        }

        url = ("https://return.umd.edu/api/daily?symptomsSaturday=false"
               "&symptomsSunday=false&lateShift=false")
        r = session.post(url, headers=headers, json=data)

    def get_dining_dollars(self):
        session = self._new_session()
        # we have to make this request first, before any others, or our
        # authentication from other umd sites doesn't carry over
        session.get("https://dsonline2.umd.edu/dpms/cas.do")

        r = session.get("https://dsonline2.umd.edu/dpms/baltrans.do")
        soup = BeautifulSoup(r.text, features="lxml")
        amounts = soup.select(".card")[0].find_all(text=re.compile(r".*\$.*"))
        amounts = [float(amount.strip().replace("$", "")) for amount in amounts]
        # first element is current amount of dining dollars, second is
        # current amount of rollover dining dollars
        current = amounts[0]
        rollover = amounts[1]
        # TODO: add transaction history as well
        return DiningDollars(current, rollover)

    def _write_codes(self):
        print(f"writing codes {self.codes} to file")
        with open(self.CODES_PATH, "w") as f:
            str_codes = [str(code) for code in self.codes]
            write_str = "\n".join(str_codes)
            f.write(write_str)


@dataclass
class DiningDollars:
    current_amount: float
    rollover_amount: float
    total_amount: float = field(init=False)

    def __post_init__(self):
        self.total_amount = self.current_amount + self.rollover_amount
