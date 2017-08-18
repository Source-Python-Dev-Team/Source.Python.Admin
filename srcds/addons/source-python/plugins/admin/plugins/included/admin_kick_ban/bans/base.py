# =============================================================================
# >> IMPORTS
# =============================================================================
# Python
from collections import OrderedDict
import json
from time import time

# Source.Python
from listeners.tick import GameThread
from menus import PagedMenu, PagedOption, SimpleMenu, SimpleOption, Text
from players.dictionary import PlayerDictionary
from players.helpers import get_client_language
from steam import SteamID
from translations.manager import language_manager

# Site-Package
from sqlalchemy.sql.expression import and_, or_

# Source.Python Admin
from admin.core.clients import clients
from admin.core.features import BaseFeature
from admin.core.frontends.menus import MenuCommand
from admin.core.frontends.motd import BaseFeaturePage
from admin.core.helpers import format_player_name, log_admin_action
from admin.core.orm import SessionContext
from admin.core.paths import ADMIN_CFG_PATH, get_server_file
from admin.core.strings import strings_common

# Included Plugin
from ..strings import plugin_strings


# =============================================================================
# >> FUNCTIONS
# =============================================================================
def load_stock_ban_reasons():
    with open(get_server_file(
            ADMIN_CFG_PATH / "included_plugins" / "admin_kick_ban" /
            "ban_reasons.json")) as f:

        ban_reasons_json = json.load(f)

    ban_reasons = OrderedDict()
    for ban_reason_json in ban_reasons_json:
        stock_ban_reason = _StockBanReason(ban_reason_json)
        ban_reasons[stock_ban_reason.id] = stock_ban_reason

    return ban_reasons


def load_stock_ban_durations():
    with open(get_server_file(
            ADMIN_CFG_PATH / "included_plugins" / "admin_kick_ban" /
            "ban_durations.json")) as f:

        ban_durations_json = json.load(f)

    ban_durations_json.sort()

    return ban_durations_json


def format_ban_duration(seconds):
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
class _StockBanReason:
    def __init__(self, data):
        self.id = data['id']
        self.translation = plugin_strings[data['translation']]
        self.duration = data['suggestedBanDuration']

stock_ban_reasons = load_stock_ban_reasons()


class _BannedPlayerInfo:
    def __init__(self, uniqueid, id_, name, banned_by, reviewed, expires_at,
                 reason, notes):

        self.uniqueid = uniqueid
        self.id = id_
        self.name = name
        self.banned_by = banned_by
        self.reviewed = reviewed
        self.expires_at = expires_at
        self.reason = reason
        self.notes = notes

stock_ban_durations = load_stock_ban_durations()


class BannedUniqueIDManager(dict):
    model = None

    def _convert_uniqueid_to_db_format(self, uniqueid):
        raise NotImplementedError

    def _convert_steamid_to_db_format(self, steamid):
        return str(SteamID.parse(steamid).to_uint64())

    def refresh(self):
        self.clear()

        with SessionContext() as session:
            banned_users = session.query(self.model).all()

            current_time = time()
            for banned_user in banned_users:
                if banned_user.is_unbanned:
                    continue

                if 0 <= banned_user.expires_at < current_time:
                    continue

                self[banned_user.uniqueid] = _BannedPlayerInfo(
                    banned_user.uniqueid, banned_user.id, banned_user.name,
                    banned_user.banned_by, banned_user.reviewed,
                    banned_user.expires_at, banned_user.reason,
                    banned_user.notes)

    def is_banned(self, uniqueid):
        uniqueid = self._convert_uniqueid_to_db_format(uniqueid)

        if uniqueid not in self:
            return False

        if self[uniqueid].expires_at < 0:
            return True

        if self[uniqueid].expires_at < time():
            del self[uniqueid]
            return False

        return True

    def save_ban_to_database(self, banned_by, uniqueid, name, duration):
        uniqueid = self._convert_uniqueid_to_db_format(uniqueid)
        banned_by = self._convert_steamid_to_db_format(banned_by)

        with SessionContext() as session:
            banned_user = self.model(uniqueid, name, banned_by, duration)

            session.add(banned_user)
            session.commit()

            self[uniqueid] = _BannedPlayerInfo(
                uniqueid, banned_user.id, name, banned_by, False,
                banned_user.expires_at, "", "")

    def remove_ban_from_database(self, ban_id):
        with SessionContext() as session:
            banned_user = session.query(
                self.model).filter_by(id=ban_id).first()

            if banned_user is not None:
                session.delete(banned_user)
                session.commit()

    def get_all_bans(self, uniqueid=None, banned_by=None, reviewed=None,
                     expired=None, unbanned=None):

        result = []

        with SessionContext() as session:
            query = session.query(self.model)

            if uniqueid is not None:
                uniqueid = self._convert_uniqueid_to_db_format(uniqueid)
                query = query.filter_by(uniqueid=uniqueid)

            if banned_by is not None:
                banned_by = self._convert_steamid_to_db_format(banned_by)
                query = query.filter_by(banned_by=banned_by)

            if reviewed is not None:
                query = query.filter_by(reviewed=reviewed)

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

            if unbanned is not None:
                query = query.filter_by(is_unbanned=unbanned)

            for banned_user in query.all():
                result.append(_BannedPlayerInfo(
                    banned_user.uniqueid, banned_user.id, banned_user.name,
                    banned_user.banned_by, banned_user.reviewed,
                    banned_user.expires_at, banned_user.reason, banned_user.notes
                ))

        return result

    def get_active_bans(self, banned_by=None, reviewed=None):
        if banned_by is not None:
            banned_by = self._convert_steamid_to_db_format(banned_by)

        current_time = time()

        result = []
        for banned_player_info in self.values():
            if (
                    banned_by is not None and
                    banned_player_info.banned_by != banned_by):

                continue

            if reviewed is False and banned_player_info.reviewed:
                continue

            if reviewed is True and not banned_player_info.reviewed:
                continue

            if banned_player_info.expires_at < current_time:
                continue

            result.append(banned_player_info)

        return result

    def review_ban(self, ban_id, reason, duration):
        with SessionContext() as session:
            banned_user = session.query(
                self.model).filter_by(id=ban_id).first()

            if banned_user is None:
                return

            banned_user.review(reason, duration)
            expires_at = banned_user.expires_at

            session.commit()

        for banned_player_info in self.values():
            if banned_player_info.id != ban_id:
                continue

            banned_player_info.reviewed = True
            banned_player_info.expires_at = expires_at
            banned_player_info.reason = reason
            break

    def lift_ban(self, ban_id, unbanned_by):
        unbanned_by = self._convert_steamid_to_db_format(unbanned_by)

        with SessionContext() as session:
            banned_user = session.query(
                self.model).filter_by(id=ban_id).first()

            if banned_user is None:
                return

            banned_user.lift_ban(unbanned_by)

            session.commit()

        for uniqueid, banned_player_info in self.items():
            if banned_player_info.id != ban_id:
                continue

            del self[uniqueid]
            break


class LiftBanFeature(BaseFeature):
    feature_abstract = True
    banned_uniqueid_manager = None
    ws_lift_ban_pages = None

    def execute(self, client, banned_player_info):
        GameThread(
            target=self.banned_uniqueid_manager.lift_ban,
            args=(banned_player_info.id, client.steamid)
        ).start()

        for ws_lift_ban_page in self.ws_lift_ban_pages:
            ws_lift_ban_page.send_remove_ban_id(banned_player_info.id)

        log_admin_action(plugin_strings['message ban_lifted'].tokenized(
            admin_name=client.name,
            player_name=banned_player_info.name,
        ))


class _LiftBanMenuCommand(MenuCommand):
    popup_title = None

    def __init__(self, feature, parent, title, id_=None):
        super().__init__(feature, parent, title, id_)

        self.popup = PagedMenu(title=self.popup_title)

        if parent is not None:
            self.popup.parent_menu = parent.popup

        @self.popup.register_select_callback
        def select_callback(popup, index, option):
            self._popups_done(clients[index], option.value)

        @self.popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            client = clients[index]
            for banned_player_info in self._get_bans(client):
                popup.append(PagedOption(
                    text=plugin_strings['ban_record'].tokenized(
                        id=banned_player_info.uniqueid,
                        name=format_player_name(banned_player_info.name)),
                    value=banned_player_info
                ))

    def _popups_done(self, client, banned_player_info):
        if not self.is_visible(client) or not self.is_selectable(client):
            client.tell(strings_common['unavailable'])
            return

        self.feature.execute(client, banned_player_info)

        self._parent.select(client)

    def _get_bans(self, client):
        raise NotImplementedError

    def select(self, client):
        client.send_popup(self.popup)


class LiftAnyBanMenuCommand(_LiftBanMenuCommand):
    def __init__(self, feature, parent, title, id_=None):
        super().__init__(feature, parent, title, id_)

        self._selected_bans = PlayerDictionary(lambda index: None)
        self.confirm_popup = SimpleMenu()

        @self.popup.register_select_callback
        def select_callback(popup, index, option):
            self._selected_bans[index] = option.value
            clients[index].send_popup(self.confirm_popup)

        @self.confirm_popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            popup.append(Text(plugin_strings['ban_record'].tokenized(
                name=self._selected_bans[index].name,
                id=self._selected_bans[index].uniqueid
            )))

            popup.append(Text(
                plugin_strings['ban_record admin_steamid'].tokenized(
                    admin_steamid=self._selected_bans[index].banned_by)))

            popup.append(Text(plugin_strings['ban_record reason'].tokenized(
                reason=self._selected_bans[index].reason)))

            if self._selected_bans[index].notes:
                popup.append(Text(plugin_strings['ban_record notes'].tokenized(
                    notes=self._selected_bans[index].notes)))

            popup.append(Text(
                plugin_strings['lift_reviewed_ban_confirmation']))

            popup.append(SimpleOption(
                choice_index=1,
                text=plugin_strings['lift_reviewed_ban_confirmation no'],
                value=(self._selected_bans[index], False),
            ))
            popup.append(SimpleOption(
                choice_index=2,
                text=plugin_strings['lift_reviewed_ban_confirmation yes'],
                value=(self._selected_bans[index], True),
            ))

        @self.confirm_popup.register_select_callback
        def select_callback(popup, index, option):
            if not option.value[1]:
                return

            self._popups_done(clients[index], option.value[0])

    def _get_bans(self, client):
        return self.feature.banned_uniqueid_manager.get_active_bans()


class LiftMyBanMenuCommand(_LiftBanMenuCommand):
    def _get_bans(self, client):
        return self.feature.banned_uniqueid_manager.get_active_bans(
            banned_by=client.steamid, reviewed=False)


class ReviewBanFeature(BaseFeature):
    feature_abstract = True
    banned_uniqueid_manager = None
    ws_review_ban_pages = None

    def execute(self, client, banned_player_info, reason, duration):
        GameThread(
            target=self.banned_uniqueid_manager.review_ban,
            args=(banned_player_info.id, reason, duration)
        ).start()

        for ws_review_ban_page in self.ws_review_ban_pages:
            ws_review_ban_page.send_remove_ban_id(banned_player_info.id)

        log_admin_action(plugin_strings['message ban_reviewed'].tokenized(
            admin_name=client.name,
            player_name=banned_player_info.name,
            duration=format_ban_duration(duration)
        ))


class ReviewBanMenuCommand(MenuCommand):
    popup_title = None

    def __init__(self, feature, parent, title, id_=None):
        super().__init__(feature, parent, title, id_)

        # (_BannedPlayerInfo instance, reason, duration)
        self._selected_bans = PlayerDictionary(lambda index: (None, "", -1))

        self.ban_popup = PagedMenu(title=self.popup_title)
        if parent is not None:
            self.ban_popup.parent_menu = parent.popup

        self.reason_popup = PagedMenu(title=self.popup_title,
                                      parent_menu=self.ban_popup)

        # TODO: Provide parent menu
        self.duration_popup = PagedMenu(title=self.popup_title)

        @self.ban_popup.register_build_callback
        def build_callback(popup, index):
            client = clients[index]
            popup.clear()

            for banned_player_info in self._get_bans(client):
                popup.append(PagedOption(
                    text=plugin_strings['ban_record'].tokenized(
                        id=banned_player_info.uniqueid,
                        name=format_player_name(banned_player_info.name)),
                    value=(banned_player_info, "", -1)
                ))

        @self.ban_popup.register_select_callback
        def select_callback(popup, index, option):
            self._selected_bans[index] = option.value
            clients[index].send_popup(self.reason_popup)

        @self.reason_popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            for stock_ban_reason in stock_ban_reasons.values():
                popup.append(PagedOption(
                    text=stock_ban_reason.translation,
                    value=(
                        self._selected_bans[index][0],
                        stock_ban_reason.translation.get_string(
                            language_manager.default),
                        stock_ban_reason.duration,
                    )
                ))

        @self.reason_popup.register_select_callback
        def select_callback(popup, index, option):
            self._selected_bans[index] = option.value
            clients[index].send_popup(self.duration_popup)

        @self.duration_popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            if self._selected_bans[index][2] is not None:
                popup.append(PagedOption(
                    text=plugin_strings['default_duration'].tokenized(
                        default=format_ban_duration(
                            self._selected_bans[index][2])),
                    value=self._selected_bans[index]
                ))

            for stock_ban_duration in stock_ban_durations:
                popup.append(PagedOption(
                    text=format_ban_duration(stock_ban_duration),
                    value=(
                        self._selected_bans[index][0],
                        self._selected_bans[index][1],
                        stock_ban_duration,
                    )
                ))

        @self.duration_popup.register_select_callback
        def select_callback(popup, index, option):
            self._popups_done(
                clients[index],
                option.value[0], option.value[1], option.value[2])

    def _popups_done(self, client, banned_player_info, reason, duration):
        if not self.is_visible(client) or not self.is_selectable(client):
            client.tell(strings_common['unavailable'])
            return

        self.feature.execute(client, banned_player_info, reason, duration)

        self._parent.select(client)

    def _get_bans(self, client):
        return self.feature.banned_uniqueid_manager.get_active_bans(
            banned_by=client.steamid, reviewed=False)

    def select(self, client):
        client.send_popup(self.ban_popup)


class RemoveBadBanFeature(BaseFeature):
    feature_abstract = True
    banned_uniqueid_manager = None
    ws_remove_bad_ban_pages = None

    def execute(self, client, banned_player_info):
        GameThread(
            target=self.banned_uniqueid_manager.remove_ban_from_database,
            args=(banned_player_info.id,)
        ).start()

        log_admin_action(plugin_strings['message ban_removed'].tokenized(
            admin_name=client.name,
            ban_id=banned_player_info.id
        ))


class RemoveBadBanMenuCommand(MenuCommand):
    popup_title = None

    def __init__(self, feature, parent, title, id_=None):
        super().__init__(feature, parent, title, id_)

        self._selected_bans = PlayerDictionary(lambda index: None)

        self.ban_popup = PagedMenu(title=self.popup_title)
        if parent is not None:
            self.ban_popup.parent_menu = parent.popup

        self.remove_popup = SimpleMenu()

        @self.ban_popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            for banned_player_info in self._get_bans(clients[index]):
                popup.append(PagedOption(
                    text=plugin_strings['ban_record'].tokenized(
                        id=banned_player_info.uniqueid,
                        name=format_player_name(banned_player_info.name)),
                    value=banned_player_info
                ))

        @self.ban_popup.register_select_callback
        def select_callback(popup, index, option):
            self._selected_bans[index] = option.value
            clients[index].send_popup(self.remove_popup)

        @self.remove_popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            popup.append(Text(plugin_strings['ban_record'].tokenized(
                name=self._selected_bans[index].name,
                id=self._selected_bans[index].uniqueid
            )))

            popup.append(Text(
                plugin_strings['ban_record admin_steamid'].tokenized(
                    admin_steamid=self._selected_bans[index].banned_by)))

            if self._selected_bans[index].notes:
                popup.append(Text(plugin_strings['ban_record notes'].tokenized(
                    notes=self._selected_bans[index].notes)))

            popup.append(Text(
                plugin_strings['remove_bad_ban_confirmation']))

            popup.append(SimpleOption(
                choice_index=1,
                text=plugin_strings['remove_bad_ban_confirmation no'],
                value=(self._selected_bans[index], False),
            ))
            popup.append(SimpleOption(
                choice_index=2,
                text=plugin_strings['remove_bad_ban_confirmation yes'],
                value=(self._selected_bans[index], True),
            ))

        @self.remove_popup.register_select_callback
        def select_callback(popup, index, option):
            if not option.value[1]:
                return

            self._popups_done(clients[index], option.value[0])

    def _popups_done(self, client, banned_player_info):
        if not self.is_visible(client) or not self.is_selectable(client):
            client.tell(strings_common['unavailable'])
            return

        self.feature.execute(client, banned_player_info)

        self._parent.select(client)

    def _get_bans(self, client):
        # Get expired, unreviewed, unlifted bans
        return self.feature.banned_uniqueid_manager.get_all_bans(
                unbanned=False, reviewed=False, expired=True)

    def select(self, client):
        client.send_popup(self.ban_popup)


class _BaseBanPage(BaseFeaturePage):
    abstract = True
    page_abstract = True
    feature_page_abstract = True

    def send_remove_ban_id(self, ban_id):
        self.send_data({
            'action': 'remove-ban-id',
            'banId': ban_id,
        })

    def _get_bans(self, client):
        raise NotImplementedError

    def _get_ban_by_id(self, client, ban_id):
        for banned_player_info in self._get_bans(client):
            if banned_player_info.id == ban_id:
                return banned_player_info
        return None


class LiftBanPage(_BaseBanPage):
    abstract = True
    page_abstract = True
    feature_page_abstract = True

    def _get_bans(self, client):
        return self.feature.banned_uniqueid_manager.get_active_bans(
            banned_by=client.steamid, reviewed=False)

    def on_page_data_received(self, data):
        client = clients[self.index]

        if data['action'] == "execute":
            ban_id = data['banId']

            banned_player_info = self._get_ban_by_id(client, ban_id)
            if banned_player_info is None:

                # Might just as well log the ban id and the client, looks like
                # this client has tried to lift somebody else's ban
                return

            client.sync_execution(
                self.feature.execute, (client, banned_player_info))

            self.send_data({
                'feature-executed': "scheduled"
            })
            return

        if data['action'] == "get-bans":
            ban_data = []

            for banned_player_info in self._get_bans(client):
                ban_data.append({
                    'uniqueid': str(banned_player_info.uniqueid),
                    'banId': banned_player_info.id,
                    'name': banned_player_info.name,
                })

            self.send_data({
                'action': "bans",
                'bans': ban_data,
            })


class ReviewBanPage(_BaseBanPage):
    abstract = True
    page_abstract = True
    feature_page_abstract = True

    def _get_bans(self, client):
        return self.feature.banned_uniqueid_manager.get_active_bans(
            banned_by=client.steamid, reviewed=False)

    def on_page_data_received(self, data):
        client = clients[self.index]

        if data['action'] == "execute":
            ban_id = data['banId']
            reason = data['reason']
            duration = data['duration']

            banned_player_info = self._get_ban_by_id(client, ban_id)
            if banned_player_info is None:

                # Might just as well log the ban id and the client, looks like
                # this client has tried to lift somebody else's ban
                return

            client.sync_execution(self.feature.execute, (
                client, banned_player_info, reason, duration))

            self.send_data({
                'feature-executed': "scheduled"
            })
            return

        if data['action'] == "get-ban-data":
            language = get_client_language(self.index)

            ban_durations = []
            for stock_ban_duration in stock_ban_durations:
                ban_durations.append({
                    'value': stock_ban_duration,
                    'title': format_ban_duration(
                        stock_ban_duration).get_string(language),
                })

            ban_reasons = []
            for stock_ban_reason in stock_ban_reasons.values():
                duration_value = stock_ban_reason.duration
                duration_title = (
                    None if duration_value is None else
                    format_ban_duration(duration_value).get_string(language))

                ban_reasons.append({
                    'hidden': stock_ban_reason.translation.get_string(
                                language_manager.default),
                    'title': stock_ban_reason.translation.get_string(language),
                    'duration-value': duration_value,
                    'duration-title': duration_title,
                })

            ban_data = []
            for banned_player_info in self._get_bans(client):
                ban_data.append({
                    'uniqueid': str(banned_player_info.uniqueid),
                    'banId': banned_player_info.id,
                    'name': banned_player_info.name,
                })

            self.send_data({
                'action': "ban-data",
                'bans': ban_data,
                'reasons': ban_reasons,
                'durations': ban_durations,
            })
