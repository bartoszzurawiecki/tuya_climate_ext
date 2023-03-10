"""
Adds support for the Tuya climate units.
For more details about self platform, please refer to the documentation at
https://github.com/custom-components/climate.e_thermostaat
"""
import logging
import requests
import voluptuous as vol
import pytuya
import time
import asyncio

from homeassistant.components.climate import ClimateEntity, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT, HVAC_MODE_OFF, HVAC_MODE_AUTO, PRESET_AWAY, PRESET_COMFORT, PRESET_HOME, 
    PRESET_SLEEP, SUPPORT_TARGET_TEMPERATURE, CURRENT_HVAC_HEAT, CURRENT_HVAC_IDLE)
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_USERNAME, CONF_PASSWORD, TEMP_CELSIUS, 
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON)
import homeassistant.helpers.config_validation as cv
from homeassistant.core import DOMAIN, HomeAssistant

__version__ = '1.0.1'

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(level=logging.ERROR)
#_LOGGER.setLevel(level=logging.DEBUG)

DEFAULT_NAME = 'Tuya climate Ext'

CONF_NAME = 'name'
CONF_DEVICEID = "id"
CONF_DEVICEKEY = "key"
CONF_DEVICEIP = "ip"
CONF_HEATER = "heater"

MIN_TEMP = 7
MAX_TEMP = 30
target_temperature_step = 0.5

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_DEVICEID): cv.string,
    vol.Required(CONF_DEVICEKEY): cv.string,
    vol.Required(CONF_DEVICEIP): cv.string,
    vol.Required(CONF_HEATER): cv.entity_id
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setup the Tuya climate Platform."""
    name = config.get(CONF_NAME)
    device_id = config.get(CONF_DEVICEID)
    device_key = config.get(CONF_DEVICEKEY)
    device_ip = config.get(CONF_DEVICEIP)
    heater = config.get(CONF_HEATER)
    
    add_entities([TuyaClimate(name, device_id, device_key, device_ip, heater)])

class TuyaClimate(ClimateEntity):
    """Representation of a Tuya climate device."""

    def __init__(self, name, device_id, device_key, device_ip, heater):
        """Initialize the thermostat."""
        self._name = name
        self._id = device_id
        self._key = device_key
        self._ip = device_ip
        self._heater = heater

        #self.hass = HomeAssistant

        self._enabled = None
        self._mode = None
        self._floorTemp = None
        self._target_temperature = None
        self._current_temperature = None
        self._lock = None

        self._pulling_lock = False

        self._device = pytuya.Device(self._id, self._ip, self._key, "device")
        self._device.set_version(3.3)
        self._get_data()

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID for self thermostat."""
        return '_'.join([self._name, 'climate'])

    @property
    def should_poll(self):
        """Polling is required."""
        return True

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return MIN_TEMP

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return MAX_TEMP

    @property
    def target_temperature_step(self):
        """Return the target temperature step."""
        return target_temperature_step

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        if self._enabled:
            return self._current_mode
        else:
            return HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """HVAC modes."""
        return [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        if (not self._enabled):
            asyncio.create_task(self.heater_turn_off())
            return CURRENT_HVAC_IDLE
        if self._target_temperature is None: 
            asyncio.create_task(self.heater_turn_off())
            return CURRENT_HVAC_IDLE
        if self._current_temperature is None: 
            asyncio.create_task(self.heater_turn_off())
            return CURRENT_HVAC_IDLE
        if self._target_temperature < self._current_temperature:
            asyncio.create_task(self.heater_turn_off())
            return CURRENT_HVAC_IDLE
        if (self._current_mode == HVAC_MODE_AUTO and self._current_temperature <= 5):
            asyncio.create_task(self.heater_turn_on())
            return CURRENT_HVAC_HEAT
        if self._current_mode == HVAC_MODE_AUTO:
            asyncio.create_task(self.heater_turn_off())
            return CURRENT_HVAC_IDLE
        asyncio.create_task(self.heater_turn_on())
        return CURRENT_HVAC_HEAT

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    def set_hvac_mode(self, mode: str):
        """Set new mode."""
        self._pulling_lock = True
        if (mode == "off" and self._enabled):
            self._device.set_value("1", False)
            self._enabled = False
        else:
            if (not self._enabled):
                #_LOGGER.warning("a")
                self._device.set_value('1', True)
                self._enabled = True
            if (mode == HVAC_MODE_HEAT and self._current_mode != HVAC_MODE_HEAT):
                #_LOGGER.warning("b")
                self._device.set_value("4", '1')
                self._current_mode = HVAC_MODE_HEAT
            elif (mode == HVAC_MODE_AUTO and self._current_mode != HVAC_MODE_AUTO):
                #_LOGGER.warning("c")
                self._device.set_value("4", '0')
                self._current_mode = HVAC_MODE_AUTO
        #_LOGGER.warning("New mode set")
        time.sleep(0.3)
        self._pulling_lock = False
        self.schedule_update_ha_state()

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._pulling_lock = True
        self._device.set_value("2", int(temperature * 2))
        # self._target_temperature = temperature
        time.sleep(0.3)
        self._pulling_lock = False
        #_LOGGER.warning("New temperature set " + str(temperature * 2))
        self.schedule_update_ha_state()

    def _parse_status(self, status):
        dps = status["dps"]
        if (dps["1"] != None):
            if (dps["1"] == False):
                self._enabled = False
            else:
                self._enabled = True

        if (dps["4"] != None):
            if (dps["4"] == "0"):
                self._current_mode = HVAC_MODE_AUTO
            else:
                self._current_mode = HVAC_MODE_HEAT

        if (dps["102"] != None):
            self._floorTemp = dps["102"] / 2
        if (dps["2"] != None):
            self._target_temperature = dps["2"] / 2
        if (dps["3"] != None):
            self._current_temperature = dps["3"] / 2

        if (dps["6"] != None):
            self._lock = dps["6"]

        #_LOGGER.debug(dps)

    def _get_data(self):
        status = None
        try:
            status = self._device.status()
        except:
            _LOGGER.warning("Can't get data. Retrying in next interval")
        else:
            self._parse_status(status)

    def update(self):
        """Get the latest data."""
        if not self._pulling_lock:
            self._get_data()
            # self.schedule_update_ha_state()

    async def heater_turn_on(self):
        """Turn heater toggleable device on."""
        #_LOGGER.warning("Heater turn on")
        if self._heater is not None:
            data = {ATTR_ENTITY_ID: self._heater}
            await self.hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data)
        #_LOGGER.warning("Heater turn on done")

    async def heater_turn_off(self):
        """Turn heater toggleable device off."""
        #_LOGGER.warning("Heater turn off")
        if self._heater is not None:
            data = {ATTR_ENTITY_ID: self._heater}
            await self.hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data)
        #_LOGGER.warning("Heater turn off done")
