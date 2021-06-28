from datetime import datetimes
from bs4 import BeautifulSoup
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from time import sleep

import urllib.request

import private_config as config

APPOINTMNET_URL_PREFIX = "https://telegov.njportal.com"

TYPE_CODES = {
  "INITIAL PERMIT (NOT FOR KNOWLEDGE TEST)": 15,
  "CDL PERMIT OR ENDORSEMENT - (NOT FOR KNOWLEDGE TEST)": 14,
  "REAL ID": 12,
  "NON-DRIVER ID": 16,
  "KNOWLEDGE TESTING": 17,
  "RENEWAL: LICENSE OR NON-DRIVER ID": 11,
  "RENEWAL: CDL": 6,
  "TRANSFER FROM OUT OF STATE": 7,
  "NEW TITLE OR REGISTRATION": 8,
  "SENIOR NEW TITLE OR REGISTRATION (65+)": 9,
  "REGISTRATION RENEWAL": 10,
  "TITLE DUPLICATE/REPLACEMENT": 13,
}

MVC_LOCATION_CODES = {
  "TRANSFER FROM OUT OF STATE": {
    "OAKLAND": 58,
    "PATERSON": 59,
    "LODI": 55,
    "WAYNE": 67,
    "RANDOLPH": 61,
    "NORTH BERGEN": 57,
    "NEWARK": 56,
    "BAYONNE": 47,
    "RAHWAY": 60,
    "SOUTH PLAINFIELD": 63,
    "EDISON": 52,
    "FLEMINGTON": 53,
    "BAKERS BASIN": 46,
    "FREEHOLD": 54,
    "EATONTOWN": 51,
    "TOMS RIVER": 65,
    "DELANCO": 50,
    "CAMDEN": 49,
    "WEST DEPTFORD": 68,
    "SALEM": 64,
    "VINELAND": 66,
    "CARDIFF": 48,
    "RIO GRANDE": 62
  }
}

APPOINTMENT_TEMPLATE_URL = "https://telegov.njportal.com/njmvc/AppointmentWizard/{type_code}/{location_code}"

SLACK_CLIENT = WebClient(token=config.SLACK_BOT_TOKEN)


def _check_config():
  if config.APPOINTMENT_TYPE not in TYPE_CODES:
    print("Appointment type {} is not corrected. Please choose one from the following types: {}".format(
      config.APPOINTMENT_TYPE, list(TYPE_CODES.keys())))
    exit(1)
  if hasattr(config, "LOCATION") and config.LOCATION not in MVC_LOCATION_CODES[config.APPOINTMENT_TYPE]:
    print("Appointment location {} is not corrected. Please choose one from the following locations: {}".format(
      config.LOCATION, list(MVC_LOCATION_CODES[config.APPOINTMENT_TYPE].keys())))
    exit(1)


def _get_config_info():
  _check_config()
  location_candidates = [(config.LOCATION, MVC_LOCATION_CODES[config.APPOINTMENT_TYPE][config.LOCATION])] if hasattr(config,
                                                                                                  "LOCATION") and config.LOCATION else list(
    MVC_LOCATION_CODES[config.APPOINTMENT_TYPE].items())
  return {"location_candidates": location_candidates}


def _monitor_appointments(config_info):
  available_slots = {}
  for location_name, location_code in config_info["location_candidates"]:
    timeslot_url = APPOINTMENT_TEMPLATE_URL.format(
      type_code=TYPE_CODES[config.APPOINTMENT_TYPE], location_code=location_code)

    # print("Checking {}".format(timeslot_url))
    request = urllib.request.Request(timeslot_url)
    try:
      response = urllib.request.urlopen(request)
    except:
      print("Failed to request {}, skipping".format(timeslot_url))
      continue

    result_html = response.read().decode("utf8")
    soup = BeautifulSoup(result_html, "html.parser")
    available_timeslots = soup.find(id="timeslots").findChildren("a", recursive=False, href=True)
    if available_timeslots:
      for timeslot in available_timeslots:
        url = APPOINTMNET_URL_PREFIX + timeslot["href"]
        # print("Available timeslots found: {}".format(url))
        available_slots[url] = {"location": location_name, "url": url, "date": url.split("/")[-2]}
  return available_slots


def _send_slack_messages(new_slots):
  new_messages = ["Appointment link: {},\n\ttype: {}\n\tdate: {},\n\tlocation: {}".format(url, config.APPOINTMENT_TYPE, detail["date"], detail["location"]) for url, detail in new_slots.items()]
  abridged_message = "\n\n------ \n **New appointment timeslots found!!!**\n------\n\n{}".format(",\n".join(new_messages))
  try:
    SLACK_CLIENT.chat_postMessage(channel="C0268KQL5GV", text=abridged_message)
  except SlackApiError as e:
    print("Failed to communicate with Slack: {}".format(e.response['error']))


if __name__ == "__main__":
  config_info = _get_config_info()
  former_date = datetime.today().strftime("%Y-%m-%d")
  daily_found_urls = set()
  while True:
    available_slots = _monitor_appointments(config_info)
    urls = set(available_slots.keys())
    new_urls = urls.difference(daily_found_urls)
    daily_found_urls = daily_found_urls.union(urls)
    if len(new_urls) > 0:
      new_slots = {url: available_slots[url] for url in new_urls}
      _send_slack_messages(new_slots)
    # print("Sleeping for 10 seconds for next scan")
    sleep(10)
    current_date = datetime.today().strftime("%Y-%m-%d")
    if current_date != former_date:
      former_date = current_date
      daily_found_urls.clear()