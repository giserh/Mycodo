# -*- coding: utf-8 -*-
import logging

import sqlalchemy
from flask import flash
from flask import url_for
from flask_babel import gettext

from mycodo.config import OUTPUT_INFO
from mycodo.databases.models import DisplayOrder
from mycodo.databases.models import Output
from mycodo.mycodo_client import DaemonControl
from mycodo.mycodo_flask.extensions import db
from mycodo.mycodo_flask.utils.utils_general import add_display_order
from mycodo.mycodo_flask.utils.utils_general import delete_entry_with_id
from mycodo.mycodo_flask.utils.utils_general import flash_success_errors
from mycodo.mycodo_flask.utils.utils_general import reorder
from mycodo.mycodo_flask.utils.utils_general import return_dependencies
from mycodo.utils.system_pi import csv_to_list_of_int
from mycodo.utils.system_pi import is_int
from mycodo.utils.system_pi import list_to_csv

logger = logging.getLogger(__name__)



#
# Output manipulation
#

def output_add(form_add):
    action = '{action} {controller}'.format(
        action=gettext("Add"),
        controller=gettext("Output"))
    error = []

    unmet_deps = return_dependencies(form_add.relay_type.data)
    if unmet_deps:
        error.append("The {dev} device you're trying to add has unmet dependencies: {dep}".format(
            dev=form_add.relay_type.data, dep=unmet_deps))

    if is_int(form_add.relay_quantity.data, check_range=[1, 20]):
        for _ in range(0, form_add.relay_quantity.data):
            try:
                new_relay = Output()
                new_relay.name = OUTPUT_INFO[form_add.relay_type.data]['name']
                new_relay.relay_type = form_add.relay_type.data
                if form_add.relay_type.data == 'wired':
                    new_relay.on_at_start = False
                elif form_add.relay_type.data == 'wireless_433MHz_pi_switch':
                    new_relay.protocol = 1
                    new_relay.pulse_length = 189
                    new_relay.on_command = '22559'
                    new_relay.off_command = '22558'
                elif form_add.relay_type.data == 'command':
                    new_relay.on_command = '/home/pi/script_on.sh'
                    new_relay.off_command = '/home/pi/script_off.sh'
                elif form_add.relay_type.data == 'command_pwm':
                    new_relay.pwm_command = '/home/pi/script_pwm.sh ((duty_cycle))'
                elif form_add.relay_type.data == 'pwm':
                    new_relay.pwm_hertz = 22000
                    new_relay.pwm_library = 'pigpio_any'

                if not error:
                    new_relay.save()
                    display_order = csv_to_list_of_int(DisplayOrder.query.first().relay)
                    DisplayOrder.query.first().relay = add_display_order(
                        display_order, new_relay.id)
                    db.session.commit()
                    manipulate_output('Add', new_relay.id)
            except sqlalchemy.exc.OperationalError as except_msg:
                error.append(except_msg)
            except sqlalchemy.exc.IntegrityError as except_msg:
                error.append(except_msg)
    else:
        error_msg = "{error}. {accepted_values}: 1-20".format(
            error=gettext("Invalid quantity"),
            accepted_values=gettext("Acceptable values")
        )
        error.append(error_msg)
    flash_success_errors(error, action, url_for('routes_page.page_output'))

    if unmet_deps:
        return 1


def output_mod(form_output):
    action = '{action} {controller}'.format(
        action=gettext("Modify"),
        controller=gettext("Output"))
    error = []

    try:
        mod_relay = Output.query.filter(
            Output.id == form_output.relay_id.data).first()
        mod_relay.name = form_output.name.data
        mod_relay.amps = form_output.amps.data

        if mod_relay.relay_type == 'wired':
            if not is_int(form_output.gpio.data):
                error.append("BCM Pin must be an integer")
            mod_relay.pin = form_output.gpio.data
            mod_relay.trigger = bool(int(form_output.trigger.data))
        elif mod_relay.relay_type == 'wireless_433MHz_pi_switch':
            if not is_int(form_output.wiringpi_pin.data):
                error.append("Pin must be an integer")
            if not is_int(form_output.protocol.data):
                error.append("Protocol must be an integer")
            if not is_int(form_output.pulse_length.data):
                error.append("Pulse Length must be an integer")
            if not is_int(form_output.on_command.data):
                error.append("On Command must be an integer")
            if not is_int(form_output.off_command.data):
                error.append("Off Command must be an integer")
            mod_relay.pin = form_output.wiringpi_pin.data
            mod_relay.protocol = form_output.protocol.data
            mod_relay.pulse_length = form_output.pulse_length.data
            mod_relay.on_command = form_output.on_command.data
            mod_relay.off_command = form_output.off_command.data
        elif mod_relay.relay_type == 'command':
            mod_relay.on_command = form_output.on_command.data
            mod_relay.off_command = form_output.off_command.data
        elif mod_relay.relay_type == 'command_pwm':
            mod_relay.pwm_command = form_output.pwm_command.data
            mod_relay.pwm_invert_signal = form_output.pwm_invert_signal.data
        elif mod_relay.relay_type == 'pwm':
            mod_relay.pin = form_output.gpio.data
            mod_relay.pwm_hertz = form_output.pwm_hertz.data
            mod_relay.pwm_library = form_output.pwm_library.data
            mod_relay.pwm_invert_signal = form_output.pwm_invert_signal.data

        if (form_output.on_at_start.data == '-1' or
                mod_relay.relay_type in ['pwm', 'command_pwm']):
            mod_relay.on_at_start = None
        else:
            mod_relay.on_at_start = bool(int(form_output.on_at_start.data))

        if not error:
            db.session.commit()
            manipulate_output('Modify', form_output.relay_id.data)
    except Exception as except_msg:
        error.append(except_msg)
    flash_success_errors(error, action, url_for('routes_page.page_output'))


def output_del(form_output):
    action = '{action} {controller}'.format(
        action=gettext("Delete"),
        controller=gettext("Output"))
    error = []

    try:
        delete_entry_with_id(Output,
                             form_output.relay_id.data)
        display_order = csv_to_list_of_int(DisplayOrder.query.first().relay)
        display_order.remove(int(form_output.relay_id.data))
        DisplayOrder.query.first().relay = list_to_csv(display_order)
        db.session.commit()
        manipulate_output('Delete', form_output.relay_id.data)
    except Exception as except_msg:
        error.append(except_msg)
    flash_success_errors(error, action, url_for('routes_page.page_output'))


def output_reorder(relay_id, display_order, direction):
    action = '{action} {controller}'.format(
        action=gettext("Reorder"),
        controller=gettext("Output"))
    error = []
    try:
        status, reord_list = reorder(display_order,
                                     relay_id,
                                     direction)
        if status == 'success':
            DisplayOrder.query.first().relay = ','.join(map(str, reord_list))
            db.session.commit()
        else:
            error.append(reord_list)
    except Exception as except_msg:
        error.append(except_msg)
    flash_success_errors(error, action, url_for('routes_page.page_output'))


#
# Manipulate output settings while daemon is running
#

def manipulate_output(action, relay_id):
    """
    Add, delete, and modify output settings while the daemon is active

    :param relay_id: output ID in the SQL database
    :type relay_id: str
    :param action: "add", "del", or "mod"
    :type action: str
    """
    control = DaemonControl()
    return_values = control.relay_setup(action, relay_id)
    if return_values and len(return_values) > 1:
        if return_values[0]:
            flash(gettext("%(err)s",
                          err='{action} Output: Daemon response: {msg}'.format(
                              action=action,
                              msg=return_values[1])),
                  "error")
        else:
            flash(gettext("%(err)s",
                          err='{action} Output: Daemon response: {msg}'.format(
                              action=gettext(action),
                              msg=return_values[1])),
                  "success")
    else:
        flash(gettext("%(err)s",
                      err='{action} Output: Could not connect to Daemon'.format(
                          action=action)),
              "error")


#
# Output manipulation
#


def output_on_off(form_output):
    action = '{action} {controller}'.format(
        action=gettext("Actuate"),
        controller=gettext("Output"))
    error = []

    try:
        control = DaemonControl()
        output = Output.query.filter_by(id=form_output.relay_id.data).first()
        if output.relay_type == 'wired' and int(form_output.relay_pin.data) == 0:
            error.append(gettext("Cannot modulate output with a GPIO of 0"))
        elif form_output.on_submit.data:
            if output.relay_type in ['wired',
                                    'wireless_433MHz_pi_switch',
                                    'command']:
                if float(form_output.sec_on.data) <= 0:
                    error.append(gettext("Value must be greater than 0"))
                else:
                    return_value = control.relay_on(form_output.relay_id.data,
                                                    duration=float(form_output.sec_on.data))
                    flash(gettext("Output turned on for %(sec)s seconds: %(rvalue)s",
                                  sec=form_output.sec_on.data,
                                  rvalue=return_value),
                          "success")
            if output.relay_type == 'pwm':
                if int(form_output.relay_pin.data) == 0:
                    error.append(gettext("Invalid pin"))
                if output.pwm_hertz <= 0:
                    error.append(gettext("PWM Hertz must be a positive value"))
                if float(form_output.pwm_duty_cycle_on.data) <= 0:
                    error.append(gettext("PWM duty cycle must be a positive value"))
                if not error:
                    return_value = control.relay_on(form_output.relay_id.data,
                                                    duty_cycle=float(form_output.pwm_duty_cycle_on.data))
                    flash(gettext("PWM set to %(dc)s%% at %(hertz)s Hz: %(rvalue)s",
                                  dc=float(form_output.pwm_duty_cycle_on.data),
                                  hertz=output.pwm_hertz,
                                  rvalue=return_value),
                          "success")
        elif form_output.turn_on.data:
            return_value = control.relay_on(form_output.relay_id.data, 0)
            flash(gettext("Output turned on: %(rvalue)s",
                          rvalue=return_value), "success")
        elif form_output.turn_off.data:
            return_value = control.relay_off(form_output.relay_id.data)
            flash(gettext("Output turned off: %(rvalue)s",
                          rvalue=return_value), "success")
    except ValueError as except_msg:
        error.append('{err}: {msg}'.format(
            err=gettext("Invalid value"),
            msg=except_msg))
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('routes_page.page_output'))
