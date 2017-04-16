var PLUGIN = function () {
    var plugin = this;

    var ANIMATION_DURATION = 1000;

    var ReviewBanPage = function (tableNode) {
        var reviewBanPage = this;

        var BanEntry = function (uniqueid, banId, name) {
            var banEntry = this;

            this.uniqueid = uniqueid;
            this.banId = banId;
            this.name = name;

            var lineNode;
            this.create = function (node) {
                lineNode = node.appendChild(document.createElement('div'));
                lineNode.classList.add('ban-table-line');

                var cellNode = lineNode.appendChild(document.createElement('div'));
                cellNode.appendChild(document.createTextNode(banEntry.uniqueid));
                cellNode.classList.add('ban-table-uniqueid');

                cellNode = lineNode.appendChild(document.createElement('div'));
                cellNode.appendChild(document.createTextNode(banEntry.name));
                cellNode.classList.add('ban-table-name');

                lineNode.style.animationName = "ban-table-row-add";

                lineNode.addEventListener('click', function (e) {
                    if (banEntry.banId)
                        showPanel(banEntry.banId);
                });
            };
            this.destroy = function () {
                banEntry.banId = undefined;
                lineNode.style.animationName = "ban-table-row-remove";
                setTimeout(function () {
                    if (lineNode)
                        lineNode.parentNode.removeChild(lineNode);
                    lineNode = undefined;
                }, ANIMATION_DURATION);
            };
            this.destroyNoDelay = function () {
                banEntry.banId = undefined;
                lineNode.parentNode.removeChild(lineNode);
                lineNode = undefined;
            };
        };

        var banEntries = [];

        tableNode.classList.add('ban-table');

        var clearBans = function () {
            banEntries.forEach(function (val, i, arr) {
                val.destroyNoDelay();
            });
            banEntries = [];
        };
        var addBan = function (uniqueid, banId, name) {
            removeBanId(banId);
            var banEntry = new BanEntry(uniqueid, banId, name);
            banEntry.create(tableNode);
            banEntries.push(banEntry);
        };
        var removeBanId = function (banId) {
            var invalidEntries = [];
            banEntries.forEach(function (val, i, arr) {
                if (val.banId == banId)
                    invalidEntries.push(val);
            });
            invalidEntries.forEach(function (val, i, arr) {
                val.destroy();
                banEntries.splice(banEntries.indexOf(val), 1);
            });
        };

        var mode = 'unknown';
        this.tryWS = function (wsSuccessCallback, wsMessageCallback, wsCloseCallback, wsErrorCallback) {
            MOTDPlayer.openWSConnection(function () {
                mode = 'ws';
                requestBans();
                if (wsSuccessCallback)
                    wsSuccessCallback();
            }, function (data) {
                switch (data['action']) {
                    case 'bans':
                        data['bans'].forEach(function (val, i, arr) {
                            addBan(val['uniqueid'], val['banId'], val['name']);
                        });
                        break;
                    case 'remove-ban-id':
                        removeBanId(data['banId']);
                        break;
                }
                if (wsMessageCallback)
                    wsMessageCallback(data);
            }, function () {
                clearBans();
                if (wsCloseCallback)
                    wsCloseCallback();
            }, function (err) {
                if (mode == 'unknown') {
                    mode = 'ajax';
                    requestBans();
                }
                if (wsErrorCallback)
                    wsErrorCallback(err);
            });
        };

        var requestBans = function () {
            switch (mode) {
                case 'ajax':
                    MOTDPlayer.post({
                        action: 'get-bans',
                    }, function (data) {
                        clearBans();
                        data['bans'].forEach(function (val, i, arr) {
                            addBan(val['uniqueid'], val['banId'], val['name']);
                        });
                    }, function (err) {
                        // TODO: Display error
                    });
                    break;

                case 'ws':
                    MOTDPlayer.sendWSData({
                        action: 'get-bans',
                    });
                    break;
            }
        };

        var execute = function (banId, reason, duration) {
            switch (mode) {
                case 'ajax':
                    MOTDPlayer.post({
                        action: 'execute',
                        banId: banId,
                        reason: reason,
                        duration: duration,
                    }, function (data) {
                        if (data['status'] == "ok") ;  // TODO: Display success popup
                        clearBans();
                        data['bans'].forEach(function (val, i, arr) {
                            addBan(val['uniqueid'], val['banId'], val['name']);
                        });
                    }, function (err) {
                        // TODO: Display error
                    });
                    break;

                case 'ws':
                    MOTDPlayer.sendWSData({
                        action: 'execute',
                        banId: banId,
                        reason: reason,
                        duration: duration,
                    });
                    break;
            }
        };

        var showPanel = function (banId) {

        };
    };

    this.init = function (tableNode, wsSuccessCallback, wsMessageCallback, wsCloseCallback, wsErrorCallback) {
        reviewBanPage = new ReviewBanPage(tableNode);
        reviewBanPage.tryWS(wsSuccessCallback, wsMessageCallback, wsCloseCallback, wsErrorCallback);
    };
};
