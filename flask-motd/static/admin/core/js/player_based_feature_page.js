var PLUGIN = function () {
    var plugin = this;

    var PlayerBasedFeaturePage = function () {
        var playerBasedFeaturePage = this;

        var PlayerEntry = function (userid, name) {
            var playerEntry = this;

            this.userid = userid;
            this.name = name;

            this.getNode = function () {
                var trNode = document.createElement('tr');
                var tdNode = trNode.appendChild(document.createElement('td'));
                tdNode.appendChild(document.createTextNode(playerEntry.userid));
                tdNode.classList.add('player-table-userid');
                tdNode = trNode.appendChild(document.createElement('td'));
                tdNode.appendChild(document.createTextNode(playerEntry.name));
                tdNode.classList.add('player-table-name');

                trNode.addEventListener('click', function (e) {
                    playerBasedFeaturePage.executeOnPlayer(playerEntry.userid);
                });
                return trNode;
            };
        };

        var playerEntries = [];

        var tableNode = document.createElement('table');
        tableNode.classList.add('player-table');

        this.render = function () {
            while (tableNode.firstChild)
                tableNode.removeChild(tableNode.firstChild);

            playerEntries.forEach(function (val, i, arr) {
                tableNode.appendChild(val.getNode());
            });
        };

        this.getNode = function () {
            return tableNode;
        };

        this.requestPlayers = function () {
            MOTDPlayer.post({
                action: 'get-players',
            }, function (data) {
                playerEntries = [];
                data['players'].forEach(function (val, i, arr) {
                    playerEntries.push(new PlayerEntry(val.userid, val.name));
                });
                playerBasedFeaturePage.render();
            }, function (err) {
                alert(err); // TODO: Display error
            });
        };

        this.executeOnPlayer = function (userid) {
            MOTDPlayer.post({
                action: 'execute',
                player_userids: [userid, ],
            }, function (data) {
                if (data['status'] == "ok") ;  // TODO: Display success popup
                playerEntries = [];
                data['players'].forEach(function (val, i, arr) {
                    playerEntries.push(new PlayerEntry(val.userid, val.name));
                });
                playerBasedFeaturePage.render();
            }, function (err) {
                // TODO: Display error
            });
        };
    };

    this.init = function () {
        var playerBasedFeaturePage = new PlayerBasedFeaturePage();
        var playerTableNode = mainNode.appendChild(playerBasedFeaturePage.getNode());
        playerBasedFeaturePage.requestPlayers();
    };

    var mainNode;
    document.addEventListener('AppInit', function (e) {
        mainNode = document.getElementById('main');
        plugin.init();

        var pluginInitEvent = new Event('PluginInit');
        document.dispatchEvent(pluginInitEvent);
    });
};
