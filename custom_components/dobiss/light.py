"""Dobiss Light Control"""
import logging
# import voluptuous as vol
from .dobiss import DobissSystem
from .const import DOMAIN
# import asyncio

from homeassistant.components.light import ColorMode, ATTR_BRIGHTNESS, LightEntity, LightEntityFeature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Dobiss Light platform."""
    coordinator = hass.data[DOMAIN]["coordinator"]

    lights = coordinator.dobiss.lights
    _LOGGER.info("Adding lights...")
    _LOGGER.debug(str(lights))

    # Add devices
    async_add_entities(
        HomeAssistantDobissLight(coordinator, light) for light in lights
    )

    _LOGGER.info("Dobiss lights added.")


class HomeAssistantDobissLight(CoordinatorEntity, LightEntity):
    """Representation of a Dobiss light in HomeAssistant."""

    def __init__(self, coordinator, light):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        """Initialize a DobissLight."""
        self.dobiss = coordinator.dobiss
        self._light = light
        self._name = light['name']

    @property
    def supported_features(self):
        # Brightness is not a feature flag in HA; it is declared via supported_color_modes
        # Only expose valid feature flags here.
        return LightEntityFeature.FLASH | LightEntityFeature.TRANSITION

    @property
    def unique_id(self):
        return f"{self._light['moduleAddress']}.{self._light['index']}"

    @property
    def device_extra_attributes(self):
        """Return device specific state attributes."""
        return self._light

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def device_info(self):
        """Return device info to group all entities under the Dobiss controller."""
        host = getattr(self.dobiss, 'host', 'dobiss')
        port = getattr(self.dobiss, 'port', None)
        ident = f"{host}:{port}" if port is not None else str(host)
        return {
            "identifiers": {(DOMAIN, ident)},
            "name": f"Dobiss Controller {host}",
            "manufacturer": "Dobiss",
        }

    @property
    def brightness(self):
        """Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        mod = self._light['moduleAddress']
        idx = self._light['index']
        mod_vals = self.coordinator.data.get(mod)
        if not mod_vals or idx >= len(mod_vals):
            return 0
        val = mod_vals[idx]
        return int(val * 255 / 100)

    @property
    def is_on(self):
        """Return true if light is on."""
        mod = self._light['moduleAddress']
        idx = self._light['index']
        mod_vals = self.coordinator.data.get(mod)
        if not mod_vals or idx >= len(mod_vals):
            return False
        val = mod_vals[idx]
        return val > 0

    async def async_turn_on(self, **kwargs):
        """Instruct the light to turn on.

        You can skip the brightness part if your light does not support
        brightness control.
        """
        _LOGGER.debug("async_turn_on")
        is_relay = self.dobiss.modules[self._light['moduleAddress']]['type'] == DobissSystem.ModuleType.Relais
        if is_relay:
            # Relays are on/off only; always turn on to 100%
            await self.dobiss.setOn(self._light['moduleAddress'], self._light['index'], 100)
        else:
            pct = int(kwargs.get(ATTR_BRIGHTNESS, 255) * 100 / 255)
            await self.dobiss.setOn(self._light['moduleAddress'], self._light['index'], pct)
        await self.coordinator.async_request_refresh()

    @property
    def supported_color_modes(self):
        is_relay = self.dobiss.modules[self._light['moduleAddress']]['type'] == DobissSystem.ModuleType.Relais
        if is_relay:
            return {ColorMode.ONOFF}
        # Dimmer: expose brightness support
        return {ColorMode.BRIGHTNESS}

    @property
    def color_mode(self):
        is_relay = self.dobiss.modules[self._light['moduleAddress']]['type'] == DobissSystem.ModuleType.Relais
        return ColorMode.ONOFF if is_relay else ColorMode.BRIGHTNESS

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        _LOGGER.debug("async_turn_off")
        await self.dobiss.setOff(self._light['moduleAddress'], self._light['index'])
        await self.coordinator.async_request_refresh()
