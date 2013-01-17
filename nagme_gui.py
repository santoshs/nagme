#
# GUI for the timer implementation
#
# Copyright (C) 2011  Santosh Sivaraj <santoshs@fossix.org>
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

# List of Todo items:
# TODO Update the timer list when a new timer is added when there was none
# TODO system tray notification when timer has expired
# TODO Play sound when timer expires
# TODO There is a timing issue in label update and expiry (see 153,154 in timer_timer)
# TODO Remove timer thread and implement as a schedulable time event, so we don't loop and waste cycles

from nagme_timer import Timer
from collections import deque
import pygtk
pygtk.require('2.0')
import gtk, gobject
import time
from datetime import datetime
import os
if os.name == 'nt':
    import winsound, sys

class MessageDialog_nb(gtk.MessageDialog):

    def __init__(self, parent=None, typ=gtk.MESSAGE_INFO,
                 buttons=gtk.BUTTONS_NONE, message_format=None):
        super(MessageDialog_nb, self).__init__(parent,
                                               gtk.DIALOG_DESTROY_WITH_PARENT|gtk.DIALOG_MODAL,
                                               typ, buttons,
                                               message_format)

    def dialog_response_cb(self, response_id, param):
        self.destroy()

    def run_nb(self):
        if not self.modal:
            self.set_modal(True)
        self.connect('response', self.dialog_response_cb)
        self.show()

class tui(Timer):
    notify_event = ("added", "expired", "deleted")
    TIMER_ADDED = 0
    TIMER_EXPIRED = 1
    TIMER_DELETED = 2

    def stop(self):
        return super(tui, self).stop()

    def delete_event(self, widget, event, data=None):
        if self.confirm_close:
            dialog = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL,
                                       gtk.MESSAGE_INFO, gtk.BUTTONS_YES_NO,
                                       "Sure you wanna quit??? Click \'No\' to keep nagging you.")
            dialog.set_title("Exit timer?")

            response = dialog.run()
            dialog.destroy()
            if response == gtk.RESPONSE_YES:
                return False
            return True

        return False

    def destroy(self, widget, data=None):
        self.stop()
        gtk.main_quit()

    def notify(self, event, timer_text, title=None):
        d = {'text':timer_text, 'title':title if title else self.notify_event[event],
             'type':self.notify_event[event]}
        self.notify_list.append(d)

    def get_values(self, widget, data=None):
        txt = self.textentry.get_text()

        if self.relative_time:
            self.add_timer_rel(self.hourspin.get_value_as_int(),
                               self.minspin.get_value_as_int(),
                               txt)
        else:
            self.add_timer(self.hourspin.get_value_as_int(),
                           self.minspin.get_value_as_int(), txt)

        self.reset_values(widget, data)
        self.update_timer_list()

    def reset_values(self, widget, data=None):
        self.textentry.set_text("")

        if self.relative_time:
            self.hourspin.spin(gtk.SPIN_HOME)
            self.minspin.spin(gtk.SPIN_HOME)
        else:
            t = time.localtime(time.time())
            self.hourspin.set_value(t[3])
            self.minspin.set_value(t[4])

    def toggle_window_hide(self):
        if self.mainwin_hidden:
            self.window.show()
            self.window.deiconify()
        else: self.window.hide()

        self.mainwin_hidden = not self.mainwin_hidden
        self.statusicon.set_visible(self.mainwin_hidden)

    def status_clicked(self, status):
        self.toggle_window_hide()
        #self.statusicon.set_tooltip("the window is visible")

    def timer_timer(self, pobj):
        while len(self.notify_list):
            i = self.notify_list.popleft()
            text = "<big><b>" + i['title'].capitalize() + "</b></big>\n\n<tt>" + i['text'] + "</tt>"

            if self.expander.get_expanded():
                if not self.next_timer:
                    self.expander.set_expanded(False)
                else:
                    self.update_timer_list()

            if i['type'] == "expired":
                self.update_timer_list()
                md = MessageDialog_nb(self.window, gtk.MESSAGE_INFO,
                                      gtk.BUTTONS_OK, None)
                md.set_markup(text)
                #self.statusicon.set_tooltip(i['text'])
                md.run_nb()
                if os.name == 'nt':
                    winsound.PlaySound("*", winsound.SND_ALIAS) 

            self.statusbar.push(0, i['title'] + " " + i['text'])

        # Countdown
        if not self.mainwin_hidden:
            if self.next_timer:
                t = datetime.fromtimestamp(self.next_timer) - datetime.now()
                text = "<i>Next:</i> <b><tt>" +  self.get_timer_text(self.next_timer) + "</tt></b> <i>in</i>\n<big>" + str(t).split(".")[0] + "</big>"
            else:
                text = "<b>Nothing to remind</b>"

            self.timer_counter.set_markup(text)

        return True

    def win_state_cb(self, widget, event):
        if event.changed_mask & gtk.gdk.WINDOW_STATE_ICONIFIED:
            if event.new_window_state & gtk.gdk.WINDOW_STATE_ICONIFIED:
                self.toggle_window_hide()

    def relative_time_cb(self, tb):
        self.relative_time = not tb.get_active()

        txt = self.textentry.get_text()
        self.reset_values(None, None)
        # Put back whatever text was there, reset_values resets all fields
        self.textentry.set_text(txt)

    def confirm_close_cb(self, tb):
        self.confirm_close = tb.get_active()

    def update_timer_list(self):
        if self.expander.get_expanded() and self.next_timer:
            self.liststore.clear()
            tl = self.get_timerlist()
            if tl:
                for t in tl:
                    self.liststore.append(t)

    def update_expander(self, expander):
        if not self.next_timer:
            label = gtk.Label("You haven't added anything")
            expander.add(label)
            label.show()
            return;

        box = gtk.VBox(False, 0)
        self.liststore = gtk.ListStore(str, str)
        self.treeview = gtk.TreeView(self.liststore)
        # For timer text
        textcell = gtk.CellRendererText()
        self.textcol = gtk.TreeViewColumn("What?", textcell, text=0)
        self.textcol.set_property('resizable', True)
        # For time (in absolute values only)
        timecell = gtk.CellRendererText()
        self.timecol = gtk.TreeViewColumn("When?", timecell, text=1)
        self.timecol.set_property('resizable', True)
        self.treeview.append_column(self.textcol)
        self.treeview.append_column(self.timecol)
        box.pack_start(self.treeview, True, True, 0)
        self.treeview.show()

        buttonDel = gtk.Button(label=None, stock=gtk.STOCK_DELETE)
        buttonDel.connect("clicked", self.del_timer, None)
        buttonDel.show()
        # label.set_size_request(200, 100)
        box.pack_start(buttonDel, False, True, 0)
        expander.add(box)
        box.show()

    def del_timer(self, widget, data=None):
        selection = self.treeview.get_selection()
        model, iter = selection.get_selected()

        if iter:
            i = selection.get_selected_rows()[1][0][0]
            model.remove(iter)
            tl = self.del_timer_at_index(i)
            self.notify(self.TIMER_DELETED, tl[1], "Deleted")

        return

    def expanded(self, expander, parameter):
        if expander.get_expanded():
            self.update_expander(expander)
            self.update_timer_list()
        else:
            if expander.child:
                expander.remove(expander.child)
            # expander.get_parent().resize(200, 1)

    def create_window(self):
        # GTK initialisation
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.connect("delete_event", self.delete_event)
        window.connect("destroy", self.destroy)
        window.connect("window-state-event", self.win_state_cb)
        window.set_border_width(10)
        window.set_title("NagMe")
        window.set_resizable(False)

        self.statusicon = gtk.status_icon_new_from_stock(gtk.STOCK_GOTO_TOP)
        self.statusicon.connect('activate', self.status_clicked)
        self.statusicon.set_visible(self.mainwin_hidden)

        vbox = gtk.VBox(False, 5)

        self.statusbar = gtk.Statusbar()
        vbox.pack_end(self.statusbar, False, True, 0)

        # I need to say something
        label = gtk.Label("Don't forget things, just tell me, I will nag you!!\n"
                          "What you want to be reminded of?")
        vbox.pack_start(label, True, True, 0)

        self.textentry = gtk.Entry(max = 0)
        vbox.pack_start(self.textentry, True, True, 0)

        self.ptimer = gobject.timeout_add(200, self.timer_timer, self)

        hbox1 = gtk.HBox(True, 5)
        hbox2 = gtk.HBox(True, 5)
        hbox3 = gtk.HBox(True, 5)
        hbox0 = gtk.HBox(True, 5)
        vbox.pack_start(hbox1, True, True, 0)
        vbox.pack_start(hbox2, True, True, 0)
        vbox.pack_start(hbox3, True, True, 0)
        window.add(vbox)

        label = gtk.Label("Hour :")
        label.set_alignment(0, 0.5)
        hbox1.pack_start(label, False, True, 0)
        adj = gtk.Adjustment(0, 0.0, 23.0, 1.0, 5.0, 0.0)
        self.hourspin = gtk.SpinButton(adj, 0, 0)
        self.hourspin.set_wrap(True)
        hbox1.pack_start(self.hourspin, False, True, 0)

        label = gtk.Label("Minute :")
        label.set_alignment(0, 0.5)
        hbox1.pack_start(label, False, True, 0)
        adj = gtk.Adjustment(0, 0.0, 59.0, 1.0, 5.0, 0.0)
        self.minspin = gtk.SpinButton(adj, 0, 0)
        self.minspin.set_wrap(True)
        hbox1.pack_start(self.minspin, False, True, 0)

        # Add a button for OK
        buttonOK = gtk.Button(label=None, stock=gtk.STOCK_ADD)
        buttonOK.connect("clicked", self.get_values, None)
        hbox2.pack_start(buttonOK, True, True, 0)
        add_tt = gtk.Tooltips()
        add_tt.set_tip(buttonOK, "Add timer", tip_private=None) # Tool tip

        # Add a button for clearing
        buttonClear = gtk.Button(label=None, stock=gtk.STOCK_CLEAR)
        buttonClear.connect_object("clicked", self.reset_values, None)
        hbox2.pack_start(buttonClear, True, True, 0)
        clear_tt = gtk.Tooltips()
        clear_tt.set_tip(buttonClear, "Clear Form", tip_private=None)

        # Close confirmation
        confirm_close_toggle = gtk.CheckButton("_Confirm Close?")
        confirm_close_toggle.connect("toggled", self.confirm_close_cb)
        confirm_close_toggle.set_active(self.confirm_close)
        hbox3.pack_start(confirm_close_toggle, True, True, 0)

        # Relative or absolute timing?
        relative_time_toggle = gtk.CheckButton("_Absolute timing?")
        relative_time_toggle.connect("toggled", self.relative_time_cb)
        hbox3.pack_start(relative_time_toggle, True, True, 0)

        # Make a display to list timers
        label_exp = gtk.Label("Timers")
        self.expander = gtk.Expander(None)
        self.expander.set_label_widget(label_exp)
        self.expander.connect("notify::expanded", self.expanded)
        vbox.pack_end(self.expander, True, True, 0)
        list_tt = gtk.Tooltips()
        list_tt.set_tip(self.expander, "Show all timers", tip_private=None)

        self.timer_counter = gtk.Label("Nothing to remind")
        self.timer_counter.set_justify(gtk.JUSTIFY_CENTER)
        vbox.pack_start(self.timer_counter, True, True, 0)

        return window

    def __init__(self):
        self.notify_list = deque([])
        self.mainwin_hidden = False
        self.relative_time = True
        self.confirm_close = True

        self.window = self.create_window()
        super(tui, self).__init__(self)
        self.window.show_all()
        self.start()

    def main(self):
        gtk.main()
        #self.test_timer()

    def test_timer(self):
        print "Nagme test start"
        self.add_timer_rel(5, 30, "Five hours from now")
        self.add_timer_rel(1, 0, "One hour from now")
        self.add_timer_rel(1, 0, "Another timer at one")
        self.add_timer_rel(23, 0, "New timer at 23 hours from now")
        self.add_timer_rel(12, 30, "Timer at 13 hours from now")
        self.add_timer_rel(2, 1, "A little later")
        self.add_timer_rel(0, 0, None)
        self.add_timer_rel(0, 0, "Now Now")
        self.add_timer_rel(0, 1, "1 min from now")
        self.list_timers()
        print "peek_next: " + str(self.peek_next())
        print "at_index: " + str(self.at_index(2))
        print "at_index: " + str(self.at_index(9))
        print "pop_next: " + str(test.pop_next())
        self.list_timers()
        self.print_times()
        print "Test complete"
