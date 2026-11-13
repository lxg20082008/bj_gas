# -*- coding: utf-8 -*-
"""北京燃气传感器实体定义（适配 HA 2026.7）。"""
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import (
    STATE_UNKNOWN,
    UnitOfVolume,
    UnitOfElectricPotential,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from .const import DOMAIN

GAS_SENSORS = {
    "balance": {
        "name": "燃气费余额",
        "icon": "hass:cash-100",
        "unit_of_measurement": "元",
        "attributes": ["last_update"],
    },
    "current_level": {
        "name": "当前燃气阶梯",
        "icon": "hass:stairs",
    },
    "current_price": {
        "name": "当前气价",
        "icon": "hass:cash-100",
        "unit_of_measurement": "元/m³",
    },
    "current_level_remain": {
        "name": "当前阶梯剩余额度",
        "device_class": SensorDeviceClass.GAS,
        "unit_of_measurement": UnitOfVolume.CUBIC_METERS,
    },
    "year_consume": {
        "name": "本年度用气量",
        "device_class": SensorDeviceClass.GAS,
        "state_class": SensorStateClass.TOTAL,
        "unit_of_measurement": UnitOfVolume.CUBIC_METERS,
    },
    "month_reg_qty": {
        "name": "当月用气量",
        "device_class": SensorDeviceClass.GAS,
        "state_class": SensorStateClass.TOTAL,
        "unit_of_measurement": UnitOfVolume.CUBIC_METERS,
    },
    "battery_voltage": {
        "name": "气表电池电压",
        "device_class": SensorDeviceClass.VOLTAGE,
        "unit_of_measurement": UnitOfElectricPotential.VOLT,
    },
    "mtr_status": {
        "name": "阀门状态",
        # 阀门状态是文本（开阀/关阀），不设数值型 device_class
    },
}


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    sensors = []
    coordinator = hass.data[DOMAIN]
    for user_code, data in coordinator.data.items():
        for key in GAS_SENSORS.keys():
            # 值为 None 的字段（如接口缺失的当月用气量）不创建实体
            if key in data.keys() and data[key] is not None:
                sensors.append(GASSensor(coordinator, user_code, key))
        for month in range(len(data["monthly_bills"])):
            sensors.append(GASHistorySensor(coordinator, user_code, month))
        for day in range(len(data["daily_bills"])):
            sensors.append(GASDailyBillSensor(coordinator, user_code, day))
    async_add_devices(sensors, True)


class GASBaseSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._unique_id = None

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def should_poll(self):
        return False


def _safe_float(value):
    """安全转浮点，失败返回 STATE_UNKNOWN。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return STATE_UNKNOWN


class GASSensor(GASBaseSensor):
    def __init__(self, coordinator, user_code, sensor_key):
        super().__init__(coordinator)
        self._user_code = user_code
        self._sensor_key = sensor_key
        self._config = GAS_SENSORS[self._sensor_key]
        self._attributes = self._config.get("attributes")
        self._coordinator = coordinator
        self._unique_id = f"{DOMAIN}.gas_{user_code}_{sensor_key}"
        self.entity_id = self._unique_id

    def get_value(self, attribute=None):
        try:
            data = self._coordinator.data.get(self._user_code) or {}
            if attribute is None:
                return data.get(self._sensor_key)
            return data.get(attribute)
        except KeyError:
            return STATE_UNKNOWN

    @property
    def name(self):
        return self._config.get("name")

    @property
    def state(self):
        value = self.get_value()
        # 数值型字段统一转 float，避免字符串状态
        if self._config.get("device_class") and value is not STATE_UNKNOWN:
            return _safe_float(value)
        return value

    @property
    def icon(self):
        return self._config.get("icon")

    @property
    def device_class(self):
        return self._config.get("device_class")

    @property
    def state_class(self):
        return self._config.get("state_class")

    @property
    def unit_of_measurement(self):
        return self._config.get("unit_of_measurement")

    @property
    def extra_state_attributes(self):
        attributes = {}
        if self._attributes is not None:
            try:
                for attribute in self._attributes:
                    attributes[attribute] = self.get_value(attribute)
            except KeyError:
                pass
        return attributes


class GASHistorySensor(GASBaseSensor):
    def __init__(self, coordinator, user_code, index):
        super().__init__(coordinator)
        self._user_code = user_code
        self._coordinator = coordinator
        self._index = index
        self._unique_id = f"{DOMAIN}.gas_{user_code}_monthly_{index + 1}"
        self.entity_id = self._unique_id

    def _bill(self):
        """安全获取当前索引的月度账单条目。"""
        try:
            return self._coordinator.data.get(self._user_code).get("monthly_bills")[self._index]
        except (KeyError, IndexError, TypeError, AttributeError):
            return None

    @property
    def name(self):
        bill = self._bill()
        if bill:
            return "燃气消耗 " + str(bill.get("mon") or "")
        return STATE_UNKNOWN

    @property
    def state(self):
        bill = self._bill()
        if bill:
            return _safe_float(bill.get("regQty"))
        return STATE_UNKNOWN

    @property
    def extra_state_attributes(self):
        bill = self._bill()
        if bill:
            return {"consume_bill": _safe_float(bill.get("amt"))}
        return {}

    @property
    def device_class(self):
        return SensorDeviceClass.GAS

    @property
    def unit_of_measurement(self):
        return UnitOfVolume.CUBIC_METERS


class GASDailyBillSensor(GASBaseSensor):
    def __init__(self, coordinator, user_code, index):
        super().__init__(coordinator)
        self._user_code = user_code
        self._coordinator = coordinator
        self._index = index
        self._unique_id = f"{DOMAIN}.gas_{user_code}_daily_{index + 1}"
        self.entity_id = self._unique_id

    def _bill(self):
        """安全获取当前索引的每日账单条目。"""
        try:
            return self._coordinator.data.get(self._user_code).get("daily_bills")[self._index]
        except (KeyError, IndexError, TypeError, AttributeError):
            return None

    @property
    def name(self):
        bill = self._bill()
        if bill:
            return "燃气消耗 " + str(bill.get("day") or "")[:10]
        return STATE_UNKNOWN

    @property
    def state(self):
        bill = self._bill()
        if bill:
            return _safe_float(bill.get("regQty"))
        return STATE_UNKNOWN

    @property
    def device_class(self):
        return SensorDeviceClass.GAS

    @property
    def unit_of_measurement(self):
        return UnitOfVolume.CUBIC_METERS
