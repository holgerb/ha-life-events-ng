"""The Life Events NG integration."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    COORDINATOR,
    CONF_EVENTS,
    CONF_EVENT_NAME,
    CONF_EVENT_DATE,
    CONF_EVENT_TYPE,
    CONF_EVENT_CUSTOM_LABEL,
    CONF_EVENT_ICON,
    CONF_EVENT_YEAR_UNKNOWN,
    EVENT_TYPES,
    SERVICE_ADD_EVENT,
    SERVICE_UPDATE_EVENT,
    SERVICE_DELETE_EVENT,
)
from .coordinator import LifeEventsCoordinator
from .event import EventValidationError, build_event_data, event_names_match

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CALENDAR]

ADD_EVENT_SCHEMA = vol.Schema({
    vol.Required(CONF_EVENT_NAME): cv.string,
    vol.Required(CONF_EVENT_DATE): cv.string,
    vol.Required(CONF_EVENT_TYPE): vol.In(EVENT_TYPES),
    vol.Optional(CONF_EVENT_CUSTOM_LABEL, default=""): cv.string,
    vol.Optional(CONF_EVENT_ICON, default=""): cv.string,
    vol.Optional(CONF_EVENT_YEAR_UNKNOWN): cv.boolean,
})

UPDATE_EVENT_SCHEMA = vol.Schema({
    vol.Required(CONF_EVENT_NAME): cv.string,
    vol.Optional("new_name"): cv.string,
    vol.Optional(CONF_EVENT_DATE): cv.string,
    vol.Optional(CONF_EVENT_TYPE): vol.In(EVENT_TYPES),
    vol.Optional(CONF_EVENT_CUSTOM_LABEL): cv.string,
    vol.Optional(CONF_EVENT_ICON): cv.string,
    vol.Optional(CONF_EVENT_YEAR_UNKNOWN): cv.boolean,
})

DELETE_EVENT_SCHEMA = vol.Schema({
    vol.Required(CONF_EVENT_NAME): cv.string,
})

_CARD_URL_BASE = "/life_events_ng"
_CARD_FILENAME = "life-events-ng-card.js"
_CARD_FILE = Path(__file__).parent / _CARD_FILENAME
_CARD_RESOURCE_URL = f"{_CARD_URL_BASE}/{_CARD_FILENAME}"


async def _register_card(hass: HomeAssistant) -> None:
    """Serve the JS file and register it as a persistent Lovelace resource."""
    # Serve the file via a static HTTP path.
    try:
        await hass.http.async_register_static_paths([
            StaticPathConfig(_CARD_RESOURCE_URL, str(_CARD_FILE), cache_headers=False),
        ])
    except Exception:  # noqa: BLE001 — already registered on quick restarts
        pass

    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        _LOGGER.debug("Lovelace not available; skipping resource registration")
        return

    mode = getattr(lovelace, "mode", getattr(lovelace, "resource_mode", "yaml"))
    if mode != "storage":
        _LOGGER.debug("Lovelace in YAML mode; add the resource manually")
        return

    async def _try_register(_now: Any) -> None:
        """Register the resource once Lovelace has loaded its collection from storage."""
        if not lovelace.resources.loaded:
            _LOGGER.debug("Lovelace resources not loaded yet, retrying in 5 s")
            async_call_later(hass, 5, _try_register)
            return

        existing = lovelace.resources.async_items()
        for resource in existing:
            if resource.get("url", "").startswith(_CARD_URL_BASE):
                _LOGGER.debug("Life Events NG card resource already registered")
                return

        await lovelace.resources.async_create_item({
            "res_type": "module",
            "url": _CARD_RESOURCE_URL,
        })
        _LOGGER.info("Registered Life Events NG card as Lovelace resource: %s", _CARD_RESOURCE_URL)

    await _try_register(None)


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    """Register the static path, card resource, and integration services."""
    await _register_card(hass)
    _register_services(hass)
    return True


def _register_services(hass: HomeAssistant) -> None:
    """Register Life Events NG services."""
    def _get_entry() -> ConfigEntry:
        """Return the configured Life Events NG entry."""
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise HomeAssistantError("Life Events NG is not configured")
        return entries[0]

    def _get_events(entry: ConfigEntry) -> list[dict[str, Any]]:
        """Return a mutable copy of the configured events."""
        return list(entry.options.get(CONF_EVENTS, entry.data.get(CONF_EVENTS, [])))

    def _find_event_index(events: list[dict[str, Any]], name: str) -> int:
        """Return the index of the event matching name."""
        for index, event in enumerate(events):
            if event_names_match(event.get(CONF_EVENT_NAME, ""), name):
                return index
        raise HomeAssistantError(f"Life Events NG event not found: {name}")

    def _save_events(entry: ConfigEntry, events: list[dict[str, Any]]) -> None:
        """Persist the updated events list."""
        options = dict(entry.options)
        options[CONF_EVENTS] = events
        hass.config_entries.async_update_entry(entry, options=options)

    async def async_add_event(call: ServiceCall) -> None:
        """Add a Life Events NG event to the configured entry."""
        entry = _get_entry()
        events = _get_events(entry)

        try:
            event_data = build_event_data(dict(call.data))
        except EventValidationError as err:
            raise HomeAssistantError(str(err)) from err

        event_name = event_data[CONF_EVENT_NAME]
        if any(event_names_match(event.get(CONF_EVENT_NAME, ""), event_name) for event in events):
            raise HomeAssistantError(f"Life Events NG event already exists: {event_name}")

        _save_events(entry, [*events, event_data])

        _LOGGER.info("Added Life Events NG event via service: %s", event_name)

    async def async_update_event(call: ServiceCall) -> None:
        """Update a Life Events NG event in the configured entry."""
        call_data = dict(call.data)
        update_keys = set(call_data) - {CONF_EVENT_NAME}
        if not update_keys:
            raise HomeAssistantError("No Life Events NG event update fields provided")

        entry = _get_entry()
        events = _get_events(entry)
        event_name = call_data[CONF_EVENT_NAME]
        event_index = _find_event_index(events, event_name)
        existing = events[event_index]

        updated = dict(existing)
        if "new_name" in call_data:
            updated[CONF_EVENT_NAME] = call_data["new_name"]
        if CONF_EVENT_DATE in call_data:
            updated[CONF_EVENT_DATE] = call_data[CONF_EVENT_DATE]
            if CONF_EVENT_YEAR_UNKNOWN not in call_data:
                updated.pop(CONF_EVENT_YEAR_UNKNOWN, None)
        for field in (
            CONF_EVENT_TYPE,
            CONF_EVENT_CUSTOM_LABEL,
            CONF_EVENT_ICON,
            CONF_EVENT_YEAR_UNKNOWN,
        ):
            if field in call_data:
                updated[field] = call_data[field]

        try:
            event_data = build_event_data(updated, existing)
        except EventValidationError as err:
            raise HomeAssistantError(str(err)) from err

        updated_name = event_data[CONF_EVENT_NAME]
        if any(
            index != event_index and event_names_match(event.get(CONF_EVENT_NAME, ""), updated_name)
            for index, event in enumerate(events)
        ):
            raise HomeAssistantError(f"Life Events NG event already exists: {updated_name}")

        events[event_index] = event_data
        _save_events(entry, events)

        _LOGGER.info("Updated Life Events NG event via service: %s", updated_name)

    async def async_delete_event(call: ServiceCall) -> None:
        """Delete a Life Events NG event from the configured entry."""
        entry = _get_entry()
        events = _get_events(entry)
        event_name = call.data[CONF_EVENT_NAME]
        event_index = _find_event_index(events, event_name)
        deleted = events.pop(event_index)

        _save_events(entry, events)

        _LOGGER.info("Deleted Life Events NG event via service: %s", deleted.get(CONF_EVENT_NAME, event_name))

    if not hass.services.has_service(DOMAIN, SERVICE_ADD_EVENT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ADD_EVENT,
            async_add_event,
            schema=ADD_EVENT_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_UPDATE_EVENT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_UPDATE_EVENT,
            async_update_event,
            schema=UPDATE_EVENT_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_DELETE_EVENT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_DELETE_EVENT,
            async_delete_event,
            schema=DELETE_EVENT_SCHEMA,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Life Events NG from a config entry."""
    coordinator = LifeEventsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
