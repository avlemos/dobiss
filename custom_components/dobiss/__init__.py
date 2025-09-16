"""Dobiss Control Systems integration."""
import asyncio
from datetime import timedelta
import logging
# import voluptuous as vol
import async_timeout

from .dobiss import DobissSystem

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
# from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
# import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, PLATFORMS, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


# Validation of the user's configuration
# PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
#    vol.Required(CONF_HOST): cv.string,
#    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
#    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.positive_int,
# })


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Dobiss component from YAML."""

    # TODO Implement this
    return True


#    # If no settings are found, use config flow
#    if config.get(DOMAIN) is None:
#        return True
#    
#    host = config[DOMAIN].get(CONF_HOST)
#    port = config[DOMAIN].get(CONF_PORT, DEFAULT_PORT)
#    update_interval = timedelta(seconds=config[DOMAIN].get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
#
#    # We need a host
#    if not host:
#        return False
#
#    success = await setupCoordinator(hass, host, port, update_interval)
#
#    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Dobiss from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    # Prefer options (set via Options Flow), then data, then default
    scan_seconds = entry.options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    update_interval = timedelta(seconds=scan_seconds)

    _LOGGER.info(f"Setting up Dobiss Control entry with data {str(entry.data)} and options {str(entry.options)}")

    # Create from config entry
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    await setupCoordinator(hass, host, port, update_interval)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register service to re-import installation
    coordinator = hass.data[DOMAIN]["coordinator"]

    async def handle_importInstallation(call):
        _LOGGER.info("Importing Dobiss installation via service call")
        await coordinator.importInstallation()

    hass.services.async_register(DOMAIN, "importInstallation", handle_importInstallation)

    # Listen for options updates to adjust polling interval without re-adding
    async def _update_listener(hass: HomeAssistant, updated_entry: ConfigEntry):
        new_scan_seconds = updated_entry.options.get(
            CONF_SCAN_INTERVAL,
            updated_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        new_interval = timedelta(seconds=new_scan_seconds)
        if coordinator.update_interval != new_interval:
            _LOGGER.info(f"Updating Dobiss polling interval to {new_scan_seconds}s via Options")
            coordinator.update_interval = new_interval

    entry.async_on_unload(entry.add_update_listener(_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    _LOGGER.info("Unloading Dobiss Control entries")
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    cfg = hass.data.get(DOMAIN)
    _LOGGER.debug(f"{DOMAIN} hass data: {cfg}")
    if unload_ok and cfg and cfg.get(entry.entry_id):
        cfg.pop(entry.entry_id)

    return unload_ok


async def setupCoordinator(hass, host, port, update_interval):
    _LOGGER.info(f"Creating update coordinator")
    if DOMAIN in hass.data:
        domainData = hass.data[DOMAIN]
        if "coordinator" in domainData:
            _LOGGER.warning("Warning: hass data already contains a coordinator. It will be overwritten!")
        _LOGGER.debug(f"Current hass {DOMAIN} data: {str(domainData)}")

    coordinator = DobissDataUpdateCoordinator(hass, host=host, port=port, update_interval=update_interval)
    await coordinator.async_refresh()

    # Store the coordinator
    hass.data[DOMAIN]["coordinator"] = coordinator

    _LOGGER.debug(f"New hass {DOMAIN} data: {str(hass.data[DOMAIN])}")

    return True


class DobissDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Dobiss data from the LAN controller."""

    def __init__(self, hass, host, port, update_interval):
        """Initialize."""
        _LOGGER.info(f"Initializing Dobiss System with host {host} and port {port}...")
        self.dobiss = DobissSystem(host, port)

        self.setupCompleted = False

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def importInstallation(self):
        """Import installation"""
        _LOGGER.info("Importing Dobiss installation...")
        await self.dobiss.connect()
        await self.dobiss.importFullInstallation()
        # Release connection so other clients (e.g., Dobiss Pro app) can use the controller
        self.dobiss.disconnect()
        _LOGGER.info("Importing Dobiss installation done")

    async def async_setup(self):
        """Setup in the background"""
        await self.importInstallation()
        self.setupCompleted = True

    async def _async_update_data(self):
        """Query states"""

        # Setup if necessary
        if not self.setupCompleted:
            await self.async_setup()

        # We use a time-out to be sure
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with async_timeout.timeout(10):
            # Connect, poll, and disconnect to avoid holding the controller exclusively
            _LOGGER.debug("Requesting all statuses...")
            await self.dobiss.connect()
            try:
                await self.dobiss.requestAllStatus()
            finally:
                # Ensure we release the connection for other apps
                self.dobiss.disconnect()
            _LOGGER.debug("Requesting all statuses done")
            return self.dobiss.values
