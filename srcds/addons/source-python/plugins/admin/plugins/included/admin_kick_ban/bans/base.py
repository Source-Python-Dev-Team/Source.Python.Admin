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
from admin.core.features import BaseFeature, Feature
from admin.core.frontends.motd import BaseFeaturePage
from admin.core.helpers import format_player_name, log_admin_action
from admin.core.orm import SessionContext
from admin.core.paths import ADMIN_CFG_PATH, get_server_file

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


class LiftBanMOTDFeature(BaseFeature):
    feature_abstract = True
    banned_uniqueid_manager = None
    ws_lift_ban_pages = None

    def get_bans(self, client):
        yield from self.banned_uniqueid_manager.get_active_bans(
            banned_by=client.steamid, reviewed=False)

    def get_ban_by_id(self, client, ban_id):
        for banned_player_info in self.get_bans(client):
            if banned_player_info.id == ban_id:
                return banned_player_info
        return None

    def execute(self, client, ban_id, player_name):
        GameThread(
            target=self.banned_uniqueid_manager.lift_ban,
            args=(ban_id, client.steamid)
        ).start()

        for ws_lift_ban_page in self.ws_lift_ban_pages:
            ws_lift_ban_page.send_remove_ban_id(ban_id)

        log_admin_action(plugin_strings['message ban_lifted'].tokenized(
            admin_name=client.name,
            player_name=player_name,
        ))


class LiftBanPopupFeature(Feature):
    feature_abstract = True
    popup_title = None
    banned_uniqueid_manager = None

    def __init__(self):
        self.ban_popup = PagedMenu(title=self.popup_title)

        @self.ban_popup.register_build_callback
        def build_callback(popup, index):
            client = clients[index]
            popup.clear()

            bans = self.banned_uniqueid_manager.get_active_bans(
                banned_by=client.steamid, reviewed=False)

            for banned_player_info in bans:
                popup.append(PagedOption(
                    text=plugin_strings['ban_record'].tokenized(
                        id=banned_player_info.uniqueid,
                        name=format_player_name(banned_player_info.name)),
                    value=banned_player_info
                ))

        @self.ban_popup.register_select_callback
        def select_callback(popup, index, option):
            client = clients[index]

            GameThread(
                target=self.banned_uniqueid_manager.lift_ban,
                args=(option.value.id, client.steamid)
            ).start()

            log_admin_action(plugin_strings['message ban_lifted'].tokenized(
                admin_name=client.name,
                player_name=option.value.name,
            ))

    def execute(self, client):
        client.send_popup(self.ban_popup)


class LiftAnyBanPopupFeature(Feature):
    feature_abstract = True
    popup_title = None
    banned_uniqueid_manager = None

    def __init__(self):
        # (_BannedPlayerInfo instance, whether confirmed or not)
        self._selected_bans = PlayerDictionary(lambda index: (None, False))

        self.ban_popup = PagedMenu(title=self.popup_title)
        self.confirm_popup = SimpleMenu()

        @self.ban_popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            # Get all bans
            bans = self.banned_uniqueid_manager.get_active_bans()

            for banned_player_info in bans:
                popup.append(PagedOption(
                    text=plugin_strings['ban_record'].tokenized(
                        id=banned_player_info.uniqueid,
                        name=format_player_name(banned_player_info.name)),
                    value=(banned_player_info, False)
                ))

        @self.ban_popup.register_select_callback
        def select_callback(popup, index, option):
            self._selected_bans[index] = option.value
            clients[index].send_popup(self.confirm_popup)

        @self.confirm_popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            popup.append(Text(plugin_strings['ban_record'].tokenized(
                name=self._selected_bans[index][0].name,
                id=self._selected_bans[index][0].uniqueid
            )))

            popup.append(Text(
                plugin_strings['ban_record admin_steamid'].tokenized(
                    admin_steamid=self._selected_bans[index][0].banned_by)))

            popup.append(Text(plugin_strings['ban_record reason'].tokenized(
                reason=self._selected_bans[index][0].reason)))

            if self._selected_bans[index][0].notes:
                popup.append(Text(plugin_strings['ban_record notes'].tokenized(
                    notes=self._selected_bans[index][0].notes)))

            popup.append(Text(
                plugin_strings['lift_reviewed_ban_confirmation']))

            popup.append(SimpleOption(
                choice_index=1,
                text=plugin_strings['lift_reviewed_ban_confirmation no'],
                value=(self._selected_bans[index][0], False),
            ))
            popup.append(SimpleOption(
                choice_index=2,
                text=plugin_strings['lift_reviewed_ban_confirmation yes'],
                value=(self._selected_bans[index][0], True),
            ))

        @self.confirm_popup.register_select_callback
        def select_callback(popup, index, option):
            if not option.value[1]:
                return

            client = clients[index]

            GameThread(
                target=self.banned_uniqueid_manager.lift_ban,
                args=(option.value[0].id, client.steamid)
            ).start()

            log_admin_action(plugin_strings['message ban_lifted'].tokenized(
                admin_name=client.name,
                player_name=option.value[0].name,
            ))

    def execute(self, client):
        client.send_popup(self.ban_popup)


class ReviewBanMOTDFeature(BaseFeature):
    feature_abstract = True
    banned_uniqueid_manager = None
    ws_review_ban_pages = None

    def get_bans(self, client):
        yield from self.banned_uniqueid_manager.get_active_bans(
            banned_by=client.steamid, reviewed=False)

    def get_ban_by_id(self, client, ban_id):
        for banned_player_info in self.get_bans(client):
            if banned_player_info.id == ban_id:
                return banned_player_info
        return None

    def execute(self, client, ban_id, reason, duration, player_name):
        GameThread(
            target=self.banned_uniqueid_manager.review_ban,
            args=(ban_id, reason, duration)
        ).start()

        for ws_review_ban_page in self.ws_review_ban_pages:
            ws_review_ban_page.send_remove_ban_id(ban_id)

        log_admin_action(plugin_strings['message ban_reviewed'].tokenized(
            admin_name=client.name,
            player_name=player_name,
            duration=format_ban_duration(duration)
        ))


class ReviewBanPopupFeature(Feature):
    feature_abstract = True
    popup_title = None
    banned_uniqueid_manager = None

    def __init__(self):
        # (_BannedPlayerInfo instance, reason, duration)
        self._selected_bans = PlayerDictionary(lambda index: (None, "", -1))

        self.ban_popup = PagedMenu(title=self.popup_title)
        self.reason_popup = PagedMenu(title=self.popup_title,
                                      parent_menu=self.ban_popup)

        # TODO: Provide parent menu
        self.duration_popup = PagedMenu(title=self.popup_title)

        @self.ban_popup.register_build_callback
        def build_callback(popup, index):
            client = clients[index]
            popup.clear()

            bans = self.banned_uniqueid_manager.get_active_bans(
                banned_by=client.steamid, reviewed=False)

            for banned_player_info in bans:
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
            client = clients[index]

            GameThread(
                target=self.banned_uniqueid_manager.review_ban,
                args=(option.value[0].id, option.value[1], option.value[2])
            ).start()

            log_admin_action(plugin_strings['message ban_reviewed'].tokenized(
                admin_name=client.name,
                player_name=option.value[0].name,
                duration=format_ban_duration(option.value[2])
            ))

    def execute(self, client):
        client.send_popup(self.ban_popup)


class SearchBadBansPopupFeature(Feature):
    feature_abstract = True
    popup_title = None
    banned_uniqueid_manager = None

    def __init__(self):
        # (_BannedPlayerInfo instance, whether to remove or not)
        self._selected_bans = PlayerDictionary(lambda index: (None, False))

        self.ban_popup = PagedMenu(title=self.popup_title)
        self.remove_popup = SimpleMenu()

        @self.ban_popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            # Get expired, unreviewed, unlifted bans
            bans = self.banned_uniqueid_manager.get_all_bans(
                unbanned=False, reviewed=False, expired=True)

            for banned_player_info in bans:
                popup.append(PagedOption(
                    text=plugin_strings['ban_record'].tokenized(
                        id=banned_player_info.uniqueid,
                        name=format_player_name(banned_player_info.name)),
                    value=(banned_player_info, False)
                ))

        @self.ban_popup.register_select_callback
        def select_callback(popup, index, option):
            self._selected_bans[index] = option.value
            clients[index].send_popup(self.remove_popup)

        @self.remove_popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            popup.append(Text(plugin_strings['ban_record'].tokenized(
                name=self._selected_bans[index][0].name,
                id=self._selected_bans[index][0].uniqueid
            )))

            popup.append(Text(
                plugin_strings['ban_record admin_steamid'].tokenized(
                    admin_steamid=self._selected_bans[index][0].banned_by)))

            if self._selected_bans[index][0].notes:
                popup.append(Text(plugin_strings['ban_record notes'].tokenized(
                    notes=self._selected_bans[index][0].notes)))

            popup.append(Text(
                plugin_strings['remove_bad_ban_confirmation']))

            popup.append(SimpleOption(
                choice_index=1,
                text=plugin_strings['remove_bad_ban_confirmation no'],
                value=(self._selected_bans[index][0], False),
            ))
            popup.append(SimpleOption(
                choice_index=2,
                text=plugin_strings['remove_bad_ban_confirmation yes'],
                value=(self._selected_bans[index][0], True),
            ))

        @self.remove_popup.register_select_callback
        def select_callback(popup, index, option):
            if not option.value[1]:
                return

            client = clients[index]

            GameThread(
                target=self.banned_uniqueid_manager.remove_ban_from_database,
                args=(option.value[0].id, )
            ).start()

            log_admin_action(plugin_strings['message ban_removed'].tokenized(
                admin_name=client.name,
                ban_id=option.value[0].id
            ))

    def execute(self, client):
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


class LiftBanPage(_BaseBanPage):
    abstract = True
    page_abstract = True
    feature_page_abstract = True

    def on_page_data_received(self, data):
        client = clients[self.index]

        if data['action'] == "execute":
            ban_id = data['banId']

            banned_player_info = self.feature.get_ban_by_id(client, ban_id)
            if banned_player_info is None:

                # Might just as well log the ban id and the client, looks like
                # this client has tried to lift somebody else's ban
                return

            client.sync_execution(self.feature.execute, (
                client, banned_player_info.id, banned_player_info.name))

            self.send_data({
                'feature-executed': "scheduled"
            })
            return

        if data['action'] == "get-bans":
            ban_data = []

            for banned_player_info in self.feature.get_bans(client):
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

    def on_page_data_received(self, data):
        client = clients[self.index]

        if data['action'] == "execute":
            ban_id = data['banId']
            reason = data['reason']
            duration = data['duration']

            banned_player_info = self.feature.get_ban_by_id(client, ban_id)
            if banned_player_info is None:
                # Might just as well log the ban id and the client, looks like
                # this client has tried to lift somebody else's ban
                return

            client.sync_execution(self.feature.execute, (
                client, banned_player_info.id, reason, duration,
                banned_player_info.name))

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
            for banned_player_info in self.feature.get_bans(client):
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
