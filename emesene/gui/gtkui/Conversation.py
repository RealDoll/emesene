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

import os
import re
import gtk
import glib
import urllib

import stock
import utils
import gui
from gui.gtkui import check_gtk3
import extension
import e3


class Conversation(gtk.VBox, gui.Conversation):
    '''a widget that contains all the components inside'''
    NAME = 'Conversation'
    DESCRIPTION = 'The widget that displays a conversation'
    AUTHOR = 'Mariano Guerra'
    WEBSITE = 'www.emesene.org'

    def __init__(self, session, cid, update_win, tab_label, members=None):
        '''constructor'''
        gtk.VBox.__init__(self)
        gui.Conversation.__init__(self, session, cid, update_win, members)
        self.set_border_width(2)

        self.typing_timeout = None
        self.tab_label = tab_label

        self._header_visible = session.config.b_show_header
        self._image_visible = session.config.b_show_info
        self._toolbar_visible = session.config.b_show_toolbar

        self.panel = gtk.VPaned()

        self.show_avatar_in_taskbar = self.session.config.get_or_set(
                                                    'b_show_avatar_in_taskbar',
                                                    True)

        Header = extension.get_default('conversation header')
        OutputText = extension.get_default('conversation output')
        InputText = extension.get_default('conversation input')
        ContactInfo = extension.get_default('conversation info')
        ConversationToolbar = extension.get_default(
            'conversation toolbar')
        TransfersBar = extension.get_default('filetransfer pool')
        CallWidget = extension.get_default('call widget')

        BelowConversation = extension.get_default('below conversation')
        if BelowConversation is not None:
            self.below_conversation = BelowConversation(self, session)

        self.header = Header(session, members)
        toolbar_handler = gui.base.ConversationToolbarHandler(self.session,
            gui.theme, self)
        self.toolbar = ConversationToolbar(toolbar_handler, self.session)
        self.toolbar.set_property('can-focus', False)
        outputview_handler = gui.base.OutputViewHandler(self)
        self.output = OutputText(self.session.config, outputview_handler)
        if self.session.conversation_start_locked:
            self.output.lock()

        self.output.set_size_request(-1, 30)
        self.input = InputText(self.session, self._on_send_message,
                               self.cycle_history, self.on_drag_data_received,
                               self._send_typing_notification)
        self.output.set_size_request(-1, 25)
        self.input.set_size_request(-1, 25)
        self.info = ContactInfo(self.session, self.members)
        self.transfers_bar = TransfersBar(self.session)
        self.call_widget = CallWidget(self.session)

        frame_input = gtk.Frame()
        frame_input.set_shadow_type(gtk.SHADOW_IN)

        input_box = gtk.VBox()
        input_box.pack_start(self.toolbar, False)
        input_box.pack_start(self.input, True, True)

        frame_input.add(input_box)

        self.panel.pack1(self.output, True, False)
        self.panel.pack2(frame_input, False, False)

        if not check_gtk3():
            self.panel_signal_id = self.panel.connect_after('expose-event',
                    self.update_panel_position)
        else:
            self.panel_signal_id = self.panel.connect_after('draw',
                    self.update_panel_position)
        self.panel.connect('button-release-event', self.on_input_panel_resize)

        self.hbox = gtk.HBox()
        if self.session.config.get_or_set('b_avatar_on_left', False):
            self.hbox.pack_start(self.info, False)
            self.hbox.pack_start(self.panel, True, True)
        else:
            self.hbox.pack_start(self.panel, True, True)
            self.hbox.pack_start(self.info, False)

        self.pack_start(self.header, False)
        self.pack_start(self.hbox, True, True)
        self.pack_start(self.transfers_bar, False)
        if self.below_conversation is not None:
            self.pack_start(self.below_conversation, False)

        if len(self.members) == 0:
            self.header.information = ('connecting', 'creating conversation')
        else:
            #update adium theme header/footer
            account = self.members[0]
            contact = self.session.contacts.safe_get(account)
            his_picture = contact.picture or \
                utils.path_to_url(os.path.abspath(gui.theme.image_theme.user))
            nick = contact.nick
            display_name = contact.display_name
            self.set_sensitive(not contact.blocked, True)
            my_picture = self.session.contacts.me.picture or \
                utils.path_to_url(os.path.abspath(gui.theme.image_theme.user))
            self.output.clear(account, nick, display_name,
                              my_picture, his_picture)

        self._load_style()
        self.subscribe_signals()
        self.tab_index = -1  # used to select an existing conversation

    def on_conversation_info_extension_changed(self, new_extension):
        if type(self.info) != new_extension:
            self.hbox.remove(self.info)
            self.info = None

            if new_extension:
                self.info = new_extension(self.session, self.members)
                if self.session.config.get_or_set('b_avatar_on_left', False):
                    self.hbox.pack_start(self.info, False)
                else:
                    self.hbox.pack_end(self.info, False)

            if self.session.config.b_show_info:
                self.info.show()

    def on_below_conversation_changed(self, newvalue):
        if type(self.below_conversation) != newvalue:
            #replace the below conversation
            if not self.below_conversation is None:
                self.remove(self.below_conversation)
                self.below_conversation = None

            if newvalue:
                self.below_conversation = newvalue(self, self.session)
                self.pack_end(self.below_conversation, False)
                self.below_conversation.show()

    def check_visible(self):
        return self.get_visible()

    def steal_emoticon(self, path_uri):
        '''receives the path or the uri for the emoticon to be added'''
        if path_uri.startswith("file://"):
            path_uri = path_uri[7:]
            path_uri = urllib.url2pathname(path_uri)
        directory = os.path.dirname(path_uri).lower()
        emcache = self.session.caches.get_emoticon_cache(self.session.account.account)
        dialog = extension.get_default('dialog')

        if directory.endswith(gui.theme.emote_theme.path.lower()):
            dialog.information(_("Can't add, default emoticon"))
        elif directory == emcache.path.lower():
            dialog.information(_("Can't add, own emoticon"))
        else:
            def on_response(response, shortcut):
                if response == stock.ACCEPT:
                    shortcut = dialog.entry.get_text()
                    if shortcut not in emcache.list():
                        self.emcache.insert((shortcut, path_uri))
                    # TODO: check if the file's hash is not already on the cache
                    else:
                        dialog.information(_("Shortcut already in use"))

            matches = re.search(r'<img src="' + path_uri + \
                '" alt="(?P<alt>\S*)" name="(?P<name>\w*)"',
                self.output.view.text)
            groupdict = {'alt': ''} if not matches else matches.groupdict()
            dialog = dialog.entry_window(
                        _("Type emoticon's shortcut: "), groupdict['alt'],
                        on_response, _("Choose custom emoticon's shortcut"))
            dialog.entry.set_max_length(7)
            dialog.show()

    def _on_icon_size_change(self, value):
        '''callback called when config.b_toolbar_small changes'''
        self.toolbar.draw()

    def _on_show_toolbar_changed(self, value):
        '''callback called when config.b_show_toolbar changes'''
        self.toolbar.set_visible(value)

    def _on_show_header_changed(self, value):
        '''callback called when config.b_show_header changes'''
        self.header.set_visible(value)

    def _on_show_info_changed(self, value):
        '''callback called when config.b_show_info changes'''
        self.info.set_visible(value)
        self.toolbar.update_toggle_avatar_icon(value)

    def _on_show_avatar_onleft(self, value):
        '''callback called when config.b_avatar_on_left changes'''
        self.hbox.reorder_child(self.panel, value)
        self.hbox.reorder_child(self.info, not value)

    def on_close(self):
        '''called when the conversation is closed'''
        self.unsubscribe_signals()
        self.destroy()
        self.info.destroy()
        self.header.destroy()

    def show(self):
        '''override the show method'''
        gtk.VBox.show(self)

        if self.session.config.b_show_header:
            self.header.show_all()

        self.info.show_all()
        if not self.session.config.b_show_info:
            self.info.hide()

        self.hbox.show()
        self.panel.show_all()

        if not self.session.config.b_show_toolbar:
            self.toolbar.hide()

    def input_grab_focus(self):
        '''
        sets the focus on the input widget
        '''
        self.input.grab_focus()

    def update_panel_position(self, *args):
        """update the panel position to be on the 80% of the height
        """
        height = self.panel.get_allocation().height
        if height > 0:
            pos = self.session.config.get_or_set("i_input_panel_position",
                    int(height*0.8))
            self.panel.set_position(pos)
            self.panel.disconnect(self.panel_signal_id)
            del self.panel_signal_id

    def on_input_panel_resize(self, *args):
        pos = self.panel.get_position()
        self.session.config.i_input_panel_position = pos

    def show_tab_menu(self):
        '''callback called when the user press a button over a widget
        chek if it's the right button and display the menu'''
        pass

    def update_tab(self):
        '''update the values of the tab'''
        self.typing_timeout = None

        self.tab_label.set_image(self.icon)
        self.tab_label.set_text(self.text)

        if self.show_avatar_in_taskbar:
            self.update_window(self.text, self.info.his_avatar.filename,
                               self.tab_index)
        else:
            self.update_window(self.text, self.icon, self.tab_index)

    def set_sensitive(self, is_sensitive, force_sensitive_block_button=False):
        """
        used to make the conversation insensitive while the conversation
        is still open while the user is disconnected and to set it back to
        sensitive when the user is reconnected.
        """
        self.input.set_sensitive(is_sensitive)
        self.info.set_sensitive(is_sensitive or force_sensitive_block_button)
        self.toolbar.set_sensitive(is_sensitive, force_sensitive_block_button)

        # redraws block button to its corresponding icon and tooltip
        contact_unblocked = not force_sensitive_block_button or is_sensitive
        self.toolbar.redraw_ublock_button(contact_unblocked)

    def set_image_visible(self, is_visible):
        """
        set the visibility of the widget that displays the images of the members

        is_visible -- boolean that says if the widget should be shown or hidden
        """
        self.info.set_visible(is_visible)

    def set_header_visible(self, is_visible):
        '''
        hide or show the widget according to is_visible

        is_visible -- boolean that says if the widget should be shown or hidden
        '''
        self.header.set_visible(is_visible)

    def set_toolbar_visible(self, is_visible):
        '''
        hide or show the widget according to is_visible

        is_visible -- boolean that says if the widget should be shown or hidden
        '''
        self.toolbar.set_visible(is_visible)

    def get_preview(self, completepath):
        return utils.makePreview(completepath)

    def on_user_typing(self, account):
        """
        inform that the other user has started typing
        """
        if account in self.members:
            self.tab_label.set_image(gui.theme.image_theme.typing)
            if self.typing_timeout is not None:
                glib.source_remove(self.typing_timeout)
            self.typing_timeout = glib.timeout_add_seconds(3, self.update_tab)

    def on_emote(self, emote):
        '''called when an emoticon is selected'''
        self.input.append(glib.markup_escape_text(emote))
        self.input_grab_focus()

    def on_filetransfer_invitation(self, transfer, cid):
        ''' called when a new file transfer is issued '''
        if transfer.contact.account == self.members[0]:
            self.transfers_bar.add(transfer)

    def on_filetransfer_accepted(self, transfer):
        ''' called when the file transfer is accepted '''
        if transfer in self.transfers_bar.transfers:
            self.transfers_bar.accepted(transfer)

        if transfer.contact.account == self.members[0]:
            contact = self._member_to_contact(self.members[0])
            message = e3.base.Message(e3.base.Message.TYPE_MESSAGE, \
            _('File transfer accepted by %s') % (contact.display_name), \
            transfer.contact.account)
            msg = gui.Message.from_information(contact, message)
            self.output.information(msg)
            self.conv_status.post_process_message(msg)

    def on_filetransfer_progress(self, transfer):
        ''' called every chunk received '''
        if transfer in self.transfers_bar.transfers:
            self.transfers_bar.update(transfer)

    def on_filetransfer_rejected(self, transfer):
        ''' called when a file transfer is rejected '''
        if transfer in self.transfers_bar.transfers:
            self.transfers_bar.canceled(transfer)

        if transfer.contact.account == self.members[0]:
            contact = self._member_to_contact(self.members[0])
            message = e3.base.Message(e3.base.Message.TYPE_MESSAGE, \
            _('File transfer rejected by %s') % (contact.display_name), \
            transfer.contact.account)
            msg = gui.Message.from_information(contact, message)
            self.output.information(msg)
            self.conv_status.post_process_message(msg)

    def on_filetransfer_canceled(self, transfer):
        ''' called when a file transfer is canceled '''
        if transfer in self.transfers_bar.transfers:
            self.transfers_bar.canceled(transfer)

        if transfer.contact.account == self.members[0]:
            contact = self._member_to_contact(self.members[0])
            message = e3.base.Message(e3.base.Message.TYPE_MESSAGE, \
            _('File transfer canceled by %s') % (contact.display_name), \
            transfer.contact.account)
            msg = gui.Message.from_information(contact, message)
            self.output.information(msg)
            self.conv_status.post_process_message(msg)

    def on_filetransfer_completed(self, transfer):
        ''' called when a file transfer is completed '''
        if transfer in self.transfers_bar.transfers:
            self.transfers_bar.finished(transfer)

        if transfer.contact.account == self.members[0]:
            contact = self._member_to_contact(self.members[0])
            message = e3.base.Message(e3.base.Message.TYPE_MESSAGE, \
            _('File transfer completed!'), transfer.contact.account)
            msg = gui.Message.from_information(contact, message)
            self.output.information(msg)
            self.conv_status.post_process_message(msg)

    def on_call_invitation(self, call, cid, westart=False):
        '''called when a new call is issued both from us or other party'''
        if cid == self.cid:
            self.call_widget.add_call(call, westart)
            self.call_widget.show_all_widgets()
            self.call_widget.set_xids()

    def on_video_call(self):
        '''called when the user is requesting a video-only call'''
        account = self.members[0]
        self.call_widget.show_all()
        x_other, x_self = self.call_widget.get_xids()
        self.session.call_invite(self.cid, account, 0,
                                 x_other, x_self) # 0 = Video only

    def on_voice_call(self):
        '''called when the user is requesting an audio-only call'''
        account = self.members[0]
        self.call_widget.show_all()
        x_other, x_self = self.call_widget.get_xids()
        self.session.call_invite(self.cid, account, 1,
                                 x_other, x_self) # 1 = Audio only

    def on_av_call(self):
        '''called when the user is requesting an audio-video call'''
        account = self.members[0]
        self.call_widget.show_all()
        x_other, x_self = self.call_widget.get_xids()
        self.session.call_invite(self.cid, account, 2,
                                 x_other, x_self) # 2 = Audio/Video

    def on_drag_data_received(self, widget, context,
                              posx, posy, selection,
                              info, timestamp):
        '''called when a file is received by text input widget'''

        if hasattr(selection, 'data'):
            data = selection.data
        else:
            data = selection.get_data()

        # skip group from contact list, it is None now
        if data is None:
            return

        # user invitation
        if selection.get_target() == 'emesene-invite':
            inviter = self.session.contacts.safe_get(self.members[0])
            invitee = self.session.contacts.get(data.strip())
            if invitee and not invitee.blocked and \
               not inviter.blocked:
                self.on_invite(invitee.account)
                return

        # file transfer
        uri = data.strip()
        uri_splitted = uri.split()
        for uri in uri_splitted:
            path = self.__get_file_path_from_dnd_dropped_uri(uri)
            if os.path.isfile(path):
                filename = os.path.basename(path)
                self.on_filetransfer_invite(filename, path)

    def __get_file_path_from_dnd_dropped_uri(self, uri):
        '''Parses an URI received from dnd and return the real path'''

        if os.name != 'nt':
            path = urllib.url2pathname(uri) # escape special chars
        else:
            path = urllib.unquote(uri) # escape special chars
        path = path.strip('\r\n\x00') # remove \r\n and NULL

        # get the path to file
        if re.match('^file:///[a-zA-Z]:/', path): # windows
            path = path[8:] # 8 is len('file:///')
        elif path.startswith('file://'): # nautilus, rox
            path = path[7:] # 7 is len('file://')
        elif path.startswith('file:'): # xffm
            path = path[5:] # 5 is len('file:')
        return path
