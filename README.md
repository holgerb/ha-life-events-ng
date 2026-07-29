# ![alt text](icon-small.png) Life Events NG for Home Assistant

[![GitHub release](https://img.shields.io/github/release/holgerb/ha-life-events-ng.svg)](https://github.com/holgerb/ha-life-events-ng/releases)
[![License](https://img.shields.io/github/license/holgerb/ha-life-events-ng)](LICENSE)

**The all-in-one birthday and anniversary integration for Home Assistant.**

Track birthdays, wedding anniversaries, and custom recurring dates — with countdown sensors, a calendar entity, a beautiful Lovelace card, and built-in notification support. No YAML required.

This fork uses the Home Assistant domain `life_events_ng` so it can be installed alongside the original `life_events` integration without entity, service, or Lovelace card conflicts.

---

## ✨ Features

- **Sensor per event** — `sensor.life_events_ng_<n>` with state = days until next occurrence
- **Rich attributes** — next date, age/years turning, event type, original date
- **Calendar entity** — `calendar.life_events_ng` integrates with the HA Calendar dashboard
- **Lovelace card** — polished card with urgency colouring, type badges, age display
- **Notification blueprint** — one-click automation for day-of and advance notifications
- **UI-only config** — add/edit/remove events from the HA UI, no YAML editing
- **Event types** — Birthday, Anniversary, Custom (with your own label)
- **Year-optional** — track day/month only when the birth year isn't known

![Life Events NG Lovelace Card](images/lovelacecard.png)

---

## 📦 Installation

### Via HACS custom repository

1. Open HACS
2. Open the three-dot menu and select **Custom repositories**
3. Add `https://github.com/holgerb/ha-life-events-ng`
4. Select **Integration** as the repository type
5. Install **Life Events NG**
6. Restart Home Assistant
7. Go to **Settings → Devices & Services → Add Integration → Life Events NG**

### Manual

1. Copy `custom_components/life_events_ng/` into your HA `custom_components/` folder
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration → Life Events NG**

---

## ⚙️ Configuration

After adding the integration, go to **Settings → Devices & Services → Life Events NG → Configure** to add your events.

### Adding an event

Select **➕ Add new event** in the dropdown and click Submit. Enter details as required and click Submit.

![Add New Event](images/addNewEvent.png)
![Test Event and Main Buttons](images/testEventAndMainButtons.png)

| Field | Description |
|---|---|
| Name | Person or event name (e.g. `Sarah`, `Mom & Dad`) |
| Date | `YYYY-MM-DD` (e.g. `1990-03-15`) or `MM-DD` if year unknown |
| Type | `birthday`, `anniversary`, or `custom` |
| Custom label | Label used if type is `custom` (e.g. `Gotcha Day`) |
| Icon | MDI icon override (e.g. `mdi:dog`) |
| Year unknown | Check if you only know the day/month — hides age/years |

Once you've added all the events you want, in the Configure window, scroll down to **Save and Finish** and click Submit.

![Save and Finish](images/saveAndFinish.png)

---

### Adding an event with a service

You can also add events from Developer Tools → Actions, scripts, automations, or the Home Assistant API:

```yaml
action: life_events_ng.add_event
data:
  name: Sarah
  date: "1990-03-15"
  type: birthday
```

For dates where the year is unknown, use `MM-DD`:

```yaml
action: life_events_ng.add_event
data:
  name: Mom and Dad
  date: "06-12"
  type: anniversary
```

Event names must be unique.

---

### Deleting an event

Go to **Settings → Devices & Services → Life Events NG → Configure** and select your event from the dropdown and click Submit.

![Select Event](images/testEvent.png)

Then tick **🗑️ Delete this event** and click Submit.

![Delete Event](images/deleteEvent.png)

Then from the dropdown, select **✅ Save and finish** and click Submit.

![Save and Finish](images/saveAndFinish.png)

---

## 🃏 Lovelace Card

The card resource is registered automatically when the integration loads — no manual resource configuration needed.

### Add the card

**Recommended:** Edit your dashboard, click **Add Card**, and search for **Life Events NG Card** in the card picker. This gives you a visual editor to configure the card without any YAML.

**Via YAML:** Alternatively, add a Manual card with the following configuration:

```yaml
type: custom:life-events-ng-card
title: Upcoming Celebrations
max_events: 10
show_types:
  - birthday
  - anniversary
  - custom
```

### Card options

| Option | Type | Default | Description |
|---|---|---|---|
| `title` | string | `Life Events NG` | Card heading |
| `max_events` | number | `10` | Maximum number of events to display |
| `show_types` | list | all types | Filter to only these event types |
| `show_past_days` | number | `0` | Also show events up to N days after they passed |

---

## 🔔 Notification Blueprint

Import the bundled blueprint to get notified on the day of an event (and/or days before):

[![Import Blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https://raw.githubusercontent.com/holgerb/ha-life-events-ng/main/blueprints/automation/life_events_ng_notify.yaml)

Or manually copy `blueprints/automation/life_events_ng_notify.yaml` to your HA blueprints folder.

The blueprint runs daily at a time you choose, checks all your Life Events NG sensors, and sends a notification for any events that are today or a set number of days away.

---

## 📡 Sensor Attributes

Each `sensor.life_events_ng_<n>` exposes:

| Attribute | Example | Description |
|---|---|---|
| `state` | `5` | Days until next occurrence |
| `next_date` | `2025-06-12` | Date of next occurrence |
| `days_until` | `5` | Same as state, for template use |
| `years_at_next` | `35` | Age or years at next occurrence (`null` if year unknown) |
| `event_type` | `birthday` | `birthday`, `anniversary`, or `custom` |
| `event_label` | `Birthday` | Human-readable label |
| `year_unknown` | `false` | Whether the birth/start year is known |
| `original_date` | `1990-06-12` | The date as entered |

---

## 🤖 Automation Examples

### Custom notification using sensor attributes

```yaml
alias: "Birthday notification"
trigger:
  - platform: template
    value_template: "{{ states('sensor.life_events_ng_sarah') | int == 0 }}"
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "🎂 Happy Birthday!"
      message: >
        Today is {{ state_attr('sensor.life_events_ng_sarah', 'event_label') }}
        for Sarah — turning {{ state_attr('sensor.life_events_ng_sarah', 'years_at_next') }}!
```

---

## 🙋 FAQ

**Can I have multiple events for the same person?**
Yes — just give them different names (e.g. `Sarah Birthday`, `Sarah Work Anniversary`).

**Will it handle leap-year birthdays (Feb 29)?**
Feb 29 birthdays are celebrated on Feb 28 in non-leap years.

**How do I show events on the Home Assistant calendar?**
The `calendar.life_events_ng` entity is created automatically. Add it to your Calendar dashboard view.

---

## 🤝 Contributing

Issues and PRs welcome at [GitHub](https://github.com/holgerb/ha-life-events-ng/issues).

## 📄 License

MIT License — see [LICENSE](LICENSE).
