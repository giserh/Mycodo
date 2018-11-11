# -*- coding: utf-8 -*-
#
#  config_units.py - Mycodo unit settings
#

from flask_babel import lazy_gettext


# Measurement information
# First unit in list is the default unit when Input is created
MEASUREMENTS = {
    'altitude': {
        'name': lazy_gettext('Altitude'),
        'meas': 'altitude',
        'units': ['m', 'ft']},
    'battery': {
        'name': lazy_gettext('Battery'),
        'meas': 'battery',
        'units': ['percent', 'decimal']},
    'boolean': {
        'name': lazy_gettext('Boolean'),
        'meas': 'boolean',
        'units': ['bool']},
    'co2': {
        'name': lazy_gettext('CO2'),
        'meas': 'co2',
        'units': ['ppm', 'ppb', 'percent']},
    'cpu_load_1m': {
        'name': lazy_gettext('CPU Load 1 min'),
        'meas': 'cpu_load',
        'units': ['cpu_load']},
    'cpu_load_5m': {
        'name': lazy_gettext('CPU Load 5 min'),
        'meas': 'cpu_load',
        'units': ['cpu_load']},
    'cpu_load_15m': {
        'name': lazy_gettext('CPU Load 15 min'),
        'meas': 'cpu_load',
        'units': ['cpu_load']},
    'dewpoint': {
        'name': lazy_gettext('Dewpoint'),
        'meas': 'temperature',
        'units': ['C', 'F', 'K']},
    'disk_space': {
        'name': lazy_gettext('Disk'),
        'meas': 'disk_space',
        'units': ['MB', 'kB', 'GB']},
    'duration_time': {
        'name': lazy_gettext('Duration'),
        'meas': 'duration_time',
        'units': ['s']},
    'duty_cycle': {
        'name': lazy_gettext('Duty Cycle'),
        'meas': 'duty_cycle',
        'units': ['percent', 'decimal']},
    'edge': {
        'name': lazy_gettext('GPIO Edge'),
        'meas': 'edge',
        'units': ['bool']},
    'electrical_conductivity': {
        'name': lazy_gettext('Electrical Conductivity'),
        'meas': 'electrical_conductivity',
        'units': ['uS_cm']},
    'electrical_current': {
        'name': lazy_gettext('Electrical Current'),
        'meas': 'electrical_current',
        'units': ['A']},
    'electrical_potential': {
        'name': lazy_gettext('Electrical Potential'),
        'meas': 'electrical_potential',
        'units': ['V']},
    'frequency': {
        'name': lazy_gettext('Frequency'),
        'meas': 'frequency',
        'units': ['Hz', 'kHz', 'MHz']},
    'gpio_state': {
        'name': lazy_gettext('GPIO State'),
        'meas': 'gpio_state',
        'units': ['bool']},
    'humidity': {
        'name': lazy_gettext('Humidity'),
        'meas': 'humidity',
        'units': ['percent', 'decimal']},
    'humidity_ratio': {
        'name': lazy_gettext('Humidity Ratio'),
        'meas': 'humidity_ratio',
        'units': ['kg_kg']},
    'ion_concentration': {
        'name': lazy_gettext('Ion Concentration'),
        'meas': 'ion_concentration',
        'units': ['pH']},
    'light': {
        'name': lazy_gettext('Light'),
        'meas': 'light',
        'units': ['full', 'ir', 'lux']},
    'moisture': {
        'name': lazy_gettext('Moisture'),
        'meas': 'moisture',
        'units': ['unitless']},
    'particulate_matter_1_0': {
        'name': lazy_gettext('PM1'),
        'meas': 'particulate_matter_1_0',
        'units': ['ug_m3']},
    'particulate_matter_2_5': {
        'name': lazy_gettext('PM2.5'),
        'meas': 'particulate_matter_2_5',
        'units': ['ug_m3']},
    'particulate_matter_10_0': {
        'name': lazy_gettext('PM10'),
        'meas': 'particulate_matter_10_0',
        'units': ['ug_m3']},
    'pid_p_value': {
        'name': lazy_gettext('PID P-Value'),
        'meas': 'pid_value',
        'units': ['pid_value']},
    'pid_i_value': {
        'name': lazy_gettext('PID I-Value'),
        'meas': 'pid_value',
        'units': ['pid_value']},
    'pid_d_value': {
        'name': lazy_gettext('PID D-Value'),
        'meas': 'pid_value',
        'units': ['pid_value']},
    'pressure': {
        'name': lazy_gettext('Pressure'),
        'meas': 'pressure',
        'units': ['Pa', 'kPa']},
    'pulse_width': {
        'name': lazy_gettext('Pulse Width'),
        'meas': 'pulse_width',
        'units': ['us']},
    'revolutions': {
        'name': lazy_gettext('Revolutions'),
        'meas': 'revolutions',
        'units': ['rpm']},
    'setpoint': {
        'name': lazy_gettext('Setpoint'),
        'meas': 'setpoint',
        'units': ['setpoint']},
    'setpoint_band_min': {
        'name': lazy_gettext('Band Min'),
        'meas': 'setpoint_band_min',
        'units': ['setpoint']},
    'setpoint_band_max': {
        'name': lazy_gettext('Band Max'),
        'meas': 'setpoint_band_max',
        'units': ['setpoint']},
    'specific_enthalpy': {
        'name': lazy_gettext('Specific Enthalpy'),
        'meas': 'specific_enthalpy',
        'units': ['kJ_kg']},
    'specific_volume': {
        'name': lazy_gettext('Specific Volume'),
        'meas': 'specific_volume',
        'units': ['m3_kg']},
    'temperature': {
        'name': lazy_gettext('Temperature'),
        'meas': 'temperature',
        'units': ['C', 'F', 'K']},
    'voc': {
        'name': lazy_gettext('VOC'),
        'meas': 'voc',
        'units': ['ppb', 'ppm']},
}

# Measurement units
UNITS = {
    'unitless': {
        'name': '',
        'unit': ''},
    'us': {
        'name': lazy_gettext('Microsecond'),
        'unit': 'µs'},
    'uS_cm': {
        'name': lazy_gettext('Microsiemens per centimeter'),
        'unit': 'μS/cm'},
    'A': {
        'name': lazy_gettext('Amp'),
        'unit': 'A'},
    'bool': {
        'name': lazy_gettext('Boolean'),
        'unit': 'bool'},
    'C': {
        'name': lazy_gettext('Celsius'),
        'unit': '°C'},
    'cpu_load': {
        'name': lazy_gettext('CPU Load'),
        'unit': ''},
    'decimal': {
        'name': lazy_gettext('Decimal'),
        'unit': ''},
    'F': {
        'name': lazy_gettext('Fahrenheit'),
        'unit': '°F'},
    'ft': {
        'name': lazy_gettext('Foot'),
        'unit': 'ft'},
    'full': {
        'name': lazy_gettext('Full'),
        'unit': 'full'},
    'GB': {
        'name': lazy_gettext('Gigabyte'),
        'unit': 'GB'},
    'Hz': {
        'name': lazy_gettext('Hertz'),
        'unit': 'Hz'},
    'ir': {
        'name': lazy_gettext('Infrared'),
        'unit': 'IR'},
    'K': {
        'name': lazy_gettext('Kelvin'),
        'unit': '°K'},
    'kB': {
        'name': lazy_gettext('Kilobyte'),
        'unit': 'kB'},
    'kg_kg': {
        'name': lazy_gettext('Kilogram per kilogram'),
        'unit': 'kg/kg'},
    'kHz': {
        'name': lazy_gettext('Kilohertz'),
        'unit': 'kHz'},
    'kJ_kg': {
        'name': lazy_gettext('Kilojoule per kilogram'),
        'unit': 'kJ/kg'},
    'kPa': {
        'name': lazy_gettext('Kilopascal'),
        'unit': 'kPa'},
    'lux': {
        'name': lazy_gettext('Lux'),
        'unit': 'lx'},
    'm': {
        'name': lazy_gettext('Meter'),
        'unit': 'm'},
    'm3_kg': {
        'name': lazy_gettext('Cubic meters per kilogram'),
        'unit': 'm^3/kg'},
    'MHz': {
        'name': lazy_gettext('Megahertz'),
        'unit': 'MHz'},
    'MB': {
        'name': lazy_gettext('Megabyte'),
        'unit': 'MB'},
    'minute': {
        'name': lazy_gettext('Minute'),
        'unit': 'm'},
    'Pa': {
        'name': lazy_gettext('Pascal'),
        'unit': 'Pa'},
    'percent': {
        'name': lazy_gettext('Percent'),
        'unit': '%'},
    'pH': {
        'name': lazy_gettext('pH'),
        'unit': 'pH'},
    'pid_value': {
        'name': lazy_gettext('PID values'),
        'unit': ''},
    'ppb': {
        'name': lazy_gettext('Parts per billion'),
        'unit': 'ppb'},
    'ppm': {
        'name': lazy_gettext('Parts per million'),
        'unit': 'ppm'},
    'rpm': {
        'name': lazy_gettext('Revolutions per minute'),
        'unit': 'rpm'},
    's': {
        'name': lazy_gettext('Second'),
        'unit': 's'},
    'setpoint': {
        'name': lazy_gettext('Setpoint'),
        'unit': ''},
    'ug_m3': {
        'name': lazy_gettext('Microgram per cubic meter'),
        'unit': 'μg/m^3'},
    'V': {
        'name': lazy_gettext('Volt'),
        'unit': 'V'}
}

# Supported conversions
UNIT_CONVERSIONS = {
    # Temperature
    'C_to_F': 'x*(9/5)+32',
    'C_to_K': 'x+273.15',
    'F_to_C': '(x-32)*5/9',
    'F_to_K': '(x+459.67)*5/9',
    'K_to_C': 'x-273.15',
    'K_to_F': '(x*9/5)−459.67',

    # Frequency
    'Hz_to_kHz': 'x/1000',
    'Hz_to_MHz': 'x/1000000',
    'kHz_to_Hz': 'x*1000',
    'kHz_to_MHz': 'x/1000',
    'MHz_to_Hz': 'x*1000000',
    'MHz_to_kHz': 'x*1000',

    # Length
    'm_to_ft': 'x*3.2808399',
    'ft_to_m': 'x/3.2808399',

    # Disk size
    'kB_to_MB': 'x/1000',
    'kB_to_GB': 'x/1000000',
    'MB_to_kB': 'x*1000',
    'MB_to_GB': 'x/1000',
    'GB_to_kB': 'x*1000000',
    'GB_to_MB': 'X*1000',

    # Concentration
    'ppm_to_ppb': 'x*1000',
    'ppb_to_ppm': 'x/1000',
    'ppm_to_percent': 'x/10000',
    'ppb_to_percent': 'x/10000000',
    'percent_to_ppm': 'x*10000',
    'percent_to_ppb': 'x*10000000',

    # Number
    'percent_to_decimal': 'x/100',
    'decimal_to_percent': 'x*100',

    # Pressure
    'Pa_to_kPa': 'x/1000',
    'kPa_to_Pa': 'x*1000',

    # Time
    's_to_minute': 'x/60',
    'minute_to_s': 'x*60'
}
