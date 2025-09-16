"""Dobiss Fan Control"""
import logging
from .dobiss import DobissSystem
from .const import DOMAIN

from homeassistant.components.fan import FanEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity


_LOGGER = logging.getLogger(__name__)

        
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Setup the Dobiss Fan platform."""
    coordinator = hass.data[DOMAIN]["coordinator"]

    fans = coordinator.dobiss.fans
    _LOGGER.info("Adding fans...")
    _LOGGER.debug(str(fans))

    # Add devices
    async_add_entities(
        HomeAssistantDobissFan(coordinator, fan) for fan in fans
    )
    
    _LOGGER.info("Dobiss fans added.")


class HomeAssistantDobissFan(CoordinatorEntity, FanEntity):
    """Representation of a Dobiss fan in HomeAssistant."""

    def __init__(self, coordinator, fan):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        """Initialize a DobissFan."""
        self.dobiss = coordinator.dobiss
        self._fan = fan
        self._name = fan['name']


    @property
    def unique_id(self):
        return "{}.{}".format(self._fan['moduleAddress'], self._fan['index'])

    @property
    def device_extra_attributes(self):
        """Return device specific state attributes."""
        return self._fan
    
    @property
    def name(self):
        """Return the display name of this fan."""
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
    def is_on(self):
        """Return true if the fan is on."""
        mod = self._fan['moduleAddress']
        idx = self._fan['index']
        mod_vals = self.coordinator.data.get(mod)
        if not mod_vals or idx >= len(mod_vals):
            return False
        val = mod_vals[idx]
        return val > 0

    async def async_turn_on(self, **kwargs):
        """Instruct the fan to turn on.
        """
        await self.dobiss.setOn(self._fan['moduleAddress'], self._fan['index'])

        # Poll states
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Instruct the fan to turn off."""
        await self.dobiss.setOff(self._fan['moduleAddress'], self._fan['index'])

        # Poll states
        await self.coordinator.async_request_refresh()
