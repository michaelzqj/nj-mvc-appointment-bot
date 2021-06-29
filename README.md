# nj-mvc-appointment-bot

Script bot for monitor appointment for NJ MVC. This script requires following Python package for running:

- bs4 (beautifulsoup)

This script will montior the availablity from https://telegov.njportal.com/njmvc/AppointmentWizard/ and if there's availability, then this script will send this to the [Slack](https://slack.com/) channel(configurable) to notify the users in that channel.

## Configuration

The example configuration:

```python
# Appointment requirement
APPOINTMENT_TYPES = {"TRANSFER FROM OUT OF STATE", "REAL ID"} # Can be not set and all supported types will be checked
LOCATION = "NEWARK" # Can be empty and all locations will be checked

# Slack configuration
SLACK_BOT_TOKEN = "TOKEN_HERE"
SLACK_CHANNEL_ID = "CHANNEL ID HERE"
```

As of 06/29/2021, only `TRANSFER FROM OUT OF STATE`, `REAL ID` and `NITIAL PERMIT (NOT FOR KNOWLEDGE TEST)` appointment types are supported. 
