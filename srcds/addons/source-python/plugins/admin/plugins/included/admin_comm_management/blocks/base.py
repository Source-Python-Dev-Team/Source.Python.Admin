# =============================================================================
# >> IMPORTS
# =============================================================================
# Python
import json
from time import time

# Source.Python
from listeners.tick import GameThread
from menus import PagedMenu, PagedOption
from players.dictionary import PlayerDictionary
from steam import SteamID

# Site-Package
from sqlalchemy.sql.expression import and_, or_

# Source.Python Admin
from admin.core.clients import clients
from admin.core.features import BaseFeature
from admin.core.frontends.menus import AdminCommand, PlayerBasedAdminCommand
from admin.core.helpers import format_player_name
from admin.core.orm import SessionContext
from admin.core.paths import ADMIN_CFG_PATH, get_server_file
from admin.core.strings import strings_common

# Included Plugin
from ..strings import plugin_strings


# =============================================================================
# >> FUNCTIONS
# =============================================================================
def load_stock_block_durations():
    with open(get_server_file(
            ADMIN_CFG_PATH / "included_plugins" / "admin_comm_management" /
            "block_durations.json")) as f:

        block_durations_json = json.load(f)

    block_durations_json.sort()

    return block_durations_json


def format_block_duration(seconds):
    if seconds < 0:
        return plugin_strings['duration permanent']

    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    if days:
        return plugin_strings['duration days'].tokenized(
            days=days, hours=hours, mins=minutes, secs=seconds)

    if hours:
        return plugin_strings['duration hours'].tokenized(
            hours=hours, mins=minutes, secs=seconds)

    if minutes:
        return plugin_strings['duration minutes'].tokenized(
            mins=minutes, secs=seconds)

    return plugin_strings['duration seconds'].tokenized(secs=seconds)


# =============================================================================
# >> CLASSES
# =============================================================================
class _BlockedCommUserInfo:
    def __init__(self, steamid64, id_, name, blocked_by, expires_at):
        self.steamid64 = steamid64
        self.id = id_
        self.name = name
        self.blocked_by = blocked_by
        self.expires_at = expires_at


class BlockedCommUserManager(dict):
    model = None

    def _convert_steamid_to_db_format(self, steamid):
        return str(SteamID.parse(steamid).to_uint64())

    def _on_change(self):
        pass

    def refresh(self):
        self.clear()

        with SessionContext() as session:
            blocked_users = session.query(self.model).all()

            current_time = time()
            for blocked_user in blocked_users:
                if blocked_user.is_unblocked:
                    continue

                if 0 <= blocked_user.expires_at < current_time:
                    continue

                self[blocked_user.steamid64] = _BlockedCommUserInfo(
                    blocked_user.steamid64, blocked_user.id, blocked_user.name,
                    blocked_user.blocked_by, blocked_user.expires_at
                )

        self._on_change()

    def is_blocked(self, steamid):
        steamid64 = self._convert_steamid_to_db_format(steamid)

        if steamid64 not in self:
            return False

        if self[steamid64].expires_at < 0:
            return True

        if self[steamid64].expires_at < time():
            del self[steamid64]
            return False

        return True

    def save_block_to_database(self, blocked_by, steamid, name, duration):
        steamid = self._convert_steamid_to_db_format(steamid)
        blocked_by = self._convert_steamid_to_db_format(blocked_by)

        with SessionContext() as session:
            blocked_user = self.model(steamid, name, blocked_by, duration)

            session.add(blocked_user)
            session.commit()

            self[steamid] = _BlockedCommUserInfo(
                steamid, blocked_user.id, name, blocked_by,
                blocked_user.expires_at)

        self._on_change()

    def get_all_blocks(
            self, steamid=None, blocked_by=None, expired=None, unblocked=None):

        result = []

        with SessionContext() as session:
            query = session.query(self.model)

            if steamid is not None:
                steamid = self._convert_steamid_to_db_format(steamid)
                query = query.filter_by(steamid64=steamid)

            if blocked_by is not None:
                blocked_by = self._convert_steamid_to_db_format(blocked_by)
                query = query.filter_by(blocked_by=blocked_by)

            if expired is not None:
                current_time = int(time())
                if expired:
                    query = query.filter(and_(
                        self.model.expires_at < current_time,
                        self.model.expires_at >= 0
                    ))
                else:
                    query = query.filter(or_(
                        self.model.expires_at >= current_time,
                        self.model.expires_at < 0
                    ))

            if unblocked is not None:
                query = query.filter_by(is_unblocked=unblocked)

            for blocked_user in query.all():
                result.append(_BlockedCommUserInfo(
                    blocked_user.steamid64, blocked_user.id, blocked_user.name,
                    blocked_user.blocked_by, blocked_user.expires_at
                ))

        return result

    def get_active_blocks(self, blocked_by=None):
        if blocked_by is not None:
            blocked_by = self._convert_steamid_to_db_format(blocked_by)

        current_time = time()

        result = []
        for blocked_comm_user_info in self.values():
            if (
                    blocked_by is not None and
                    blocked_comm_user_info.blocked_by != blocked_by):

                continue

            if blocked_comm_user_info.expires_at < current_time:
                continue

            result.append(blocked_comm_user_info)

        return result

    def lift_block(self, id_, unblocked_by):
        unblocked_by = self._convert_steamid_to_db_format(unblocked_by)

        with SessionContext() as session:
            blocked_user = session.query(self.model).filter_by(id=id_).first()

            if blocked_user is None:
                return

            blocked_user.lift_block(unblocked_by)

            session.commit()

        for steamid64, blocked_comm_user_info in self.items():
            if blocked_comm_user_info.id != id_:
                continue

            del self[steamid64]
            break

        self._on_change()


class BlockCommFeature(BaseFeature):
    feature_abstract = True
    blocked_comm_user_manager = None

    def execute(self, client, player, duration):
        if player.is_fake_client() or player.is_hltv():
            client.tell(plugin_strings['error bot_cannot_block'])
            return

        GameThread(
            target=self.blocked_comm_user_manager.save_block_to_database,
            args=(
                client.steamid,
                player.steamid,
                player.name,
                duration
            )
        ).start()

    def filter(self, client, player):
        if self.blocked_comm_user_manager.is_blocked(player.steamid):
            return False

        if client.player == player:
            return False

        another_client = clients[player.index]
        return not another_client.has_permission(self.flag)


class BlockCommAdminCommand(PlayerBasedAdminCommand):
    base_filter = 'human'

    def __init__(self, feature, parent, title, id_=None):
        super().__init__(feature, parent, title, id_)

        self._selected_players = PlayerDictionary(lambda index: ())

        self.duration_popup = PagedMenu(
            parent_menu=self.popup,
            title=plugin_strings['popup_title duration'])

        @self.duration_popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            for block_duration in stock_block_durations:
                popup.append(PagedOption(
                    text=format_block_duration(block_duration),
                    value=(self._selected_players[index], block_duration)
                ))

        @self.duration_popup.register_select_callback
        def select_callback(popup, index, option):
            client = clients[index]

            for player in self._filter_player_ids(client, option.value[0]):
                self.feature.execute(client, player, option.value[1])

    def _player_select(self, client, player_ids):
        index = client.player.index
        self._selected_players[index] = player_ids

        client.send_popup(self.duration_popup)


class UnblockCommFeature(BaseFeature):
    feature_abstract = True
    blocked_comm_user_manager = None

    def execute(self, client, blocked_comm_user_info):
        GameThread(
            target=self.blocked_comm_user_manager.lift_block,
            args=(blocked_comm_user_info.id, client.steamid)
        ).start()


class _UnblockCommAdminCommand(AdminCommand):
    popup_title = None

    def __init__(self, feature, parent, title, id_=None):
        super().__init__(feature, parent, title, id_)

        self.popup = PagedMenu(title=self.popup_title)

        if parent is not None:
            self.popup.parent_menu = parent.popup

        @self.popup.register_select_callback
        def select_callback(popup, index, option):
            self._blocked_comm_user_info_select(clients[index], option.value)

        @self.popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            client = clients[index]
            for blocked_comm_user_info in self._get_blocks(client):
                popup.append(PagedOption(
                    text=plugin_strings['block_record'].tokenized(
                        id=blocked_comm_user_info.steamid64,
                        name=format_player_name(blocked_comm_user_info.name)
                    ),
                    value=blocked_comm_user_info
                ))

    def _get_blocks(self, client):
        raise NotImplementedError

    def _blocked_comm_user_info_select(self, client, blocked_comm_user_info):
        if not self.is_visible(client) or not self.is_selectable(client):
            client.tell(strings_common['unavailable'])
            return

        self.feature.execute(client, blocked_comm_user_info)

        self._parent.select(client)

    def select(self, client):
        client.send_popup(self.popup)


class UnblockAnyCommAdminCommand(_UnblockCommAdminCommand):
    def _get_blocks(self, client):
        return self.feature.blocked_comm_user_manager.get_active_blocks()


class UnblockMyCommAdminCommand(_UnblockCommAdminCommand):
    def _get_blocks(self, client):
        return self.feature.blocked_comm_user_manager.get_active_blocks(
            blocked_by=client.steamid)


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
stock_block_durations = load_stock_block_durations()
