from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from .const import DOMAIN, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL
import voluptuous as vol

# TODO Discovery
# async def _async_has_devices(hass) -> bool:
#     """Return if there are devices that can be discovered."""
#     # TODO Check if there are any devices that can be discovered in the network.
#     devices = await hass.async_add_executor_job(my_pypi_dependency.discover)
#     return len(devices) > 0


# config_entry_flow.register_discovery_flow(
#     DOMAIN, "Dobiss Domotics", _async_has_devices, config_entries.CONN_CLASS_UNKNOWN
# )


# Config GUI
from homeassistant.core import callback

# Options Flow is registered on the ConfigFlow class
class DobissConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """The config flow for the Dobiss Domotics integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        return await setupStep(self, user_input, True, "user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return DobissOptionsFlowHandler(config_entry)


class DobissOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Store options (do not modify data here)
            return self.async_create_entry(title="", data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
                CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
            })

        # Defaults: prefer existing options, then data, then global defaults
        current_host = self.config_entry.options.get(
            CONF_HOST,
            self.config_entry.data.get(CONF_HOST, ""),
        )
        current_port = self.config_entry.options.get(
            CONF_PORT,
            self.config_entry.data.get(CONF_PORT, DEFAULT_PORT),
        )
        current_scan = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        data_schema = {
            vol.Required(CONF_HOST, default=current_host): str,
            vol.Optional(CONF_PORT, default=current_port): int,
            vol.Optional(CONF_SCAN_INTERVAL, default=current_scan): int,
        }
        return self.async_show_form(step_id="init", data_schema=vol.Schema(data_schema))


async def setupStep(flow, user_input, check_unique=True, step_name="user"):
    # Filled in?
    if user_input is not None:
        # Don't configure the same controler twice
        if check_unique:
            await flow.async_set_unique_id(f"dobiss-{user_input[CONF_HOST]}")
            flow._abort_if_unique_id_configured()

        # TODO Try to connect
        #valid = await is_valid(user_input)
        valid = True
        if valid:
            return flow.async_create_entry(
                title=f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                data={
                    "host": user_input[CONF_HOST],
                    "port": user_input[CONF_PORT],
                    "scan_interval": user_input[CONF_SCAN_INTERVAL]
                }
            )
    
    data_schema = {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int
    }

    return flow.async_show_form(step_id=step_name, data_schema=vol.Schema(data_schema))
