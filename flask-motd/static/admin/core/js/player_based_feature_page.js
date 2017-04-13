var PLUGIN = function () {
    var plugin = this;

    var ANIMATION_DURATION = 1000;

    var PlayerBasedFeaturePage = function (tableNode) {
        var playerBasedFeaturePage = this;

        var PlayerEntry = function (userid, name) {
            var playerEntry = this;

            this.userid = userid;
            this.name = name;

            var lineNode;
            this.create = function (node) {
                lineNode = node.appendChild(document.createElement('div'));
                lineNode.classList.add('player-table-line');
                var cellNode = lineNode.appendChild(document.createElement('div'));
                cellNode.appendChild(document.createTextNode(playerEntry.userid));
                cellNode.classList.add('player-table-userid');
                cellNode = lineNode.appendChild(document.createElement('div'));
                cellNode.appendChild(document.createTextNode(playerEntry.name));
                cellNode.classList.add('player-table-name');

                lineNode.style.animationName = "player-table-row-add";

                lineNode.addEventListener('click', function (e) {
                    if (playerEntry.userid > -1)
                        executeOnPlayer(playerEntry.userid);
                });
            };
            this.destroy = function () {
                playerEntry.userid = -1;
                lineNode.style.animationName = "player-table-row-remove";
                setTimeout(function () {
                    if (lineNode)
                        lineNode.parentNode.removeChild(lineNode);
                    lineNode = undefined;
                }, ANIMATION_DURATION);
            };
            this.destroyNoDelay = function () {
                playerEntry.userid = -1;
                lineNode.parentNode.removeChild(lineNode);
                lineNode = undefined;
            };
        };

        var playerEntries = [];

        tableNode.classList.add('player-table');

        var clearPlayers = function () {
            playerEntries.forEach(function (val, i, arr) {
                val.destroyNoDelay();
            });
            playerEntries = [];
        };
        var addPlayer = function (userid, name) {
            removeUserid(userid);
            var playerEntry = new PlayerEntry(userid, name);
            playerEntry.create(tableNode);
            playerEntries.push(playerEntry);
        };
        var removeUserid = function (userid) {
            var invalidEntries = [];
            playerEntries.forEach(function (val, i, arr) {
                if (val.userid == userid)
                    invalidEntries.push(val);
            });
            invalidEntries.forEach(function (val, i, arr) {
                val.destroy();
                playerEntries.splice(playerEntries.indexOf(val), 1);
            });
        };

        var mode = 'unknown';
        this.tryWS = function (wsSuccessCallback, wsMessageCallback, wsCloseCallback, wsErrorCallback) {
            MOTDPlayer.openWSConnection(function () {
                mode = 'ws';
                requestPlayers();
                if (wsSuccessCallback)
                    wsSuccessCallback();
            }, function (data) {
                switch (data['action']) {
                    case 'add-player':
                        addPlayer(data['player']['userid'], data['player']['name']);
                        break;
                    case 'remove-userid':
                        removeUserid(data['userid']);
                        break;
                }
                if (wsMessageCallback)
                    wsMessageCallback(data);
            }, function () {
                clearPlayers();
                if (wsCloseCallback)
                    wsCloseCallback();
            }, function (err) {
                mode = 'ajax';
                requestPlayers();
                if (wsErrorCallback)
                    wsErrorCallback(err);
            });
        };

        var requestPlayers = function () {
            switch (mode) {
                case 'ajax':
                    MOTDPlayer.post({
                        action: 'get-players',
                    }, function (data) {
                        clearPlayers();
                        data['players'].forEach(function (val, i, arr) {
                            var playerEntry = new PlayerEntry(val.userid, val.name);
                            playerEntry.create(tableNode);
                            playerEntries.push(playerEntry);
                        });
                    }, function (err) {
                        // TODO: Display error
                    });
                    break;

                case 'ws':
                    MOTDPlayer.sendWSData({
                        action: 'get-players',
                    });
                    break;
            }
        };

        var executeOnPlayer = function (userid) {
            switch (mode) {
                case 'ajax':
                    MOTDPlayer.post({
                        action: 'execute',
                        player_userids: [userid, ],
                    }, function (data) {
                        if (data['status'] == "ok") ;  // TODO: Display success popup
                        clearPlayers();
                        data['players'].forEach(function (val, i, arr) {
                            var playerEntry = new PlayerEntry(userid, name);
                            playerEntry.create(tableNode);
                            playerEntries.push(playerEntry);
                        });
                    }, function (err) {
                        // TODO: Display error
                    });
                    break;

                case 'ws':
                    MOTDPlayer.sendWSData({
                        action: 'execute',
                        player_userids: [userid, ],
                    });
                    break;
            }
        };
    };

    this.init = function (tableNode, wsSuccessCallback, wsMessageCallback, wsCloseCallback, wsErrorCallback) {
        playerBasedFeaturePage = new PlayerBasedFeaturePage(tableNode);
        playerBasedFeaturePage.tryWS(wsSuccessCallback, wsMessageCallback, wsCloseCallback, wsErrorCallback);
    };
};
