#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#  setup-database.py - Tool for creating Mycodo SQLite databases
#
#  Copyright (C) 2015  Kyle T. Gabriel
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

import getopt
import re
import sqlite3
import subprocess
import sys
import time

sql_database_mycodo = 'config/mycodo.db'
sql_database_user = 'config/users.db'

# GPIO pins (BCM numbering) and name of devices attached to relay
relay_num = None
relay_pin = [0] * 9
relay_name = [0] * 9
relay_trigger = [0] * 9

# Temperature & Humidity Sensors
sensor_t_num = 0
sensor_t_name = [0] * 5
sensor_t_device = [0] * 5
sensor_t_pin = [0] * 5
sensor_t_period = [0] * 5
sensor_t_log = [0] * 5
sensor_t_graph = [0] * 5
sensor_t_read_temp_c = [0] * 5
sensor_t_read_hum = [0] * 5
sensor_t_dewpt_c = [0] * 5

# Temperature Sensor Temperature PID
pid_t_temp_relay = [0] * 5
pid_t_temp_set = [0] * 5
pid_t_temp_period = [0] * 5
pid_t_temp_p = [0] * 5
pid_t_temp_i = [0] * 5
pid_t_temp_d = [0] * 5
pid_t_temp_or = [0] * 5
pid_t_temp_alive = [1] * 5
pid_t_temp_down = 0
pid_t_temp_up = 0
pid_t_temp_number = None

# Temperature & Humidity Sensors
sensor_ht_num = 0
sensor_ht_name = [0] * 5
sensor_ht_device = [0] * 5
sensor_ht_pin = [0] * 5
sensor_ht_period = [0] * 5
sensor_ht_log = [0] * 5
sensor_ht_graph = [0] * 5
sensor_ht_read_temp_c = [0] * 5
sensor_ht_read_hum = [0] * 5
sensor_ht_dewpt_c = [0] * 5

# HT Sensor Temperature PID
pid_ht_temp_relay = [0] * 5
pid_ht_temp_set = [0] * 5
pid_ht_temp_period = [0] * 5
pid_ht_temp_p = [0] * 5
pid_ht_temp_i = [0] * 5
pid_ht_temp_d = [0] * 5
pid_ht_temp_or = [0] * 5
pid_ht_temp_alive = [1] * 5
pid_ht_temp_down = 0
pid_ht_temp_up = 0
pid_ht_temp_number = None

# HT Sensor Humidity PID
pid_ht_hum_relay = [0] * 5
pid_ht_hum_set = [0] * 5
pid_ht_hum_period = [0] * 5
pid_ht_hum_p = [0] * 5
pid_ht_hum_i = [0] * 5
pid_ht_hum_d = [0] * 5
pid_ht_hum_or = [0] * 5
pid_ht_hum_alive = [1] * 5
pid_ht_hum_down = 0
pid_ht_hum_up = 0
pid_ht_hum_number = None

# CO2 Sensors
sensor_co2_num = 0
sensor_co2_name = [0] * 5
sensor_co2_device = [0] * 5
sensor_co2_pin = [0] * 5
sensor_co2_period = [0] * 5
sensor_co2_log = [0] * 5
sensor_co2_graph = [0] * 5
sensor_co2_read_co2 = [0] * 5

# CO2 PID
pid_co2_relay = [0] * 5
pid_co2_set = [0] * 5
pid_co2_period = [0] * 5
pid_co2_p = [0] * 5
pid_co2_i = [0] * 5
pid_co2_d = [0] * 5
pid_co2_or = [0] * 5
pid_co2_alive = [1] * 5
pid_co2_down = 0
pid_co2_up = 0
pid_co2_number = None

# Timers
timer_num = None
timer_name = [0] * 9
timer_relay = [0] * 9
timer_state = [0] * 9
timer_duration_on = [0] * 9
timer_duration_off = [0] * 9
timer_change = 0

# SMTP notify
smtp_host = None
smtp_ssl = None
smtp_port = None
smtp_user = None
smtp_pass = None
smtp_email_from = None
smtp_email_to = None

# Miscellaneous
camera_light = None
server = None
client_que = '0'
client_var = None
terminate = False

def menu():
    if len(sys.argv) == 1:
        usage()
        return 1

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ad:hip::',
            ["adduser", "deleteuser=", "help", "install-db=", "pwchange="])
    except getopt.GetoptError as err:
        print(err) # will print "option -a not recognized"
        usage()
        return 2
    for opt, arg in opts:
        if opt in ("-a", "--adduser"):
            add_user()
            return 1
        elif opt in ("-d", "--deleteuser"):
            delete_user(sys.argv[2])
            return 1
        elif opt in ("-h", "--help"):
            usage()
            return 1
        elif opt in ("-i", "--install-db"):
            if sys.argv[2] == 'all' or sys.argv[2] == 'user' or sys.argv[2] == 'mycodo':
                setup_db(sys.argv[2])
            else:
                print 'Error: One option required: mycodo-db.py --db-setup [all, user, mycodo]'
                return 0
            return 1
        elif opt in ("-p", "--pwchange"):
            password_change(sys.argv[2])
            return 1
        else:
            assert False, "Fail"

def usage():
    print 'setup-database.py: Create and manage Mycodo databases.\n'
    print 'Usage:  setup-database.py [OPTION]...\n'
    print 'Options:'
    print '    -a, --adduser'
    print '           Add user to existing users.db database'
    print '    -d, --deleteuser user'
    print '           Delete user from existing users.db database'
    print '    -h, --help'
    print '           Display this help and exit'
    print '    -i, --install-db user/mycodo/all'
    print '           Create new users.db, mycodo.db. or both'
    print '    -p, --pwchange user'
    print '           Create a new password for user'
    print '\nExample: setup-database.py -i all'

def add_user():
    print 'Add user to users.db'
    pass_checks = True
    while pass_checks:
        user_name = raw_input('\nUsername (a-z, A-Z, 2-64 chars): ')
        if test_username(user_name):
            pass_checks = False

    pass_checks = True
    while pass_checks:
        user_password = raw_input('Password: ')
        user_password_again = raw_input('Password (again): ')
        if user_password != user_password_again:
            print "Passwords don't match"
        else:
            if test_password(user_password):
                user_password_hash = subprocess.check_output(["php", "includes/hash.php", "hash", user_password])
                pass_checks = False

    pass_checks = True
    while pass_checks:
        user_email = raw_input('Email: ')
        if is_email(user_email):
            pass_checks = False
        else:
            print 'Not a properly-formatted email\n'

    conn = sqlite3.connect(sql_database_user)
    cur = conn.cursor()
    cur.execute("INSERT INTO users (user_name, user_password_hash, user_email) VALUES ('{user_name}', '{user_password_hash}', '{user_email}')".\
        format(user_name=user_name, user_password_hash=user_password_hash, user_email=user_email))
    conn.commit()
    cur.close()

def delete_user(user_name):
    if query_yes_no("Confirm delete user '%s' from /var/www/mycodo/config/users.db" % user_name):
        conn = sqlite3.connect(sql_database_user)
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE user_name = '%s' " % user_name)
        conn.commit()
        cur.close()

def password_change(user_name):
    if query_yes_no("Confirm change password of user '%s' from /var/www/mycodo/config/users.db" % user_name):
        pass_checks = True
        while pass_checks:
            user_password = raw_input('password: ')
            user_password_again = raw_input('password (again): ')
            if user_password != user_password_again:
                print "Passwords don't match"
            elif test_password(user_password):
                    user_password_hash = subprocess.check_output(["php", "includes/hash.php", "hash", user_password])
                    pass_checks = False

        conn = sqlite3.connect(sql_database_user)
        cur = conn.cursor()
        cur.execute("UPDATE users SET user_password_hash='%s' WHERE user_name='%s'" % (user_password_hash, user_name))
        conn.commit()
        cur.close()

def setup_db(target):
    global sql_database_mycodo
    global sql_database_user

    if target == 'all' or target == 'mycodo':
        if not query_yes_no('Use default save path /var/www/mycodo/config/mycodo.db?'):
            sql_database_mycodo = input('user.db save path: ')
        delete_all_tables_mycodo()
        create_all_tables_mycodo()
        create_rows_columns_mycodo()
    if target == 'all' or target == 'user':
        if not query_yes_no('Use default save path /var/www/mycodo/config/user.db?'):
            sql_database_user = input('user.db save path: ')
        delete_all_tables_user()
        create_all_tables_user()
        create_rows_columns_user()

def delete_all_tables_mycodo():
    print "mydoco.db: Delete all tables"
    conn = sqlite3.connect(sql_database_mycodo)
    cur = conn.cursor()
    cur.execute('DROP TABLE IF EXISTS Relays ')
    cur.execute('DROP TABLE IF EXISTS TSensor ')
    cur.execute('DROP TABLE IF EXISTS HTSensor ')
    cur.execute('DROP TABLE IF EXISTS CO2Sensor ')
    cur.execute('DROP TABLE IF EXISTS Timers ')
    cur.execute('DROP TABLE IF EXISTS Numbers ')
    cur.execute('DROP TABLE IF EXISTS SMTP ')
    cur.execute('DROP TABLE IF EXISTS Misc ')
    conn.close()

def create_all_tables_mycodo():
    print "mycodo.db: Create all tables"
    conn = sqlite3.connect(sql_database_mycodo)
    cur = conn.cursor()
    cur.execute("CREATE TABLE Relays (Id INT, Name TEXT, Pin INT, Trigger INT)")
    cur.execute("CREATE TABLE TSensor (Id INT, Name TEXT, Pin TEXT, Device TEXT, Period INT, Activated INT, Graph INT, Temp_Relay INT, Temp_OR INT, Temp_Set REAL, Temp_Period INT, Temp_P REAL, Temp_I REAL, Temp_D REAL)")
    cur.execute("CREATE TABLE HTSensor (Id INT, Name TEXT, Pin INT, Device TEXT, Period INT, Activated INT, Graph INT, Temp_Relay INT, Temp_OR INT, Temp_Set REAL, Temp_Period INT, Temp_P REAL, Temp_I REAL, Temp_D REAL, Hum_Relay INT, Hum_OR INT, Hum_Set REAL, Hum_Period INT, Hum_P REAL, Hum_I REAL, Hum_D REAL)")
    cur.execute("CREATE TABLE CO2Sensor (Id INT, Name TEXT, Pin INT, Device TEXT, Period INT, Activated INT, Graph INT, CO2_Relay INT, CO2_OR INT, CO2_Set INT, CO2_Period INT, CO2_P REAL, CO2_I REAL, CO2_D REAL)")
    cur.execute("CREATE TABLE Timers (Id INT, Name TEXT, Relay INT, State INT, DurationOn INT, DurationOff INT)")
    cur.execute("CREATE TABLE Numbers (Relays INT, TSensors INT, HTSensors INT, CO2Sensors INT, Timers INT)")
    cur.execute("CREATE TABLE SMTP (Host TEXT, SSL INT, Port INT, User TEXT, Pass TEXT, Email_From TEXT, Email_To TEXT)")
    cur.execute("CREATE TABLE Misc (Camera_Relay INT, Display_Last INT, Display_Timestamp INT)")
    conn.close()

def create_rows_columns_mycodo():
    print "mydodo.db: Create all rows and columns"
    conn = sqlite3.connect(sql_database_mycodo)
    cur = conn.cursor()
    for i in range(1, 9):
        cur.execute("INSERT INTO Relays VALUES(%d, 'Relay%d', 0, 0)" % (i, i))
    for i in range(1, 5):
        cur.execute("INSERT INTO TSensor VALUES(%d, 'T-S%d', '0', 'DS18B20', 120, 0, 0, 0, 1, 25.0, 90, 0, 0, 0)" % (i, i))
    for i in range(1, 5):
        cur.execute("INSERT INTO HTSensor VALUES(%d, 'HT-S%d', 0, 'DHT22', 120, 0, 0, 0, 1, 25.0, 90, 0, 0, 0, 0, 1, 50.0, 90, 0, 0, 0)" % (i, i))
    for i in range(1, 5):
        cur.execute("INSERT INTO CO2Sensor VALUES(%d, 'CO2-S%d', 0, 'K30', 120, 0, 0, 0, 1, 1000, 90, 0, 0, 0)" % (i, i))
    for i in range(1, 9):
        cur.execute("INSERT INTO Timers VALUES(%d, 'Timer%d', 0, 0, 60, 360)" % (i, i))
    cur.execute("INSERT INTO Numbers VALUES(0, 0, 0, 0, 0)")
    cur.execute("INSERT INTO SMTP VALUES('smtp.gmail.com', 1, 587, 'email@gmail.com', 'password', 'me@gmail.com', 'you@gmail.com')")
    cur.execute("INSERT INTO Misc VALUES(0, 1, 1)")
    conn.commit()
    cur.close()


def delete_all_tables_user():
    print "user.db: Delete all tables"
    conn = sqlite3.connect(sql_database_user)
    cur = conn.cursor()
    cur.execute('DROP TABLE IF EXISTS `users` ')
    conn.close()


def create_all_tables_user():
    print "user.db: Create all tables"
    conn = sqlite3.connect(sql_database_user)
    cur = conn.cursor()

    cur.execute("CREATE TABLE IF NOT EXISTS `users` (`user_id` INTEGER PRIMARY KEY, `user_name` varchar(64), `user_password_hash` varchar(255), `user_email` varchar(64))")
    cur.execute("CREATE UNIQUE INDEX `user_name_UNIQUE` ON `users` (`user_name` ASC)")
    cur.execute("CREATE UNIQUE INDEX `user_email_UNIQUE` ON `users` (`user_email` ASC)")
    conn.close()


def create_rows_columns_user():
    print "user.db: Create all rows and columns"
    conn = sqlite3.connect(sql_database_user)
    cur = conn.cursor()

    pass_checks = True
    print "\nPassword for user 'admin' (minimum 6 charachters in length)"
    while pass_checks:
        admin_password = raw_input('Password: ')
        admin_password_again = raw_input('Password (again): ')
        if admin_password != admin_password_again:
            print "Passwords don't match"
        elif test_password(admin_password):
                admin_password_hash = subprocess.check_output(["php", "includes/hash.php", "hash", admin_password])
                pass_checks = False

    pass_checks = True
    print "\nEmail for user 'admin'"
    while pass_checks:
        admin_email = raw_input('email: ')
        if is_email(admin_email):
            pass_checks = False
        else:
            print 'Not a properly-formatted email\n'

    cur.execute("INSERT INTO users (user_name, user_password_hash, user_email) VALUES ('{user_name}', '{user_password_hash}', '{user_email}')".\
        format(user_name='admin', user_password_hash=admin_password_hash, user_email=admin_email))

    if query_yes_no('\nCreate additional user account?'):
        pass_checks = True
        print "\nCreate user (a-z, A-Z, 2-64 characters)"
        while pass_checks:
            user_name = raw_input('username: ')
            if test_username(user_name):
                pass_checks = False

        pass_checks = True
        print "\nPassword for user '" + user_name + "'"
        while pass_checks:
            user_password = raw_input('password: ')
            user_password_again = raw_input('password (again): ')
            if user_password != user_password_again:
                print "Passwords don't match"
            elif test_password(user_password):
                    user_password_hash = subprocess.check_output(["php", "includes/hash.php", "hash", user_password])
                    pass_checks = False

        pass_checks = True
        print "\nEmail for user '" + user_name + "'"
        while pass_checks:
            user_email = raw_input('email: ')
            if is_email(user_email):
                pass_checks = False
            else:
                print 'Not a properly-formatted email\n'

        cur.execute("INSERT INTO users (user_name, user_password_hash, user_email) VALUES ('{user_name}', '{user_password_hash}', '{user_email}')".\
            format(user_name=user_name, user_password_hash=user_password_hash, user_email=user_email))

    if query_yes_no("\nAllow 'guest' access (view but not modify)?"):

        pass_checks = True
        print "\nPassword for user 'guest'"
        while pass_checks:
            user_password = raw_input('password: ')
            user_password_again = raw_input('password (again): ')
            if user_password != user_password_again:
                print "Passwords don't match"
            elif test_password(user_password):
                    user_password_hash = subprocess.check_output(["php", "/var/www/mycodo/includes/hash.php", "hash", user_password])
                    pass_checks = False

        cur.execute("INSERT INTO users (user_name, user_password_hash, user_email) VALUES ('{user_name}', '{user_password_hash}', '{user_email}')".\
            format(user_name='guest', user_password_hash=user_password_hash, user_email='guest@guest.com'))

    conn.commit()
    cur.close()


def is_email(email):
    pattern = '[\.\w]{1,}[@]\w+[.]\w+'
    if re.match(pattern, email):
        return True
    else:
        return False


def pass_length_min(pw):
    'Password must be at least 6 characters\n'
    return len(pw) >= 6

def test_password(pw, tests=[pass_length_min]):
    for test in tests:
        if not test(pw):
            print(test.__doc__)
            return False
    return True


def characters(un):
    'User name must be only letters and numbers\n'
    return re.match("^[A-Za-z0-9_-]+$", un)

def user_length_min(un):
    'Password must be at least 2 characters\n'
    return len(un) >= 2

def user_length_max(un):
    'Password cannot be more than 64 characters\n'
    return len(un) <= 64

def test_username(un, tests=[characters, user_length_min, user_length_max]):
    for test in tests:
        if not test(un):
            print(test.__doc__)
            return False
    return True


def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'y' or 'n').\n")




#
#
# Old code (may be used)
#
# 

def add_columns(table, variable, value):
    #print "Add to Table: %s Variable: %s Value: %s" % (table, variable, value)
    conn = sqlite3.connect(sql_database_mycodo)
    cur = conn.cursor()
    if represents_int(value) or represents_float(value):
        query = "INSERT INTO %s (%s) VALUES ( '%s' )" % (table, variable, value)
    else:
        query = "INSERT INTO %s (%s) VALUES ( %s )" % (table, variable, value)
    cur.execute(query)
    conn.commit()
    cur.close()

# Print all values in all tables
def view_columns():
    conn = sqlite3.connect(sql_database_mycodo)
    cur = conn.cursor()

    cur.execute('SELECT Id, Name, Pin, Trigger FROM Relays')
    print "Table: Relays"
    print "Id Name Pin Trigger"
    for row in cur :
        print "%s %s %s %s" % (row[0], row[1], row[2], row[3])

    cur.execute('SELECT Id, Name, Pin, Device, Period, Activated, Graph, Temp_Relay, Temp_OR, Temp_Set, Temp_P, Temp_I, Temp_D, Hum_Relay, Hum_OR, Hum_Set, Hum_P, Hum_I, Hum_D FROM HTSensor')
    print "\nTable: HTSensor"
    print "Id Name Pin Device Period Activated Graph Temp_Relay Temp_OR Temp_Set Temp_P Temp_I Temp_D Hum_Relay Hum_OR Hum_Set Hum_P Hum_I Hum_D"
    for row in cur :
        print "%s %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s" % (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10], row[11], row[12], row[13], row[14], row[15], row[16], row[17], row[18])

    cur.execute('SELECT Id, Name, Pin, Device, Period, Activated, Graph, CO2_Relay, CO2_OR, CO2_Set, CO2_P, CO2_I, CO2_D FROM CO2Sensor ')
    print "\nTable: CO2Sensor"
    print "Id Name Pin Device Period Activated Graph CO2_Relay CO2_OR CO2_Set CO2_P CO2_I CO2_D"
    for row in cur :
        print "%s %s %s %s %s %s %s %s %s %s %s %s %s" % (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10], row[11], row[12])

    cur.execute('SELECT Id, Name, State, Relay, DurationOn, DurationOff FROM Timers ')
    print "\nTable: Timers"
    print "Id Name State Relay DurationOn DurationOff"
    for row in cur :
        print "%s %s %s %s %s %s" % (row[0], row[1], row[2], row[3], row[4], row[5])

    cur.execute('SELECT Relays, HTSensors, CO2Sensors, Timers FROM Numbers ')
    print "\nTable: Numbers"
    print "Relays HTSensors CO2Sensors Timers"
    for row in cur :
        print "%s %s %s %s" % (row[0], row[1], row[2], row[3])

    cur.execute('SELECT Host, SSL, Port, User, Pass, Email_From, Email_To FROM SMTP ')
    print "\nTable: SMTP"
    print "Host SSL Port User Pass Email_From Email_To"
    for row in cur :
        print "%s %s %s %s %s %s %s\n" % (row[0], row[1], row[2], row[3], row[4], row[5], row[6])

    cur.execute('SELECT Camera_Relay FROM Misc')
    print "\nTable: Misc"
    print "Camera_Relay"
    for row in cur :
        print "%s\n" % row[0]

    cur.close()

def delete_all_rows():
    print "Delete All Rows"
    conn = sqlite3.connect(sql_database_mycodo)
    cur = conn.cursor()
    cur.execute('DELETE FROM Relays ')
    cur.execute('DELETE FROM HTSensor ')
    cur.execute('DELETE FROM CO2Sensor ')
    cur.execute('DELETE FROM Timers ')
    cur.execute('DELETE FROM Numbers ')
    cur.execute('DELETE FROM SMTP ')
    conn.commit()
    cur.close()

def delete_row(table, Id):
    print "Delete Row: %s" % row
    conn = sqlite3.connect(sql_database_mycodo)
    cur = conn.cursor()
    query = "DELETE FROM %s WHERE Id = '%s' " % (table, Id)
    cur.execute(query)
    conn.commit()
    cur.close()

def update_value(table, Id, variable, value):
    print "Update Table: %s Id: %s Variable: %s Value: %s" % (
        table, Id, variable, value)
    conn = sqlite3.connect(sql_database_mycodo)
    cur = conn.cursor()

    if Id is '0':
        if represents_int(value) or represents_float(value):
            query = "UPDATE %s SET %s=%s" % (
                table, variable, value)
        else:
            query = "UPDATE %s SET %s='%s'" % (
                table, variable, value)
    else:
        if represents_int(value) or represents_float(value):
            query = "UPDATE %s SET %s=%s WHERE Id=%s" % (
                table, variable, value, Id)
        else:
            query = "UPDATE %s SET %s='%s' WHERE Id=%s" % (
                table, variable, value, Id)
    cur.execute(query)
    conn.commit()
    cur.close()

# Check if string represents an integer column
def represents_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

# Check if string represents a float column
def represents_float(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

#set_global_variables(0)
#start_time = time.time()
menu()
#elapsed_time = time.time() - start_time
#print '\nScript Completed in %.2f seconds' % elapsed_time
