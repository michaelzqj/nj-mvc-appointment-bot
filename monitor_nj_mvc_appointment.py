from datetime import datetime
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
  },
  "REAL ID": {
    "OAKLAND": 141,
    "PATERSON": 142,
    "LODI": 136,
    "WAYNE": 140,
    "RANDOLPH": 145,
    "NORTH BERGEN": 139,
    "NEWARK": 138,
    "BAYONNE": 125,
    "RAHWAY": 144,
    "SOUTH PLAINFIELD": 131,
    "EDISON": 132,
    "FLEMINGTON": 133,
    "BAKERS BASIN": 124,
    "FREEHOLD": 135,
    "EATONTOWN": 130,
    "TOMS RIVER": 134,
    "DELANCO": 129,
    "CAMDEN": 127,
    "WEST DEPTFORD": 143,
    "SALEM": 128,
    "VINELAND": 137,
    "CARDIFF": 146,
    "RIO GRANDE": 126
  },
  "INITIAL PERMIT (NOT FOR KNOWLEDGE TEST)": {
    "OAKLAND": 203,
    "PATERSON": 204,
    "LODI": 198,
    "WAYNE": 202,
    "RANDOLPH": 207,
    "NORTH BERGEN": 201,
    "NEWARK": 200,
    "BAYONNE": 187,
    "RAHWAY": 206,
    "SOUTH PLAINFIELD": 193,
    "EDISON": 194,
    "FLEMINGTON": 195,
    "BAKERS BASIN": 186,
    "FREEHOLD": 197,
    "EATONTOWN": 192,
    "TOMS RIVER": 196,
    "DELANCO": 191,
    "CAMDEN": 189,
    "WEST DEPTFORD": 205,
    "SALEM": 190,
    "VINELAND": 199,
    "CARDIFF": 208,
    "RIO GRANDE": 188
  }
}

APPOINTMENT_TEMPLATE_URL = "https://telegov.njportal.com/njmvc/AppointmentWizard/{type_code}/{location_code}"

SLACK_CLIENT = WebClient(token=config.SLACK_BOT_TOKEN)


def _check_config():
  supported_types = set(MVC_LOCATION_CODES.keys()).intersection(set(TYPE_CODES.keys()))
  if hasattr(config, "APPOINTMENT_TYPES") and config.APPOINTMENT_TYPES.difference(supported_types):
    print("Appointment types {} are not corrected. Please choose one from the following types: {}".format(
      config.APPOINTMENT_TYPES, supported_types))
    exit(1)

  if hasattr(config, "APPOINTMENT_TYPES") and config.APPOINTMENT_TYPES and hasattr(config, "LOCATION"):
    supported_locations = set()
    for type in config.APPOINTMENT_TYPES:
      if not supported_locations:
        supported_locations = set(MVC_LOCATION_CODES[type])
        continue
      supported_locations = supported_locations.intersection(set(MVC_LOCATION_CODES[type]))
    if config.LOCATION not in supported_locations:
      print("Appointment location {} is not corrected. Please choose one from the following locations: {}".format(
          config.LOCATION, supported_locations))
    exit(1)


def _get_config_info():
  _check_config()
  info = {}
  type_candidates = [(type, TYPE_CODES[type])
                     for type in config.APPOINTMENT_TYPES] if hasattr(config, "APPOINTMENT_TYPES") and config.APPOINTMENT_TYPES else list(TYPE_CODES.items())
  for type, type_code in type_candidates:
    if type not in MVC_LOCATION_CODES:
      continue
    type_location_candidates = [(config.LOCATION, MVC_LOCATION_CODES[type][config.LOCATION])] if hasattr(config,
                                                                                                  "LOCATION") and config.LOCATION else list(
    MVC_LOCATION_CODES[type].items())
    info[(type, type_code)] = type_location_candidates
  return info


def _monitor_appointments(config_info):
  available_slots = {}
  for (type, type_code), location_candidates in config_info.items():
    for location_name, location_code in location_candidates:
      timeslot_url = APPOINTMENT_TEMPLATE_URL.format(
        type_code=type_code, location_code=location_code)

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
          available_slots[url] = {"type": type, "location": location_name, "url": url, "date": url.split("/")[-2]}
  return available_slots


def _send_slack_messages(new_slots):
  new_messages = ["Appointment Slot #{}:\n\tlink: <{}|URL>,\n\ttype: {}\n\tdate: {},\n\tlocation: {}".format(
    index + 1, url, detail["type"], detail["date"], detail["location"])
    for index, (url, detail) in enumerate(sorted(list(new_slots.items())))]
  abridged_message = "\n\n------ \n *New appointment timeslots found!!!*\n------\n\n{}".format(",\n".join(new_messages))
  try:
    SLACK_CLIENT.chat_postMessage(channel=config.SLACK_CHANNEL_ID, text=abridged_message)
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
    sleep(10)
    current_date = datetime.today().strftime("%Y-%m-%d")
    if current_date != former_date:
      former_date = current_date
      daily_found_urls.clear()