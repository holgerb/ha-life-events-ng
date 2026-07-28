"""The Life Events integration."""
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

_CARD_URL_BASE = "/life_events"
_CARD_FILENAME = "life-events-card.js"
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
                _LOGGER.debug("Life Events card resource already registered")
                return

        await lovelace.resources.async_create_item({
            "res_type": "module",
            "url": _CARD_RESOURCE_URL,
        })
        _LOGGER.info("Registered Life Events card as Lovelace resource: %s", _CARD_RESOURCE_URL)

    await _try_register(None)


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    """Register the static path, card resource, and integration services."""
    await _register_card(hass)
    _register_services(hass)
    return True


def _register_services(hass: HomeAssistant) -> None:
    """Register Life Events services."""
    if hass.services.has_service(DOMAIN, SERVICE_ADD_EVENT):
        return

    async def async_add_event(call: ServiceCall) -> None:
        """Add a Life Events event to the configured entry."""
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise HomeAssistantError("Life Events is not configured")

        entry = entries[0]
        events = list(entry.options.get(CONF_EVENTS, entry.data.get(CONF_EVENTS, [])))

        try:
            event_data = build_event_data(dict(call.data))
        except EventValidationError as err:
            raise HomeAssistantError(str(err)) from err

        event_name = event_data[CONF_EVENT_NAME]
        if any(event_names_match(event.get(CONF_EVENT_NAME, ""), event_name) for event in events):
            raise HomeAssistantError(f"Life Events event already exists: {event_name}")

        options = dict(entry.options)
        options[CONF_EVENTS] = [*events, event_data]
        hass.config_entries.async_update_entry(entry, options=options)

        _LOGGER.info("Added Life Events event via service: %s", event_name)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_EVENT,
        async_add_event,
        schema=ADD_EVENT_SCHEMA,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Life Events from a config entry."""
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
