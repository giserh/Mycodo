# coding=utf-8
import datetime
import time

from flask_babel import lazy_gettext

from mycodo.databases.models import Conversion
from mycodo.databases.models import DeviceMeasurements
from mycodo.inputs.base_input import AbstractInput
from mycodo.inputs.sensorutils import calculate_dewpoint
from mycodo.inputs.sensorutils import calculate_vapor_pressure_deficit
from mycodo.utils.database import db_retrieve_table_daemon
from mycodo.utils.influx import parse_measurement
from mycodo.utils.influx import write_influxdb_value


def constraints_pass_positive_value(mod_input, value):
    """
    Check if the user input is acceptable
    :param mod_input: SQL object with user-saved Input options
    :param value: float
    :return: tuple: (bool, list of strings)
    """
    errors = []
    all_passed = True
    # Ensure value is positive
    if value <= 0:
        all_passed = False
        errors.append("Must be a positive value")

    # Ensure logging interval and period options don't cause measurements to exceed device memory
    measurements_can_be_stored = 16512  # The memory of the device only permits 16512 measurements to be stored
    measurements_per_period = int(mod_input.period / value)
    if measurements_per_period > measurements_can_be_stored:
        all_passed = False
        errors.append(
            "Number of calculated measurements exceeds device memory: With a "
            "Logging Interval of {li} seconds and a download period of {per} "
            "seconds, {meas_t} measurements will be conducted, however, only "
            "{meas_a} measurements can be stored on the device. Either "
            "increase your Logging Interval or decrease the Input Period.".format(
                li=value,
                per=mod_input.period,
                meas_t=measurements_per_period,
                meas_a=measurements_can_be_stored))
    return all_passed, errors, mod_input


# Measurements
measurements_dict = {
    0: {
        'measurement': 'temperature',
        'unit': 'C'
    },
    1: {
        'measurement': 'humidity',
        'unit': 'percent'
    },
    2: {
        'measurement': 'battery',
        'unit': 'percent'
    },
    3: {
        'measurement': 'dewpoint',
        'unit': 'C'
    },
    4: {
        'measurement': 'vapor_pressure_deficit',
        'unit': 'Pa'
    }
}

# Input information
INPUT_INFORMATION = {
    'input_name_unique': 'SHT31_SMART_GADGET',
    'input_manufacturer': 'Sensorion',
    'input_name': 'SHT31 Smart Gadget',
    'measurements_name': 'Humidity/Temperature',
    'measurements_dict': measurements_dict,

    'options_enabled': [
        'bt_location',
        'measurements_select',
        'custom_options',
        'period',
        'pre_output',
        'log_level_debug'
    ],
    'options_disabled': ['interface'],

    'dependencies_module': [
        ('pip-pypi', 'filelock', 'filelock'),
        ('apt', 'pi-bluetooth', 'pi-bluetooth'),
        ('apt', 'libglib2.0-dev', 'libglib2.0-dev'),
        ('pip-pypi', 'bluepy', 'bluepy')

    ],

    'interfaces': ['BT'],
    'bt_location': '00:00:00:00:00:00',
    'bt_adapter': '0',

    'custom_options': [
        {
            'id': 'download_stored_data',
            'type': 'bool',
            'default_value': True,
            'name': lazy_gettext('Download Stored Data'),
            'phrase': lazy_gettext('Download the data logged to the device.')
        },
        {
            'id': 'logging_interval',
            'type': 'integer',
            'default_value': 600,
            'required': True,
            'constraints_pass': constraints_pass_positive_value,
            'name': lazy_gettext('Set Logging Interval'),
            'phrase': lazy_gettext(
                'Set the logging interval (seconds) the device will store '
                'measurements on its internal memory.')
        }
    ]
}


class InputModule(AbstractInput):
    """
    A support class for Sensorion's SHT31 Smart Gadget

    """
    def __init__(self, input_dev, testing=False):
        super(InputModule, self).__init__()
        self.setup_logger(testing=testing, name=__name__, input_dev=input_dev)
        self.running = True
        self.unique_id = input_dev.unique_id
        self._measurements = None
        self.download_stored_data = None
        self.logging_interval_ms = None
        self.gadget = None
        self.connected = False
        self.connect_error = None
        self.device_information = {}
        self.initialized = False
        self.last_downloaded_timestamp = None

        if not testing:
            from mycodo.devices.sht31_smart_gadget import SHT31
            from bluepy import btle
            import filelock

            self.device_measurements = db_retrieve_table_daemon(
                DeviceMeasurements).filter(
                    DeviceMeasurements.device_id == input_dev.unique_id)

            if input_dev.custom_options:
                for each_option in input_dev.custom_options.split(';'):
                    option = each_option.split(',')[0]
                    value = each_option.split(',')[1]
                    if option == 'download_stored_data':
                        self.download_stored_data = bool(value)
                    elif option == 'logging_interval':
                        self.logging_interval_ms = int(value) * 1000

            self.filelock = filelock
            self.lock_file_bluetooth = '/var/lock/bluetooth_dev_hci{}'.format(
                input_dev.bt_adapter)
            self.SHT31 = SHT31
            self.btle = btle
            self.location = input_dev.location
            self.bt_adapter = input_dev.bt_adapter

    def connect(self):
        # Make three attempts to connect
        for _ in range(3):
            if not self.running:
                break
            try:
                self.gadget = self.SHT31(
                    addr=self.location, iface=self.bt_adapter)
                self.connected = True
                self.connect_error = None
                break
            except self.btle.BTLEException as e:
                self.connect_error = e
            time.sleep(0.1)

        if not self.connected:
            self.logger.error(
                "Could not connect: {}".format(self.connect_error))

    def disconnect(self):
        try:
            self.gadget.disconnect()
        except self.btle.BTLEException as e:
            self.logger.error("Disconnect Error: {}".format(e))
        except Exception:
            self.logger.exception("Disconnecting")
        finally:
            self.connected = False

    def download_data(self):
        # Clear data previously stored in dictionary
        self.gadget.loggedDataReadout = {'Temp': {}, 'Humi': {}}

        # Download stored data starting from self.gadget.newestTimeStampMs
        self.gadget.readLoggedDataInterval(
            startMs=self.gadget.newestTimeStampMs)

        while self.running:
            if (not self.gadget.waitForNotifications(5) or
                    not self.gadget.isLogReadoutInProgress()):
                break  # Done reading data

        list_timestamps_temp = []
        list_timestamps_humi = []

        # Store logged temperature
        measurement = self.device_measurements.filter(
            DeviceMeasurements.channel == 0).first()
        conversion = db_retrieve_table_daemon(
            Conversion, unique_id=measurement.conversion_id)
        for each_ts, each_measure in self.gadget.loggedDataReadout['Temp'].items():
            if not self.running:
                break
            list_timestamps_temp.append(each_ts)
            datetime_ts = datetime.datetime.utcfromtimestamp(each_ts / 1000)
            if self.is_enabled(0):
                if -200 > each_measure or each_measure > 200:
                    continue  # Temperature outside acceptable range

                measurement_single = {
                    0: {
                        'measurement': 'temperature',
                        'unit': 'C',
                        'value': each_measure
                    }
                }
                measurement_single = parse_measurement(
                    conversion,
                    measurement,
                    measurement_single,
                    measurement.channel,
                    measurement_single[0])
                write_influxdb_value(
                    self.unique_id,
                    measurement_single[0]['unit'],
                    value=measurement_single[0]['value'],
                    measure=measurement_single[0]['measurement'],
                    channel=0,
                    timestamp=datetime_ts)

        # Store logged humidity
        measurement = self.device_measurements.filter(
            DeviceMeasurements.channel == 1).first()
        conversion = db_retrieve_table_daemon(
            Conversion, unique_id=measurement.conversion_id)
        for each_ts, each_measure in self.gadget.loggedDataReadout['Humi'].items():
            if not self.running:
                break
            list_timestamps_humi.append(each_ts)
            datetime_ts = datetime.datetime.utcfromtimestamp(each_ts / 1000)
            if self.is_enabled(1):
                if 0 >= each_measure or each_measure > 100:
                    continue  # Humidity outside acceptable range

                measurement_single = {
                    1: {
                        'measurement': 'humidity',
                        'unit': 'percent',
                        'value': each_measure
                    }
                }
                measurement_single = parse_measurement(
                    conversion,
                    measurement,
                    measurement_single,
                    measurement.channel,
                    measurement_single[1])
                write_influxdb_value(
                    self.unique_id,
                    measurement_single[1]['unit'],
                    value=measurement_single[1]['value'],
                    measure=measurement_single[1]['measurement'],
                    channel=1,
                    timestamp=datetime_ts)

        # Find common timestamps from both temperature and humidity lists
        list_timestamps_both = list(
            set(list_timestamps_temp).intersection(list_timestamps_humi))

        for each_ts in list_timestamps_both:
            if not self.running:
                break

            temperature = self.gadget.loggedDataReadout['Temp'][each_ts]
            humidity = self.gadget.loggedDataReadout['Humi'][each_ts]

            if ((-200 > temperature or temperature > 200) or
                    (0 > humidity or humidity > 100)):
                continue  # Measurement outside acceptable range

            datetime_ts = datetime.datetime.utcfromtimestamp(each_ts / 1000)
            # Calculate and store dew point
            if (self.is_enabled(3) and
                    self.is_enabled(0) and
                    self.is_enabled(1)):
                measurement = self.device_measurements.filter(
                    DeviceMeasurements.channel == 3).first()
                conversion = db_retrieve_table_daemon(
                    Conversion, unique_id=measurement.conversion_id)
                dewpoint = calculate_dewpoint(temperature, humidity)
                measurement_single = {
                    3: {
                        'measurement': 'dewpoint',
                        'unit': 'C',
                        'value': dewpoint
                    }
                }
                measurement_single = parse_measurement(
                    conversion,
                    measurement,
                    measurement_single,
                    measurement.channel,
                    measurement_single[3])
                write_influxdb_value(
                    self.unique_id,
                    measurement_single[3]['unit'],
                    value=measurement_single[3]['value'],
                    measure=measurement_single[3]['measurement'],
                    channel=3,
                    timestamp=datetime_ts)

            # Calculate and store vapor pressure deficit
            if (self.is_enabled(4) and
                    self.is_enabled(0) and
                    self.is_enabled(1)):
                measurement = self.device_measurements.filter(
                    DeviceMeasurements.channel == 4).first()
                conversion = db_retrieve_table_daemon(
                    Conversion, unique_id=measurement.conversion_id)
                vpd = calculate_vapor_pressure_deficit(temperature, humidity)
                measurement_single = {
                    4: {
                        'measurement': 'vapor_pressure_deficit',
                        'unit': 'Pa',
                        'value': vpd
                    }
                }
                measurement_single = parse_measurement(
                    conversion,
                    measurement,
                    measurement_single,
                    measurement.channel,
                    measurement_single[4])
                write_influxdb_value(
                    self.unique_id,
                    measurement_single[4]['unit'],
                    value=measurement_single[4]['value'],
                    measure=measurement_single[4]['measurement'],
                    channel=4,
                    timestamp=datetime_ts)

        # Download successfully finished, set newest timestamp
        self.gadget.newestTimeStampMs = self.gadget.tmp_newestTimeStampMs

    def get_device_information(self):
        if 'info_timestamp' not in self.device_information:
            self.initialize()

        if 'info_timestamp' in self.device_information:
            return self.device_information

    def get_measurement(self):
        """ Obtain and return the measurements """
        self.return_dict = measurements_dict.copy()

        self.logger.debug("Starting measurement")
        try:
            with self.filelock.FileLock(self.lock_file_bluetooth, timeout=3600):
                if not self.initialized:
                    self.initialize()

                if not self.connected:
                    self.connect()

                if self.connected:
                    try:
                        # Download stored data
                        if self.download_stored_data:
                            self.download_data()
                            if not self.running:
                                return

                        # Set logging interval if not already set
                        if ('logger_interval_ms' in self.device_information
                                and self.logging_interval_ms != self.device_information['logger_interval_ms']):
                            self.set_logging_interval()

                        # Get battery percent charge
                        if self.is_enabled(2):
                            self.set_value(2, self.gadget.readBattery())

                        # Get temperature and humidity last so their timestamp in the
                        # database will be the most accurate
                        if self.is_enabled(0):
                            self.set_value(0, self.gadget.readTemperature())

                        if self.is_enabled(1):
                            self.set_value(1, self.gadget.readHumidity())
                    except self.btle.BTLEDisconnectError:
                        self.logger.error("Disconnected")
                        return
                    except Exception:
                        self.logger.exception("Unknown Error")
                        return
                    finally:
                        self.disconnect()

                    if (self.is_enabled(3) and
                            self.is_enabled(0) and
                            self.is_enabled(1)):
                        self.set_value(3, calculate_dewpoint(
                            self.get_value(0), self.get_value(1)))

                    if (self.is_enabled(4) and
                            self.is_enabled(0) and
                            self.is_enabled(1)):
                        self.set_value(4, calculate_vapor_pressure_deficit(
                            self.get_value(0), self.get_value(1)))

                    self.logger.debug("Completed measurement")
                    return self.return_dict
                else:
                    self.logger.debug("Not connected: Not measuring")

        except self.filelock.Timeout:
            self.logger.error("Lock timeout")

    def initialize(self):
        """Initialize the device by obtaining sensor information"""
        if not self.connected:
            self.connect()

        if self.connected:
            # Fill device information dictionary
            self.device_information['manufacturer'] = self.gadget.readManufacturerNameString()
            self.device_information['model'] = self.gadget.readModelNumberString()
            self.device_information['serial_number'] = self.gadget.readSerialNumberString()
            self.device_information['device_name'] = self.gadget.readDeviceName()
            self.device_information['firmware_revision'] = self.gadget.readFirmwareRevisionString()
            self.device_information['hardware_revision'] = self.gadget.readHardwareRevisionString()
            self.device_information['software_revision'] = self.gadget.readSoftwareRevisionString()
            self.device_information['logger_interval_ms'] = self.gadget.readLoggerIntervalMs()
            self.device_information['battery'] = self.gadget.readBattery()
            self.device_information['info_timestamp'] = int(time.time() * 1000)
            self.logger.info(
                "{man}, {mod}, SN: {sn}, Name: {name}, Firmware: {fw}, "
                "Hardware: {hw}, Software: {sw}, Log Interval: {sec} sec".format(
                    man=self.device_information['manufacturer'],
                    mod=self.device_information['model'],
                    sn=self.device_information['serial_number'],
                    name=self.device_information['device_name'],
                    fw=self.device_information['firmware_revision'],
                    hw=self.device_information['hardware_revision'],
                    sw=self.device_information['software_revision'],
                    sec=self.device_information['logger_interval_ms'] / 1000))
        self.initialized = True

    def set_logging_interval(self):
        """Set logging interval (resets memory; set after downloading data)"""
        if not self.connected:
            self.connect()

        if self.connected:
            self.gadget.setLoggerIntervalMs(self.logging_interval_ms)
            self.device_information['logger_interval_ms'] = self.logging_interval_ms
            self.logger.info(
                "Set log interval: {} sec".format(self.logging_interval_ms / 1000))
