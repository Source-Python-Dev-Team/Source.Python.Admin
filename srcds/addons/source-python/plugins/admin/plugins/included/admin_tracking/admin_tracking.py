# =============================================================================
# >> IMPORTS
# =============================================================================
# Python
from configparser import ConfigParser
from enum import IntEnum
from time import localtime, strftime, time

# Source.Python
from commands import CommandReturn
from events import Event
from listeners import OnClientActive
from listeners.tick import GameThread
from menus import PagedMenu, PagedOption, SimpleMenu, Text
from players.dictionary import PlayerDictionary
from players.entity import Player
from steam import SteamID

# Source.Python Admin
from admin.core.clients import clients
from admin.core.helpers import extract_ip_address, format_player_name
from admin.core.features import (
    BaseFeature, BasePlayerBasedFeature, PlayerBasedFeature)
from admin.core.frontends.commands import (
    BaseFeatureCommand, BasePlayerBasedFeatureCommand)
from admin.core.frontends.menus import (
    main_menu, MenuSection, PlayerBasedMenuCommand)
from admin.core.helpers import chat_message, console_message
from admin.core.orm import SessionContext
from admin.core.paths import ADMIN_CFG_PATH, get_server_file
from admin.core.plugins.strings import PluginStrings

# Included Plugin
from .models import TrackedPlayerRecord as DB_Record


# =============================================================================
# >> FUNCTIONS
# =============================================================================
def _remove_old_database_records():
    with SessionContext() as session:
        max_record_life_seconds = (
            int(plugin_config['database']['max_record_life_days']) * 24 * 3600)

        (
            session
            .query(DB_Record)
            .filter(DB_Record.seen_at < time() - max_record_life_seconds)
            .delete(synchronize_session=False)
        )

        session.commit()


def _get_records_for_steamid(steamid):
    records = []
    steamid64 = str(SteamID.parse(steamid).to_uint64())

    # Firstly, add live records (if player is on the server)
    for tracked_player in tracked_players.values():
        if tracked_player.steamid == steamid64:
            for record in reversed(tracked_player):
                records.append(_TrackRecordReport(
                    steamid64,
                    record.ip_address,
                    record.name,
                    record.seen_at,
                    live=True
                ))

            break

    # Secondly, add records from the database
    with SessionContext() as session:

        db_records = (
            session
            .query(DB_Record)
            .filter_by(steamid64=steamid64)
            .order_by(DB_Record.seen_at.desc())
            .all()
        )

    for db_record in db_records:
        records.append(_TrackRecordReport(
            db_record.steamid64,
            db_record.ip_address,
            db_record.name,
            db_record.seen_at,
            live=False
        ))

    return records


def _get_records_for_ip_address(ip_address):
    records = []
    seen_steamids = []

    # Firstly, add live records (if player is on the server)
    for tracked_player in tracked_players.values():
        if not tracked_player:
            continue

        record = tracked_player[-1]

        if record.ip_address != ip_address:
            continue

        seen_steamids.append(tracked_player.steamid)

        records.append(_TrackRecordReport(
            tracked_player.steamid,
            ip_address,
            record.name,
            record.seen_at,
            live=True
        ))

    # Secondly, add records from the database
    with SessionContext() as session:
        db_records = (
            session
                .query(DB_Record)
                .filter_by(ip_address=ip_address)
                .order_by(DB_Record.seen_at.desc())
                .all()
        )

    for db_record in db_records:
        if db_record.steamid64 in seen_steamids:
            continue

        seen_steamids.append(db_record.steamid64)

        records.append(_TrackRecordReport(
            db_record.steamid64,
            db_record.ip_address,
            db_record.name,
            db_record.seen_at,
            live=False
        ))

    return records


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
PLUGIN_CONFIG_FILE = get_server_file(
    ADMIN_CFG_PATH / "included_plugins" / "admin_tracking" / "config.ini")

plugin_config = ConfigParser()
plugin_config.read(PLUGIN_CONFIG_FILE)

plugin_strings = PluginStrings("admin_tracking")

_last_shown_records = PlayerDictionary(lambda index: None)


# =============================================================================
# >> CLASSES
# =============================================================================
class _Record:
    def __init__(self, ip_address, name, seen_at):
        self.ip_address = ip_address
        self.name = name
        self.seen_at = seen_at


class _TrackedPlayer(list):
    def __init__(self, index):
        super().__init__()

        self.player = Player(index)
        self.steamid = None
        if not (
                self.player.is_fake_client() or
                self.player.is_hltv() or
                'BOT' in self.player.steamid
        ):

            self.steamid = str(SteamID.parse(self.player.steamid).to_uint64())

    def track(self, name=None):
        if self.steamid is None:
            return

        self.append(_Record(
            extract_ip_address(self.player.address),
            self.player.name if name is None else name,
            int(time())
        ))

    def save_to_database(self):
        if self.steamid is None:
            return

        with SessionContext() as session:
            db_record = (
                session
                .query(DB_Record)
                .filter_by(steamid64=self.steamid)
                .order_by(DB_Record.seen_at.desc())
                .first()
            )

            if db_record is None:
                last_name = last_ip_address = ""
            else:
                last_name = db_record.name
                last_ip_address = db_record.ip_address

            for record in self:
                if (
                        record.name == last_name and
                        record.ip_address == last_ip_address
                ):
                    continue

                db_record = DB_Record()
                db_record.steamid64 = self.steamid
                db_record.name = record.name
                db_record.ip_address = record.ip_address
                db_record.seen_at = record.seen_at

                session.add(db_record)

                last_name, last_ip_address = record.name, record.ip_address

            session.commit()

        self.clear()


class _TrackedPlayerDictionary(PlayerDictionary):
    def on_automatically_removed(self, index):
        tracked_player = self[index]
        GameThread(target=tracked_player.save_to_database).start()


class _TrackRecordReport:
    def __init__(self, steamid, ip_address, name, seen_at, live):
        self.steamid = steamid
        self.ip_address = ip_address
        self.name = name
        self.seen_at = seen_at
        self.live = live


class _TrackPopupOption(IntEnum):
    SEARCH_BY_IP = 0


class _TrackPopupFeature(PlayerBasedFeature):
    flag = "admin.admin_tracking.track"
    allow_execution_on_equal_priority = True

    def __init__(self):
        self._selected_records = PlayerDictionary(lambda index: None)
        self._records_to_show = None

        self.record_popup = PagedMenu(
            title=plugin_strings['popup_title select_record'])

        self.track_popup = PagedMenu()

        self.dummy_popup = SimpleMenu()
        self.dummy_popup.append(Text(plugin_strings['processing']))

        @self.record_popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            for i, record in enumerate(self._records_to_show, start=1):
                text = plugin_strings['record_title'].tokenized(
                    id=i,
                    seen_at=strftime(
                        "%d %b %Y %H:%M:%S", localtime(record.seen_at)
                    ),
                    name=format_player_name(record.name)
                )

                # If it's a live (unsaved) record, add a prefix
                if record.live:
                    text = plugin_strings['prefix live_record'].tokenized(
                        text=text)

                popup.append(PagedOption(
                    text=text,
                    value=(i, record)
                ))

        @self.record_popup.register_select_callback
        def select_callback(popup, index, option):
            client = clients[index]

            self._selected_records[index] = option.value
            client.send_popup(self.track_popup)

        @self.track_popup.register_build_callback
        def build_callback(popup, index):
            popup.title = plugin_strings['record_title'].tokenized(
                id=self._selected_records[index][0],
                seen_at=strftime(
                    "%d %b %Y %H:%M:%S", localtime(
                        self._selected_records[index][1].seen_at)
                ),
                name=format_player_name(self._selected_records[index][1].name)
            )

            popup.clear()
            popup.append(Text(plugin_strings['popup_text name'].tokenized(
                name=self._selected_records[index][1].name,
            )))
            popup.append(Text(plugin_strings['popup_text steamid'].tokenized(
                steamid=self._selected_records[index][1].steamid,
            )))
            popup.append(Text(
                plugin_strings['popup_text ip_address'].tokenized(
                    ip_address=self._selected_records[index][1].ip_address,
            )))
            popup.append(PagedOption(
                text=plugin_strings['popup_title search_for_ip'].tokenized(
                    ip_address=self._selected_records[index][1].ip_address),
                value=(
                    _TrackPopupOption.SEARCH_BY_IP,
                    self._selected_records[index][1].ip_address
                )
            ))

        @self.track_popup.register_select_callback
        def select_callback(popup, index, option):
            client = clients[index]
            if option.value[0] == _TrackPopupOption.SEARCH_BY_IP:
                client.send_popup(self.dummy_popup)

                GameThread(
                    target=self._show_players_for_ip_address,
                    args=(client, option.value[1], )
                ).start()

    def _show_records_for_steamid(self, client, steamid):
        self._records_to_show = _get_records_for_steamid(steamid)
        _last_shown_records[client.player.index] = self._records_to_show[:]

        client.send_popup(self.record_popup)

    def _show_players_for_ip_address(self, client, ip_address):
        self._records_to_show = _get_records_for_ip_address(ip_address)
        _last_shown_records[client.player.index] = self._records_to_show[:]

        client.send_popup(self.record_popup)

    def execute(self, client, player):
        if (
                player.is_fake_client() or
                player.is_hltv() or
                'BOT' in player.steamid
        ):

            client.tell(plugin_strings['error bot_cannot_track'])
            return

        client.send_popup(self.dummy_popup)

        GameThread(
            target=self._show_records_for_steamid,
            args=(client, player.steamid)
        ).start()

# The singleton object of the _TrackPopupFeature class.
track_popup_feature = _TrackPopupFeature()


class _TrackPopupMenuCommand(PlayerBasedMenuCommand):
    base_filter = 'human'
    allow_multiple_choices = False


class _TextReportsMixin:
    @classmethod
    def _show_records(cls, client, message_func, records, start, end):
        if records:
            message_func(plugin_strings['result_count'].tokenized(
                count=len(records), start=start, end=end))

            for i, record in enumerate(records, start=1):
                text = plugin_strings['record_title'].tokenized(
                    id=i,
                    seen_at=strftime(
                        "%d %b %Y %H:%M:%S", localtime(record.seen_at)
                    ),
                    name=format_player_name(record.name)
                )

                # If it's a live (unsaved) record, add a prefix
                if record.live:
                    text = plugin_strings['prefix live_record'].tokenized(
                        text=text)

                message_func(text)
        else:
            message_func(plugin_strings['no_results'])

        _last_shown_records[client.player.index] = records[:]

    @classmethod
    def _show_records_for_steamid(
            cls, client, message_func, steamid, start_record_num):

        limit = int(plugin_config['text']['records_to_show_per_request'])

        try:
            records = _get_records_for_steamid(steamid)[
                      start_record_num-1:start_record_num+limit-1]
        except ValueError:
            message_func(plugin_strings['invalid_steamid'])
            return

        cls._show_records(
            client, message_func, records, start_record_num,
            min(start_record_num + len(records), start_record_num + limit) - 1
        )

    @classmethod
    def _show_records_for_ip_address(
            cls, client, message_func, ip_address, start_record_num):

        limit = int(plugin_config['text']['records_to_show_per_request'])

        records = _get_records_for_ip_address(ip_address)[
                  start_record_num - 1:start_record_num + limit - 1]

        cls._show_records(
            client, message_func, records, start_record_num,
            min(start_record_num + len(records), start_record_num + limit) - 1
        )


class _TrackSteamIDTextFeature(_TextReportsMixin, BasePlayerBasedFeature):
    flag = "admin.admin_tracking.track"

    def filter(self, client, player):
        # "track player" command will try to filter its results using our
        # filter, and is the only reason we subclass BasePlayerBasedFeature
        # instead of BaseFeature
        return True

    def execute(self, client, message_func, steamid, start_record_num):
        message_func(plugin_strings['processing'])

        GameThread(
            target=self._show_records_for_steamid,
            args=(client, message_func, steamid, start_record_num)
        ).start()

# The singleton object of the _TrackSteamIDTextFeature class.
track_steamid_text_feature = _TrackSteamIDTextFeature()


class _TrackSteamIDCommand(BaseFeatureCommand):
    def _execute(self, command_info, message_func, steamid, start_record_num):
        client = clients[command_info.index]
        client.sync_execution(
            self.feature.execute,
            (client, message_func, steamid, start_record_num)
        )

    def _get_public_chat_callback(self):
        def public_chat_callback(
                command_info, steamid, start_record_num:int=1):

            def message_func(message):
                chat_message(message, (command_info.index, ))

            self._execute(
                command_info, message_func, steamid, start_record_num)

            return CommandReturn.CONTINUE

        return public_chat_callback

    def _get_private_chat_callback(self):
        def private_chat_callback(
                command_info, steamid, start_record_num:int=1):

            def message_func(message):
                chat_message(message, (command_info.index, ))

            self._execute(
                command_info, message_func, steamid, start_record_num)

            return CommandReturn.BLOCK

        return private_chat_callback

    def _get_client_callback(self):
        def client_callback(command_info, steamid, start_record_num:int=1):
            def message_func(message):
                console_message(message, (command_info.index, ))

            self._execute(
                command_info, message_func, steamid, start_record_num)

        return client_callback


class _TrackIPAddressTextFeature(_TextReportsMixin, BaseFeature):
    flag = "admin.admin_tracking.track"

    def execute(self, client, message_func, ip_address, start_record_num):
        message_func(plugin_strings['processing'])

        GameThread(
            target=self._show_records_for_ip_address,
            args=(client, message_func, ip_address, start_record_num)
        ).start()

# The singleton object of the _TrackIPAddressTextFeature class.
track_ip_address_text_feature = _TrackIPAddressTextFeature()


class _TrackIPAddressCommand(BaseFeatureCommand):
    def _execute(
            self, command_info, message_func, ip_address, start_record_num):

        client = clients[command_info.index]
        client.sync_execution(
            self.feature.execute,
            (client, message_func, ip_address, start_record_num)
        )

    def _get_public_chat_callback(self):
        def public_chat_callback(
                command_info, ip_address, start_record_num:int=1):

            def message_func(message):
                chat_message(message, (command_info.index, ))

            self._execute(
                command_info, message_func, ip_address, start_record_num)

            return CommandReturn.CONTINUE

        return public_chat_callback

    def _get_private_chat_callback(self):
        def private_chat_callback(
                command_info, ip_address, start_record_num:int=1):

            def message_func(message):
                chat_message(message, (command_info.index, ))

            self._execute(
                command_info, message_func, ip_address, start_record_num)

            return CommandReturn.BLOCK

        return private_chat_callback

    def _get_client_callback(self):
        def client_callback(command_info, ip_address, start_record_num:int=1):
            def message_func(message):
                console_message(message, (command_info.index, ))

            self._execute(
                command_info, message_func, ip_address, start_record_num)

        return client_callback


class _TrackPlayerCommand(BasePlayerBasedFeatureCommand):
    deny_mass_execution = True

    def _execute(
            self, command_info, filter_str, filter_args, message_func,
            start_record_num):

        client = clients[command_info.index]

        for player in self._get_target_players(
                client, filter_str, filter_args):

            client.sync_execution(
                self.feature.execute,
                (client, message_func, player.steamid, start_record_num)
            )

            break

        else:
            message_func(plugin_strings['failed_filter'])

    def _get_public_chat_callback(self):
        def public_chat_callback(
                command_info, filter_str:str, filter_args:str="",
                start_record_num:int=1):

            def message_func(message):
                chat_message(message, (command_info.index, ))

            self._execute(command_info, filter_str, filter_args, message_func,
                          start_record_num)

            return CommandReturn.CONTINUE

        return public_chat_callback

    def _get_private_chat_callback(self):
        def private_chat_callback(
                command_info, filter_str:str, filter_args:str="",
                start_record_num:int=1):

            def message_func(message):
                chat_message(message, (command_info.index, ))

            self._execute(command_info, filter_str, filter_args, message_func,
                          start_record_num)

            return CommandReturn.BLOCK

        return private_chat_callback

    def _get_client_callback(self):
        def client_callback(
                command_info, filter_str:str, filter_args:str="",
                start_record_num:int=1):

            def message_func(message):
                console_message(message, (command_info.index, ))

            self._execute(command_info, filter_str, filter_args, message_func,
                          start_record_num)

        return client_callback


class _DetailTextFeature(BaseFeature):
    flag = "admin.admin_tracking.track"

    def execute(self, client, message_func, record_id):
        if _last_shown_records[client.player.index] is None:
            message_func(plugin_strings['no_results'])
            return

        try:
            record = _last_shown_records[client.player.index][record_id - 1]
        except IndexError:
            message_func(plugin_strings['no_results'])
            return

        message_func(plugin_strings['detail'].tokenized(
            id=record_id,
            seen_at=strftime("%d %b %Y %H:%M:%S", localtime(record.seen_at)),
            name=record.name,
            steamid=record.steamid,
            ip_address=record.ip_address,
        ))

# The singleton object of the _DetailTextFeature class.
detail_text_feature = _DetailTextFeature()


class _DetailCommand(BaseFeatureCommand):
    def _execute(self, command_info, message_func, record_id):
        client = clients[command_info.index]
        client.sync_execution(
            self.feature.execute, (client, message_func, record_id))

    def _get_public_chat_callback(self):
        def public_chat_callback(command_info, record_id:int):
            def message_func(message):
                chat_message(message, (command_info.index,))

            self._execute(command_info, message_func, record_id)

            return CommandReturn.CONTINUE

        return public_chat_callback

    def _get_private_chat_callback(self):
        def private_chat_callback(command_info, record_id:int):
            def message_func(message):
                chat_message(message, (command_info.index,))

            self._execute(command_info, message_func, record_id)

            return CommandReturn.BLOCK

        return private_chat_callback

    def _get_client_callback(self):
        def client_callback(command_info, record_id:int):
            def message_func(message):
                console_message(message, (command_info.index,))

            self._execute(command_info, message_func, record_id)

        return client_callback


# =============================================================================
# >> PLAYER DICTIONARY
# =============================================================================
tracked_players = _TrackedPlayerDictionary(_TrackedPlayer)


# =============================================================================
# >> COMMAND FRONTEND
# =============================================================================
_TrackSteamIDCommand(["track", "steamid"], track_steamid_text_feature)
_TrackIPAddressCommand(["track", "ip"], track_ip_address_text_feature)
# _TrackPlayerCommand also uses SteamID, thus its feature is not a typo
_TrackPlayerCommand(["track", "player"], track_steamid_text_feature)
_DetailCommand(["track", "detail"], detail_text_feature)


# =============================================================================
# >> MENU ENTRIES
# =============================================================================
menu_section = main_menu.add_entry(MenuSection(
    main_menu, plugin_strings['section_title']))

track_menu_command = menu_section.add_entry(_TrackPopupMenuCommand(
    track_popup_feature,
    menu_section,
    plugin_strings['popup_title track']
))


# =============================================================================
# >> SYNCHRONOUS DATABASE OPERATIONS
# =============================================================================
_remove_old_database_records()


# =============================================================================
# >> LISTENERS
# =============================================================================
@OnClientActive
def listener_on_client_active(index):
    tracked_player = tracked_players[index]
    tracked_player.track()


# =============================================================================
# >> EVENTS
# =============================================================================
@Event('player_changename')
def on_player_changename(ev):
    tracked_player = tracked_players.from_userid(ev['userid'])
    tracked_player.track(ev['newname'])
