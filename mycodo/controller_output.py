# coding=utf-8
#
# controller_output.py - Output controller to manage turning outputs on/off
#
#  Copyright (C) 2017  Kyle T. Gabriel
#
#  This file is part of Mycodo
#
#  Mycodo is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Mycodo is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Mycodo. If not, see <http://www.gnu.org/licenses/>.
#
#  Contact at kylegabriel.com

import datetime
import logging
import pigpio
import RPi.GPIO as GPIO
import threading
import time
import timeit

from sqlalchemy import and_
from sqlalchemy import or_

from mycodo_client import DaemonControl
from databases.models import Conditional
from databases.models import ConditionalActions
from databases.models import Misc
from databases.models import Output
from databases.models import SMTP
from devices.wireless_433mhz_pi_switch import Transmit433MHz
from utils.database import db_retrieve_table_daemon
from utils.influx import write_influxdb_value
from utils.send_data import send_email
from utils.system_pi import cmd_output


class OutputController(threading.Thread):
    """
    class for controlling outputs

    """
    def __init__(self):
        threading.Thread.__init__(self)

        self.logger = logging.getLogger("mycodo.output")

        self.thread_startup_timer = timeit.default_timer()
        self.thread_shutdown_timer = 0
        self.control = DaemonControl()

        self.output_id = {}
        self.output_unique_id = {}
        self.output_type = {}
        self.output_name = {}
        self.output_pin = {}
        self.output_amps = {}
        self.output_trigger = {}
        self.output_on_at_start = {}
        self.output_on_until = {}
        self.output_last_duration = {}
        self.output_on_duration = {}

        # wireless
        self.output_protocol = {}
        self.output_pulse_length = {}
        self.output_bit_length = {}
        self.output_on_command = {}
        self.output_off_command = {}
        self.wireless_pi_switch = {}

        # PWM
        self.pwm_hertz = {}
        self.pwm_library = {}
        self.pwm_output = {}
        self.pwm_state = {}
        self.pwm_time_turned_on = {}

        self.output_time_turned_on = {}

        self.logger.debug("Initializing Outputs")
        try:
            smtp = db_retrieve_table_daemon(SMTP, entry='first')
            self.smtp_max_count = smtp.hourly_max
            self.smtp_wait_time = time.time() + 3600
            self.smtp_timer = time.time()
            self.email_count = 0
            self.allowed_to_send_notice = True

            outputs = db_retrieve_table_daemon(Output, entry='all')
            self.all_outputs_initialize(outputs)
            # Turn all outputs off
            self.all_outputs_off()
            # Turn outputs on that are set to be on at start
            self.all_outputs_on()
            self.logger.debug("Outputs Initialized")

        except Exception as except_msg:
            self.logger.exception(
                "Problem initializing outputs: {err}".format(err=except_msg))

        self.running = False

    def run(self):
        try:
            self.running = True
            self.logger.info(
                "Output controller activated in {:.1f} ms".format(
                    (timeit.default_timer() - self.thread_startup_timer)*1000))
            while self.running:
                current_time = datetime.datetime.now()
                for output_id in self.output_id:
                    # Is the current time past the time the output was supposed
                    # to turn off at?
                    if (self.output_on_until[output_id] < current_time and
                            self.output_on_duration[output_id] and
                            self.output_pin[output_id] is not None):

                        # Use threads to prevent a slow execution of a
                        # process that could slow the loop
                        turn_output_off = threading.Thread(
                            target=self.output_on_off,
                            args=(output_id,
                                  'off',))
                        turn_output_off.start()

                        if self.output_last_duration[output_id] > 0:
                            duration = float(self.output_last_duration[output_id])
                            timestamp = datetime.datetime.utcnow() - datetime.timedelta(seconds=duration)
                            write_db = threading.Thread(
                                target=write_influxdb_value,
                                args=(self.output_unique_id[output_id],
                                      'duration_sec',
                                      duration,
                                      timestamp,))
                            write_db.start()

                time.sleep(0.10)
        finally:
            self.all_outputs_off()
            self.cleanup_gpio()
            self.running = False
            self.logger.info(
                "Output controller deactivated in {:.1f} ms".format(
                    (timeit.default_timer() - self.thread_shutdown_timer)*1000))

    def output_on_off(self, output_id, state,
                     duration=0.0,
                     min_off=0.0,
                     duty_cycle=0.0,
                     trigger_conditionals=True):
        """
        Turn a output on or off
        The GPIO may be either HIGH or LOW to activate a output. This trigger
        state will be referenced to determine if the GPIO needs to be high or
        low to turn the output on or off.

        Conditionals will be checked for each action requested of a output, and
        if true, those conditional actions will be executed. For example:
            'If output 1 turns on, turn output 3 off'

        :param output_id: Unique ID for output
        :type output_id: int
        :param state: What state is desired? 'on' or 'off'
        :type state: str
        :param duration: If state is 'on', a duration can be set to turn the output off after
        :type duration: float
        :param min_off: Don't turn on if not off for at least this duration (0 = disabled)
        :type min_off: float
        :param duty_cycle: Duty cycle of PWM output
        :type duty_cycle: float
        :param trigger_conditionals: Whether to trigger conditionals to act or not
        :type trigger_conditionals: bool
        """
        # Check if output exists
        output_id = int(output_id)
        if output_id not in self.output_id:
            self.logger.warning(
                "Cannot turn {state} Output with ID {id}. "
                "It doesn't exist".format(
                    state=state, id=output_id))
            return 1

        # Signaled to turn output on
        if state == 'on':

            # Check if pin is valid
            if (self.output_type[output_id] in ['pwm',
                                              'wired',
                                              'wireless_433MHz_pi_switch'] and
                    self.output_pin[output_id] is None):
                self.logger.warning(
                    u"Invalid pin for output {id} ({name}): {pin}.".format(
                        id=self.output_id[output_id],
                        name=self.output_name[output_id],
                        pin=self.output_pin[output_id]))
                return 1

            # Check if max amperage will be exceeded
            if self.output_type[output_id] in ['command',
                                             'wired',
                                             'wireless_433MHz_pi_switch']:
                current_amps = self.current_amp_load()
                max_amps = db_retrieve_table_daemon(Misc, entry='first').max_amps
                if current_amps + self.output_amps[output_id] > max_amps:
                    self.logger.warning(
                        u"Cannot turn output {} ({}) On. If this output turns on, "
                        u"there will be {} amps being drawn, which exceeds the "
                        u"maximum set draw of {} amps.".format(
                            self.output_id[output_id],
                            self.output_name[output_id],
                            current_amps,
                            max_amps))
                    return 1

                # If the output is used in a PID, a minimum off duration is set,
                # and if the off duration has surpassed that amount of time (i.e.
                # has it been off for longer then the minimum off duration?).
                current_time = datetime.datetime.now()
                if (min_off and not self.is_on(output_id) and
                        current_time > self.output_on_until[output_id]):
                    off_seconds = (current_time - self.output_on_until[output_id]).total_seconds()
                    if off_seconds < min_off:
                        self.logger.debug(
                            u"Output {id} ({name}) instructed to turn on by PID, "
                            u"however the minimum off period of {min_off_sec} "
                            u"seconds has not been reached yet (it has only been "
                            u"off for {off_sec} seconds).".format(
                                id=self.output_id[output_id],
                                name=self.output_name[output_id],
                                min_off_sec=min_off,
                                off_sec=off_seconds))
                        return 1

            # Turn output on for a duration
            if (self.output_type[output_id] in ['command',
                                              'wired',
                                              'wireless_433MHz_pi_switch'] and
                    duration):
                time_now = datetime.datetime.now()
                if self.is_on(output_id) and self.output_on_duration[output_id]:
                    if self.output_on_until[output_id] > time_now:
                        remaining_time = (self.output_on_until[output_id] - time_now).total_seconds()
                    else:
                        remaining_time = 0
                    time_on = self.output_last_duration[output_id] - remaining_time
                    self.logger.debug(
                        u"Output {rid} ({rname}) is already on for a duration "
                        u"of {ron:.2f} seconds (with {rremain:.2f} seconds "
                        u"remaining). Recording the amount of time the output "
                        u"has been on ({rbeenon:.2f} sec) and updating the on "
                        u"duration to {rnewon:.2f} seconds.".format(
                            rid=self.output_id[output_id],
                            rname=self.output_name[output_id],
                            ron=self.output_last_duration[output_id],
                            rremain=remaining_time,
                            rbeenon=time_on,
                            rnewon=duration))
                    self.output_on_until[output_id] = time_now + datetime.timedelta(seconds=duration)
                    self.output_last_duration[output_id] = duration

                    if time_on > 0:
                        # Write the duration the output was ON to the
                        # database at the timestamp it turned ON
                        duration = float(time_on)
                        timestamp = datetime.datetime.utcnow() - datetime.timedelta(seconds=duration)
                        write_db = threading.Thread(
                            target=write_influxdb_value,
                            args=(self.output_unique_id[output_id],
                                  'duration_sec',
                                  duration,
                                  timestamp,))
                        write_db.start()

                    return 0
                elif self.is_on(output_id) and not self.output_on_duration:
                    self.output_on_duration[output_id] = True
                    self.output_on_until[output_id] = time_now + datetime.timedelta(seconds=duration)
                    self.output_last_duration[output_id] = duration
                    self.logger.debug(
                        u"Output {id} ({name}) is currently on without a "
                        u"duration. Turning into a duration  of {dur:.1f} "
                        u"seconds.".format(
                            id=self.output_id[output_id],
                            name=self.output_name[output_id],
                            dur=duration))
                    return 0
                else:
                    self.output_on_until[output_id] = time_now + datetime.timedelta(seconds=duration)
                    self.output_on_duration[output_id] = True
                    self.output_last_duration[output_id] = duration
                    self.logger.debug(
                        u"Output {id} ({name}) on for {dur:.1f} "
                        u"seconds.".format(
                            id=self.output_id[output_id],
                            name=self.output_name[output_id],
                            dur=duration))
                    self.output_switch(output_id, 'on')

            # Just turn output on
            elif self.output_type[output_id] in ['command',
                                               'wired',
                                               'wireless_433MHz_pi_switch']:
                if self.is_on(output_id):
                    self.logger.warning(
                        u"Output {id} ({name}) is already on.".format(
                            id=self.output_id[output_id],
                            name=self.output_name[output_id]))
                    return 1
                else:
                    # Record the time the output was turned on in order to
                    # calculate and log the total duration is was on, when
                    # it eventually turns off.
                    self.output_time_turned_on[output_id] = datetime.datetime.now()
                    self.logger.debug(
                        u"Output {id} ({name}) ON at {timeon}.".format(
                            id=self.output_id[output_id],
                            name=self.output_name[output_id],
                            timeon=self.output_time_turned_on[output_id]))
                    self.output_switch(output_id, 'on')

            # PWM output
            elif self.output_type[output_id] == 'pwm':
                # Record the time the PWM was turned on
                if self.pwm_hertz[output_id] <= 0:
                    self.logger.warning(u"PWM Hertz must be a positive value")
                    return 1
                self.pwm_time_turned_on[output_id] = datetime.datetime.now()
                self.logger.debug(
                    u"PWM {id} ({name}) ON with a duty cycle of {dc:.2f}% at {hertz} Hz".format(
                        id=self.output_id[output_id],
                        name=self.output_name[output_id],
                        dc=abs(duty_cycle),
                        hertz=self.pwm_hertz[output_id]))
                self.output_switch(output_id, 'on', duty_cycle=duty_cycle)

                # Write the duty cycle of the PWM to the database
                write_db = threading.Thread(
                    target=write_influxdb_value,
                    args=(self.output_unique_id[output_id],
                          'duty_cycle',
                          duty_cycle,))
                write_db.start()

        # Signaled to turn output off
        elif state == 'off':
            if not self._is_setup(output_id):
                return
            if (self.output_type[output_id] in ['pwm',
                                              'wired',
                                              'wireless_433MHz_pi_switch'] and
                    self.output_pin[output_id] is None):
                return

            self.output_switch(output_id, 'off')

            self.logger.debug(u"Output {id} ({name}) turned off.".format(
                    id=self.output_id[output_id],
                    name=self.output_name[output_id]))

            # Write PWM duty cycle to database
            if (self.output_type[output_id] == 'pwm' and
                    self.pwm_time_turned_on[output_id] is not None):
                # Write the duration the PWM was ON to the database
                # at the timestamp it turned ON
                duration = (datetime.datetime.now() - self.pwm_time_turned_on[output_id]).total_seconds()
                self.pwm_time_turned_on[output_id] = None
                timestamp = datetime.datetime.utcnow() - datetime.timedelta(seconds=duration)
                write_db = threading.Thread(
                    target=write_influxdb_value,
                    args=(self.output_unique_id[output_id],
                          'duty_cycle',
                          duty_cycle,
                          timestamp,))
                write_db.start()

            # Write output duration on to database
            elif (self.output_time_turned_on[output_id] is not None or
                    self.output_on_duration[output_id]):
                duration = 0
                if self.output_on_duration[output_id]:
                    remaining_time = 0
                    time_now = datetime.datetime.now()
                    if self.output_on_until[output_id] > time_now:
                        remaining_time = (self.output_on_until[output_id] - time_now).total_seconds()
                    duration = self.output_last_duration[output_id] - remaining_time
                    self.output_on_duration[output_id] = False
                    self.output_on_until[output_id] = datetime.datetime.now()

                if self.output_time_turned_on[output_id] is not None:
                    # Write the duration the output was ON to the database
                    # at the timestamp it turned ON
                    duration = (datetime.datetime.now() - self.output_time_turned_on[output_id]).total_seconds()
                    self.output_time_turned_on[output_id] = None

                timestamp = datetime.datetime.utcnow() - datetime.timedelta(seconds=duration)
                write_db = threading.Thread(
                    target=write_influxdb_value,
                    args=(self.output_unique_id[output_id],
                          'duration_sec',
                          duration,
                          timestamp,))
                write_db.start()

        if trigger_conditionals:
            self.check_conditionals(output_id,
                                    state=state,
                                    on_duration=duration,
                                    duty_cycle=duty_cycle)

    def output_switch(self, output_id, state, duty_cycle=None):
        """Conduct the actual execution of GPIO state change, PWM, or command execution"""
        if self.output_type[output_id] == 'wired':
            if state == 'on':
                GPIO.output(self.output_pin[output_id],
                            self.output_trigger[output_id])
            elif state == 'off':
                GPIO.output(self.output_pin[output_id],
                            not self.output_trigger[output_id])

        elif self.output_type[output_id] == 'wireless_433MHz_pi_switch':
            if state == 'on':
                self.wireless_pi_switch[output_id].transmit(
                    int(self.output_on_command[output_id]))
            elif state == 'off':
                self.wireless_pi_switch[output_id].transmit(
                    int(self.output_off_command[output_id]))

        elif self.output_type[output_id] == 'command':
            if state == 'on' and self.output_on_command[output_id]:
                cmd_return, _, cmd_status = cmd_output(
                    self.output_on_command[output_id])
            elif state == 'off' and self.output_off_command[output_id]:
                cmd_return, _, cmd_status = cmd_output(
                    self.output_off_command[output_id])
            else:
                return
            self.logger.debug(
                u"Output {state} command returned: "
                u"{stat}: '{ret}'".format(
                    state=state,
                    stat=cmd_status,
                    ret=cmd_return))

        elif self.output_type[output_id] == 'pwm':
            if state == 'on':
                if self.pwm_library[output_id] == 'pigpio_hardware':
                    self.pwm_output[output_id].hardware_PWM(
                        self.output_pin[output_id],
                        self.pwm_hertz[output_id],
                        abs(duty_cycle) * 10000)
                elif self.pwm_library[output_id] == 'pigpio_any':
                    self.pwm_output[output_id].set_PWM_frequency(
                        self.output_pin[output_id],
                        self.pwm_hertz[output_id])
                    calc_duty_cycle = int((abs(duty_cycle) / 100.0) * 255)
                    if calc_duty_cycle > 255:
                        calc_duty_cycle = 255
                    if calc_duty_cycle < 0:
                        calc_duty_cycle = 0
                    self.pwm_output[output_id].set_PWM_dutycycle(
                        self.output_pin[output_id],
                        calc_duty_cycle)
                self.pwm_state[output_id] = abs(duty_cycle)
            elif state == 'off':
                if self.pwm_library[output_id] == 'pigpio_hardware':
                    self.pwm_output[output_id].hardware_PWM(
                        self.output_pin[output_id],
                        self.pwm_hertz[output_id], 0)
                elif self.pwm_library[output_id] == 'pigpio_any':
                    self.pwm_output[output_id].set_PWM_frequency(
                        self.output_pin[output_id],
                        self.pwm_hertz[output_id])
                    self.pwm_output[output_id].set_PWM_dutycycle(
                        self.output_pin[output_id], 0)
                self.pwm_state[output_id] = None

    def check_conditionals(self, output_id, state=None, on_duration=None, duty_cycle=None):
        conditionals = db_retrieve_table_daemon(Conditional)
        conditionals = conditionals.filter(
            Conditional.if_relay_id == output_id)
        conditionals = conditionals.filter(
            Conditional.is_activated == True)

        self.logger.error("TEST01: {} {}".format(conditionals.all(), on_duration))

        if self.is_on(output_id):
            conditionals = conditionals.filter(
                or_(Conditional.if_relay_state == 'on',
                    Conditional.if_relay_state == 'on_any'))

            self.logger.error("TEST02: {} {}".format(conditionals.all(), on_duration))

            on_with_duration = and_(
                Conditional.if_relay_state == 'on',
                Conditional.if_relay_duration == on_duration)
            conditionals = conditionals.filter(
                or_(Conditional.if_relay_state == 'on_any',
                    on_with_duration))

            self.logger.error("TEST03: {} {}".format(conditionals.all(), on_duration))

        else:
            conditionals = conditionals.filter(
                Conditional.if_relay_state == 'off')

        for each_conditional in conditionals.all():
            self.logger.error("TEST04: {} {}".format(each_conditional.if_relay_duration, on_duration))

            conditional_actions = db_retrieve_table_daemon(ConditionalActions)
            conditional_actions = conditional_actions.filter(
                ConditionalActions.conditional_id == each_conditional.id).all()

            for each_cond_action in conditional_actions:
                now = time.time()
                timestamp = datetime.datetime.fromtimestamp(now).strftime('%Y-%m-%d %H-%M-%S')
                message = u"{ts}\n[Output Conditional {id}] {name}\n".format(
                    ts=timestamp,
                    id=each_cond_action.id,
                    name=each_conditional.name)

                if each_cond_action.do_action == 'relay':
                    if each_cond_action.do_relay_id not in self.output_name:
                        message += u"Error: Invalid output ID {id}.".format(
                            id=each_cond_action.do_relay_id)
                    else:
                        message += u"If output {id} ({name}) turns {state}, Then ".format(
                            id=each_conditional.if_relay_id,
                            name=self.output_name[each_conditional.if_relay_id],
                            state=each_conditional.if_relay_state)
                        message += u"turn output {id} ({name}) {state}".format(
                            id=each_cond_action.do_relay_id,
                            name=self.output_name[each_cond_action.do_relay_id],
                            state=each_cond_action.do_relay_state)

                        if each_cond_action.do_relay_duration == 0:
                            self.output_on_off(each_cond_action.do_relay_id,
                                               each_cond_action.do_relay_state)
                        else:
                            message += u" for {dur} seconds".format(
                                dur=each_cond_action.do_relay_duration)
                            self.output_on_off(each_cond_action.do_relay_id,
                                               each_cond_action.do_relay_state,
                                               duration=each_cond_action.do_relay_duration)
                    message += ".\n"

                elif each_cond_action.do_action == 'command':
                    # Execute command as user mycodo
                    message += u"Execute: '{}'. ".format(
                        each_cond_action.do_action_string)

                    # Check command for variables to replace with values
                    command_str = each_cond_action.do_action_string
                    command_str = command_str.replace(
                        "((output_pin))", str(self.output_pin[output_id]))
                    command_str = command_str.replace(
                        "((output_action))", str(state))
                    command_str = command_str.replace(
                        "((output_duration))", str(on_duration))
                    command_str = command_str.replace(
                        "((output_pwm))", str(duty_cycle))
                    _, _, cmd_status = cmd_output(command_str)

                    message += u"Status: {}. ".format(cmd_status)

                elif each_cond_action.do_action == 'email':
                    if (self.email_count >= self.smtp_max_count and
                            time.time() < self.smtp_wait_time):
                        self.allowed_to_send_notice = False
                    else:
                        if time.time() > self.smtp_wait_time:
                            self.email_count = 0
                            self.smtp_wait_time = time.time() + 3600
                        self.allowed_to_send_notice = True
                    self.email_count += 1

                    if self.allowed_to_send_notice:
                        message += u"Notify {}.".format(
                            each_cond_action.email_notify)

                        smtp = db_retrieve_table_daemon(SMTP, entry='first')
                        send_email(
                            smtp.host, smtp.ssl, smtp.port, smtp.user,
                            smtp.passw, smtp.email_from,
                            each_cond_action.do_action_string, message)
                    else:
                        self.logger.debug(
                            "[Output Conditional {}] True: {:.0f} seconds "
                            "left to be allowed to email again.".format(
                                each_conditional.id,
                                self.smtp_wait_time-time.time()))

                elif each_cond_action.do_action == 'flash_lcd':
                    start_flashing = threading.Thread(
                        target=self.control.flash_lcd,
                        args=(each_cond_action.do_lcd_id, 1,))
                    start_flashing.start()

                # TODO: Implement photo/video actions for output conditionals
                elif each_cond_action.do_action == 'photo':
                    self.logger.error("Photo action not currently implemented")

                elif each_cond_action.do_action == 'video':
                    self.logger.error("Video action not currently implemented")

                self.logger.info(u"{}".format(message))

    def all_outputs_initialize(self, outputs):
        for each_output in outputs:
            self.output_id[each_output.id] = each_output.id
            self.output_unique_id[each_output.id] = each_output.unique_id
            self.output_type[each_output.id] = each_output.relay_type
            self.output_name[each_output.id] = each_output.name
            self.output_pin[each_output.id] = each_output.pin
            self.output_amps[each_output.id] = each_output.amps
            self.output_trigger[each_output.id] = each_output.trigger
            self.output_on_at_start[each_output.id] = each_output.on_at_start
            self.output_on_until[each_output.id] = datetime.datetime.now()
            self.output_last_duration[each_output.id] = 0
            self.output_on_duration[each_output.id] = False
            self.output_time_turned_on[each_output.id] = None
            self.output_protocol[each_output.id] = each_output.protocol
            self.output_pulse_length[each_output.id] = each_output.pulse_length
            self.output_bit_length[each_output.id] = each_output.bit_length
            self.output_on_command[each_output.id] = each_output.on_command
            self.output_off_command[each_output.id] = each_output.off_command

            self.pwm_hertz[each_output.id] = each_output.pwm_hertz
            self.pwm_library[each_output.id] = each_output.pwm_library
            self.pwm_time_turned_on[each_output.id] = None

            if self.output_pin[each_output.id] is not None:
                self.setup_pin(each_output.id)

            self.logger.debug(u"{id} ({name}) Initialized".format(
                id=each_output.id, name=each_output.name))

    def all_outputs_off(self):
        """Turn all outputs off"""
        for each_output_id in self.output_id:
            if (self.output_on_at_start[each_output_id] is None or
                    self.output_type[each_output_id] == 'pwm'):
                pass  # Don't turn off
            else:
                self.output_on_off(each_output_id, 'off',
                                  trigger_conditionals=False)

    def all_outputs_on(self):
        """Turn all outputs on that are set to be on at startup"""
        for each_output_id in self.output_id:
            if (self.output_on_at_start[each_output_id] is None or
                    self.output_type[each_output_id] == 'pwm'):
                pass  # Don't turn on or off
            elif self.output_on_at_start[each_output_id]:
                self.output_on_off(each_output_id, 'on',
                                  trigger_conditionals=False)
            elif not self.output_on_at_start[each_output_id]:
                self.output_on_off(each_output_id, 'off',
                                  trigger_conditionals=False)

    def cleanup_gpio(self):
        for each_output_pin in self.output_pin:
            GPIO.cleanup(each_output_pin)

    def add_mod_output(self, output_id):
        """
        Add or modify local dictionary of output settings form SQL database

        When a output is added or modified while the output controller is
        running, these local variables need to also be modified to
        maintain consistency between the SQL database and running controller.

        :param output_id: Unique ID for each output
        :type output_id: int

        :return: 0 for success, 1 for fail, with success for fail message
        :rtype: int, str
        """
        output_id = int(output_id)
        try:
            output = db_retrieve_table_daemon(Output, device_id=output_id)

            self.output_type[output_id] = output.relay_type

            # Turn current pin off
            if output_id in self.output_pin and self.output_state(output_id) != 'off':
                self.output_switch(output_id, 'off')

            self.output_id[output_id] = output.id
            self.output_unique_id[output_id] = output.unique_id
            self.output_type[output_id] = output.relay_type
            self.output_name[output_id] = output.name
            self.output_pin[output_id] = output.pin
            self.output_amps[output_id] = output.amps
            self.output_trigger[output_id] = output.trigger
            self.output_on_at_start[output_id] = output.on_at_start
            self.output_on_until[output_id] = datetime.datetime.now()
            self.output_time_turned_on[output_id] = None
            self.output_last_duration[output_id] = 0
            self.output_on_duration[output_id] = False
            self.output_protocol[output_id] = output.protocol
            self.output_pulse_length[output_id] = output.pulse_length
            self.output_bit_length[output_id] = output.bit_length
            self.output_on_command[output_id] = output.on_command
            self.output_off_command[output_id] = output.off_command

            self.pwm_hertz[output_id] = output.pwm_hertz
            self.pwm_library[output_id] = output.pwm_library

            if self.output_pin[output_id]:
                self.setup_pin(output.id)

            message = u"Output {id} ({name}) initialized".format(
                id=self.output_id[output_id],
                name=self.output_name[output_id])
            self.logger.debug(message)

            return 0, "success"
        except Exception as except_msg:
            self.logger.exception(1)
            return 1, "Add_Mod_Output Error: ID {id}: {err}".format(
                id=output_id, err=except_msg)

    def del_output(self, output_id):
        """
        Delete local variables

        The controller local variables must match the SQL database settings.
        Therefore, this is called when a output has been removed from the SQL
        database.

        :param output_id: Unique ID for each output
        :type output_id: str

        :return: 0 for success, 1 for fail (with error message)
        :rtype: int, str
        """
        output_id = int(output_id)

        # Turn current pin off
        if output_id in self.output_pin and self.output_state(output_id) != 'off':
            self.output_switch(output_id, 'off')

        try:
            self.logger.debug(u"Output {id} ({name}) Deleted.".format(
                id=self.output_id[output_id], name=self.output_name[output_id]))
            self.output_id.pop(output_id, None)
            self.output_unique_id.pop(output_id, None)
            self.output_type.pop(output_id, None)
            self.output_name.pop(output_id, None)
            self.output_pin.pop(output_id, None)
            self.output_amps.pop(output_id, None)
            self.output_trigger.pop(output_id, None)
            self.output_on_at_start.pop(output_id, None)
            self.output_on_until.pop(output_id, None)
            self.output_last_duration.pop(output_id, None)
            self.output_on_duration.pop(output_id, None)
            self.output_protocol.pop(output_id, None)
            self.output_pulse_length.pop(output_id, None)
            self.output_bit_length.pop(output_id, None)
            self.output_on_command.pop(output_id, None)
            self.output_off_command.pop(output_id, None)
            self.wireless_pi_switch.pop(output_id, None)

            self.pwm_hertz.pop(output_id, None)
            self.pwm_library.pop(output_id, None)
            self.pwm_output.pop(output_id, None)
            self.pwm_state.pop(output_id, None)
            self.pwm_time_turned_on.pop(output_id, None)

            return 0, "success"
        except Exception as msg:
            return 1, "Del_Output Error: ID {id}: {msg}".format(
                id=output_id, msg=msg)

    def output_sec_currently_on(self, output_id):
        if not self.is_on(output_id):
            return 0
        else:
            time_now = datetime.datetime.now()
            sec_currently_on = 0
            if self.output_on_duration[output_id]:
                remaining_time = 0
                if self.output_on_until[output_id] > time_now:
                    remaining_time = (self.output_on_until[output_id] - time_now).total_seconds()
                sec_currently_on = self.output_last_duration[output_id] - remaining_time
            elif self.output_time_turned_on[output_id]:
                sec_currently_on = (time_now - self.output_time_turned_on[output_id]).total_seconds()
            return sec_currently_on

    def output_setup(self, action, output_id):
        """ Add, delete, or modify a specific output """
        if action in ['Add', 'Modify']:
            return self.add_mod_output(output_id)
        elif action == 'Delete':
            return self.del_output(output_id)
        else:
            return [1, 'Invalid output_setup action']

    def current_amp_load(self):
        """
        Calculate the current amp draw from all the devices connected to
        all outputs currently on.

        :return: total amerage draw
        :rtype: float
        """
        amp_load = 0.0
        for each_output_id, each_output_amps in self.output_amps.items():
            if self.is_on(each_output_id):
                amp_load += each_output_amps
        return amp_load

    def setup_pin(self, output_id):
        """
        Setup pin for this output

        :param output_id: Unique ID for each output
        :type output_id: int

        :rtype: None
        """
        if self.output_type[output_id] == 'wired':
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(True)
                GPIO.setup(self.output_pin[output_id], GPIO.OUT)
                GPIO.output(self.output_pin[output_id], not self.output_trigger[output_id])
                state = 'LOW' if self.output_trigger[output_id] else 'HIGH'
                self.logger.info(
                    "Output {id} setup on pin {pin} and turned OFF "
                    "(OFF={state})".format(id=output_id, pin=self.output_pin[output_id], state=state))
            except Exception as except_msg:
                self.logger.exception(
                    "Output {id} was unable to be setup on pin {pin} with "
                    "trigger={trigger}: {err}".format(
                        id=output_id, pin=self.output_pin[output_id],
                        trigger=self.output_trigger[output_id], err=except_msg))

        elif self.output_type[output_id] == 'wireless_433MHz_pi_switch':
            self.wireless_pi_switch[output_id] = Transmit433MHz(
                self.output_pin[output_id],
                protocol=int(self.output_protocol[output_id]),
                pulse_length=int(self.output_pulse_length[output_id]),
                bit_length=int(self.output_bit_length[output_id]))

        elif self.output_type[output_id] == 'pwm':
            try:
                self.pwm_output[output_id] = pigpio.pi()
                if self.pwm_library[output_id] == 'pigpio_hardware':
                    self.pwm_output[output_id].hardware_PWM(
                        self.output_pin[output_id], self.pwm_hertz[output_id], 0)
                elif self.pwm_library[output_id] == 'pigpio_any':
                    self.pwm_output[output_id].set_PWM_frequency(
                        self.output_pin[output_id], self.pwm_hertz[output_id])
                    self.pwm_output[output_id].set_PWM_dutycycle(
                        self.output_pin[output_id], 0)
                self.pwm_state[output_id] = None
                self.logger.info("PWM {id} setup on pin {pin}".format(
                    id=output_id, pin=self.output_pin[output_id]))
            except Exception as except_msg:
                self.logger.exception(
                    "PWM {id} was unable to be setup on pin {pin}: "
                    "{err}".format(id=output_id, pin=self.output_pin[output_id], err=except_msg))

    def output_state(self, output_id):
        """
        :param output_id: Unique ID for each output
        :type output_id: int

        :return: Whether the output is currently "ON"
        :rtype: str
        """
        if output_id in self.output_type:
            if self.output_type[output_id] == 'wired':
                if (self.output_pin[output_id] is not None and
                        self.output_trigger[output_id] == GPIO.input(self.output_pin[output_id])):
                    return 'on'
            elif self.output_type[output_id] in ['command',
                                               'wireless_433MHz_pi_switch']:
                if self.output_time_turned_on[output_id]:
                    return 'on'
            elif self.output_type[output_id] == 'pwm':
                if output_id in self.pwm_state and self.pwm_state[output_id]:
                    return self.pwm_state[output_id]
        return 'off'

    def is_on(self, output_id):
        """
        :param output_id: Unique ID for each output
        :type output_id: int

        :return: Whether the output is currently "ON"
        :rtype: bool
        """
        if (self.output_type[output_id] == 'wired' and
                self._is_setup(output_id)):
            return self.output_trigger[output_id] == GPIO.input(self.output_pin[output_id])
        elif self.output_type[output_id] in ['command',
                                           'wireless_433MHz_pi_switch']:
            if self.output_time_turned_on[output_id]:
                return True
        elif self.output_type[output_id] == 'pwm':
            if self.pwm_time_turned_on[output_id]:
                return True
        return False

    def _is_setup(self, output_id):
        """
        This function checks to see if the GPIO pin is setup and ready
        to use. This is for safety and to make sure we don't blow anything.

        :param output_id: Unique ID for each output
        :type output_id: int

        :return: Is it safe to manipulate this output?
        :rtype: bool
        """
        if self.output_type[output_id] == 'wired' and self.output_pin[output_id]:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.output_pin[output_id], GPIO.OUT)
            return True
        elif self.output_type[output_id] in ['command',
                                           'wireless_433MHz_pi_switch']:
            return True
        elif self.output_type[output_id] == 'pwm':
            if output_id in self.pwm_output:
                return True
        return False

    def is_running(self):
        return self.running

    def stop_controller(self):
        """Signal to stop the controller"""
        self.thread_shutdown_timer = timeit.default_timer()
        self.running = False
