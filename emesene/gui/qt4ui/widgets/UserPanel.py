# -*- coding: utf-8 -*-

#    This file is part of emesene.
#
#    emesene is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    emesene is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with emesene; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import e3
import extension

import PyQt4.QtGui as QtGui
import PyQt4.QtCore as QtCore
from gui.qt4ui.Utils import tr
from gui.qt4ui.widgets import StatusButton


class UserPanel(QtGui.QWidget):
    '''a panel to display and manipulate the user information'''
    NAME = 'User Panel'
    DESCRIPTION = 'A widget to display/modify the account information on the main window'
    AUTHOR = 'Mariano Guerra'
    WEBSITE = 'www.emesene.org'

    def __init__(self, session, main_window):
        QtGui.QWidget.__init__(self)
        self.session = session
        self.main_window = main_window
        self.session = session
        # a widget dic to avoid proliferation of instance variables:
        self._widget_dict = {}
        self._enabled = True

        nick_edit_cls = extension.get_default('nick edit')
        avatar_cls = extension.get_default('avatar')

        widget_dict = self._widget_dict

        self.nick_box = QtGui.QHBoxLayout()
        self.nick = nick_edit_cls()
        self.nick.setToolTip(tr('Click here to set your nick name'))
        widget_dict['mail_btn'] = QtGui.QToolButton()
        widget_dict['mail_btn'].setAutoRaise(True)
        widget_dict['mail_btn'].setIcon(
                                    QtGui.QIcon.fromTheme('mail-unread'))
        widget_dict['mail_btn'].setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        widget_dict['mail_btn'].setText("(0)")
        widget_dict['mail_btn'].setToolTip(tr('Click here to access your mail'))

        self.userpanel_button = None

        self.search = QtGui.QToolButton()
        self.search.setCheckable(True)
        self.search.setIcon(QtGui.QIcon.fromTheme('edit-find'))
        self.search.setToolTip(tr('Search (Ctrl+F)'))
        self.nick_box.addWidget(self.nick)
        self.nick_box.addWidget(widget_dict['mail_btn'])
        self.nick_box.addWidget(self.search)

        empty_message_text = tr("Click here to set your message")
        self.message = nick_edit_cls(allow_empty=True,
            empty_message=empty_message_text)
        self.message.setToolTip(empty_message_text)
        widget_dict['status_combo'] = StatusButton.StatusButton(self.session)
        widget_dict['status_combo'].setToolTip(tr('Click here to change your status'))
        psm_box = QtGui.QHBoxLayout()
        psm_box.setContentsMargins(0, 0, 0, 0)
        psm_box.addWidget(self.message)
        psm_box.addWidget(widget_dict['status_combo'])
        widget_dict['psm_box'] = psm_box
        widget_dict['display_pic'] = avatar_cls(self.session, size=64)
        widget_dict['display_pic'].setToolTip(tr('Click here to set your avatar'))

        my_info_lay_left = QtGui.QVBoxLayout()
        my_info_lay_left.setContentsMargins(0, 0, 0, 0)
        my_info_lay_left.addLayout(self.nick_box)
        my_info_lay_left.addLayout(psm_box)

        my_info_lay = QtGui.QHBoxLayout()
        my_info_lay.addWidget(widget_dict['display_pic'])
        my_info_lay.addLayout(my_info_lay_left)
        my_info_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(my_info_lay)
        self.session.signals.status_change_succeed.subscribe(
                                self._widget_dict['status_combo'].set_status)
        self.session.config.subscribe(self._on_show_mail_inbox_changed,
            'b_show_mail_inbox')

        self.nick.nick_changed.connect(
                                        self.on_nick_changed)
        self.message.nick_changed.connect(
                                        self.on_message_changed)
        if session.session_has_service(e3.Session.SERVICE_PROFILE_PICTURE):
            widget_dict['display_pic'].clicked.connect(
                                            self.on_avatar_click)
        widget_dict['mail_btn'].clicked.connect(
                                    self._on_mail_click)

        self.on_profile_update_succeed(self.session.contacts.me.display_name,
            self.session.contacts.me.message)
        self.on_picture_change_succeed(self.session.account.account,
            self.session.config.last_avatar)
        self._on_show_mail_inbox_changed(self.session.config.b_show_mail_inbox)
        self._add_subscriptions()

    def _add_subscriptions(self):
        '''subscribe all signals'''
        self.session.signals.message_change_succeed.subscribe(
            self.on_message_change_succeed)
        self.session.signals.media_change_succeed.subscribe(
            self.on_media_change_succeed)
        if self.session.session_has_service(e3.Session.SERVICE_STATUS):
            self.session.signals.status_change_succeed.subscribe(
                self.on_status_change_succeed)
        self.session.signals.contact_list_ready.subscribe(
            self.on_contact_list_ready)
        self.session.signals.picture_change_succeed.subscribe(
            self.on_picture_change_succeed)
        self.session.signals.profile_get_succeed.subscribe(
            self.on_profile_update_succeed)
        self.session.signals.profile_set_succeed.subscribe(
            self.on_profile_update_succeed)

        extension.unsubscribe(
            self._on_userpanel_button_changed, "userpanel button")

    def remove_subscriptions(self):
        '''unsubscribe all signals'''
        self.session.signals.message_change_succeed.unsubscribe(
            self.on_message_change_succeed)
        self.session.signals.media_change_succeed.unsubscribe(
            self.on_media_change_succeed)
        if self.session.session_has_service(e3.Session.SERVICE_STATUS):
            self.session.signals.status_change_succeed.unsubscribe(
                self.on_status_change_succeed)
        self.session.signals.contact_list_ready.unsubscribe(
            self.on_contact_list_ready)
        self.session.signals.picture_change_succeed.unsubscribe(
            self.on_picture_change_succeed)
        self.session.signals.profile_get_succeed.unsubscribe(
            self.on_profile_update_succeed)
        self.session.signals.profile_set_succeed.unsubscribe(
            self.on_profile_update_succeed)

        extension.unsubscribe(
            self._on_userpanel_button_changed, "userpanel button")

    def _on_userpanel_button_changed(self, newvalue):
        if type(self.userpanel_button) != newvalue:
            #first remove current button
            if not self.userpanel_button is None:
                self.nick_box.removeWidget(self.userpanel_button)
                self.userpanel_button = None

            if newvalue is not None:
                #add new button
                self.userpanel_button = newvalue(self, self.main_window)
                self.nick_box.AddWidget(self.userpanel_button)
                self.userpanel_button.show()

    def _set_enabled(self, value):
        '''set the value of enabled and modify the widgets to reflect the status
        '''
        self.nick.setEnabled(value)
        self.message.setEnabled(value)
        self._widget_dict['status_combo'].setEnabled(value)
        self.search.setEnabled(value)
        if self.userpanel_button:
            self.userpanel_button.setEnabled(value)
        self._enabled = value

    def _get_enabled(self):
        '''return the value of the enabled property
        '''
        return self._enabled

    enabled = property(fget=_get_enabled, fset=_set_enabled)

    def on_status_change_succeed(self, stat):
        '''callback called when the status has been changed successfully'''
        self._widget_dict['status_combo'].set_status(stat)

    def on_message_change_succeed(self, message):
        '''callback called when the message has been changed successfully'''
        if self.session.contacts.me.media is None or self.session.contacts.me.media is "":
            self.message.set_text(message)
        else:
            self.message.set_text('♫ ' + self.session.contacts.me.media)

    def on_media_change_succeed(self, message):
        '''callback called when the message has been changed successfully'''
        if not message is None:
            self.message.set_text(message)

    def on_contact_list_ready(self):
        '''callback called when the contact list is ready to be used'''
        self.enabled = True

    def on_picture_change_succeed(self, account, path):
        '''callback called when the picture of an account is changed'''
        # out account
        if account == self.session.account.account:
            self._widget_dict['display_pic'].set_from_file(path)

    def on_profile_update_succeed(self, nick, message):
        '''method called when information about our profile is obtained
        '''
        self.nick.set_text(nick)
        if message is not '':
            self.message.set_text(message)

    def on_avatar_click(self):
        '''method called when user click on his avatar
        '''
        chooser = extension.get_and_instantiate('avatar chooser', self.session)
        chooser.exec_()

    def on_nick_changed(self, new_text):
        '''method called when the nick is changed'''
        self.session.set_nick(new_text)

    def on_message_changed(self, new_text):
        '''method called when the nick is changed'''
        self.session.set_message(new_text)

    def _on_show_mail_inbox_changed(self, value):
        '''callback called when config.b_show_mail_inbox changes'''
        self._widget_dict['mail_btn'].setVisible(value)

    def _on_mail_click(self):
        self.main_window.on_mail_click()

    def set_mail_count(self, count):
        self._widget_dict['mail_btn'].setText("(%d)" % count)
