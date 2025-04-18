from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed
)
from time import time
from .const import DOMAIN, DATA_VEHICLES, DEFAULT_INTERVAL, DEFAULT_INTERVAL_CHARGING, DEFAULT_INTERVAL_STATISTICS
from .kamereon import Feature, PluggedStatus, HVACStatus, Period
_LOGGER = logging.getLogger(__name__)


class KamereonCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, config):
        """Initialise coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Kamereon Coordinator",
            update_interval=timedelta(minutes=1),
        )
        self._hass = hass
        self._vehicles = hass.data[DOMAIN][DATA_VEHICLES]
        self._config = config

        self._last_update = {}

    async def force_update(self):
        self._last_update = {}
        await self.async_refresh()

    async def _async_update_data(self):
        """Fetch data from API."""
        interval = self._config.get("interval", DEFAULT_INTERVAL)
        interval_charging = self._config.get("interval_charging", DEFAULT_INTERVAL_CHARGING)

        try:
            for vehicle in self._vehicles:
                if not vehicle in self._last_update:
                    self._last_update[vehicle] = 0

                # EV, decide which time to use
                if Feature.BATTERY_STATUS in self._vehicles[vehicle].features and self._vehicles[vehicle].plugged_in == PluggedStatus.PLUGGED:
                    _LOGGER.debug("Charging, using charging interval")
                    interval = interval_charging

                # Update on every cycle if HVAC on
                if self._vehicles[vehicle].hvac_status == HVACStatus.ON:
                    _LOGGER.debug("HVAC on, updating every cycle")
                    interval = 0

                # If we are overdue an update
                if time() > self._last_update[vehicle] + (interval * 60):
                    _LOGGER.debug("Update overdue, updating")
                    await self._hass.async_add_executor_job(self._vehicles[vehicle].refresh)
                    self._last_update[vehicle] = time()
                   
        except BaseException:
            _LOGGER.warning("Error communicating with API")
        return True


class StatisticsCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, config):
        """Initialise coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Statistics Coordinator",
            update_interval=timedelta(minutes=config.get("interval_statistics", DEFAULT_INTERVAL_STATISTICS)),
        )
        self._hass = hass
        self._vehicles = hass.data[DOMAIN][DATA_VEHICLES]

    async def _async_update_data(self):
        """Fetch data from API."""
        output = {}
        try:
            for vehicle in self._vehicles:
                if not Feature.DRIVING_JOURNEY_HISTORY in self._vehicles[vehicle].features:
                    continue

                output[vehicle] = {
                    'daily': await self._hass.async_add_executor_job(self._vehicles[vehicle].fetch_trip_histories, Period.DAILY),
                    'monthly': await self._hass.async_add_executor_job(self._vehicles[vehicle].fetch_trip_histories, Period.MONTHLY)
                }
        except BaseException:
            _LOGGER.warning("Error communicating with statistics API")
        
        return output
