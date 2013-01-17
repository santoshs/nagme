#
# A Timer implementation for short notifications
#
# Copyright (C) 2011  Santosh Sivaraj <ssantosh@fossix.org>
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
#   02110-1301, USA
#

# TODO Make timer thread into a timer event, make it dynamic, instead
#      of checking for the expiry in a loop

import time
import threading
from threading import Lock

days_in_months = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def is_leap_year(year):
    '''Find whether year is a leap year or not, True if it is'''
    if year == 400 == 0 or year % 4 == 0:
        return True
    if year % 100 == 0:
        return False
    return False

class Timer(threading.Thread):
    """A scheduling timer class"""
    # Class variables
    timerlist = []
    timermap = {}
    list_lock = Lock()
    _stop = threading.Event() # required when we need to stop the thread
    next_timer = None

    def __init__(self, obj):
        lt = time.localtime(time.time())
        if is_leap_year(lt[0]): days_in_months[1] = 29
        self.cobj = obj         # hack!! getting the child object so we can
                                # call the child's functions

        # start the timer thread, which will wake up every 1 second
        threading.Thread.__init__(self)
        return None

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()

    def run(self):
        while not self.stopped():
            if self.next_timer and self.next_timer <= time.time():
                tl = self.get_timer_text(self.next_timer)
                self.notify(self.cobj.TIMER_EXPIRED, tl)
                self.pop()
            time.sleep(1)

    def add_timer_absolute(self, timetuple, text):
        t = time.mktime(timetuple)

        if t in self.timerlist: # Will not happen, except in tests
            return

        self.list_lock.acquire()

        try:
            text = text.strip()
            if len(text) == 0:
                text = "Timer at " + time.ctime(t)
            self.timermap[t] = text

            self.timerlist.append(t)
            self.timerlist.sort()
            self.next_timer = self.timerlist[0]
            self.notify(self.cobj.TIMER_ADDED, self.timermap[t])
        finally:
            self.list_lock.release()
            print text + " timer added"

    def add_timer_rel(self, hour, minute, text):
        lt = time.localtime(time.time())
        day = lt[2]
        month = lt[1]
        year = lt[0]

        assert minute < 60
        assert hour < 24

        minute += lt[4]
        if minute > 59:
            hour += 1
            minute = minute - 59

        hour += lt[3]
        if hour >= 24:
            day += 1;
            hour = hour - 24
            if day > days_in_months[month - 1]:
                month += 1
                day = 1
            if month > 12:
                year += 1
                month = 1

        ttuple = (year, month, day, hour, minute, lt[5], lt[6], lt[7], lt[8])
        self.add_timer_absolute(ttuple, text)

    def add_timer(self, hour, minute, text):
        lt = time.localtime(time.time())
        day = lt[2]
        month = lt[1]
        year = lt[0]

        assert minute < 60
        assert hour < 24

        # Making seconds as zero, so to keep granularity at minute level as
        # this is abosolute and we don't have seconds yet, so the expectation
        # of the user should be at the start of the minute
        ttuple = (year, month, day, hour, minute, 0, lt[6], lt[7], lt[8])
        self.add_timer_absolute(ttuple, text)

    def get_timer_text(self, timer):
        if timer == None:
            return ""
        return self.timermap[timer];

    def get_timer(self, timer):
        return [timer, self.timermap[timer]]

    def at_index(self, index):
        """Return a {time:text list} at index"""
        if index > len(self.timerlist):
            return None
        return [self.timerlist[index], self.timermap[self.timerlist[index]]]

    def peek_next(self):
        """Return the next timer to be fired in the form of a dict"""
        return self.at_index(0)

    def del_timer_at_index(self, i):
        t = self.timerlist[i]
        d = self.timermap[t]
        self.list_lock.acquire()
        try:
            del self.timerlist[i]
            del self.timermap[t]

            if len(self.timerlist):
                self.next_timer = self.timerlist[0]
            else: self.next_timer = None
        finally:
             self.list_lock.release()

        return [t, d]

    def pop(self):
        return self.del_timer_at_index(0)

    def get_timerlist(self):
        if not self.next_timer:
            return None
        l = []
        tm = None
        for t in self.timerlist:
            tm = [self.timermap[t], time.ctime(t)]
            l.append(tm)
        return l

    def list_timers(self):
        print self.timerlist
        for t in self.timerlist:
            print "Will fire timer for " + str(self.timermap[t]) + " at " + str(t)

    def print_times(self):
        for t in self.timerlist:
            print self.timermap[t] + " - " + time.ctime(t)
